#pragma once

#include "IAudioDeviceProvider.h"
#include "IAudioPlaybackSession.h"
#include "CallbackGate.h"

#include <mutex>
#include <chrono>
#include <unordered_map>
#include <vector>

namespace AudioBule::Core
{

// IAudioDeviceProvider 的生产实现，包装 AudioPlaybackConnection。
//
// 线程模型：Connect / Disconnect 由 ConnectionManager 在工作线程上调用；
// StateChanged 的处理器也可能在任意线程触发，所以 m_connections 一律加锁。
class WinRtDeviceProvider final : public IAudioDeviceProvider
{
public:
    using SessionFactory = std::function<std::shared_ptr<IAudioPlaybackSession>(std::wstring_view)>;
    explicit WinRtDeviceProvider(LogContext log = {}, SessionFactory factory = {},
        std::chrono::milliseconds openStateTimeout = std::chrono::seconds(2));
    ~WinRtDeviceProvider() override;

    bool IsSupported() const override;
    std::vector<DeviceInfo> EnumerateDevices() override;
    ConnectResult Connect(std::wstring_view deviceId, LogContext const& log = {}, uint64_t connectionId = 0) override;
    void Disconnect(std::wstring_view deviceId, LogContext const& log = {}) override;

private:
    struct ConnectionRecord
    {
        std::shared_ptr<IAudioPlaybackSession> session;
        uint64_t connectionId = 0;
        bool opening = true;
        bool closed = false;
    };
    void ObserveClosed(std::wstring const& id, std::shared_ptr<ConnectionRecord> const& record);
    void RemoveAndClose(std::wstring const& id, std::shared_ptr<ConnectionRecord> const& record);
    LogContext m_log;
    SessionFactory m_factory;
    std::chrono::milliseconds m_openStateTimeout;
    std::shared_ptr<CallbackGate> m_callbacks = std::make_shared<CallbackGate>();
    std::mutex m_mutex;
    std::unordered_map<std::wstring, std::shared_ptr<ConnectionRecord>> m_connections;
};

} // namespace AudioBule::Core
