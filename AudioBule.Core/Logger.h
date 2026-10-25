#pragma once
#include "DiagnosticsTypes.h"
#include <string_view>
#include <vector>

namespace AudioBule::Core
{
struct LogSnapshotFile
{
    // 持有不允许删除共享的读句柄，轮转和历史清理不能删除快照文件。
    std::shared_ptr<void> handle;
    uint64_t bytes = 0;
};
struct LogSnapshot
{
    std::vector<LogSnapshotFile> files;
    std::vector<std::string> memoryTail;
    LogStatus status;
    std::string sessionId;
    bool incomplete = true;
};

// 上下文按值跨线程传递，停止后仍可安全使用，不引用任何业务对象。
class LogContext
{
public:
    LogContext() = default;
    LogContext Operation(LogTrigger trigger = LogTrigger::System, std::wstring_view deviceId = {}) const noexcept;
    LogContext WithDevice(std::wstring_view deviceId) const noexcept;
    bool Write(LogEvent event, LogFields fields = {}, LogLevel level = LogLevel::Info) const noexcept;
    uint64_t OperationId() const noexcept { return m_operation; }
private:
    friend class Logger;
    std::shared_ptr<Detail::LogState> m_state;
    uint64_t m_operation = 0, m_related = 0, m_started = 0;
    LogTrigger m_trigger = LogTrigger::None;
    std::array<char, 33> m_device{};
};

class Logger final
{
public:
    explicit Logger(LoggerOptions options = {}) noexcept;
    ~Logger();
    Logger(Logger const&) = delete;
    Logger& operator=(Logger const&) = delete;
    LogContext Context() const noexcept;
    LogStatus Status() const noexcept;
    std::wstring Root() const;
    void SetDetailed(bool enabled, std::chrono::seconds duration = std::chrono::minutes(15)) noexcept;
    LogSnapshot Snapshot(std::chrono::milliseconds timeout = std::chrono::seconds(2)) const noexcept;
    bool Stop(std::chrono::milliseconds timeout = std::chrono::seconds(2), bool clean = true) noexcept;
    static std::wstring DefaultRoot();
private:
    std::shared_ptr<Detail::LogState> m_state;
};
}
