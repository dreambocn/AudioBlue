#pragma once
#include <windows.h>
#include <array>
#include <chrono>
#include <cstdint>
#include <memory>
#include <string>

namespace AudioBule::Core
{
enum class LogLevel { Debug, Info, Warning, Error, Critical };
enum class LogTrigger { None, Manual, Startup, System };
enum class LogStage { None, Initialize, Enumerate, Create, Start, Open, Close, Cleanup, Read, Parse, Write, Replace, Restore };
enum class LogOutcome { None, Succeeded, Failed, Cancelled, Ignored, Empty, Unsupported };
enum class LogEvent
{
    SessionStarted, InitializationCompleted, UnhandledException, PreviousSessionUnclean,
    ShutdownRequested, ShutdownCompleted, SupportProbeFailed, EnumerateCompleted,
    ConnectRequested, ConnectCompleted, RequestIgnored, CancelRequested, LateResult,
    CleanupCompleted, DisconnectCompleted, ConnectionClosed, ProviderStage,
    SettingsMissing, SettingsLoaded, SettingsInvalid, SettingsSaved, SettingsFailed,
    StartupCompleted, StartupFailed, NotificationsUnavailable, NotificationFailed,
    NotificationCleanupFailed, TrayReady, TrayFailed, TrayMessageFailed, TrayRestored,
    WindowIconFallback, ExitDialogFailed, ResourceMissing, AudioIdentityChanged,
    AudioIdentityFailed, BluetoothSettingsFailed, RefreshFailed, OperationFailed,
    EventsDropped, StorageRecovered, DetailedEnabled, DetailedDisabled, ExportCompleted, EventsSuppressed,
    Count
};

// 字段只接受枚举和数字，不能意外提交设备名、异常正文或用户路径。
struct LogFields
{
    LogStage stage = LogStage::None;
    LogOutcome outcome = LogOutcome::None;
    HRESULT hresult = 0;
    DWORD win32Error = 0;
    int64_t count = 0;
    int32_t failure = 0;
    int32_t status = 0;
    int32_t stateBefore = -1;
    int32_t stateAfter = -1;
};

struct LogStatus
{
    bool ready = false, available = false, stopped = false, detailed = false;
    uint64_t accepted = 0, written = 0, dropped = 0, filtered = 0, rejected = 0, writeFailures = 0;
    std::array<uint64_t, 5> droppedByLevel{};
    size_t queued = 0, queuedBytes = 0;
    DWORD lastError = 0;
    uint32_t detailedSeconds = 0;
};

namespace Detail { struct LogState; class LogIo; }
struct LoggerOptions
{
    std::wstring root;
    size_t maxRecords = 2048, maxQueueBytes = 4 * 1024 * 1024;
    size_t reservedRecords = 256, reservedBytes = 512 * 1024;
    size_t maxFileBytes = 4 * 1024 * 1024, maxFiles = 5;
    size_t maxRootBytes = 100 * 1024 * 1024;
    uint32_t retentionDays = 7;
    bool debugMirror = false;
    // 内部故障注入接缝；正常调用方保持为空，使用系统文件适配器。
    std::shared_ptr<Detail::LogIo> io;
};
}
