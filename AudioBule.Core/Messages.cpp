#include "pch.h"
#include "Messages.h"
#include "StringUtil.h"

namespace AudioBule::Core
{

std::wstring MessageForConnectFailure(ConnectFailure failure, HRESULT extendedError)
{
    switch (failure)
    {
    case ConnectFailure::DeviceNotSupported:
        return L"此设备不支持 A2DP 音频接收";

    case ConnectFailure::RequestTimedOut:
        return L"连接请求超时。请确认设备已开机且在附近，然后重试。";

    case ConnectFailure::DeniedBySystem:
        return L"连接被系统拒绝。请在「设置 - 蓝牙和设备」中检查设备状态。";

    case ConnectFailure::GenericFailure:
        // 0x8007001F = ERROR_GEN_FAILURE。实测中这个码几乎总是同一个原因：
        // 手机正作为 A2DP 源连着别的设备（耳机/车机），无法同时当接收端。
        // 不加这个针对性提示，用户只会看到一句没头没尾的「失败」。
        if (static_cast<DWORD>(extendedError) == 0x8007001Fu)
        {
            return L"设备当前无法作为蓝牙音频接收端（0x8007001F）。"
                   L"请先断开手机上已连接的其它蓝牙音频设备（如耳机、车机），再重试。";
        }
        return L"连接失败（" + FormatWin32Error(static_cast<DWORD>(extendedError)) + L"）。";

    case ConnectFailure::UnknownFailure:
        return L"连接失败（" + FormatWin32Error(static_cast<DWORD>(extendedError)) + L"）。";

    case ConnectFailure::HresultError:
        return L"连接时发生错误（" + FormatWin32Error(static_cast<DWORD>(extendedError)) + L"）。";

    case ConnectFailure::DeviceNotFound:
        return L"设备已不可用。点击「刷新」重新扫描。";

    case ConnectFailure::None:
    default:
        return L"未知错误";
    }
}

} // namespace AudioBule::Core