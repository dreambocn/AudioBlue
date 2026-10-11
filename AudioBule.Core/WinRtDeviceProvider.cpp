#include "pch.h"
#include "WinRtDeviceProvider.h"

#include <winrt/Windows.Devices.Enumeration.h>
#include <winrt/Windows.Foundation.Collections.h>
#include <winrt/Windows.Foundation.Metadata.h>
#include <winrt/Windows.Media.Audio.h>

namespace AudioBule::Core
{

using namespace winrt::Windows::Devices::Enumeration;
using namespace winrt::Windows::Foundation::Metadata;
using namespace winrt::Windows::Media::Audio;

namespace {

// 把 OpenAsync 的 Status 映射到我们的 ConnectFailure。
// 实测值（winrt/impl/windows.media.audio.0.h）：
//   Success=0, RequestTimedOut=1, DeniedBySystem=2, UnknownFailure=3
ConnectFailure MapOpenStatus(AudioPlaybackConnectionOpenResultStatus status)
{
    switch (status)
    {
    case AudioPlaybackConnectionOpenResultStatus::Success:
        return ConnectFailure::None;
    case AudioPlaybackConnectionOpenResultStatus::RequestTimedOut:
        return ConnectFailure::RequestTimedOut;
    case AudioPlaybackConnectionOpenResultStatus::DeniedBySystem:
        return ConnectFailure::DeniedBySystem;
    case AudioPlaybackConnectionOpenResultStatus::UnknownFailure:
    default:
        return ConnectFailure::UnknownFailure;
    }
}

// ⚠️ AudioPlaybackConnectionState **只有** Closed=0 与 Opened=1，
// 没有中间的 Connecting 状态。「连接中」是 AudioBule 自己的
// ConnectionState::Connecting，由 ConnectionManager 在 OpenAsync 返回前维持。
constexpr int kAudioConnectionClosed = 0;

} // namespace

WinRtDeviceProvider::WinRtDeviceProvider() = default;

WinRtDeviceProvider::~WinRtDeviceProvider()
{
    std::lock_guard<std::mutex> lock(m_mutex);
    // 直接清空即可：AudioPlaybackConnection 的析构会关闭底层 A2DP 会话。
    // 刻意不逐个 Close() —— 程序退出路径上任何 COM 调用都可能失败并阻塞。
    m_connections.clear();
}

bool WinRtDeviceProvider::IsSupported() const
{
    try
    {
        // Windows 10 2004 以下 AudioPlaybackConnection 类型不存在。
        // 先探测再调用，否则低版本系统上会在 GetDeviceSelector 处 E_NOINTERFACE。
        return ApiInformation::IsTypePresent(winrt::name_of<AudioPlaybackConnection>());
    }
    catch (...)
    {
        return false;
    }
}

std::vector<DeviceInfo> WinRtDeviceProvider::EnumerateDevices()
{
    std::vector<DeviceInfo> result;

    if (!IsSupported())
    {
        return result;
    }

    auto selector = AudioPlaybackConnection::GetDeviceSelector();

    // 同步阻塞：ConnectionManager::Refresh 是同步方法，调用方已在工作线程上
    auto devices = DeviceInformation::FindAllAsync(selector).get();

    for (auto const& device : devices)
    {
        DeviceInfo info;
        info.id = std::wstring(device.Id());
        auto name = device.Name();
        info.name = name.empty() ? info.id : std::wstring(name);
        result.push_back(std::move(info));
    }

    return result;
}

ConnectResult WinRtDeviceProvider::Connect(std::wstring_view deviceId)
{
    std::wstring id(deviceId);

    if (!IsSupported())
    {
        return ConnectResult{ false, ConnectFailure::DeviceNotSupported, 0 };
    }

    {
        std::lock_guard<std::mutex> lock(m_mutex);
        if (m_connections.find(id) != m_connections.end())
        {
            // 已连着。ConnectionManager 的幂等检查通常已拦住，这里是第二道防线。
            return ConnectResult{ true, ConnectFailure::None, 0 };
        }
    }

    AudioPlaybackConnection connection = nullptr;
    try
    {
        // 不能写 winrt::to_hstring(std::wstring) —— CppWinRT 的 base.h 没有
        // 该重载。显式构造一次即可（详见 PROGRESS.md 第 27 条）。
        winrt::hstring nativeId{ std::wstring_view{ id } };
        connection = AudioPlaybackConnection::TryCreateFromId(nativeId);
    }
    catch (winrt::hresult_error const& e)
    {
        return ConnectResult{ false, ConnectFailure::HresultError, e.code() };
    }

    if (!connection)
    {
        // 设备不支持 A2DP Sink（spike 实测：部分手机会这样）
        return ConnectResult{ false, ConnectFailure::DeviceNotSupported, 0 };
    }

    try
    {
        // StartAsync 返回 void，无结果值可查 —— 不要试图检查它的「返回值」
        connection.StartAsync().get();

        auto openResult = connection.OpenAsync().get();

        if (openResult.Status() != AudioPlaybackConnectionOpenResultStatus::Success)
        {
            auto extended = openResult.ExtendedError();

            // ERROR_GEN_FAILURE (0x8007001F) 在实践中几乎总是同一个原因：
            // 手机正作为 A2DP 源连着别的设备，无法同时当接收端。
            // 归到 GenericFailure 而不是 UnknownFailure，好让 Messages 给出
            // 针对性的操作建议（见 Review Focus 第 1 条）。
            ConnectFailure failure = MapOpenStatus(openResult.Status());
            if (static_cast<DWORD>(extended) == 0x8007001Fu)
            {
                failure = ConnectFailure::GenericFailure;
            }

            return ConnectResult{ false, failure, extended };
        }
    }
    catch (winrt::hresult_error const& e)
    {
        return ConnectResult{ false, ConnectFailure::HresultError, e.code() };
    }

    {
        std::lock_guard<std::mutex> lock(m_mutex);

        // 重新检查：等待 OpenAsync 期间可能已被别的线程连上或断开
        if (m_connections.find(id) != m_connections.end())
        {
            return ConnectResult{ true, ConnectFailure::None, 0 };
        }

        m_connections.emplace(id, connection);

        // 底层连接被系统关闭（设备走远、手机关蓝牙）时通知 ConnectionManager。
        connection.StateChanged(
            [this, id](AudioPlaybackConnection const& sender, auto const&)
            {
                if (static_cast<int>(sender.State()) != kAudioConnectionClosed)
                {
                    return;
                }
                {
                    std::lock_guard<std::mutex> lock(m_mutex);
                    m_connections.erase(id);
                }
                ConnectionLost.Raise(id);
            });
    }

    return ConnectResult{ true, ConnectFailure::None, 0 };
}

void WinRtDeviceProvider::Disconnect(std::wstring_view deviceId)
{
    std::wstring id(deviceId);

    AudioPlaybackConnection connection = nullptr;
    {
        std::lock_guard<std::mutex> lock(m_mutex);
        auto it = m_connections.find(id);
        if (it == m_connections.end())
        {
            return;   // 幂等：未连接时直接返回
        }
        connection = it->second;
        m_connections.erase(it);
    }

    // 必须在锁外 Close：Close 会同步触发 StateChanged，
    // 上面那个 lambda 会再取锁。锁内调用 = 非递归 mutex 自死锁。
    try
    {
        connection.Close();
    }
    catch (winrt::hresult_error const&)
    {
        // 关不掉也不要紧：连接对象已从表里移除并在此析构，
        // AudioPlaybackConnection 的析构同样会关闭底层会话。
    }
}

} // namespace AudioBule::Core