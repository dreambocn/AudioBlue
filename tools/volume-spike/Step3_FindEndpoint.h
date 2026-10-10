#pragma once

#include <string>
#include <vector>
#include <memory>

// 端点在 A2DP 连接建立后可能延迟出现，重试 5 次每次间隔 500ms。
// 全部失败返回 nullptr。
wil::com_ptr<IMMDevice> FindDevice(
    const wil::com_ptr<IMMDeviceEnumerator>& enumerator,
    const std::wstring& endpointId);

struct RenderEndpointInfo
{
    std::wstring id;
    std::wstring friendlyName;
};

// 枚举系统全部 eRender 端点。
// 当 System_DeviceEndpointId 属性缺失时（实测：本机两台蓝牙设备均无此属性），
// 只能用「设备名模糊匹配 + 端点属性比对」兜底关联，先靠此函数看有哪些候选。
std::vector<RenderEndpointInfo> ListRenderEndpoints(const wil::com_ptr<IMMDeviceEnumerator>& enumerator);

// 同上但不打印任何输出。用于 1 秒一次的密集轮询，避免刷屏。
std::vector<RenderEndpointInfo> ListRenderEndpointsQuiet(const wil::com_ptr<IMMDeviceEnumerator>& enumerator);

// 连接建立后轮询渲染端点，找出相对基线新增的端点。
// A2DP Sink 端点通常在真正有音频流过时才被实例化，故需轮询等待。
// baseline 为连接前的端点 Id 集合；返回新增的端点（可能为空）。
std::vector<RenderEndpointInfo> PollForNewEndpoints(
    const wil::com_ptr<IMMDeviceEnumerator>& enumerator,
    const std::vector<std::wstring>& baseline,
    int maxSeconds);

// 默认渲染端点的峰值表。
// 用于自证「音频是否真的在流」—— 不能依赖人工确认播放，
// 否则测试结论无法区分「端点不存在」与「根本没播放」。
class PeakMeter
{
public:
    // 为指定端点创建峰值表；失败返回 nullptr
    static std::unique_ptr<PeakMeter> Create(const std::wstring& endpointId,
        const wil::com_ptr<IMMDeviceEnumerator>& enumerator);

    // 最近一次采样的峰值（0.0 ~ 1.0）
    float Sample();

    const std::wstring& Name() const { return name_; }

private:
    std::wstring name_;
    wil::com_ptr<IAudioMeterInformation> meter_;
};