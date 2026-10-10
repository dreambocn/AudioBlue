#include "pch.h"
#include "Step1_Enumerate.h"

int wmain()
{
    // 本程序全部输出为中文窄字符串。窄 wprintf 按控制台当前 ANSI 代码页解释字节，
    // 默认 936(GBK) 下会输出乱码，必须切到 UTF-8 代码页。
    SetConsoleOutputCP(CP_UTF8);
    _setmode(_fileno(stdout), _O_U8TEXT);

    wprintf(L"=== A2DP 音量控制可行性 Spike ===\n\n");

    if (!IsA2dpSinkSupported())
    {
        wprintf(L"[结论] 系统不支持 A2DP Sink，无法继续验证。\n");
        return 1;
    }

    wprintf(L"[1/5] 枚举 A2DP 设备...\n");
    auto devices = EnumerateA2dpDevices();
    if (devices.empty())
    {
        wprintf(L"[结论] 没有可用设备，无法验证。请配对设备后重试。\n");
        return 2;
    }

    // 后续步骤在此插入

    return 0;
}