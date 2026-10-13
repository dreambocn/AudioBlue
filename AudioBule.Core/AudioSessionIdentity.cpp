#include "pch.h"
#include "AudioSessionIdentity.h"
#include <audiopolicy.h>
#include <mmdeviceapi.h>
#include <condition_variable>
#include <thread>

namespace AudioBule::Core
{
std::optional<size_t> MatchA2dpSessionDevice(
    std::wstring_view displayName, std::vector<DeviceInfo> const& devices)
{
    std::optional<size_t> result;
    for (size_t i = 0; i < devices.size(); ++i)
    {
        if (devices[i].id.empty() || devices[i].name.empty()) continue;
        auto suffix = L"(" + devices[i].name + L" A2DP SNK)";
        if (!displayName.ends_with(suffix)) continue;
        if (result) return std::nullopt;
        result = i;
    }
    return result;
}

namespace
{
std::wstring TakeString(LPWSTR value)
{
    std::wstring result = value ? value : L"";
    ::CoTaskMemFree(value);
    return result;
}
std::wstring DisplayName(IAudioSessionControl* session)
{
    LPWSTR value = nullptr;
    if (FAILED(session->GetDisplayName(&value))) return {};
    return TakeString(value);
}
std::wstring IconPath(IAudioSessionControl* session)
{
    LPWSTR value = nullptr;
    if (FAILED(session->GetIconPath(&value))) return {};
    return TakeString(value);
}
DWORD AudioServiceProcessId()
{
    // 会话必须属于 Windows Audio 服务，不能修改名称相似的普通应用。
    auto manager = ::OpenSCManagerW(nullptr, nullptr, SC_MANAGER_CONNECT);
    if (!manager) return 0;
    auto service = ::OpenServiceW(manager, L"Audiosrv", SERVICE_QUERY_STATUS);
    ::CloseServiceHandle(manager);
    if (!service) return 0;
    SERVICE_STATUS_PROCESS status{};
    DWORD bytes = 0;
    bool success = ::QueryServiceStatusEx(service, SC_STATUS_PROCESS_INFO,
        reinterpret_cast<BYTE*>(&status), sizeof(status), &bytes) != FALSE;
    ::CloseServiceHandle(service);
    return success && status.dwCurrentState == SERVICE_RUNNING ? status.dwProcessId : 0;
}
}

struct AudioSessionIdentity::Impl
{
    struct OwnedSession
    {
        wil::com_ptr<IAudioSessionControl2> control;
        std::wstring deviceId, instanceId, originalName, originalIcon, appliedName;
    };
    std::wstring iconPath;
    std::mutex mutex;
    std::condition_variable changed;
    std::vector<DeviceInfo> devices;
    bool stopping = false, dirty = false;
    // 只由工作线程访问；保存会话原值，断开或退出时条件恢复。
    std::vector<OwnedSession> owned;
    std::thread worker;

