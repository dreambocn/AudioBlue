#pragma once

#include "ConnectionEntry.h"
#include <functional>

namespace AudioBule::Core
{
// 蓝牙会话的最小平台接缝：测试可控制打开与关闭通知的先后，不接触真实设备。
class IAudioPlaybackSession
{
public:
    virtual ~IAudioPlaybackSession() = default;
    virtual void SetClosedHandler(std::function<void()> handler) = 0;
    virtual void ClearClosedHandler() noexcept = 0;
    virtual ConnectResult Open() = 0;
    virtual bool IsOpen() const = 0;
    virtual void Close() noexcept = 0;
};
}
