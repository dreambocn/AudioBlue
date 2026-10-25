#include <gtest/gtest.h>
#include "Logger.h"
#include "DiagnosticPrivacy.h"
#include "StringUtil.h"
#include <filesystem>
#include <fstream>
#include <thread>
#include <vector>
#include <algorithm>

using namespace AudioBule::Core;

// 持续负载只由专项脚本显式运行，不增加每次核心回归的耗时。
TEST(LoggingBenchmark, DISABLED_Throughput)
{
    wchar_t rootText[32768]{}, secondsText[16]{}, reportText[32768]{};
    ASSERT_GT(::GetEnvironmentVariableW(L"AUDIOBULE_TEST_ROOT", rootText, static_cast<DWORD>(std::size(rootText))), 0u);
    ASSERT_GT(::GetEnvironmentVariableW(L"AUDIOBULE_LOG_BENCH_SECONDS", secondsText, static_cast<DWORD>(std::size(secondsText))), 0u);
    ASSERT_GT(::GetEnvironmentVariableW(L"AUDIOBULE_LOG_BENCH_REPORT", reportText, static_cast<DWORD>(std::size(reportText))), 0u);
    auto seconds = std::stoi(secondsText);
    ASSERT_GE(seconds, 5); ASSERT_LE(seconds, 120);
    auto root = std::filesystem::path(rootText);
    ASSERT_TRUE(root.is_absolute()); ASSERT_TRUE(std::filesystem::path(reportText).is_absolute());
    LoggerOptions options; options.root = (root / L"benchmark-logs").wstring();
    Logger logger(options);
    // 预热并释放快照，避免基准期间人为固定归档文件。
    {
        auto snapshot = logger.Snapshot();
        // 历史日志可能因导出预算被截断；性能预热只验证当前会话的写入状态。
        ASSERT_TRUE(snapshot.status.available);
        ASSERT_EQ(snapshot.status.dropped, 0u);
    }
    std::array<std::vector<double>, 4> samples;
    std::vector<std::thread> threads;
    for (size_t i = 0; i < samples.size(); ++i)
    {
        threads.emplace_back([&, i] {
            auto context = logger.Context().Operation(LogTrigger::Manual, L"性能测试设备");
            auto start = std::chrono::steady_clock::now();
            for (int j = 0; j < seconds * 250; ++j)
            {
                auto before = std::chrono::steady_clock::now();
                context.Write(LogEvent::ConnectRequested);
                samples[i].push_back(std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - before).count());
                std::this_thread::sleep_until(start + std::chrono::milliseconds((j + 1) * 4));
            }
        });
    }
    for (auto& thread : threads) thread.join();
    std::vector<double> durations;
    for (auto& sample : samples) durations.insert(durations.end(), sample.begin(), sample.end());
    std::sort(durations.begin(), durations.end());
    ASSERT_FALSE(durations.empty());
    auto p95 = durations[durations.size() * 95 / 100];
    auto p99 = durations[durations.size() * 99 / 100];
    EXPECT_TRUE(logger.Stop());
    auto status = logger.Status();
    std::ofstream report(std::filesystem::path(reportText), std::ios::binary | std::ios::trunc);
    ASSERT_TRUE(report.good());
    report << "{\"producers\":4,\"events_per_second\":1000,\"seconds\":" << seconds <<
        ",\"events\":" << durations.size() << ",\"p95_ms\":" << p95 << ",\"p99_ms\":" << p99 <<
        ",\"dropped\":" << status.dropped << ",\"write_failures\":" << status.writeFailures << "}\n";
    report.close();
    EXPECT_EQ(status.dropped, 0u); EXPECT_EQ(status.writeFailures, 0u);
    EXPECT_LE(p95, 1.0); EXPECT_LE(p99, 5.0);
}
