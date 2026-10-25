#include "pch.h"
#include "Logger.h"
#include "LogWriter.h"
#include "DiagnosticPrivacy.h"
#include <filesystem>
#include <thread>

namespace AudioBule::Core
{
Logger::Logger(LoggerOptions options) noexcept
{
    try
    {
        auto state = std::make_shared<Detail::LogState>();
        if (options.root.empty()) options.root = DefaultRoot();
        // 构造阶段只做词法校验，文件属性探测也必须留在后台线程。
        if (!std::filesystem::path(options.root).is_absolute() || options.maxRecords == 0 || options.maxRecords > 65536 ||
            options.maxQueueBytes < sizeof(Detail::LogRecord) || options.maxQueueBytes > 64 * 1024 * 1024 ||
            options.maxFileBytes < 4096 || options.maxFileBytes > 4 * 1024 * 1024 || options.maxFiles == 0 || options.maxFiles > 5)
            return;
        options.reservedRecords = std::min(options.reservedRecords, options.maxRecords / 2);
        options.reservedBytes = std::min(options.reservedBytes, options.maxQueueBytes / 2);
        state->options = std::move(options);
        state->session = Detail::RandomHex(16);
        if (::BCryptGenRandom(nullptr, state->key.data(), static_cast<ULONG>(state->key.size()), BCRYPT_USE_SYSTEM_PREFERRED_RNG) >= 0)
            ::BCryptOpenAlgorithmProvider(&state->algorithm, BCRYPT_SHA256_ALGORITHM, nullptr, BCRYPT_ALG_HANDLE_HMAC_FLAG);
        std::thread worker([state] { Detail::RunWriter(state); });
        worker.detach();
        m_state = std::move(state);
        Context().Write(LogEvent::SessionStarted);
    }
    catch (...) { m_state.reset(); }
}
Logger::~Logger() { Stop(std::chrono::milliseconds(0), false); }
LogContext Logger::Context() const noexcept
{
    LogContext result; result.m_state = m_state; return result;
}
LogStatus Logger::Status() const noexcept
{
    if (!m_state) { LogStatus result; result.ready = true; result.lastError = ERROR_INVALID_PARAMETER; return result; }
    std::lock_guard lock(m_state->mutex);
    auto result = m_state->status;
    auto until = m_state->detailedUntil.load();
    auto now = ::GetTickCount64();
    result.detailed = until > now;
    result.detailedSeconds = result.detailed ? static_cast<uint32_t>((until - now + 999) / 1000) : 0;
    result.queued = m_state->records.size(); result.queuedBytes = result.queued * sizeof(Detail::LogRecord);
    return result;
}
std::wstring Logger::Root() const { return m_state ? m_state->options.root : std::wstring{}; }
std::wstring Logger::DefaultRoot()
{
    wchar_t buffer[32768]{};
    auto length = ::GetEnvironmentVariableW(L"LOCALAPPDATA", buffer, static_cast<DWORD>(std::size(buffer)));
    if (!length || length >= std::size(buffer)) return {};
    auto root = std::filesystem::path(buffer);
    return root.is_absolute() ? (root / L"AudioBule" / L"Logs").wstring() : std::wstring{};
}
void Logger::SetDetailed(bool enabled, std::chrono::seconds duration) noexcept
{
    if (!m_state) return;
    auto seconds = std::clamp<int64_t>(duration.count(), 1, 900);
    m_state->detailedUntil = enabled ? ::GetTickCount64() + static_cast<uint64_t>(seconds) * 1000 : 0;
    Context().Write(enabled ? LogEvent::DetailedEnabled : LogEvent::DetailedDisabled);
    m_state->changed.notify_one();
}
LogSnapshot Logger::Snapshot(std::chrono::milliseconds timeout) const noexcept
{
    try
    {
        if (!m_state) return {};
        auto promise = std::make_shared<std::promise<LogSnapshot>>();
        auto future = promise->get_future();
        {
            std::lock_guard lock(m_state->mutex);
            if (m_state->stopping || m_state->snapshot) return {};
            m_state->snapshot = std::move(promise); m_state->snapshotTarget = m_state->sequence;
        }
        m_state->changed.notify_one();
        if (future.wait_for(timeout) == std::future_status::ready) return future.get();
    }
    catch (...) {}
    LogSnapshot result; result.status = Status(); return result;
}
bool Logger::Stop(std::chrono::milliseconds timeout, bool clean) noexcept
{
    if (!m_state) return false;
    std::unique_lock lock(m_state->mutex);
    if (!m_state->stopping) { m_state->stopping = true; m_state->clean = clean; }
    m_state->changed.notify_one();
    bool done = m_state->finished.wait_for(lock, timeout, [&] { return m_state->status.stopped; });
    if (!done) m_state->abandoned = true;
    return done && m_state->status.available && m_state->status.dropped == 0;
}
LogContext LogContext::Operation(LogTrigger trigger, std::wstring_view deviceId) const noexcept
{
    auto result = WithDevice(deviceId);
    result.m_related = m_operation;
    result.m_operation = m_state ? ++m_state->operation : 0;
    result.m_started = ::GetTickCount64(); result.m_trigger = trigger;
    return result;
}
LogContext LogContext::WithDevice(std::wstring_view deviceId) const noexcept
{
    auto result = *this; result.m_device = {};
    if (deviceId.empty() || deviceId.size() > 32768 || !m_state || !m_state->algorithm) return result;
    std::array<unsigned char, 32> hash{};
    if (::BCryptHash(m_state->algorithm, m_state->key.data(), static_cast<ULONG>(m_state->key.size()),
        reinterpret_cast<PUCHAR>(const_cast<wchar_t*>(deviceId.data())), static_cast<ULONG>(deviceId.size() * sizeof(wchar_t)),
        hash.data(), static_cast<ULONG>(hash.size())) >= 0)
    {
        constexpr char hex[] = "0123456789abcdef";
        for (size_t i = 0; i < 16; ++i) { result.m_device[i * 2] = hex[hash[i] >> 4]; result.m_device[i * 2 + 1] = hex[hash[i] & 15]; }
    }
    ::SecureZeroMemory(hash.data(), hash.size()); return result;
}
bool LogContext::Write(LogEvent event, LogFields fields, LogLevel level) const noexcept
{
    if (!m_state || static_cast<unsigned>(event) >= static_cast<unsigned>(LogEvent::Count) || static_cast<unsigned>(level) > static_cast<unsigned>(LogLevel::Critical)) return false;
    try
    {
        auto now = ::GetTickCount64();
        Detail::LogRecord record;
        record.event = event; record.fields = fields; record.level = level; record.trigger = m_trigger;
        record.elapsed = now - m_state->started; record.duration = m_started ? now - m_started : 0;
        record.operation = m_operation; record.related = m_related; record.device = m_device; record.tid = ::GetCurrentThreadId();
        ::GetSystemTimeAsFileTime(&record.time);
        std::lock_guard lock(m_state->mutex);
        if (m_state->stopping || m_state->status.stopped) { ++m_state->status.rejected; return false; }
        if (level == LogLevel::Debug && m_state->detailedUntil <= now) { ++m_state->status.filtered; return false; }
        // 高频环境故障按固定事件聚合，不抑制每次连接的终态事件。
        if (event == LogEvent::AudioIdentityFailed || event == LogEvent::ResourceMissing ||
            event == LogEvent::NotificationsUnavailable || event == LogEvent::TrayMessageFailed)
        {
            auto& repetition = m_state->repetitions[static_cast<size_t>(event)];
            if (repetition.last && repetition.code == fields.hresult && now - repetition.last < 60000)
            { ++repetition.count; ++m_state->status.filtered; return false; }
            record.fields.count += static_cast<int64_t>(repetition.count);
            repetition = {now, 0, fields.hresult};
        }
        auto const& options = m_state->options;
        bool high = level >= LogLevel::Warning;
        auto maxCount = options.maxRecords - (high ? 0 : options.reservedRecords);
        auto maxBytes = options.maxQueueBytes - (high ? 0 : options.reservedBytes);
        if (m_state->records.size() >= maxCount || (m_state->records.size() + 1) * sizeof(record) > maxBytes)
        { m_state->Drop(level); return false; }
        record.sequence = m_state->sequence + 1;
        m_state->records.push_back(record);
        ++m_state->sequence; ++m_state->status.accepted;
        m_state->changed.notify_one(); return true;
    }
    catch (...)
    {
        std::lock_guard lock(m_state->mutex); m_state->Drop(level); return false;
    }
}
}
