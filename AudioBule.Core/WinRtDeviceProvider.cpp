#include "pch.h"
#include "WinRtDeviceProvider.h"

#include <winrt/Windows.Devices.Enumeration.h>
#include <winrt/Windows.Foundation.Metadata.h>
#include <winrt/Windows.Media.Audio.h>
#include <thread>

namespace AudioBule::Core
{
using namespace winrt::Windows::Devices::Enumeration;
using namespace winrt::Windows::Foundation::Metadata;
using namespace winrt::Windows::Media::Audio;

namespace
{
ConnectFailure MapOpenStatus(AudioPlaybackConnectionOpenResultStatus status)
{
    switch (status)
    {
    case AudioPlaybackConnectionOpenResultStatus::Success: return ConnectFailure::None;
    case AudioPlaybackConnectionOpenResultStatus::RequestTimedOut: return ConnectFailure::RequestTimedOut;
    case AudioPlaybackConnectionOpenResultStatus::DeniedBySystem: return ConnectFailure::DeniedBySystem;
    default: return ConnectFailure::UnknownFailure;
    }
}

// 只有这个适配器接触 WinRT 会话，Provider 的并发与生命周期可使用模拟会话验证。
class WinRtPlaybackSession final : public IAudioPlaybackSession
{
public:
    WinRtPlaybackSession(AudioPlaybackConnection connection, LogContext log)
        : m_connection(std::move(connection)), m_log(std::move(log)) {}
    ~WinRtPlaybackSession() override { Close(); }
    void SetClosedHandler(std::function<void()> handler) override
    {
        m_token = m_connection.StateChanged([handler = std::move(handler), log = m_log](auto const& sender, auto const&) {
            try { if (sender.State() == AudioPlaybackConnectionState::Closed) handler(); }
            catch (...) { log.Write(LogEvent::ProviderStage, { .stage = LogStage::Close, .outcome = LogOutcome::Failed, .hresult = winrt::to_hresult() }, LogLevel::Warning); }
        });
        m_subscribed = true;
    }
    void ClearClosedHandler() noexcept override
    {
        if (!m_subscribed.exchange(false)) return;
        try { m_connection.StateChanged(m_token); }
        catch (...) { m_log.Write(LogEvent::ProviderStage, { .stage = LogStage::Cleanup, .hresult = winrt::to_hresult() }, LogLevel::Warning); }
    }
    ConnectResult Open() override
    {
        auto stage = LogStage::Start;
        try
        {
            m_log.Write(LogEvent::ProviderStage, { .stage = stage }, LogLevel::Debug);
            m_connection.StartAsync().get();
            stage = LogStage::Open;
            m_log.Write(LogEvent::ProviderStage, { .stage = stage }, LogLevel::Debug);
            auto result = m_connection.OpenAsync().get();
            if (result.Status() != AudioPlaybackConnectionOpenResultStatus::Success)
            {
                auto extended = result.ExtendedError();
                auto failure = static_cast<DWORD>(extended) == 0x8007001Fu ? ConnectFailure::GenericFailure : MapOpenStatus(result.Status());
                m_log.Write(LogEvent::ProviderStage, { .stage = stage, .outcome = LogOutcome::Failed, .hresult = extended,
                    .failure = static_cast<int32_t>(failure), .status = static_cast<int32_t>(result.Status()) }, LogLevel::Warning);
                return { false, failure, extended };
            }
            return { true, ConnectFailure::None, 0 };
        }
        catch (winrt::hresult_error const& error)
        {
            m_log.Write(LogEvent::ProviderStage, { .stage = stage, .outcome = LogOutcome::Failed, .hresult = error.code() }, LogLevel::Warning);
            return { false, ConnectFailure::HresultError, error.code() };
        }
    }
    bool IsOpen() const override { return m_connection.State() == AudioPlaybackConnectionState::Opened; }
    void Close() noexcept override
    {
        if (m_closed.exchange(true)) return;
        ClearClosedHandler();
        try { m_connection.Close(); }
        catch (...) { m_log.Write(LogEvent::ProviderStage, { .stage = LogStage::Close, .outcome = LogOutcome::Failed, .hresult = winrt::to_hresult() }, LogLevel::Warning); }
    }
private:
    AudioPlaybackConnection m_connection;
    LogContext m_log;
    winrt::event_token m_token{};
    std::atomic<bool> m_subscribed{false}, m_closed{false};
};
}

WinRtDeviceProvider::WinRtDeviceProvider(LogContext log, SessionFactory factory, std::chrono::milliseconds openStateTimeout)
    : m_log(std::move(log)), m_factory(std::move(factory)),
      m_openStateTimeout(std::max(openStateTimeout, std::chrono::milliseconds::zero())) {}

WinRtDeviceProvider::~WinRtDeviceProvider()
{
    // 先禁止并等待外部回调，再在锁外退订和释放会话。
    m_callbacks->CloseAndWait();
    decltype(m_connections) connections;
    { std::lock_guard lock(m_mutex); connections.swap(m_connections); }
    for (auto const& [id, record] : connections)
    {
        record->session->ClearClosedHandler();
        record->session->Close();
    }
}

bool WinRtDeviceProvider::IsSupported() const
{
    if (m_factory) return true;
    try { return ApiInformation::IsTypePresent(winrt::name_of<AudioPlaybackConnection>()); }
    catch (...) { m_log.Write(LogEvent::SupportProbeFailed, { .hresult = winrt::to_hresult() }, LogLevel::Warning); return false; }
}

std::vector<DeviceInfo> WinRtDeviceProvider::EnumerateDevices()
{
    std::vector<DeviceInfo> result;
    if (!IsSupported()) return result;
    // 调用方已经切到工作线程；枚举失败交给 Manager 保留原快照。
    auto devices = DeviceInformation::FindAllAsync(AudioPlaybackConnection::GetDeviceSelector()).get();
    for (auto const& device : devices)
    {
        auto name = device.Name();
        result.push_back({ std::wstring(device.Id()), name.empty() ? std::wstring(device.Id()) : std::wstring(name) });
    }
    return result;
}

ConnectResult WinRtDeviceProvider::Connect(std::wstring_view deviceId, LogContext const& log, uint64_t connectionId)
{
    std::wstring id(deviceId);
    if (!IsSupported()) return { false, ConnectFailure::DeviceNotSupported, 0 };
    {
        std::lock_guard lock(m_mutex);
        if (m_connections.contains(id)) return { false, ConnectFailure::HresultError, HRESULT_FROM_WIN32(ERROR_BUSY) };
    }
    auto record = std::make_shared<ConnectionRecord>();
    record->connectionId = connectionId;
    try
    {
        if (m_factory) record->session = m_factory(id);
        else if (auto connection = AudioPlaybackConnection::TryCreateFromId(winrt::hstring(id)))
            record->session = std::make_shared<WinRtPlaybackSession>(std::move(connection), log);
        if (!record->session)
        {
            log.Write(LogEvent::ProviderStage, { .stage = LogStage::Create, .outcome = LogOutcome::Unsupported }, LogLevel::Warning);
            return { false, ConnectFailure::DeviceNotSupported, 0 };
        }
    }
    catch (...)
    {
        auto error = winrt::to_hresult();
        log.Write(LogEvent::ProviderStage, { .stage = LogStage::Create, .outcome = LogOutcome::Failed, .hresult = error }, LogLevel::Warning);
        return { false, ConnectFailure::HresultError, error };
    }

    {
        std::lock_guard lock(m_mutex);
        if (auto it = m_connections.find(id); it != m_connections.end())
        {
            // 不把另一次尚未完成的打开当成当前请求成功。
            return { false, ConnectFailure::HresultError, HRESULT_FROM_WIN32(ERROR_BUSY) };
        }
        m_connections.emplace(id, record);
    }
    bool committed = false;
    auto cleanup = wil::scope_exit([&] { if (!committed) RemoveAndClose(id, record); });
    try
    {
        // 监听先于 Start/Open 注册，打开阶段关闭只标记当前记录，不发布过期成功。
        record->session->SetClosedHandler([this, gate = m_callbacks, id, weak = std::weak_ptr(record)] {
            auto lease = gate->TryEnter();
            if (!lease) return;
            if (auto current = weak.lock()) ObserveClosed(id, current);
        });
        auto result = record->session->Open();
        if (!result.succeeded) return result;
        bool open = record->session->IsOpen();
        if (!open)
        {
            // SDK 成功结果可能先于 State 更新；只等待连接状态，不探测播放或循环重连。
            auto started = std::chrono::steady_clock::now();
            auto deadline = started + m_openStateTimeout;
            while (!open && std::chrono::steady_clock::now() < deadline)
            {
                {
                    std::lock_guard lock(m_mutex);
                    auto it = m_connections.find(id);
                    // 真正的关闭、移除或替换不能被延迟状态同步掩盖。
                    if (it == m_connections.end() || it->second != record || record->closed) break;
                }
                std::this_thread::sleep_for(std::chrono::milliseconds(10));
                open = record->session->IsOpen();
            }
            log.Write(LogEvent::ProviderStateSynchronized, { .stage = LogStage::Open,
                .outcome = open ? LogOutcome::Succeeded : LogOutcome::Failed,
                .count = std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now() - started).count(),
                .stateBefore = 0, .stateAfter = open ? 1 : 0 }, open ? LogLevel::Info : LogLevel::Warning);
        }
        {
            std::lock_guard lock(m_mutex);
            auto it = m_connections.find(id);
            if (it != m_connections.end() && it->second == record && !record->closed && open)
            {
                record->opening = false;
                committed = true;
            }
        }
        if (!committed)
        {
            auto error = HRESULT_FROM_WIN32(ERROR_CONNECTION_ABORTED);
            log.Write(LogEvent::ProviderStage, { .stage = LogStage::Open, .outcome = LogOutcome::Failed, .hresult = error }, LogLevel::Warning);
            return { false, ConnectFailure::HresultError, error };
        }
        log.Write(LogEvent::ProviderStage, { .stage = LogStage::Open, .outcome = LogOutcome::Succeeded }, LogLevel::Debug);
        return result;
    }
    catch (...)
    {
        auto error = winrt::to_hresult();
        log.Write(LogEvent::ProviderStage, { .stage = LogStage::Open, .outcome = LogOutcome::Failed, .hresult = error }, LogLevel::Warning);
        return { false, ConnectFailure::HresultError, error };
    }
}

