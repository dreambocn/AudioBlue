#pragma once

#include <string>
#include <vector>

struct A2dpDeviceInfo
{
    std::wstring id;
    std::wstring name;
};

// 检测系统是否支持 A2DP Sink（Windows 10 2004+）
bool IsA2dpSinkSupported();

// 枚举已配对的 A2DP Sink 设备。系统不支持或无设备时返回空向量。
std::vector<A2dpDeviceInfo> EnumerateA2dpDevices();