#pragma once

// 本头文件的接口用到 HRESULT，因此必须自包含 windows.h ——
// 否则每个包含它的 TU 都要自己记得先包含 windows.h。
#include <windows.h>

#include <string>

namespace AudioBule::Core
{

// 连接的四个状态。注意 Connecting 之后只有两个出口：Connected 或 Failed。
// 没有「取消中」—— 取消语义由断开后在 Disconnected 状态下重建条目承担。
enum class ConnectionState
{
    Disconnected,
    Connecting,
    Connected,
    Failed,
};

// 连接失败的归类。生产实现在 OpenAsync 的 Status + ExtendedError 上做映射，
// 测试实现直接指定。
enum class ConnectFailure
{
    None,
    DeviceNotSupported,   // TryCreateFromId 返回 null
    RequestTimedOut,      // AudioPlaybackConnectionOpenResultStatus::RequestTimedOut
    DeniedBySystem,       // AudioPlaybackConnectionOpenResultStatus::DeniedBySystem
    GenericFailure,       // ExtendedError 落在已知可诊断的码上（如 0x8007001F）
    UnknownFailure,       // 其余 Status
    HresultError,         // 抛 winrt::hresult_error
    DeviceNotFound,       // 刷新后设备消失
};

struct ConnectResult
{
    bool succeeded = false;
    ConnectFailure failure = ConnectFailure::None;
    HRESULT extendedError = 0;   // 仅失败时有意义
};

struct DeviceInfo
{
    std::wstring id;
    std::wstring name;
};

struct ConnectionEntry
{
    std::wstring deviceId;
    std::wstring displayName;
    ConnectionState state = ConnectionState::Disconnected;

    // 仅 state == Failed 时有效。连上后必须清空。
    std::wstring errorMessage;
};

} // namespace AudioBule::Core