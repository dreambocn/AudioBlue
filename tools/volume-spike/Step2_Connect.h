#pragma once

#include "Step1_Enumerate.h"

using namespace winrt::Windows::Media::Audio;

// 建立一个真实的 A2DP Sink 连接。
// 关键：渲染端点只在连接激活后才出现在 Core Audio 列表里 ——
// 仅配对不连接时枚举 eRender 是看不到蓝牙端点的。
// 返回是否连接成功。
bool ConnectDevice(const A2dpDeviceInfo& device, AudioPlaybackConnection& outConnection);

// 依次尝试每台设备，返回第一台 OpenAsync 成功的设备名（全部失败返回空）。
// 成功时通过 outConnection 输出该连接对象，供状态监听使用。
std::wstring ConnectAnyDevice(const std::vector<A2dpDeviceInfo>& devices,
    AudioPlaybackConnection& outConnection);

// 订阅连接的 StateChanged，把状态迁移打印出来。
// State 一直停在 0(Closed) 说明连接根本没真正建立 —— 此时
// PC 不会在手机的输出列表里出现，A2DP 流也不可能建立。
class ConnectionStateWatcher
{
public:
    void Attach(const AudioPlaybackConnection& connection);
    ~ConnectionStateWatcher();

    int CurrentState() const { return state_; }
    bool SawConnected() const { return sawConnected_; }

private:
    winrt::event_token token_{};
    AudioPlaybackConnection connection_{ nullptr };
    int state_ = 0;
    bool sawConnected_ = false;
};