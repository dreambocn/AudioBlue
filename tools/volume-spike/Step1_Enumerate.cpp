#include "pch.h"
#include "Step1_Enumerate.h"

using namespace winrt::Windows::Devices::Enumeration;
using namespace winrt::Windows::Foundation::Metadata;
using namespace winrt::Windows::Media::Audio;

bool IsA2dpSinkSupported()
{
    try
    {
        return ApiInformation::IsTypePresent(winrt::name_of<AudioPlaybackConnection>());
    }
    catch (winrt::hresult_error const&)
    {
        return false;
    }
}

std::vector<A2dpDeviceInfo> EnumerateA2dpDevices()
{
    std::vector<A2dpDeviceInfo> result;

    if (!IsA2dpSinkSupported())
    {
        wprintf(L"[SKIP] 系统不支持 A2DP Sink（需要 Windows 10 2004 / build 19041 及以上）\n");
        return result;
    }

    auto selector = AudioPlaybackConnection::GetDeviceSelector();

    DeviceInformationCollection devices = nullptr;
    try
    {
        // 同步阻塞等待 —— Spike 是控制台程序，阻塞可接受且避免协程复杂度
        devices = DeviceInformation::FindAllAsync(selector).get();
    }
    catch (winrt::hresult_error const& e)
    {
        wprintf(L"[FAIL] 枚举设备失败: %s (0x%08X)\n",
            e.message().c_str(), static_cast<uint32_t>(e.code()));
        return result;
    }

    if (devices.Size() == 0)
    {
        wprintf(L"[INFO] 未找到已配对的 A2DP 设备。请先在系统设置中配对蓝牙设备。\n");
        return result;
    }

    for (const auto& device : devices)
    {
        A2dpDeviceInfo info;
        info.id = std::wstring(device.Id());
        info.name = device.Name().empty() ? L"(未命名)" : std::wstring(device.Name());
        wprintf(L"[OK]   设备: %s\n       Id : %s\n", info.name.c_str(), info.id.c_str());
        result.push_back(std::move(info));
    }

    wprintf(L"[OK] 共枚举到 %zu 台设备\n", result.size());
    return result;
}