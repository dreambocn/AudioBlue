#pragma once

#include "ConnectionEntry.h"
#include "Logger.h"
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
//  - EnumerateDevices 允许抛异常；ConnectionManager 保留原快照并返回刷新失败。
//  - 底层连接被系统关闭时，必须携带原连接代次 Raise ConnectionLost。
class IAudioDeviceProvider
{
public:
    virtual ~IAudioDeviceProvider() = default;

    virtual bool IsSupported() const = 0;
    virtual std::vector<DeviceInfo> EnumerateDevices() = 0;
    virtual ConnectResult Connect(std::wstring_view deviceId, LogContext const& log = {}, uint64_t connectionId = 0) = 0;
    virtual void Disconnect(std::wstring_view deviceId, LogContext const& log = {}) = 0;

    // 代次由 Manager 在连接开始前分配，迟到事件不能关闭同设备的新连接。
    SimpleEvent<std::wstring, uint64_t> ConnectionLost;
};

} // namespace AudioBule::Core
