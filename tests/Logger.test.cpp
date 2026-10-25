#include <gtest/gtest.h>
#include "Logger.h"
#include "LogWriter.h"
#include "DiagnosticExport.h"
#include "DiagnosticPrivacy.h"
#include "Settings.h"
#include "ConnectionManager.h"
#include "StringUtil.h"
#include <winrt/Windows.Data.Json.h>
#include <winrt/Windows.Foundation.Collections.h>
#include <filesystem>
#include <fstream>
#include <future>
#include <thread>
#include <set>
#include <wil/resource.h>

using namespace AudioBule::Core;
namespace fs = std::filesystem;
using winrt::Windows::Data::Json::JsonObject;

namespace
{
class LoggingTest : public testing::Test
{
protected:
    fs::path root;
    LoggerOptions Options()
    {
        LoggerOptions result; result.root = (root / L"Logs").wstring(); return result;
    }
    void SetUp() override
    {
        wchar_t temporary[32768]{};
        ASSERT_GT(::GetTempPathW(static_cast<DWORD>(std::size(temporary)), temporary), 0u);
        wchar_t overrideRoot[32768]{};
        auto length = ::GetEnvironmentVariableW(L"AUDIOBULE_TEST_ROOT", overrideRoot, static_cast<DWORD>(std::size(overrideRoot)));
        auto parent = length && length < std::size(overrideRoot) ? fs::path(overrideRoot) : fs::path(temporary);
        ASSERT_TRUE(parent.is_absolute());
        root = parent / L"AudioBule-Logging-Tests" / Utf8ToWide(Detail::RandomHex(16));
        fs::create_directories(root);
    }
    void TearDown() override
    {
        // 仅删除本用例随机创建的绝对目录，不触碰日常配置或日志。
        ASSERT_TRUE(root.is_absolute());
        ASSERT_EQ(root.parent_path().filename(), L"AudioBule-Logging-Tests");
        std::error_code ec; fs::remove_all(root, ec);
    }
    std::vector<winrt::Windows::Data::Json::JsonObject> Read(LogSnapshot const& snapshot)
    {
        std::vector<winrt::Windows::Data::Json::JsonObject> result;
        for (auto const& file : snapshot.files)
        {
            LARGE_INTEGER zero{}; EXPECT_TRUE(::SetFilePointerEx(file.handle.get(), zero, nullptr, FILE_BEGIN));
            std::string text(static_cast<size_t>(file.bytes), '\0');
            DWORD read = 0; EXPECT_TRUE(::ReadFile(file.handle.get(), text.data(), static_cast<DWORD>(text.size()), &read, nullptr));
            text.resize(read);
            size_t start = 0;
            for (auto end = text.find('\n'); end != std::string::npos; end = text.find('\n', start))
            {
                result.push_back(JsonObject::Parse(winrt::hstring(Utf8ToWide(text.substr(start, end - start))))); start = end + 1;
            }
        }
        return result;
    }
};
class GateIo final : public Detail::LogIo
{
public:
    std::promise<void> entered, release;
    std::shared_future<void> released = release.get_future().share();
    std::atomic<bool> first{true}, opened{false};
    ~GateIo() { Open(); }
    void Open() { if (!opened.exchange(true)) release.set_value(); }
    DWORD Write(HANDLE file, std::string_view text) noexcept override
    {
        if (first.exchange(false)) { entered.set_value(); released.wait(); }
        DWORD written = 0;
        if (!::WriteFile(file, text.data(), static_cast<DWORD>(text.size()), &written, nullptr)) return ::GetLastError();
        return written == text.size() ? 0 : ERROR_WRITE_FAULT;
    }
    DWORD Flush(HANDLE file) noexcept override { return ::FlushFileBuffers(file) ? 0 : ::GetLastError(); }
};
class FailingIo final : public Detail::LogIo
{
public:
    std::atomic<DWORD> error{ERROR_DISK_FULL};
    std::promise<void> recovered;
    std::atomic<bool> signalled{false};
    DWORD Write(HANDLE file, std::string_view text) noexcept override
    {
        if (auto code = error.load()) return code;
        DWORD written = 0;
        if (!::WriteFile(file, text.data(), static_cast<DWORD>(text.size()), &written, nullptr)) return ::GetLastError();
        if (!signalled.exchange(true)) recovered.set_value();
        return written == text.size() ? 0 : ERROR_WRITE_FAULT;
    }
    DWORD Flush(HANDLE file) noexcept override { return ::FlushFileBuffers(file) ? 0 : ::GetLastError(); }
};
class FlushFailureIo final : public Detail::LogIo
{
public:
    DWORD Write(HANDLE file, std::string_view text) noexcept override
    {
        DWORD written = 0;
        if (!::WriteFile(file, text.data(), static_cast<DWORD>(text.size()), &written, nullptr)) return ::GetLastError();
        return written == text.size() ? 0 : ERROR_WRITE_FAULT;
    }
    DWORD Flush(HANDLE) noexcept override { return ERROR_WRITE_FAULT; }
};
class LoggedProvider final : public IAudioDeviceProvider
{
public:
    bool enumerateThrows = false, blocked = false, disconnectThrows = false;
    ConnectResult result{true, ConnectFailure::None, 0};
    std::promise<void> entered, release;
    std::shared_future<void> released = release.get_future().share();
    std::atomic<bool> opened{false};
    std::atomic<int> closed{0};
    ~LoggedProvider() { Open(); }
    void Open() { if (!opened.exchange(true)) release.set_value(); }
    bool IsSupported() const override { return true; }
    std::vector<DeviceInfo> EnumerateDevices() override
    {
        if (enumerateThrows) throw winrt::hresult_error(E_ACCESSDENIED, L"私人设备信息");
        return {{L"private-device-id", L"私人手机"}};
    }
    ConnectResult Connect(std::wstring_view, LogContext const& log) override
    {
        if (blocked) { entered.set_value(); released.wait(); }
        log.Write(LogEvent::ProviderStage, { .stage = LogStage::Open, .outcome = result.succeeded ? LogOutcome::Succeeded : LogOutcome::Failed, .hresult = result.extendedError });
        return result;
    }
    void Disconnect(std::wstring_view, LogContext const&) override
    {
        ++closed;
        if (disconnectThrows) throw winrt::hresult_error(E_FAIL);
    }
};
}

