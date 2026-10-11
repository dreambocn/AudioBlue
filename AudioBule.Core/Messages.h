#pragma once

#include "ConnectionEntry.h"

#include <string>

namespace AudioBule::Core
{

// Core 层错误文案。spec §3.7 规定：Core 产出的字符串走这里，
// App 不硬编码 Core 的错误文案。
//
// 当前返回简体中文。计划二（增强功能）会改成按 UI 语言查表的静态表，
// 接口形态保持不变 —— 届时只需改这个 .cpp。
std::wstring MessageForConnectFailure(ConnectFailure failure, HRESULT extendedError);

} // namespace AudioBule::Core