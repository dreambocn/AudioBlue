#pragma once

// 本头文件的接口用到 DWORD / HRESULT，因此必须自包含 windows.h ——
// 否则每个包含它的 TU 都要自己记得先包含 windows.h。
#include <windows.h>

#include <string>
#include <string_view>

namespace AudioBule::Core
{

// 宽字符串 → UTF-8。按 wcslen 语义处理，遇 NUL 停止。
std::string WideToUtf8(std::wstring_view text);

// UTF-8 → 宽字符串。无效的 UTF-8 字节序列替换为 U+FFFD，不抛异常。
std::wstring Utf8ToWide(std::string_view text);

// 把 HRESULT/Win32 错误码格式化为 0x%08X（八位大写十六进制）。
std::wstring FormatWin32Error(DWORD code);

// 取系统错误文本。系统没有可用文本时回落到 FormatWin32Error，保证非空。
std::wstring FormatMessageForHresult(HRESULT hr);

} // namespace AudioBule::Core