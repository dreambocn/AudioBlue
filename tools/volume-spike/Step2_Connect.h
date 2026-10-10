#pragma once

#include "Step1_Enumerate.h"

// 建立一个真实的 A2DP Sink 连接。
// 关键：渲染端点只在连接激活后才出现在 Core Audio 列表里 ——
// 仅配对不连接时枚举 eRender 是看不到蓝牙端点的。
// 返回是否连接成功。
bool ConnectFirstDevice(const A2dpDeviceInfo& device);