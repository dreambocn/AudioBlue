#include "pch.h"
#include "DiagnosticExport.h"
#include "DiagnosticPrivacy.h"
#include "StringUtil.h"
#include "AudioBule.Version.h"
#include <winrt/Windows.Data.Json.h>
#include <filesystem>
#include <cmath>
#include <set>
#include <wil/resource.h>

namespace AudioBule::Core
{
namespace
{
using namespace winrt::Windows::Data::Json;
bool Hex(std::wstring_view value, size_t length)
{
    return value.size() == length && std::all_of(value.begin(), value.end(), [](wchar_t c) {
        return (c >= L'0' && c <= L'9') || (c >= L'a' && c <= L'f') || (c >= L'A' && c <= L'F'); });
}
bool Timestamp(std::wstring_view value)
{
    if (value.size() != 24) return false;
    for (size_t i = 0; i < value.size(); ++i)
    {
        wchar_t expected = i == 4 || i == 7 ? L'-' : i == 10 ? L'T' : i == 13 || i == 16 ? L':' : i == 19 ? L'.' : i == 23 ? L'Z' : 0;
        if (expected ? value[i] != expected : (value[i] < L'0' || value[i] > L'9')) return false;
    }
    return true;
}
// 重新构造所有字符串字段；未知字段和任意原始消息不会被复制到导出文件。
std::string Sanitize(std::string const& line, std::set<std::string>& sessions)
{
    if (line.size() > 4096) return {};
    auto json = JsonObject::Parse(winrt::hstring(Utf8ToWide(line)));
    if (json.GetNamedNumber(L"schema_version") != 1) return {};
    auto event = WideToUtf8(std::wstring(json.GetNamedString(L"event")));
    LogEvent kind = LogEvent::Count;
    for (size_t i = 0; i < static_cast<size_t>(LogEvent::Count); ++i)
        if (event == Detail::Definition(static_cast<LogEvent>(i)).name) { kind = static_cast<LogEvent>(i); break; }
    if (kind == LogEvent::Count) return {};
    auto session = std::wstring(json.GetNamedString(L"session_id"));
    auto timestamp = std::wstring(json.GetNamedString(L"timestamp_utc"));
    auto token = std::wstring(json.GetNamedString(L"device_token"));
    if (!Hex(session, 32) || !Timestamp(timestamp) || (!token.empty() && !Hex(token, 32))) return {};
    auto const& definition = Detail::Definition(kind);
    std::string output = "{\"schema_version\":1,\"record_type\":\"log\",\"session_id\":" + Detail::JsonQuote(WideToUtf8(session)) +
        ",\"timestamp_utc\":" + Detail::JsonQuote(WideToUtf8(timestamp)) + ",\"device_token\":" + Detail::JsonQuote(WideToUtf8(token)) +
        ",\"event\":" + Detail::JsonQuote(definition.name) + ",\"module\":" + Detail::JsonQuote(definition.module) +
        ",\"message\":" + Detail::JsonQuote(WideToUtf8(definition.message));
    for (auto key : {L"sequence", L"elapsed_ms", L"duration_ms", L"pid", L"tid", L"operation_id", L"related_operation_id", L"count", L"failure", L"status", L"state_before", L"state_after"})
    {
        double value = json.GetNamedNumber(key);
        if (!std::isfinite(value) || std::floor(value) != value || value < -2147483648.0 || value > 9007199254740991.0) return {};
        output += "," + Detail::JsonQuote(WideToUtf8(key)) + ":" + std::to_string(static_cast<int64_t>(value));
    }
    for (auto key : {L"hresult", L"win32_error"})
    {
        auto value = std::wstring(json.GetNamedString(key));
        if (value.size() != 10 || !value.starts_with(L"0x") || !Hex(std::wstring_view(value).substr(2), 8)) return {};
        output += "," + Detail::JsonQuote(WideToUtf8(key)) + ":" + Detail::JsonQuote(WideToUtf8(value));
    }
    auto safeEnum = [&](wchar_t const* key, auto count, auto name) {
        auto value = WideToUtf8(std::wstring(json.GetNamedString(key)));
        bool found = false;
        for (int i = 0; i < count; ++i) if (value == name(i)) found = true;
        if (!found) throw std::invalid_argument("诊断枚举值无效");
        output += "," + Detail::JsonQuote(WideToUtf8(key)) + ":" + Detail::JsonQuote(value);
    };
    safeEnum(L"level", 5, [](int i) { return Detail::LevelName(static_cast<LogLevel>(i)); });
    safeEnum(L"trigger", 4, [](int i) { return Detail::TriggerName(static_cast<LogTrigger>(i)); });
    safeEnum(L"stage", 13, [](int i) { return Detail::StageName(static_cast<LogStage>(i)); });
    safeEnum(L"outcome", 7, [](int i) { return Detail::OutcomeName(static_cast<LogOutcome>(i)); });
    if (kind == LogEvent::SessionStarted)
    {
        auto version = std::wstring(json.GetNamedString(L"app_version"));
        auto arch = std::wstring(json.GetNamedString(L"architecture"));
        auto configuration = std::wstring(json.GetNamedString(L"configuration"));
        if (version.empty() || version.size() > 32 || !std::all_of(version.begin(), version.end(), [](wchar_t c) { return (c >= L'0' && c <= L'9') || c == L'.'; }) ||
            (arch != L"ARM64" && arch != L"x64") || (configuration != L"Release" && configuration != L"Debug")) return {};
        output += ",\"app_version\":" + Detail::JsonQuote(WideToUtf8(version)) + ",\"architecture\":" + Detail::JsonQuote(WideToUtf8(arch)) +
            ",\"configuration\":" + Detail::JsonQuote(WideToUtf8(configuration));
        auto os = std::wstring(json.GetNamedString(L"os_version", L"0.0.0"));
        if (os.empty() || os.size() > 32 || !std::all_of(os.begin(), os.end(), [](wchar_t c) { return (c >= L'0' && c <= L'9') || c == L'.'; })) return {};
        output += ",\"os_version\":" + Detail::JsonQuote(WideToUtf8(os)) + ",\"packaged\":" + (json.GetNamedBoolean(L"packaged", false) ? "true" : "false");
    }
    if (sessions.size() < 32) sessions.insert(WideToUtf8(session));
    return output + "}\n";
}
void WriteAll(HANDLE handle, std::string_view content)
{
    DWORD written = 0;
    if (!::WriteFile(handle, content.data(), static_cast<DWORD>(content.size()), &written, nullptr)) winrt::throw_last_error();
    if (written != content.size()) winrt::throw_hresult(HRESULT_FROM_WIN32(ERROR_WRITE_FAULT));
}
}
DiagnosticExportResult ExportDiagnostics(LogSnapshot const& snapshot, std::wstring const& target,
    std::atomic<bool> const& cancelled, size_t maxBytes) noexcept
{
    DiagnosticExportResult result;
    result.incomplete = snapshot.incomplete;
    try
    {
        std::filesystem::path destination(target);
        if (!destination.is_absolute() || !Detail::SafeDirectory(destination.parent_path().wstring()) || maxBytes < 4096 || maxBytes > 20 * 1024 * 1024)
        { result.error = ERROR_INVALID_PARAMETER; return result; }
        auto attributes = ::GetFileAttributesW(destination.c_str());
        if (attributes != INVALID_FILE_ATTRIBUTES && (attributes & (FILE_ATTRIBUTE_REPARSE_POINT | FILE_ATTRIBUTE_DIRECTORY)))
        { result.error = ERROR_ACCESS_DENIED; return result; }
        auto suffix = Utf8ToWide(Detail::RandomHex(16));
        auto bodyPath = destination.wstring() + L"." + suffix + L".body.tmp";
        auto finalPath = destination.wstring() + L"." + suffix + L".tmp";
        auto cleanup = wil::scope_exit([&] { ::DeleteFileW(bodyPath.c_str()); ::DeleteFileW(finalPath.c_str()); });
        wil::unique_hfile body(::CreateFileW(bodyPath.c_str(), GENERIC_WRITE | GENERIC_READ, 0, nullptr, CREATE_NEW, FILE_ATTRIBUTE_TEMPORARY, nullptr));
        if (!body) winrt::throw_last_error();
        size_t bytes = 0;
        std::string firstTimestamp, lastTimestamp;
        std::set<std::string> sessions;
        auto consume = [&](std::string const& line) {
            if (cancelled) { result.cancelled = true; return; }
            std::string safe;
            try { safe = Sanitize(line, sessions); } catch (...) {}
            if (safe.empty()) { ++result.skipped; result.incomplete = true; return; }
            if (bytes + safe.size() > maxBytes - 4096) { ++result.skipped; result.incomplete = true; return; }
            auto timestamp = WideToUtf8(std::wstring(JsonObject::Parse(winrt::hstring(Utf8ToWide(safe))).GetNamedString(L"timestamp_utc")));
            if (firstTimestamp.empty() || timestamp < firstTimestamp) firstTimestamp = timestamp;
            if (lastTimestamp.empty() || timestamp > lastTimestamp) lastTimestamp = timestamp;
            WriteAll(body.get(), safe); bytes += safe.size(); ++result.records;
        };
        uint64_t readBudget = 20 * 1024 * 1024;
        for (auto const& file : snapshot.files)
        {
            if (cancelled) break;
            if (!file.handle || file.bytes > readBudget) { result.incomplete = true; ++result.skipped; continue; }
            readBudget -= file.bytes;
            LARGE_INTEGER zero{};
            if (!::SetFilePointerEx(file.handle.get(), zero, nullptr, FILE_BEGIN)) { result.incomplete = true; ++result.skipped; continue; }
            uint64_t remaining = file.bytes;
            std::string line;
            bool oversized = false;
            while (remaining && !cancelled)
            {
                char buffer[8192]; DWORD count = 0;
                if (!::ReadFile(file.handle.get(), buffer, static_cast<DWORD>(std::min<uint64_t>(remaining, sizeof(buffer))), &count, nullptr) || !count)
                { result.incomplete = true; ++result.skipped; break; }
                remaining -= count;
                for (DWORD i = 0; i < count; ++i)
                {
                    if (buffer[i] == '\n')
                    {
                        if (oversized) { ++result.skipped; result.incomplete = true; } else consume(line);
                        line.clear(); oversized = false;
                    }
                    else if (!oversized)
                    {
                        if (line.size() >= 4096) { line.clear(); oversized = true; } else line += buffer[i];
                    }
                }
            }
            if (!line.empty() || oversized) { result.incomplete = true; ++result.skipped; }
        }
        size_t tails = 0;
        for (auto const& line : snapshot.memoryTail) { if (++tails > 64) { result.incomplete = true; ++result.skipped; continue; } consume(line); }
        if (cancelled) { result.cancelled = true; return result; }
        std::string sessionList = "[";
        for (auto const& session : sessions) { if (sessionList.size() > 1) sessionList += ','; sessionList += Detail::JsonQuote(session); }
        sessionList += ']';
        std::string droppedLevels = "{";
        for (size_t i = 0; i < snapshot.status.droppedByLevel.size(); ++i)
        {
            if (i) droppedLevels += ',';
            droppedLevels += Detail::JsonQuote(Detail::LevelName(static_cast<LogLevel>(i))) + ":" + std::to_string(snapshot.status.droppedByLevel[i]);
        }
        droppedLevels += '}';
        std::string manifest = "{\"record_type\":\"manifest\",\"schema_version\":1" + Detail::RuntimeInfoJson() +
            ",\"created_utc\":" + Detail::JsonQuote(Detail::UtcTimestamp()) + ",\"incomplete\":" + (result.incomplete ? "true" : "false") +
            ",\"first_event_utc\":" + Detail::JsonQuote(firstTimestamp) + ",\"last_event_utc\":" + Detail::JsonQuote(lastTimestamp) +
            ",\"minimum_level\":" + Detail::JsonQuote(snapshot.status.detailed ? "debug" : "info") +
            ",\"records\":" + std::to_string(result.records) + ",\"skipped\":" + std::to_string(result.skipped) +
            ",\"dropped\":" + std::to_string(snapshot.status.dropped) + ",\"write_failures\":" + std::to_string(snapshot.status.writeFailures) +
            ",\"dropped_by_level\":" + droppedLevels +
            ",\"storage_available\":" + (snapshot.status.available ? "true" : "false") +
            ",\"last_error\":" + Detail::JsonQuote(Detail::HexCode(snapshot.status.lastError)) + ",\"sessions\":" + sessionList + "}\n";
        wil::unique_hfile output(::CreateFileW(finalPath.c_str(), GENERIC_WRITE, 0, nullptr, CREATE_NEW, FILE_ATTRIBUTE_NORMAL, nullptr));
        if (!output) winrt::throw_last_error();
        WriteAll(output.get(), manifest);
        LARGE_INTEGER zero{}; winrt::check_bool(::SetFilePointerEx(body.get(), zero, nullptr, FILE_BEGIN));
        for (;;)
        {
            if (cancelled) { result.cancelled = true; return result; }
            char buffer[8192]; DWORD count = 0;
            winrt::check_bool(::ReadFile(body.get(), buffer, sizeof(buffer), &count, nullptr));
            if (!count) break;
            WriteAll(output.get(), std::string_view(buffer, count));
        }
        winrt::check_bool(::FlushFileBuffers(output.get())); output.reset(); body.reset();
        if (cancelled) { result.cancelled = true; return result; }
        winrt::check_bool(::MoveFileExW(finalPath.c_str(), destination.c_str(), MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH));
        result.succeeded = true;
    }
    catch (winrt::hresult_error const& error) { result.error = static_cast<DWORD>(error.code().value); }
    catch (...) { result.error = ERROR_UNHANDLED_EXCEPTION; }
    return result;
}
}
