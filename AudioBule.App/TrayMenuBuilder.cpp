#include "pch.h"
#include "TrayMenuBuilder.h"

namespace AudioBule::App::TrayService
{
int ShowTrayMenu(HWND owner, POINT point, bool autoReconnect)
{
    HMENU menu = ::CreatePopupMenu();
    if (!menu) return 0;
    bool success = ::AppendMenuW(menu, MF_STRING, kCmdShowDevices, L"设备列表") &&
        ::AppendMenuW(menu, MF_STRING, kCmdBluetoothSettings, L"蓝牙设置…") &&
        ::AppendMenuW(menu, MF_STRING | (autoReconnect ? MF_CHECKED : MF_UNCHECKED),
            kCmdAutoReconnect, L"启动时自动重连") &&
        ::AppendMenuW(menu, MF_STRING | MF_GRAYED, 0, L"开机自启（尚未启用）") &&
        ::AppendMenuW(menu, MF_SEPARATOR, 0, nullptr) &&
        ::AppendMenuW(menu, MF_STRING, kCmdAbout, L"关于 AudioBule") &&
        ::AppendMenuW(menu, MF_STRING, kCmdExit, L"退出");
    int command = 0;
    if (success)
    {
        // 使用 UI 线程的真实顶层 HWND；message-only HWND 无法成为前台窗口。
        ::SetForegroundWindow(owner);
        command = static_cast<int>(::TrackPopupMenuEx(menu,
            TPM_RIGHTBUTTON | TPM_RETURNCMD | TPM_NONOTIFY,
            point.x, point.y, owner, nullptr));
        ::PostMessageW(owner, WM_NULL, 0, 0);
    }
    ::DestroyMenu(menu);
    return command;
}
}
