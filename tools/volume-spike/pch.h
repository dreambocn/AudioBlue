#pragma once

#include "targetver.h"

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <objbase.h>
#include <fcntl.h>
#include <io.h>
#include <mmdeviceapi.h>
#include <endpointvolume.h>
// PKEY_Device_FriendlyName 等属性键常量定义于此。
// 注意：SDK 26100 中此头名为 functiondiscoverykeys_devpkey.h，
// 旧文档里的 functiondiscoverykeysapi.h 已不存在。
#include <functiondiscoverykeys_devpkey.h>

#include <cstdio>
#include <string>
#include <vector>

#include <wil/common.h>
#include <wil/com.h>
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