void WinRtDeviceProvider::ObserveClosed(std::wstring const& id, std::shared_ptr<ConnectionRecord> const& record)
{
    bool notify = false;
    {
        std::lock_guard lock(m_mutex);
        auto it = m_connections.find(id);
        if (it == m_connections.end() || it->second != record) return;
        record->closed = true;
        if (!record->opening) { m_connections.erase(it); notify = true; }
    }
    // 不在状态锁内发布事件；代次让 Manager 拒绝已进入队列的旧连接通知。
    if (notify) ConnectionLost.Raise(id, record->connectionId);
}

void WinRtDeviceProvider::RemoveAndClose(std::wstring const& id, std::shared_ptr<ConnectionRecord> const& record)
{
    {
        std::lock_guard lock(m_mutex);
        auto it = m_connections.find(id);
        if (it != m_connections.end() && it->second == record) m_connections.erase(it);
    }
    record->session->ClearClosedHandler();
    record->session->Close();
}

void WinRtDeviceProvider::Disconnect(std::wstring_view deviceId, LogContext const&)
{
    std::shared_ptr<ConnectionRecord> record;
    {
        std::lock_guard lock(m_mutex);
        auto it = m_connections.find(std::wstring(deviceId));
        if (it == m_connections.end()) return;
        record = std::move(it->second);
        m_connections.erase(it);
    }
    // 退订和 Close 均可能同步触发系统调用，不得持有 Provider 状态锁。
    record->session->ClearClosedHandler();
    record->session->Close();
}
}
