#pragma once

#include <string>
#include <vector>

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