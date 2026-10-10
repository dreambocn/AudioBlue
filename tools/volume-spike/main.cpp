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

        wil::com_ptr<IMMDeviceEnumerator> enumerator;
        HRESULT hr = CoCreateInstance(
            __uuidof(MMDeviceEnumerator), nullptr, CLSCTX_INPROC_SERVER,
            __uuidof(IMMDeviceEnumerator), reinterpret_cast<void**>(enumerator.put()));
        if (FAILED(hr))
        {
            wprintf(L"[FAIL] 创建 MMDeviceEnumerator 失败: 0x%08X\n", static_cast<uint32_t>(hr));
            return 4;
        }

        // 连接前基线
        std::vector<std::wstring> baselineIds;
        for (const auto& e : ListRenderEndpoints(enumerator))
        {
            baselineIds.push_back(e.id);
        }
        wprintf(L"[INFO] 连接前基线：%u 个渲染端点\n", static_cast<unsigned>(baselineIds.size()));

        auto connectedName = ConnectAnyDevice(devices);
        if (connectedName.empty())
        {
            wprintf(L"[结论] 所有设备均无法建立 A2DP 连接，验证终止。\n");
            wprintf(L"        请确认手机已解锁亮屏、在范围内、未连其它蓝牙音频设备。\n");
            return 4;
        }
        wprintf(L"\n[OK] 已连接设备: %s\n", connectedName.c_str());

        wprintf(L"\n[4/5] 连接建立后轮询渲染端点...\n");
        auto added = PollForNewEndpoints(enumerator, baselineIds, 40);

        if (added.empty())
        {
            wprintf(L"\n[结论] 连接已建立且音频可流过，但 %d 秒内没有出现任何蓝牙渲染端点。\n", 40);
            wprintf(L"        → A2DP Sink 端点未暴露给 Core Audio，音量控制方案不可行。\n");
            wprintf(L"[5/5] 跳过（无可关联端点）\n");
            return 3;
        }

        for (const auto& e : added)
        {
            wprintf(L"[KEY] 发现新增端点: %s\n       Id: %s\n",
                e.friendlyName.c_str(), e.id.c_str());
        }

        wprintf(L"\n[5/5] 对新增端点验证音量读写...\n");
        wil::com_ptr<IMMDevice> device = FindDevice(enumerator, added.front().id);
        if (!device)
        {
            wprintf(L"[结论] 无法取到新增端点的 IMMDevice。\n");
            return 5;
        }

        wil::com_ptr<IAudioEndpointVolume> volume;
        hr = device->Activate(__uuidof(IAudioEndpointVolume), CLSCTX_ALL, nullptr,
            reinterpret_cast<void**>(volume.put()));
        if (FAILED(hr))
        {
            wprintf(L"[FAIL] 激活 IAudioEndpointVolume 失败: 0x%08X\n", static_cast<uint32_t>(hr));
            wprintf(L"[结论] 该端点不支持音量控制。\n");
            return 5;
        }

        float originalVolume = 0.0f;
        bool volumeRead = ReadMasterVolume(volume, originalVolume);

        bool muted = false;
        ReadMute(volume, muted);

        bool writeOk = false;
        if (volumeRead)
        {
            writeOk = WriteMasterVolume(volume, 0.5f);
        }

        if (writeOk && volumeRead)
        {
            WriteMasterVolume(volume, originalVolume);
        }

        wprintf(L"\n[结论] 音量可读=%s 可写=%s\n",
            volumeRead ? L"是" : L"否", writeOk ? L"是" : L"否");
        return volumeRead && writeOk ? 0 : 5;
    }
    wprintf(L"[OK]   %u 台设备成功关联到音频端点\n", static_cast<unsigned>(endpointIds.size()));

    return 0;
}