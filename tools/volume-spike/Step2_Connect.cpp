#include "pch.h"
#include "Step2_Connect.h"

using namespace winrt::Windows::Media::Audio;

bool ConnectDevice(const A2dpDeviceInfo& device, AudioPlaybackConnection& outConnection)
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
        wprintf(L"[INFO] OpenAsync 状态枚举值: %d\n", static_cast<int>(openResult.Status()));
        wprintf(L"[INFO] 连接对象当前 State: %d\n", static_cast<int>(connection.State()));

        if (openResult.Status() != AudioPlaybackConnectionOpenResultStatus::Success)
        {
            auto ext = openResult.ExtendedError();
            wprintf(L"[FAIL] 连接未建立，扩展错误码 0x%08X\n", static_cast<uint32_t>(ext));

            switch (ext)
            {
            case 0x8007001F:
                wprintf(L"[HINT] 0x8007001F = ERROR_GEN_FAILURE。常见原因：\n");
                wprintf(L"       · 手机正作为 A2DP 源连接其它设备（耳机/车机），无法同时做接收端\n");
                wprintf(L"       · 手机未处于可接受连接的状态（息屏/锁屏）\n");
                wprintf(L"       · 手机蓝牙关闭或超出范围\n");
                break;
            default:
                break;
            }
            return false;
        }

        wprintf(L"[OK]   OpenAsync 成功: %s\n", device.name.c_str());
        outConnection = connection;
        wprintf(L"       请检查手机蓝牙音频输出列表，此时应出现「这台电脑」。\n");
        return true;
    }
    catch (winrt::hresult_error const& e)
    {
        wprintf(L"[FAIL] 建立连接时抛出异常: %s (0x%08X)\n",
            e.message().c_str(), static_cast<uint32_t>(e.code()));
        return false;
    }
}

std::wstring ConnectAnyDevice(const std::vector<A2dpDeviceInfo>& devices,
    AudioPlaybackConnection& outConnection)
{
    for (const auto& device : devices)
    {
        wprintf(L"\n[TRY] 尝试连接: %s\n", device.name.c_str());
        if (ConnectDevice(device, outConnection))
        {
            return device.name;
        }
    }
    return {};
}

void ConnectionStateWatcher::Attach(const AudioPlaybackConnection& connection)
{
    connection_ = connection;
    state_ = static_cast<int>(connection.State());

    token_ = connection.StateChanged([this](const AudioPlaybackConnection& sender, const auto&)
    {
        auto newState = static_cast<int>(sender.State());
        auto old = state_;
        state_ = newState;
        if (newState == 2) { sawConnected_ = true; }

        wprintf(L"       >>> 状态变化: %d -> %d\n", old, newState);
    });
}

ConnectionStateWatcher::~ConnectionStateWatcher()
{
    if (connection_ && token_)
    {
        connection_.StateChanged(token_);
    }
}