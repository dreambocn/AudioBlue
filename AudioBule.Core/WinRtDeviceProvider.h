#pragma once

#include "IAudioDeviceProvider.h"

#include <mutex>
#include <unordered_map>
#include <vector>

#include <winrt/Windows.Media.Audio.h>

namespace AudioBule::Core
{

// IAudioDeviceProvider 的生产实现，包装 AudioPlaybackConnection。
//
// 线程模型：Connect / Disconnect 由 ConnectionManager 在工作线程上调用；
// StateChanged 的处理器也可能在任意线程触发，所以 m_connections 一律加锁。
class WinRtDeviceProvider final : public IAudioDeviceProvider
{
public:
    WinRtDeviceProvider();
    ~WinRtDeviceProvider() override;

    bool IsSupported() const override;
    std::vector<DeviceInfo> EnumerateDevices() override;
    ConnectResult Connect(std::wstring_view deviceId) override;
    void Disconnect(std::wstring_view deviceId) override;

private:
    std::mutex m_mutex;
    std::unordered_map<std::wstring, winrt::Windows::Media::Audio::AudioPlaybackConnection>
        m_connections;
};

} // namespace AudioBule::Core