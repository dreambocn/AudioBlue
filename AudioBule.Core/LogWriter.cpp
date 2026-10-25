#include "pch.h"
#include "LogWriter.h"
#include "DiagnosticPrivacy.h"
#include "StringUtil.h"
#include "AudioBule.Version.h"
#include <filesystem>
#include <map>
#include <thread>

namespace AudioBule::Core::Detail
{
namespace fs = std::filesystem;
namespace
{
class SystemLogIo final : public LogIo
{
public:
    DWORD Write(HANDLE file, std::string_view text) noexcept override
    {
        DWORD written = 0;
        if (!::WriteFile(file, text.data(), static_cast<DWORD>(text.size()), &written, nullptr)) return ::GetLastError();
        return written == text.size() ? ERROR_SUCCESS : ERROR_WRITE_FAULT;
    }
    DWORD Flush(HANDLE file) noexcept override { return ::FlushFileBuffers(file) ? ERROR_SUCCESS : ::GetLastError(); }
};
std::shared_ptr<void> Own(HANDLE handle)
{
    if (handle == INVALID_HANDLE_VALUE || !handle) return {};
    return {handle, [](void* value) { ::CloseHandle(value); }};
}
bool SessionName(std::wstring const& value)
{
    return value.size() == 32 && std::all_of(value.begin(), value.end(), [](wchar_t c) { return (c >= L'0' && c <= L'9') || (c >= L'a' && c <= L'f'); });
}
bool SegmentName(std::wstring const& value)
{
    return value.size() == 14 && value.substr(8) == L".jsonl" &&
        std::all_of(value.begin(), value.begin() + 8, [](wchar_t c) { return c >= L'0' && c <= L'9'; });
}
std::vector<fs::path> Segments(fs::path const& directory)
{
    std::vector<fs::path> paths;
    if (!SafeDirectory(directory.wstring())) return paths;
    std::error_code ec;
    size_t examined = 0;
    for (fs::directory_iterator it(directory, ec), end; !ec && it != end && examined++ < 64; it.increment(ec))
    {
        if (!SegmentName(it->path().filename().wstring())) continue;
        auto attributes = ::GetFileAttributesW(it->path().c_str());
        if (attributes != INVALID_FILE_ATTRIBUTES && !(attributes & (FILE_ATTRIBUTE_DIRECTORY | FILE_ATTRIBUTE_REPARSE_POINT))) paths.push_back(it->path());
    }
    std::sort(paths.begin(), paths.end()); return paths;
}
uint64_t FileBytes(HANDLE file)
{
    LARGE_INTEGER size{}; return ::GetFileSizeEx(file, &size) && size.QuadPart >= 0 ? static_cast<uint64_t>(size.QuadPart) : 0;
}
LogSnapshotFile Pin(fs::path const& path)
{
    // OPEN_REPARSE_POINT 后再次检查句柄属性，拒绝链接文件。
    auto handle = Own(::CreateFileW(path.c_str(), GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, nullptr,
        OPEN_EXISTING, FILE_FLAG_OPEN_REPARSE_POINT | FILE_FLAG_SEQUENTIAL_SCAN, nullptr));
    BY_HANDLE_FILE_INFORMATION info{};
    if (!handle || !::GetFileInformationByHandle(handle.get(), &info) || (info.dwFileAttributes & FILE_ATTRIBUTE_REPARSE_POINT)) return {};
    return {handle, FileBytes(handle.get())};
}
struct History { fs::path path; fs::file_time_type modified; uint64_t bytes; };
std::vector<History> InactiveSessions(fs::path const& root, std::string const& current)
{
    std::vector<History> result;
    std::error_code ec;
    size_t examined = 0;
    for (fs::directory_iterator it(root, ec), end; !ec && it != end && examined++ < 1024; it.increment(ec))
    {
        auto name = it->path().filename().wstring();
        if (!SessionName(name) || name == Utf8ToWide(current) || !SafeDirectory(it->path().wstring())) continue;
        auto active = Own(::CreateFileW((it->path() / L"active").c_str(), GENERIC_READ, 0, nullptr, OPEN_EXISTING, FILE_FLAG_OPEN_REPARSE_POINT, nullptr));
        if (!active) continue;
        uint64_t bytes = 0;
        for (auto const& path : Segments(it->path())) { auto size = fs::file_size(path, ec); if (!ec) bytes += size; ec.clear(); }
        auto modified = fs::last_write_time(it->path(), ec);
        if (!ec) result.push_back({it->path(), modified, bytes});
        ec.clear();
    }
    std::sort(result.begin(), result.end(), [](auto const& a, auto const& b) { return a.modified < b.modified; });
    return result;
}
void CleanupHistory(LogState& state, uint64_t& unclean)
{
    auto mutex = Own(::CreateMutexW(nullptr, FALSE, L"Local\\AudioBule.LogRetention"));
    if (!mutex) return;
    auto wait = ::WaitForSingleObject(mutex.get(), 0);
    if (wait != WAIT_OBJECT_0 && wait != WAIT_ABANDONED) return;
    auto release = wil::scope_exit([&] { ::ReleaseMutex(mutex.get()); });
    auto history = InactiveSessions(state.options.root, state.session);
    uint64_t total = 0;
    for (auto const& item : history)
    {
        total += item.bytes;
        if (::GetFileAttributesW((item.path / L"complete").c_str()) == INVALID_FILE_ATTRIBUTES) ++unclean;
    }
    auto expired = fs::file_time_type::clock::now() - std::chrono::hours(24LL * state.options.retentionDays);
    // 为当前会话保留预算；活动会话的总量仅作软限制。
    auto budget = state.options.maxRootBytes > state.options.maxFileBytes * state.options.maxFiles ?
        state.options.maxRootBytes - state.options.maxFileBytes * state.options.maxFiles : 0;
    for (auto const& item : history)
    {
        if (item.modified >= expired && total <= budget) continue;
        bool removed = true;
        for (auto const& path : Segments(item.path)) if (!::DeleteFileW(path.c_str())) removed = false;
        if (!removed) continue;
        // 只处理已知文件，不递归删除目录中的未知用户内容。
        ::DeleteFileW((item.path / L"active").c_str());
        ::DeleteFileW((item.path / L"complete").c_str());
        if (::RemoveDirectoryW(item.path.c_str())) total -= item.bytes;
    }
}
}
LogState::~LogState()
{
    if (algorithm) ::BCryptCloseAlgorithmProvider(algorithm, 0);
    ::SecureZeroMemory(key.data(), key.size());
}
std::string Serialize(LogRecord const& record, std::string const& session)
{
    auto const& definition = Definition(record.event);
    SYSTEMTIME time{}; ::FileTimeToSystemTime(&record.time, &time);
    char timestamp[32]{};
    sprintf_s(timestamp, "%04u-%02u-%02uT%02u:%02u:%02u.%03uZ", time.wYear, time.wMonth,
        time.wDay, time.wHour, time.wMinute, time.wSecond, time.wMilliseconds);
    auto const& fields = record.fields;
    std::string line = "{\"schema_version\":1,\"record_type\":\"log\",\"timestamp_utc\":" + JsonQuote(timestamp) +
        ",\"session_id\":" + JsonQuote(session) + ",\"sequence\":" + std::to_string(record.sequence) +
        ",\"elapsed_ms\":" + std::to_string(record.elapsed) + ",\"duration_ms\":" + std::to_string(record.duration) +
        ",\"pid\":" + std::to_string(::GetCurrentProcessId()) + ",\"tid\":" + std::to_string(record.tid) +
        ",\"level\":" + JsonQuote(LevelName(record.level)) + ",\"module\":" + JsonQuote(definition.module) +
        ",\"event\":" + JsonQuote(definition.name) + ",\"message\":" + JsonQuote(WideToUtf8(definition.message)) +
        ",\"operation_id\":" + std::to_string(record.operation) + ",\"related_operation_id\":" + std::to_string(record.related) +
        ",\"device_token\":" + JsonQuote(record.device.data()) + ",\"trigger\":" + JsonQuote(TriggerName(record.trigger)) +
        ",\"stage\":" + JsonQuote(StageName(fields.stage)) + ",\"outcome\":" + JsonQuote(OutcomeName(fields.outcome)) +
        ",\"hresult\":" + JsonQuote(HexCode(static_cast<uint32_t>(fields.hresult))) + ",\"win32_error\":" + JsonQuote(HexCode(fields.win32Error)) +
        ",\"count\":" + std::to_string(fields.count) + ",\"failure\":" + std::to_string(fields.failure) +
        ",\"status\":" + std::to_string(fields.status) + ",\"state_before\":" + std::to_string(fields.stateBefore) +
        ",\"state_after\":" + std::to_string(fields.stateAfter);
    if (record.event == LogEvent::SessionStarted) line += RuntimeInfoJson();
    return line + "}\n";
}
void RunWriter(std::shared_ptr<LogState> state) noexcept
{
    std::shared_ptr<void> active, file;
    std::deque<LogRecord> tail;
    uint64_t outputSequence = 0;
    LogRecord lastAttempt;
    uint64_t lastSequence = 0, reportedDropped = 0, retryAt = 0, lastFlush = 0;
    size_t bytes = 0, segment = 0, failures = 0;
    fs::path directory;
    std::vector<fs::path> paths;
    std::shared_ptr<LogIo> io;
    auto failure = [&](DWORD error) {
        std::lock_guard lock(state->mutex);
        state->status.available = false; state->status.lastError = error; ++state->status.writeFailures;
        constexpr uint64_t delays[] = {1000, 5000, 30000};
        retryAt = ::GetTickCount64() + delays[std::min(failures++, std::size(delays) - 1)];
    };
    auto openNext = [&]() -> DWORD {
        if (paths.size() >= state->options.maxFiles)
        {
            if (!::DeleteFileW(paths.front().c_str())) return ::GetLastError();
            paths.erase(paths.begin());
        }
        wchar_t name[32]{}; swprintf_s(name, L"%08zu.jsonl", ++segment);
        auto path = directory / name;
        auto next = Own(::CreateFileW(path.c_str(), GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_DELETE, nullptr, CREATE_NEW, FILE_ATTRIBUTE_NORMAL, nullptr));
        if (!next) return ::GetLastError();
        file = std::move(next); bytes = 0; paths.push_back(path); return ERROR_SUCCESS;
    };
    auto append = [&](LogRecord const& record) -> DWORD {
        auto emitted = record; emitted.sequence = ++outputSequence; lastAttempt = emitted;
        auto line = Serialize(emitted, state->session);
        if (line.size() > 4096) return ERROR_BUFFER_OVERFLOW;
        if (!file || bytes + line.size() > state->options.maxFileBytes)
        {
            if (file) { auto error = io->Flush(file.get()); if (error) return error; file.reset(); }
            auto error = openNext(); if (error) return error;
        }
        auto error = io->Write(file.get(), line);
        if (error) { file.reset(); return error; }
        bytes += line.size();
        if (state->options.debugMirror) ::OutputDebugStringW(Utf8ToWide(line).c_str());
        { std::lock_guard lock(state->mutex); ++state->status.written; }
        return ERROR_SUCCESS;
    };
    try
    {
        io = state->options.io ? state->options.io : std::make_shared<SystemLogIo>();
        directory = fs::path(state->options.root) / Utf8ToWide(state->session);
        for (;;)
        {
            bool stopping = false;
            { std::lock_guard lock(state->mutex); stopping = state->stopping; }
            DWORD error = ERROR_SUCCESS;
            if (!active && (::GetTickCount64() >= retryAt || stopping))
            {
                std::error_code ec;
                if (SafeDirectory(state->options.root)) fs::create_directories(directory, ec);
                else ec = std::error_code(ERROR_ACCESS_DENIED, std::system_category());
                if (ec || !SafeDirectory(directory.wstring())) error = ec ? static_cast<DWORD>(ec.value()) : ERROR_ACCESS_DENIED;
                else
                {
                    active = Own(::CreateFileW((directory / L"active").c_str(), GENERIC_READ | GENERIC_WRITE, 0, nullptr, OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr));
                    if (!active) error = ::GetLastError();
                    else
                    {
                        uint64_t unclean = 0; CleanupHistory(*state, unclean);
                        if (unclean)
                        {
                            LogRecord record; record.event = LogEvent::PreviousSessionUnclean; record.level = LogLevel::Warning;
                            record.fields.count = static_cast<int64_t>(unclean); ::GetSystemTimeAsFileTime(&record.time);
                            error = append(record);
                        }
                    }
                }
                if (error) failure(error);
            }
            if (active && (::GetTickCount64() >= retryAt || stopping))
            {
                size_t processed = 0;
                while (processed++ < 128)
                {
                    LogRecord record;
                    {
                        std::lock_guard lock(state->mutex);
                        if (state->records.empty()) break;
                        record = state->records.front(); state->records.pop_front();
                    }
                    lastSequence = record.sequence;
                    error = append(record);
                    if (error)
                    {
                        tail.push_back(lastAttempt); if (tail.size() > 64) tail.pop_front();
                        { std::lock_guard lock(state->mutex); state->Drop(record.level); }
                        failure(error); break;
                    }
                    bool recovered = false;
                    { std::lock_guard lock(state->mutex); recovered = state->status.writeFailures && !state->status.available; state->status.available = true; state->status.lastError = 0; state->status.ready = true; }
                    if (recovered)
                    {
                        LogRecord recovery; recovery.event = LogEvent::StorageRecovered; recovery.level = LogLevel::Info;
                        ::GetSystemTimeAsFileTime(&recovery.time); auto recoveryError = append(recovery); if (recoveryError) { failure(recoveryError); break; }
                    }
                }
                uint64_t dropped = 0;
                { std::lock_guard lock(state->mutex); dropped = state->status.dropped; }
                if (!error && dropped != reportedDropped)
                {
                    LogRecord record; record.event = LogEvent::EventsDropped; record.level = LogLevel::Warning;
                    record.fields.count = static_cast<int64_t>(dropped - reportedDropped); ::GetSystemTimeAsFileTime(&record.time);
                    error = append(record); if (error) failure(error); else reportedDropped = dropped;
                }
                if (!error && file && ::GetTickCount64() - lastFlush >= 1000)
                { error = io->Flush(file.get()); lastFlush = ::GetTickCount64(); if (error) failure(error); }
            }
            std::shared_ptr<std::promise<LogSnapshot>> request;
            uint64_t snapshotTarget = 0;
            {
                std::lock_guard lock(state->mutex);
                state->status.ready = true;
                if (state->snapshot && (lastSequence >= state->snapshotTarget || !state->status.available || stopping)) { request = std::move(state->snapshot); snapshotTarget = state->snapshotTarget; }
            }
            if (request)
            {
                LogSnapshot snapshot;
                snapshot.sessionId = state->session;
                if (file) { auto flushError = io->Flush(file.get()); if (flushError) failure(flushError); }
                {
                    std::lock_guard lock(state->mutex); snapshot.status = state->status;
                    auto until = state->detailedUntil.load(); auto now = ::GetTickCount64();
                    snapshot.status.detailed = until > now;
                    snapshot.status.detailedSeconds = until > now ? static_cast<uint32_t>((until - now + 999) / 1000) : 0;
                }
                snapshot.incomplete = !snapshot.status.available || snapshot.status.dropped != 0 || lastSequence < snapshotTarget;
                uint64_t budget = 20 * 1024 * 1024;
                auto add = [&](fs::path const& path) {
                    if (snapshot.files.size() >= 32) { snapshot.incomplete = true; return; }
                    auto pinned = Pin(path);
                    if (!pinned.handle || pinned.bytes > budget) { snapshot.incomplete = true; return; }
                    budget -= pinned.bytes; snapshot.files.push_back(std::move(pinned));
                };
                for (auto const& path : paths) add(path);
                auto history = InactiveSessions(state->options.root, state->session);
                for (auto it = history.rbegin(); it != history.rend() && snapshot.files.size() < 32; ++it)
                    for (auto const& path : Segments(it->path)) add(path);
                for (auto const& record : tail) snapshot.memoryTail.push_back(Serialize(record, state->session));
                request->set_value(std::move(snapshot));
            }
            bool done = false;
            std::vector<LogRecord> summaries;
            {
                std::lock_guard lock(state->mutex);
                if (state->status.available)
                {
                    for (size_t i = 0; i < state->repetitions.size(); ++i)
                    {
                        auto& repetition = state->repetitions[i];
                        if (repetition.count && (state->stopping || ::GetTickCount64() - repetition.last >= 60000))
                        {
                            LogRecord summary; summary.event = LogEvent::EventsSuppressed; summary.level = LogLevel::Info;
                            summary.fields.count = static_cast<int64_t>(repetition.count); summary.fields.hresult = repetition.code;
                            summary.fields.status = static_cast<int32_t>(i); ::GetSystemTimeAsFileTime(&summary.time);
                            summaries.push_back(summary); repetition.count = 0;
                        }
                    }
                }
            }
            for (auto const& summary : summaries) { auto summaryError = append(summary); if (summaryError) { failure(summaryError); break; } }
            {
                std::lock_guard lock(state->mutex);
                done = state->stopping && (state->records.empty() || !state->status.available);
                if (done && !state->records.empty()) { for (auto const& record : state->records) state->Drop(record.level); state->records.clear(); }
            }
            if (done) break;
            auto until = state->detailedUntil.load();
            if (until && until <= ::GetTickCount64() && state->detailedUntil.compare_exchange_strong(until, 0))
            {
                LogRecord record; record.event = LogEvent::DetailedDisabled; record.level = LogLevel::Info;
                ::GetSystemTimeAsFileTime(&record.time); if (active && file) { auto expiryError = append(record); if (expiryError) failure(expiryError); }
            }
            std::unique_lock lock(state->mutex);
            auto wake = [&] { return state->stopping || state->snapshot || (!state->records.empty() && ::GetTickCount64() >= retryAt); };
            state->changed.wait_for(lock, std::chrono::milliseconds(250), wake);
        }
        if (file) { auto error = io->Flush(file.get()); if (error) failure(error); }
        bool markClean = false;
        { std::lock_guard lock(state->mutex); markClean = state->clean && !state->abandoned && state->status.available && !state->status.dropped; }
        if (markClean)
        {
            auto complete = Own(::CreateFileW((directory / L"complete").c_str(), GENERIC_WRITE, 0, nullptr, CREATE_NEW, FILE_ATTRIBUTE_NORMAL, nullptr));
            if (!complete) failure(::GetLastError());
        }
    }
    catch (...) { failure(ERROR_UNHANDLED_EXCEPTION); }
    file.reset(); active.reset();
    std::shared_ptr<std::promise<LogSnapshot>> pending;
    {
        std::lock_guard lock(state->mutex);
        for (auto const& record : state->records) state->Drop(record.level);
        state->records.clear();
        state->status.ready = true; state->status.stopped = true; pending = std::move(state->snapshot);
    }
    if (pending) { try { pending->set_value({}); } catch (...) {} }
    state->finished.notify_all();
}
}