TEST_F(LoggingTest, ConcurrentRecordsHaveUniqueSequencesAndRemainParseable)
{
    auto options = Options(); options.maxRecords = 8192; options.reservedRecords = 0;
    Logger logger(options);
    std::vector<std::thread> threads;
    for (int i = 0; i < 4; ++i) threads.emplace_back([&] {
        auto operation = logger.Context().Operation(LogTrigger::Manual, L"私人设备-MAC-00:11:22:33:44:55");
        for (int j = 0; j < 500; ++j) operation.Write(LogEvent::ConnectRequested);
    });
    for (auto& thread : threads) thread.join();
    auto snapshot = logger.Snapshot(); ASSERT_FALSE(snapshot.incomplete);
    auto records = Read(snapshot); EXPECT_EQ(records.size(), 2001u);
    std::set<double> sequences;
    for (auto const& record : records)
    {
        EXPECT_EQ(std::wstring(record.GetNamedString(L"session_id")).size(), 32u);
        sequences.insert(record.GetNamedNumber(L"sequence"));
        EXPECT_EQ(std::wstring(record.Stringify()).find(L"私人设备"), std::wstring::npos);
    }
    EXPECT_EQ(sequences.size(), records.size()); EXPECT_EQ(logger.Status().dropped, 0u);
    snapshot = {}; EXPECT_TRUE(logger.Stop());
}
TEST_F(LoggingTest, DeviceTokensAreStableOnlyWithinOneSession)
{
    Logger first(Options());
    first.Context().Operation(LogTrigger::Manual, L"私人手机").Write(LogEvent::ConnectRequested);
    first.Context().Operation(LogTrigger::Manual, L"私人手机").Write(LogEvent::ConnectRequested);
    auto snapshot = first.Snapshot(); auto records = Read(snapshot);
    ASSERT_EQ(records.size(), 3u);
    auto token = records[1].GetNamedString(L"device_token"); EXPECT_EQ(token.size(), 32u);
    EXPECT_EQ(token, records[2].GetNamedString(L"device_token"));
    snapshot = {}; EXPECT_TRUE(first.Stop());
    Logger second(Options());
    second.Context().Operation(LogTrigger::Manual, L"私人手机").Write(LogEvent::ConnectRequested);
    snapshot = second.Snapshot(); records = Read(snapshot);
    auto found = std::find_if(records.begin(), records.end(), [](auto const& row) { return row.GetNamedString(L"event") == L"connection.requested"; });
    ASSERT_NE(found, records.end()); EXPECT_NE(token, found->GetNamedString(L"device_token"));
    snapshot = {}; EXPECT_TRUE(second.Stop());
}
TEST_F(LoggingTest, QueueIsBoundedAndHighLevelsUseReservedCapacity)
{
    auto gate = std::make_shared<GateIo>(); auto entered = gate->entered.get_future();
    auto options = Options(); options.io = gate; options.maxRecords = 8; options.reservedRecords = 2;
    Logger logger(options);
    auto cleanup = wil::scope_exit([&] { gate->Open(); logger.Stop(); });
    ASSERT_EQ(entered.wait_for(std::chrono::seconds(2)), std::future_status::ready);
    for (int i = 0; i < 30; ++i) logger.Context().Write(LogEvent::ConnectRequested);
    EXPECT_EQ(logger.Status().queued, 6u);
    EXPECT_TRUE(logger.Context().Write(LogEvent::OperationFailed, {}, LogLevel::Error));
    EXPECT_TRUE(logger.Context().Write(LogEvent::OperationFailed, {}, LogLevel::Error));
    EXPECT_FALSE(logger.Context().Write(LogEvent::OperationFailed, {}, LogLevel::Error));
    EXPECT_EQ(logger.Status().queued, 8u); EXPECT_GT(logger.Status().dropped, 0u);
    EXPECT_GT(logger.Status().droppedByLevel[static_cast<size_t>(LogLevel::Info)], 0u);
    EXPECT_EQ(logger.Status().droppedByLevel[static_cast<size_t>(LogLevel::Error)], 1u);
    gate->Open(); auto snapshot = logger.Snapshot(); EXPECT_TRUE(snapshot.incomplete);
}
TEST_F(LoggingTest, StopTimeoutDoesNotLeaveDanglingBusinessReferences)
{
    auto gate = std::make_shared<GateIo>(); auto entered = gate->entered.get_future();
    auto options = Options(); options.io = gate;
    auto logger = std::make_unique<Logger>(options); auto context = logger->Context();
    auto cleanup = wil::scope_exit([&] { gate->Open(); if (logger) logger->Stop(); });
    ASSERT_EQ(entered.wait_for(std::chrono::seconds(2)), std::future_status::ready);
    auto started = std::chrono::steady_clock::now();
    EXPECT_FALSE(logger->Stop(std::chrono::milliseconds(20)));
    EXPECT_LT(std::chrono::steady_clock::now() - started, std::chrono::seconds(1));
    logger.reset(); EXPECT_FALSE(context.Write(LogEvent::ConnectRequested));
    gate->Open();
    // 对共享文件适配器的同步屏障证明阻塞线程已恢复，另一个记录器仍可正常工作。
    Logger other(Options()); EXPECT_TRUE(other.Stop());
}
TEST_F(LoggingTest, RotationLimitsFileCountAndSize)
{
    auto options = Options(); options.maxFileBytes = 4096; options.maxFiles = 3;
    Logger logger(options);
    for (int i = 0; i < 100; ++i) logger.Context().Write(LogEvent::ConnectRequested);
    auto snapshot = logger.Snapshot(); ASSERT_FALSE(snapshot.incomplete);
    EXPECT_LE(snapshot.files.size(), 3u);
    for (auto const& file : snapshot.files) EXPECT_LE(file.bytes, 4096u);
    snapshot = {}; EXPECT_TRUE(logger.Stop());
}
TEST_F(LoggingTest, DiskFailureIsVisibleAndStopRemainsBounded)
{
    auto options = Options(); auto failing = std::make_shared<FailingIo>(); options.io = failing;
    Logger logger(options); auto snapshot = logger.Snapshot();
    EXPECT_TRUE(snapshot.incomplete); EXPECT_FALSE(logger.Status().available);
    EXPECT_GT(logger.Status().writeFailures, 0u); EXPECT_EQ(logger.Status().lastError, static_cast<DWORD>(ERROR_DISK_FULL));
    EXPECT_FALSE(logger.Stop());
}
TEST_F(LoggingTest, UnwritableRootDoesNotPreventCallerFromContinuing)
{
    auto options = Options(); options.root = (root / L"ordinary-file").wstring();
    std::ofstream(root / L"ordinary-file") << "已存在的普通文件";
    Logger logger(options); EXPECT_FALSE(logger.Status().available);
    logger.Context().Write(LogEvent::ConnectRequested);
    auto snapshot = logger.Snapshot(); EXPECT_TRUE(snapshot.incomplete); EXPECT_FALSE(snapshot.status.available);
    EXPECT_EQ(fs::file_size(root / L"ordinary-file"), std::string("已存在的普通文件").size());
    EXPECT_FALSE(logger.Stop());
}
TEST_F(LoggingTest, DebugFilteringAndRepetitionDoNotSuppressConnectionOutcomes)
{
    Logger logger(Options());
    EXPECT_FALSE(logger.Context().Write(LogEvent::ProviderStage, {}, LogLevel::Debug));
    logger.SetDetailed(true);
    EXPECT_TRUE(logger.Context().Write(LogEvent::ProviderStage, {}, LogLevel::Debug));
    logger.SetDetailed(false);
    for (int i = 0; i < 20; ++i) logger.Context().Write(LogEvent::AudioIdentityFailed, { .hresult = E_FAIL }, LogLevel::Warning);
    for (int i = 0; i < 20; ++i) EXPECT_TRUE(logger.Context().Write(LogEvent::ConnectCompleted, { .outcome = LogOutcome::Failed }, LogLevel::Warning));
    auto snapshot = logger.Snapshot(); auto records = Read(snapshot);
    size_t repeated = 0, outcomes = 0;
    for (auto const& record : records) { auto name = record.GetNamedString(L"event"); repeated += name == L"audio_identity.failed"; outcomes += name == L"connection.completed"; }
    EXPECT_EQ(repeated, 1u); EXPECT_EQ(outcomes, 20u); EXPECT_GE(logger.Status().filtered, 20u);
    snapshot = {}; EXPECT_TRUE(logger.Stop());
}
TEST_F(LoggingTest, ExportRemovesUnknownFieldsAndUserControlledMessage)
{
    Logger logger(Options()); auto snapshot = logger.Snapshot(); auto records = Read(snapshot);
    ASSERT_FALSE(records.empty());
    auto malicious = records.front();
    malicious.Insert(L"message", winrt::Windows::Data::Json::JsonValue::CreateStringValue(L"私人手机 C:\\Users\\秘密"));
    malicious.Insert(L"private_data", winrt::Windows::Data::Json::JsonValue::CreateStringValue(L"00:11:22:33:44:55"));
    LogSnapshot input; input.incomplete = false; input.status.available = true;
    input.memoryTail.push_back(WideToUtf8(std::wstring(malicious.Stringify())));
    std::atomic<bool> cancelled{false}; auto output = root / L"export.jsonl";
    auto result = ExportDiagnostics(input, output.wstring(), cancelled);
    EXPECT_TRUE(result.succeeded); EXPECT_EQ(result.records, 1u);
    std::ifstream file(output, std::ios::binary); std::string text((std::istreambuf_iterator<char>(file)), {});
    EXPECT_EQ(text.find("private_data"), std::string::npos); EXPECT_EQ(text.find("00:11"), std::string::npos);
    EXPECT_EQ(text.find("C:\\Users"), std::string::npos); EXPECT_EQ(text.find("私人手机"), std::string::npos);
    snapshot = {}; EXPECT_TRUE(logger.Stop());
}
TEST_F(LoggingTest, InvalidSchemaAndOversizedInputAreReportedAsPartial)
{
    LogSnapshot input; input.incomplete = false;
    input.memoryTail = {"{\"schema_version\":999}", std::string(5000, 'x'), "not-json"};
    std::atomic<bool> cancelled{false};
    auto result = ExportDiagnostics(input, (root / L"partial.jsonl").wstring(), cancelled, 4096);
    EXPECT_TRUE(result.succeeded); EXPECT_TRUE(result.incomplete); EXPECT_EQ(result.skipped, 3u);
}
TEST_F(LoggingTest, CancelledExportPreservesExistingTarget)
{
    auto output = root / L"export.jsonl"; std::ofstream(output) << "保留原文件";
    std::atomic<bool> cancelled{true};
    auto result = ExportDiagnostics({}, output.wstring(), cancelled);
    EXPECT_TRUE(result.cancelled); EXPECT_FALSE(result.succeeded);
    std::ifstream file(output); std::string content((std::istreambuf_iterator<char>(file)), {});
    EXPECT_EQ(content, "保留原文件");
}
TEST_F(LoggingTest, SettingsCorruptionHasDiagnosticWithoutContents)
{
    auto path = root / L"settings.json"; std::ofstream(path) << "{私人数据";
    Logger logger(Options()); LoadSettings(path.wstring(), logger.Context());
    auto snapshot = logger.Snapshot(); auto records = Read(snapshot);
    EXPECT_TRUE(std::any_of(records.begin(), records.end(), [](auto const& record) { return record.GetNamedString(L"event") == L"settings.invalid"; }));
    snapshot = {}; EXPECT_TRUE(logger.Stop());
}
TEST_F(LoggingTest, RelativeLogAndExportPathsAreRejected)
{
    auto options = Options(); options.root = L"relative-logs";
    Logger logger(options); EXPECT_FALSE(logger.Context().Write(LogEvent::SessionStarted));
    std::atomic<bool> cancelled{false};
    EXPECT_EQ(ExportDiagnostics({}, L"relative-export.jsonl", cancelled).error, static_cast<DWORD>(ERROR_INVALID_PARAMETER));
}

