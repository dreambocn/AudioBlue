#pragma once
#include "ConnectionEntry.h"
#include "Logger.h"
#include <memory>
#include <optional>
#include <string_view>
#include <vector>

namespace AudioBule::Core
{
// 完整匹配系统 A2DP 会话的设备名；重名时拒绝猜测归属。
std::optional<size_t> MatchA2dpSessionDevice(
    std::wstring_view displayName, std::vector<DeviceInfo> const& devices);

// 在独立 MTA 线程维护音量合成器的名称和图标，不接管音频播放。
class AudioSessionIdentity final
{
public:
    explicit AudioSessionIdentity(std::wstring iconPath, LogContext log = {});
    ~AudioSessionIdentity();
    void SetDevices(std::vector<DeviceInfo> devices);
private:
    struct Impl;
    std::unique_ptr<Impl> m_impl;
};
}
