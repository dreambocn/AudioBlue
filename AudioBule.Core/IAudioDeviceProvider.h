#pragma once

#include "ConnectionEntry.h"
#include "SimpleEvent.h"

#include <string>
#include <string_view>
#include <vector>

namespace AudioBule::Core
{

// 设备枚举与连接的抽象。存在的唯一理由是让 ConnectionManager 脱离
// AudioPlaybackConnection 依赖，从而可单元测试（spec §6）。
//
// 实现约定：
//  - Connect / Disconnect 会被 ConnectionManager 在**工作线程**上调用，
//    不得在 UI 线程直接调用。
//  - EnumerateDevices 允许抛异常；ConnectionManager 会吞掉并视为空列表。
//  - 底层连接被系统关闭时，必须 Raise ConnectionLost。
class IAudioDeviceProvider
{
public:
    virtual ~IAudioDeviceProvider() = default;

    virtual bool IsSupported() const = 0;
    virtual std::vector<DeviceInfo> EnumerateDevices() = 0;
    virtual ConnectResult Connect(std::wstring_view deviceId) = 0;
    virtual void Disconnect(std::wstring_view deviceId) = 0;

    // 参数为 deviceId（宽字符，与 ConnectionEntry::deviceId 同类型）。
    // 由 provider 在观察到连接被系统关闭时触发。
    SimpleEvent<std::wstring> ConnectionLost;
};

} // namespace AudioBule::Core