#include "pch.h"
#include "Step1_Enumerate.h"
#include "Step2_EndpointId.h"
#include "Step2_Connect.h"
#include "Step3_FindEndpoint.h"
#include "Step4_Volume.h"

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

    wprintf(L"\n[2/5] 读取设备音频端点 ID...\n");
    auto endpointIds = GetEndpointIdsForDevices(devices);
    if (endpointIds.empty())
    {
        wprintf(L"[结论] 没有任何设备暴露 System_DeviceEndpointId 属性。\n");
        wprintf(L"        原假设（属性 ID 可直接关联端点）不成立，转入兜底方案验证。\n");

        wprintf(L"\n[3/5] 建立 A2DP 连接（端点仅在连接激活后才出现）...\n");
        if (!ConnectFirstDevice(devices.front()))
        {
            wprintf(L"[结论] 无法建立 A2DP 连接，验证终止。\n");
            wprintf(L"        请确认手机已配对且可连接，再重试。\n");
            return 4;
        }

        wprintf(L"\n[4/5] 连接建立后重新枚举渲染端点...\n");
        wil::com_ptr<IMMDeviceEnumerator> enumerator;
        HRESULT hr = CoCreateInstance(
            __uuidof(MMDeviceEnumerator), nullptr, CLSCTX_INPROC_SERVER,
            __uuidof(IMMDeviceEnumerator), reinterpret_cast<void**>(enumerator.put()));
        if (FAILED(hr))
        {
            wprintf(L"[FAIL] 创建 MMDeviceEnumerator 失败: 0x%08X\n", static_cast<uint32_t>(hr));
            return 4;
        }

        auto renderEndpoints = ListRenderEndpoints(enumerator);
        if (renderEndpoints.empty())
        {
            wprintf(L"[结论] 系统没有任何活动渲染端点，音量控制方案完全不可行。\n");
            return 4;
        }

        wprintf(L"\n[INFO] 上方 %u 个渲染端点中请人工确认是否存在蓝牙设备。\n",
            static_cast<unsigned>(renderEndpoints.size()));
        wprintf(L"        若存在蓝牙端点 → 名称模糊匹配可行但不稳定；\n");
        wprintf(L"        若不存在 → A2DP 端点未暴露给 Core Audio，音量控制不可行。\n");

        wprintf(L"\n[5/5] 跳过（待确认是否存在蓝牙端点后再验证回调）\n");
        return 3;
    }
    wprintf(L"[OK]   %u 台设备成功关联到音频端点\n", static_cast<unsigned>(endpointIds.size()));

    return 0;
}