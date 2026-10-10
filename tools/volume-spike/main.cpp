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

        AudioPlaybackConnection connection{ nullptr };
        auto connectedName = ConnectAnyDevice(devices, connection);
        if (connectedName.empty())
        {
            wprintf(L"[结论] 所有设备均无法建立 A2DP 连接，验证终止。\n");
            wprintf(L"        请确认手机已解锁亮屏、在范围内、未连其它蓝牙音频设备。\n");
            return 4;
        }
        wprintf(L"\n[OK] OpenAsync 成功设备: %s\n", connectedName.c_str());

        ConnectionStateWatcher watcher;
        watcher.Attach(connection);
        wprintf(L"[INFO] 订阅状态变化，初始状态 = %d（0=Closed 1=Connecting 2=Connected）\n",
            watcher.CurrentState());
        wprintf(L"       >>> 现在打开手机蓝牙音频输出列表，检查是否出现「这台电脑」。\n");
        wprintf(L"       >>> 只有连接状态变为 2(Connected) 时才会出现。\n");

        wprintf(L"\n[4/5] 确认音频确实在流，并同时观察是否出现新端点...\n");

        // 为每个渲染端点建峰值表 —— 音频可能不流到默认端点，
        // 只采样默认端点会漏判
        std::vector<std::unique_ptr<PeakMeter>> meters;
        for (const auto& id : baselineIds)
        {
            auto meter = PeakMeter::Create(id, enumerator);
            if (meter)
            {
                wprintf(L"[INFO] 峰值表: %s\n", meter->Name().c_str());
                meters.push_back(std::move(meter));
            }
        }
        if (meters.empty())
        {
            wprintf(L"[FAIL] 无法获取任何端点的峰值表，测试无法自证。\n");
            return 6;
        }

        wprintf(L"\n[INFO] %u 个峰值表就绪，开始 90 秒采样。\n", static_cast<unsigned>(meters.size()));
        wprintf(L"       >>> 请在小米 15 上把蓝牙音频输出切到这台电脑，然后播放音乐。\n");
        wprintf(L"       >>> 程序会自行检测音量峰值来确认音频真的在流，无需人工判断。\n");
        wprintf(L"       连接状态 = %d\n", watcher.CurrentState());

        std::vector<RenderEndpointInfo> added;
        bool audioFlowing = false;
        std::wstring flowingEndpoint;

        for (int i = 1; i <= 90; ++i)
        {
            Sleep(1000);

            std::wstring line = L"";
            for (const auto& meter : meters)
            {
                float peak = meter->Sample();
                if (peak > 0.01f)
                {
                    audioFlowing = true;
                    flowingEndpoint = meter->Name();
                }

                wchar_t buf[64];
                swprintf_s(buf, L"[%.3f]", peak);
                line += buf;
                line += meter->Name();
                line += L"  ";
            }

            wprintf(L"       t=%2ds  %s%s\n", i, line.c_str(),
                audioFlowing ? L"<== 音频在流!" : L"");

            if (audioFlowing)
            {
                auto current = ListRenderEndpointsQuiet(enumerator);
                for (const auto& endpoint : current)
                {
                    bool existed = false;
                    for (const auto& id : baselineIds)
                    {
                        if (id == endpoint.id) { existed = true; break; }
                    }
                    if (!existed)
                    {
                        added.push_back(endpoint);
                        wprintf(L"       >>> 发现新增端点: %s\n", endpoint.friendlyName.c_str());
                    }
                }
            }

            if (audioFlowing && !added.empty())
            {
                break;
            }
        }

        wprintf(L"\n[自证] 连接状态 = %d（2=Connected）, 音频在流 = %s",
            watcher.CurrentState(), audioFlowing ? L"是" : L"否");
        if (audioFlowing)
        {
            wprintf(L"（端点: %s）", flowingEndpoint.c_str());
        }
        wprintf(L"\n");

        if (!audioFlowing)
        {
            wprintf(L"\n[结论] 90 秒内没有任何端点出现音频活动（峰值恒为 0）。\n");
            if (watcher.CurrentState() != 2)
            {
                wprintf(L"        根因：连接状态停留在 %d，从未变为 2(Connected)。\n",
                    watcher.CurrentState());
                wprintf(L"        → PC 根本没有对外宣告自己是 A2DP 接收端，手机输出列表里\n");
                wprintf(L"          自然看不到它，A2DP 流无从建立。\n");
                wprintf(L"        → 本次测试无效，不能对音量方案下结论。\n");
            }
            else
            {
                wprintf(L"        连接已建立(状态=2)但仍无音频，需排查音频路由。\n");
            }
            return 6;
        }

        if (added.empty())
        {
            wprintf(L"\n[结论] 音频确实在流（端点: %s），但没有出现任何蓝牙渲染端点。\n",
                flowingEndpoint.c_str());
            wprintf(L"        → A2DP Sink 端点未暴露给 Core Audio，音量控制方案不可行。\n");
            wprintf(L"[5/5] 跳过（无可关联端点）\n");
            return 3;
        }

        wprintf(L"\n[结论] 音频在流且出现了蓝牙端点 → 方案可行，继续验证音量读写。\n");

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