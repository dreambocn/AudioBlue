#pragma once

#include "targetver.h"

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <objbase.h>
#include <fcntl.h>
#include <io.h>
#include <mmdeviceapi.h>
#include <endpointvolume.h>

#include <cstdio>
#include <string>
#include <vector>

#include <wil/common.h>
#include <wil/result.h>

// C++/WinRT 的 Windows.Foundation 头会定义 GetCurrentTime 宏，
// 与 windows.h 中的声明冲突，导致 C4002 错误
#undef GetCurrentTime

#include <winrt/base.h>
#include <winrt/Windows.Foundation.h>
// 范围 for 遍历 WinRT 集合（DeviceInformationCollection 等）依赖此头提供的迭代器
#include <winrt/Windows.Foundation.Collections.h>
#include <winrt/Windows.Foundation.Metadata.h>
#include <winrt/Windows.Devices.Enumeration.h>
#include <winrt/Windows.Media.Audio.h>