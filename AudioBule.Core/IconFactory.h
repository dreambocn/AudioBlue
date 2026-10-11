#pragma once

namespace AudioBule::Core
{

// 托盘图标句柄。刻意不用 windows.h 的 HICON（它是 struct HICON__*），
// 以免调用方为了用本文件而被迫包含 windows.h。
struct TrayIcon
{
    void* handle = nullptr;

    explicit operator bool() const { return handle != nullptr; }
};

// 生成 32x32 托盘图标（SVG 经 Direct2D 渲染）。
//   darkTheme = false → 浅色任务栏：画深色图形
//   darkTheme = true  → 深色任务栏：画浅色图形
// 返回空 TrayIcon 表示渲染失败；调用方可继续运行，只是没有托盘图标。
// 调用方**必须**用 DestroyTrayIcon 释放，否则 GDI 对象泄漏。
TrayIcon CreateTrayIcon(bool darkTheme);

void DestroyTrayIcon(TrayIcon icon);

} // namespace AudioBule::Core