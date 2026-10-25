#include "pch.h"
#include "DiagnosticPrivacy.h"
#include "StringUtil.h"
#include "AudioBule.Version.h"
#include <appmodel.h>
#include <bcrypt.h>
#include <filesystem>
#include <stdexcept>

#pragma comment(lib, "bcrypt.lib")

namespace AudioBule::Core::Detail
{
namespace
{
constexpr EventDefinition kEvents[] = {
    {"app.session_started", L"应用会话已启动", "app"},
    {"app.initialization_completed", L"应用初始化完成", "app"},
    {"app.unhandled_exception", L"发生未处理异常", "app"},
    {"app.previous_session_unclean", L"上次会话未完整结束", "app"},
    {"app.shutdown_requested", L"已请求退出应用", "app"},
    {"app.shutdown_completed", L"业务资源清理完成", "app"},
    {"device.support_probe_failed", L"系统支持性探测失败", "device"},
    {"device.enumerate_completed", L"设备枚举已结束", "device"},
    {"connection.requested", L"已接受连接请求", "connection"},
    {"connection.completed", L"连接操作已结束", "connection"},
    {"connection.request_ignored", L"已忽略重复或无效请求", "connection"},
    {"connection.cancel_requested", L"已撤销界面连接请求，等待底层清理", "connection"},
    {"connection.late_result", L"已丢弃迟到的连接结果", "connection"},
    {"connection.cleanup_completed", L"迟到连接清理已结束", "connection"},
    {"connection.disconnect_completed", L"断开操作已结束", "connection"},
    {"connection.closed_observed", L"观察到系统连接关闭，未推断外部原因", "connection"},
    {"provider.stage", L"底层连接阶段结果", "provider"},
    {"settings.missing", L"首次启动或配置文件尚未创建", "settings"},
    {"settings.loaded", L"配置读取完成", "settings"},
    {"settings.invalid", L"配置无效，已回退默认值", "settings"},
    {"settings.saved", L"配置保存完成", "settings"},
    {"settings.failed", L"配置读写失败", "settings"},
    {"desktop.startup_completed", L"启动项操作已完成", "desktop"},
    {"desktop.startup_failed", L"启动项操作失败或被系统拒绝", "desktop"},
    {"desktop.notifications_unavailable", L"系统通知不可用", "desktop"},
    {"desktop.notification_failed", L"连接通知发送失败", "desktop"},
    {"desktop.notification_cleanup_failed", L"通知服务注销失败", "desktop"},
    {"tray.ready", L"托盘初始化完成", "tray"},
    {"tray.failed", L"托盘初始化失败", "tray"},
    {"tray.message_failed", L"托盘消息或操作失败", "tray"},
    {"tray.restored", L"托盘图标已恢复", "tray"},
    {"window.icon_fallback", L"窗口图标回退到嵌入资源", "window"},
    {"window.exit_dialog_failed", L"退出确认无法显示", "window"},
    {"ui.resource_missing", L"界面文字资源缺失", "ui"},
    {"audio_identity.changed", L"音频会话标识匹配或恢复结果变化", "audio_identity"},
    {"audio_identity.failed", L"音频会话外观更新或恢复失败", "audio_identity"},
    {"desktop.bluetooth_settings_failed", L"无法打开系统蓝牙设置", "desktop"},
    {"app.refresh_failed", L"设备刷新流程异常", "app"},
    {"app.operation_failed", L"界面设备操作流程异常", "app"},
    {"diagnostics.events_dropped", L"部分诊断事件未能保留", "diagnostics"},
    {"diagnostics.storage_recovered", L"日志存储已恢复", "diagnostics"},
    {"diagnostics.detailed_enabled", L"已临时开启详细日志", "diagnostics"},
    {"diagnostics.detailed_disabled", L"详细日志已关闭或到期", "diagnostics"},
    {"diagnostics.export_completed", L"诊断导出已结束", "diagnostics"},
    {"diagnostics.events_suppressed", L"重复环境告警已聚合，状态编号对应原始事件", "diagnostics"},
    {"connection.reconnect_requested", L"已接受手动重新连接请求", "connection"},
    {"provider.state_synchronized", L"原生连接状态同步已结束", "provider"}
};
static_assert(std::size(kEvents) == static_cast<size_t>(LogEvent::Count));
}
EventDefinition const& Definition(LogEvent event) noexcept
{
    auto index = static_cast<size_t>(event);
    return kEvents[index < std::size(kEvents) ? index : 0];
}
char const* LevelName(LogLevel value) noexcept
{
    constexpr char const* names[] = {"debug", "info", "warning", "error", "critical"};
    auto i = static_cast<size_t>(value); return i < std::size(names) ? names[i] : "info";
}
char const* TriggerName(LogTrigger value) noexcept
{
    constexpr char const* names[] = {"none", "manual", "startup", "system"};
    auto i = static_cast<size_t>(value); return i < std::size(names) ? names[i] : "none";
}
char const* StageName(LogStage value) noexcept
{
    constexpr char const* names[] = {"none", "initialize", "enumerate", "create", "start", "open", "close", "cleanup", "read", "parse", "write", "replace", "restore"};
    auto i = static_cast<size_t>(value); return i < std::size(names) ? names[i] : "none";
}
char const* OutcomeName(LogOutcome value) noexcept
{
    constexpr char const* names[] = {"none", "succeeded", "failed", "cancelled", "ignored", "empty", "unsupported"};
    auto i = static_cast<size_t>(value); return i < std::size(names) ? names[i] : "none";
}
std::string JsonQuote(std::string_view value)
{
    std::string result = "\"";
    constexpr char hex[] = "0123456789abcdef";
    for (unsigned char c : value)
    {
        if (c == '"' || c == '\\') { result += '\\'; result += static_cast<char>(c); }
        else if (c < 32) { result += "\\u00"; result += hex[c >> 4]; result += hex[c & 15]; }
        else result += static_cast<char>(c);
    }
    return result + '"';
}
std::string HexCode(uint32_t value)
{
    char text[11]{}; sprintf_s(text, "0x%08X", value); return text;
}
std::string UtcTimestamp()
{
    SYSTEMTIME time{}; ::GetSystemTime(&time);
    char text[32]{};
    sprintf_s(text, "%04u-%02u-%02uT%02u:%02u:%02u.%03uZ", time.wYear, time.wMonth,
        time.wDay, time.wHour, time.wMinute, time.wSecond, time.wMilliseconds);
    return text;
}
std::string RandomHex(size_t bytes)
{
    if (bytes > 32) throw std::invalid_argument("随机标识长度超出范围");
    std::array<unsigned char, 32> buffer{};
    if (::BCryptGenRandom(nullptr, buffer.data(), static_cast<ULONG>(bytes), BCRYPT_USE_SYSTEM_PREFERRED_RNG) < 0)
        throw std::runtime_error("系统随机源不可用");
    constexpr char hex[] = "0123456789abcdef";
    std::string result;
    for (size_t i = 0; i < bytes; ++i) { result += hex[buffer[i] >> 4]; result += hex[buffer[i] & 15]; }
    ::SecureZeroMemory(buffer.data(), buffer.size());
    return result;
}
std::string RuntimeInfoJson()
{
#if defined(_M_ARM64)
    constexpr char architecture[] = "ARM64";
#else
    constexpr char architecture[] = "x64";
#endif
#if defined(_DEBUG)
    constexpr char configuration[] = "Debug";
#else
    constexpr char configuration[] = "Release";
#endif
    // 仅记录系统版本数字，不读取机器名、用户标识或安装路径。
    OSVERSIONINFOW version{}; version.dwOSVersionInfoSize = sizeof(version);
    using VersionFunction = LONG (WINAPI*)(OSVERSIONINFOW*);
    VersionFunction query = nullptr;
    auto address = ::GetProcAddress(::GetModuleHandleW(L"ntdll.dll"), "RtlGetVersion");
    static_assert(sizeof(query) == sizeof(address));
    memcpy(&query, &address, sizeof(query));
    if (query) query(&version);
    UINT32 length = 0;
    bool packaged = ::GetCurrentPackageFullName(&length, nullptr) == ERROR_INSUFFICIENT_BUFFER;
    return ",\"app_version\":" + JsonQuote(AUDIOBULE_VERSION) + ",\"architecture\":" + JsonQuote(architecture) +
        ",\"configuration\":" + JsonQuote(configuration) + ",\"os_version\":" +
        JsonQuote(std::to_string(version.dwMajorVersion) + "." + std::to_string(version.dwMinorVersion) + "." + std::to_string(version.dwBuildNumber)) +
        ",\"packaged\":" + (packaged ? "true" : "false");
}
bool SafeDirectory(std::wstring const& path) noexcept
{
    try
    {
        auto current = std::filesystem::path(path);
        if (!current.is_absolute()) return false;
        current = current.lexically_normal();
        for (;;)
        {
            DWORD attributes = ::GetFileAttributesW(current.c_str());
            if (attributes != INVALID_FILE_ATTRIBUTES && ((attributes & FILE_ATTRIBUTE_REPARSE_POINT) || !(attributes & FILE_ATTRIBUTE_DIRECTORY))) return false;
            auto parent = current.parent_path();
            if (parent == current || parent.empty()) break;
            current = std::move(parent);
        }
        return true;
    }
    catch (...) { return false; }
}
}
