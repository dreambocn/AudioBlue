#pragma once
#include <windows.h>

namespace AudioBule::App::TrayService
{
constexpr int kCmdShowDevices = 1000;
constexpr int kCmdBluetoothSettings = 1001;
constexpr int kCmdAutoReconnect = 1002;
constexpr int kCmdAbout = 1004;
constexpr int kCmdExit = 1005;

// 必须由拥有 owner 窗口的 UI 线程调用；返回 0 表示取消。
int ShowTrayMenu(HWND owner, POINT point, bool autoReconnect);
}
