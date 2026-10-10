#pragma once

#include "Step1_Enumerate.h"
#include <string>
#include <vector>

// 读取每台设备的 System_DeviceEndpointId 属性。
// 属性缺失或非字符串的设备会被跳过（Review Focus 第 3 条）。
std::vector<std::wstring> GetEndpointIdsForDevices(const std::vector<A2dpDeviceInfo>& devices);