    explicit Impl(std::wstring icon) : iconPath(std::move(icon)), worker([this] { Run(); }) {}
    ~Impl()
    {
        { std::lock_guard lock(mutex); stopping = true; }
        changed.notify_one();
        worker.join();
    }
    void Restore(OwnedSession const& session)
    {
        // 其它程序或系统已覆盖时，不能用旧值覆盖对方的新设置。
        if (DisplayName(session.control.get()) == session.appliedName)
            session.control->SetDisplayName(session.originalName.c_str(), nullptr);
        if (IconPath(session.control.get()) == iconPath)
            session.control->SetIconPath(session.originalIcon.c_str(), nullptr);
    }
    void Scan(std::vector<DeviceInfo> const& targets)
    {
        for (auto it = owned.begin(); it != owned.end();)
        {
            AudioSessionState state = AudioSessionStateExpired;
            auto target = std::find_if(targets.begin(), targets.end(), [&](auto const& item) { return item.id == it->deviceId; });
            bool available = SUCCEEDED(it->control->GetState(&state)) && state != AudioSessionStateExpired;
            if (target == targets.end() || !available)
            {
                Restore(*it);
                it = owned.erase(it);
            }
            else
            {
                auto name = L"AudioBule · " + target->name;
                if (name != it->appliedName && DisplayName(it->control.get()) == it->appliedName &&
                    SUCCEEDED(it->control->SetDisplayName(name.c_str(), nullptr))) it->appliedName = std::move(name);
                ++it;
            }
        }
        if (targets.empty()) return;
        DWORD servicePid = AudioServiceProcessId();
        if (!servicePid) return;
        wil::com_ptr<IMMDeviceEnumerator> enumerator;
        if (FAILED(::CoCreateInstance(__uuidof(MMDeviceEnumerator), nullptr, CLSCTX_ALL,
            IID_PPV_ARGS(enumerator.put())))) return;
        wil::com_ptr<IMMDeviceCollection> endpoints;
        if (FAILED(enumerator->EnumAudioEndpoints(eRender, DEVICE_STATE_ACTIVE, endpoints.put()))) return;
        UINT count = 0;
        if (FAILED(endpoints->GetCount(&count))) return;
        for (UINT i = 0; i < count; ++i)
        {
            wil::com_ptr<IMMDevice> endpoint;
            if (FAILED(endpoints->Item(i, endpoint.put()))) continue;
            wil::com_ptr<IAudioSessionManager2> manager;
            if (FAILED(endpoint->Activate(__uuidof(IAudioSessionManager2), CLSCTX_ALL, nullptr,
                reinterpret_cast<void**>(manager.put())))) continue;
            wil::com_ptr<IAudioSessionEnumerator> sessions;
            if (FAILED(manager->GetSessionEnumerator(sessions.put()))) continue;
            int sessionCount = 0;
            if (FAILED(sessions->GetCount(&sessionCount))) continue;
            for (int j = 0; j < sessionCount; ++j)
            {
                wil::com_ptr<IAudioSessionControl> session;
                if (FAILED(sessions->GetSession(j, session.put()))) continue;
                wil::com_ptr<IAudioSessionControl2> control;
                if (FAILED(session->QueryInterface(IID_PPV_ARGS(control.put())))) continue;
                DWORD pid = 0;
                AudioSessionState state = AudioSessionStateExpired;
                if (FAILED(control->GetProcessId(&pid)) || pid != servicePid ||
                    FAILED(control->GetState(&state)) || state != AudioSessionStateActive) continue;
                LPWSTR value = nullptr;
                if (FAILED(control->GetSessionInstanceIdentifier(&value))) continue;
                auto instance = TakeString(value);
                if (instance.empty() || std::any_of(owned.begin(), owned.end(),
                    [&](auto const& item) { return item.instanceId == instance; })) continue;
                auto originalName = DisplayName(control.get());
                auto match = MatchA2dpSessionDevice(originalName, targets);
                if (!match) continue;
                auto originalIcon = IconPath(control.get());
                auto name = L"AudioBule · " + targets[*match].name;
                OwnedSession record{ control, targets[*match].id, std::move(instance),
                    std::move(originalName), std::move(originalIcon), std::move(name) };
                // 任一写入失败就恢复已修改的一项，不保留半完成的品牌显示。
                HRESULT nameHr = control->SetDisplayName(record.appliedName.c_str(), nullptr);
                HRESULT iconHr = SUCCEEDED(nameHr) ? control->SetIconPath(iconPath.c_str(), nullptr) : nameHr;
                if (FAILED(nameHr) || FAILED(iconHr)) { Restore(record); continue; }
                owned.push_back(std::move(record));
            }
        }
    }
    void Run() noexcept
    {
        HRESULT initialized = ::CoInitializeEx(nullptr, COINIT_MULTITHREADED);
        if (FAILED(initialized)) return;
        try
        {
            // 缺少图标时直接回退到系统显示，不写入无效路径。
            DWORD attributes = ::GetFileAttributesW(iconPath.c_str());
            if (attributes != INVALID_FILE_ATTRIBUTES && !(attributes & FILE_ATTRIBUTE_DIRECTORY))
            {
                std::unique_lock lock(mutex);
                while (!stopping)
                {
                    changed.wait_for(lock, std::chrono::seconds(1), [this] { return stopping || dirty; });
                    if (stopping) break;
                    auto targets = devices;
                    dirty = false;
                    lock.unlock();
                    Scan(targets);
                    lock.lock();
                }
            }
        }
        catch (...) { ::OutputDebugStringW(L"AudioBule：音频会话外观更新失败，保留系统显示。\n"); }
        for (auto const& session : owned) Restore(session);
        owned.clear();
        ::CoUninitialize();
    }
};

AudioSessionIdentity::AudioSessionIdentity(std::wstring iconPath) : m_impl(std::make_unique<Impl>(std::move(iconPath))) {}
AudioSessionIdentity::~AudioSessionIdentity() = default;
void AudioSessionIdentity::SetDevices(std::vector<DeviceInfo> devices)
{
    std::lock_guard lock(m_impl->mutex);
    // 重绘窗口不应造成重复扫描，设备集合变化才立即唤醒工作线程。
    if (devices.size() == m_impl->devices.size() && std::equal(devices.begin(), devices.end(), m_impl->devices.begin(),
        [](auto const& a, auto const& b) { return a.id == b.id && a.name == b.name; })) return;
    m_impl->devices = std::move(devices);
    m_impl->dirty = true;
    m_impl->changed.notify_one();
}
}
