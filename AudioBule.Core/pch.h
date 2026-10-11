#pragma once

#include "targetver.h"

#define WIN32_LEAN_AND_MEAN
// windows.h 的 min/max 宏会与 std::min/std::max 冲突（报 C2589 等）。
// 一旦用了标准库容器就应当定义它。
#define NOMINMAX
#include <windows.h>
#include <objbase.h>

#include <algorithm>
#include <string>
#include <vector>

#include <wil/common.h>
#include <wil/com.h>
#include <wil/result.h>

// C++/WinRT 的 Windows.Foundation 头会定义 GetCurrentTime 宏，与 windows.h 冲突导致 C4002。
// 必须在包含 C++/WinRT 头之前 #undef。
#undef GetCurrentTime

#include <winrt/base.h>
#include <winrt/Windows.Foundation.h>
// 范围 for 遍历 WinRT 集合（DeviceInformationCollection 等）依赖此头的迭代器
#include <winrt/Windows.Foundation.Collections.h>
#include <winrt/Windows.Foundation.Metadata.h>