#pragma once
#include "Logger.h"
#include <bcrypt.h>
#include <atomic>
#include <condition_variable>
#include <deque>
#include <future>
#include <mutex>

namespace AudioBule::Core::Detail
{
// 真实文件与故障适配器共享同一个写入接缝，测试不需要填满磁盘。
class LogIo
{
public:
    virtual ~LogIo() = default;
    virtual DWORD Write(HANDLE file, std::string_view text) noexcept = 0;
    virtual DWORD Flush(HANDLE file) noexcept = 0;
};
struct LogRecord
{
    LogEvent event{};
    LogFields fields;
    LogLevel level{};
    LogTrigger trigger{};
    uint64_t sequence = 0, elapsed = 0, duration = 0, operation = 0, related = 0;
    DWORD tid = 0;
    FILETIME time{};
    std::array<char, 33> device{};
};
struct LogState
{
    LoggerOptions options;
    std::string session;
    std::array<unsigned char, 32> key{};
    BCRYPT_ALG_HANDLE algorithm = nullptr;
    std::mutex mutex;
    std::condition_variable changed, finished;
    std::deque<LogRecord> records;
    struct Repetition { uint64_t last = 0, count = 0; HRESULT code = 0; };
    std::array<Repetition, static_cast<size_t>(LogEvent::Count)> repetitions{};
    LogStatus status;
    std::atomic<uint64_t> operation{0}, detailedUntil{0};
    uint64_t started = ::GetTickCount64(), sequence = 0, snapshotTarget = 0;
    bool stopping = false, clean = false, abandoned = false;
    std::shared_ptr<std::promise<LogSnapshot>> snapshot;
    // 调用方持有 mutex；集中维护总数和按等级分布，防止统计不一致。
    void Drop(LogLevel level) noexcept { ++status.dropped; ++status.droppedByLevel[static_cast<size_t>(level)]; }
    ~LogState();
};
void RunWriter(std::shared_ptr<LogState> state) noexcept;
std::string Serialize(LogRecord const& record, std::string const& session);
}