TEST_F(LoggingTest, UncleanSessionIsRecognizedWithoutClaimingACrash)
{
    { Logger previous(Options()); EXPECT_TRUE(previous.Stop(std::chrono::seconds(2), false)); }
    Logger logger(Options()); auto snapshot = logger.Snapshot(); auto records = Read(snapshot);
    EXPECT_TRUE(std::any_of(records.begin(), records.end(), [](auto const& row) { return row.GetNamedString(L"event") == L"app.previous_session_unclean"; }));
    snapshot = {}; EXPECT_TRUE(logger.Stop());
}
TEST_F(LoggingTest, HistoryCleanupDoesNotRemoveUnknownFiles)
{
    { Logger previous(Options()); EXPECT_TRUE(previous.Stop()); }
    auto directories = fs::directory_iterator(Options().root);
    auto previousPath = directories->path();
    std::ofstream(previousPath / L"user-notes.txt") << "必须保留";
    auto options = Options(); options.retentionDays = 0;
    Logger logger(options); { auto snapshot = logger.Snapshot(); }
    EXPECT_TRUE(fs::exists(previousPath / L"user-notes.txt"));
    EXPECT_TRUE(logger.Stop());
}
TEST_F(LoggingTest, SnapshotPinPreventsRotationFromDeletingItsInput)
{
    auto options = Options(); options.maxFileBytes = 4096; options.maxFiles = 2;
    Logger logger(options);
    for (int i = 0; i < 6; ++i) logger.Context().Write(LogEvent::ConnectRequested);
    auto pinned = logger.Snapshot(); ASSERT_FALSE(pinned.files.empty());
    for (int i = 0; i < 40; ++i) logger.Context().Write(LogEvent::ConnectRequested);
    auto observation = logger.Snapshot();
    EXPECT_FALSE(Read(pinned).empty());
    size_t files = 0;
    for (auto const& directory : fs::directory_iterator(options.root))
        for (auto const& item : fs::directory_iterator(directory.path())) if (item.path().extension() == L".jsonl") ++files;
    EXPECT_LE(files, 2u);
    pinned = {}; observation = {}; logger.Stop();
}
TEST_F(LoggingTest, SnapshotTimeoutReturnsPromptlyWhenStorageIsBlocked)
{
    auto gate = std::make_shared<GateIo>(); auto entered = gate->entered.get_future();
    auto options = Options(); options.io = gate; Logger logger(options);
    auto cleanup = wil::scope_exit([&] { gate->Open(); logger.Stop(); });
    ASSERT_EQ(entered.wait_for(std::chrono::seconds(2)), std::future_status::ready);
    auto start = std::chrono::steady_clock::now();
    auto snapshot = logger.Snapshot(std::chrono::milliseconds(20));
    EXPECT_TRUE(snapshot.incomplete);
    EXPECT_LT(std::chrono::steady_clock::now() - start, std::chrono::seconds(1));
}
TEST_F(LoggingTest, WriteFaultIsNotReportedAsSuccessfulPersistence)
{
    auto options = Options(); auto failing = std::make_shared<FailingIo>(); failing->error = ERROR_WRITE_FAULT; options.io = failing;
    Logger logger(options); auto snapshot = logger.Snapshot();
    EXPECT_TRUE(snapshot.incomplete); EXPECT_GT(logger.Status().dropped, 0u);
    EXPECT_EQ(logger.Status().lastError, static_cast<DWORD>(ERROR_WRITE_FAULT));
    EXPECT_FALSE(logger.Stop());
}
TEST_F(LoggingTest, RecoveryKeepsTheMissingEventNotice)
{
    auto options = Options(); auto io = std::make_shared<FailingIo>(); auto recovered = io->recovered.get_future(); options.io = io;
    Logger logger(options);
    { auto failed = logger.Snapshot(); EXPECT_TRUE(failed.incomplete); }
    io->error = ERROR_SUCCESS;
    logger.Context().Write(LogEvent::ConnectRequested);
    EXPECT_EQ(recovered.wait_for(std::chrono::seconds(3)), std::future_status::ready);
    auto snapshot = logger.Snapshot(); auto records = Read(snapshot);
    EXPECT_TRUE(logger.Status().available); EXPECT_TRUE(snapshot.incomplete); EXPECT_GT(snapshot.status.dropped, 0u);
    EXPECT_TRUE(std::any_of(records.begin(), records.end(), [](auto const& row) { return row.GetNamedString(L"event") == L"diagnostics.storage_recovered"; }));
    snapshot = {}; EXPECT_FALSE(logger.Stop());
}
TEST_F(LoggingTest, FlushFailureCannotProduceACompleteMarker)
{
    auto options = Options(); options.io = std::make_shared<FlushFailureIo>();
    Logger logger(options); auto snapshot = logger.Snapshot();
    EXPECT_TRUE(snapshot.incomplete); EXPECT_FALSE(logger.Stop()); snapshot = {};
    for (auto const& directory : fs::directory_iterator(options.root)) EXPECT_FALSE(fs::exists(directory.path() / L"complete"));
}
TEST_F(LoggingTest, ExportSizeLimitReportsTruncation)
{
    Logger logger(Options());
    for (int i = 0; i < 20; ++i) logger.Context().Write(LogEvent::ConnectRequested);
    auto snapshot = logger.Snapshot(); std::atomic<bool> cancelled{false}; auto target = root / L"bounded.jsonl";
    auto result = ExportDiagnostics(snapshot, target.wstring(), cancelled, 4096);
    EXPECT_TRUE(result.succeeded); EXPECT_TRUE(result.incomplete); EXPECT_GT(result.skipped, 0u);
    EXPECT_LE(fs::file_size(target), 4096u);
    snapshot = {}; EXPECT_TRUE(logger.Stop());
}

