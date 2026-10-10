#include "pch.h"
#include "Step2_Connect.h"

using namespace winrt::Windows::Media::Audio;

bool ConnectFirstDevice(const A2dpDeviceInfo& device)
{
    AudioPlaybackConnection connection = nullptr;
    try
    {
        connection = AudioPlaybackConnection::TryCreateFromId(device.id);
    }
    catch (winrt::hresult_error const& e)
    {
        wprintf(L"[FAIL] TryCreateFromId 抛出异常: %s (0x%08X)\n",
            e.message().c_str(), static_cast<uint32_t>(e.code()));
        return false;
    }

    if (!connection)
    {
        wprintf(L"[FAIL] TryCreateFromId 返回 null —— 该设备不支持 A2DP Sink\n");
        return false;
    }

    try
    {
        // StartAsync 返回 void，无结果值可查
        connection.StartAsync().get();

        auto openResult = connection.OpenAsync().get();
        wprintf(L"[INFO] OpenAsync 结果: %s\n",
            openResult.Status() == AudioPlaybackConnectionOpenResultStatus::Success ? L"Success" : L"失败");

        if (openResult.Status() != AudioPlaybackConnectionOpenResultStatus::Success)
        {
            wprintf(L"[FAIL] 连接未建立，扩展错误码 0x%08X\n",
                static_cast<uint32_t>(openResult.ExtendedError()));
            return false;
        }

        wprintf(L"[OK]   已连接: %s\n", device.name.c_str());
        wprintf(L"       请在手机上开始播放音频，然后继续。\n");
        return true;
    }
    catch (winrt::hresult_error const& e)
    {
        wprintf(L"[FAIL] 建立连接时抛出异常: %s (0x%08X)\n",
            e.message().c_str(), static_cast<uint32_t>(e.code()));
        return false;
    }
}