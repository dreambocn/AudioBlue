#pragma once

#include "targetver.h"

#define WIN32_LEAN_AND_MEAN
// windows.h 的 min/max 宏与 std::min/std::max 冲突
#define NOMINMAX
#include <windows.h>
#include <objbase.h>

#include <algorithm>
#include <string>
#include <vector>

#include <wil/common.h>
#include <wil/com.h>
#include <wil/result.h>

// C++/WinRT 的 Windows.Foundation 头会定义 GetCurrentTime 宏，
// 与 windows.h 冲突导致 C4002。必须在包含 C++/WinRT 头之前 #undef。
#undef GetCurrentTime

#include <winrt/base.h>
#include <winrt/Windows.Foundation.h>
#include <winrt/Windows.Foundation.Collections.h>
#include <winrt/Windows.Foundation.Metadata.h>

// Core 的公开头 —— App 可以依赖 Core，反之不行（Core 不引用任何 WinUI 头）。
#include "ConnectionEntry.h"
#include "ConnectionManager.h"
#include "IAudioDeviceProvider.h"
#include "IconFactory.h"
#include "Messages.h"
#include "Settings.h"
#include "SimpleEvent.h"
#include "StringUtil.h"
#include "WinRtDeviceProvider.h"