TEST_F(LoggingTest, CancellationAndLateCleanupKeepTheSameOperation)
{
    Logger logger(Options());
    LoggedProvider provider; provider.blocked = true;
    auto entered = provider.entered.get_future();
    auto release = wil::scope_exit([&] { provider.Open(); });
    {
        ConnectionManager manager(provider, logger.Context()); manager.Refresh();
        auto operation = manager.ConnectAsync(L"private-device-id", LogTrigger::Startup);
        EXPECT_EQ(entered.wait_for(std::chrono::seconds(2)), std::future_status::ready);
        EXPECT_TRUE(manager.CancelConnection(L"private-device-id"));
        EXPECT_TRUE(manager.IsConnectionPending(L"private-device-id"));
        provider.Open(); operation.get(); manager.WaitForIdle();
        EXPECT_EQ(provider.closed, 1);
        EXPECT_EQ(manager.Snapshot().front().state, ConnectionState::Disconnected);
    }
    auto snapshot = logger.Snapshot(); auto records = Read(snapshot);
    double operation = 0; size_t terminal = 0, cancellations = 0, late = 0, cleanup = 0;
    for (auto const& record : records)
    {
        auto name = record.GetNamedString(L"event");
        if (name == L"connection.requested") operation = record.GetNamedNumber(L"operation_id");
        if (name == L"connection.cancel_requested" || name == L"connection.late_result" || name == L"connection.completed")
            EXPECT_EQ(record.GetNamedNumber(L"operation_id"), operation);
        if (name == L"connection.completed") { ++terminal; EXPECT_EQ(record.GetNamedString(L"outcome"), L"cancelled"); }
        cancellations += name == L"connection.cancel_requested";
        late += name == L"connection.late_result";
        if (name == L"connection.cleanup_completed" && record.GetNamedNumber(L"operation_id") == operation) ++cleanup;
    }
    EXPECT_GT(operation, 0); EXPECT_EQ(terminal, 1u); EXPECT_EQ(cancellations, 1u); EXPECT_EQ(late, 1u); EXPECT_EQ(cleanup, 1u);
    snapshot = {}; EXPECT_TRUE(logger.Stop());
}
TEST_F(LoggingTest, EnumerationAndDisconnectExceptionsAreLoggedWithoutChangingFallback)
{
    Logger logger(Options()); LoggedProvider provider;
    {
        ConnectionManager manager(provider, logger.Context());
        provider.enumerateThrows = true; manager.Refresh(); EXPECT_TRUE(manager.Snapshot().empty());
        provider.enumerateThrows = false; manager.Refresh(); manager.ConnectAsync(L"private-device-id").get();
        provider.disconnectThrows = true; manager.DisconnectAsync(L"private-device-id").get();
        EXPECT_EQ(manager.Snapshot().front().state, ConnectionState::Disconnected);
    }
    auto snapshot = logger.Snapshot(); auto records = Read(snapshot);
    size_t failures = 0;
    for (auto const& record : records)
        if ((record.GetNamedString(L"event") == L"device.enumerate_completed" || record.GetNamedString(L"event") == L"connection.disconnect_completed") &&
            record.GetNamedString(L"outcome") == L"failed") ++failures;
    EXPECT_EQ(failures, 2u); snapshot = {}; EXPECT_TRUE(logger.Stop());
}
