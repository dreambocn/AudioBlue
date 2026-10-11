#include <gtest/gtest.h>

#include "Settings.h"

#include <windows.h>

#include <cstdio>
#include <string>

using namespace AudioBule::Core;

namespace {

// 每个用例一个独立临时目录，避免互相污染
class TempDir
{
public:
    TempDir()
    {
        wchar_t tempDir[MAX_PATH] = {};
        DWORD length = ::GetTempPathW(MAX_PATH, tempDir);
        if (length == 0 || length >= MAX_PATH)
        {
            return;
        }
        m_path = std::wstring(tempDir, length) + L"AudioBuleTest_" +
            std::to_wstring(::GetCurrentProcessId()) + L"_" +
            std::to_wstring(reinterpret_cast<uintptr_t>(this));
        ::CreateDirectoryW(m_path.c_str(), nullptr);
    }

    ~TempDir()
    {
        if (!m_path.empty())
        {
            DeleteFileW(FilePath().c_str());
            ::RemoveDirectoryW(m_path.c_str());
        }
    }

    TempDir(TempDir const&) = delete;
    TempDir& operator=(TempDir const&) = delete;

    std::wstring FilePath() const { return m_path + L"\\settings.json"; }

private:
    std::wstring m_path;
};

void WriteTextFile(std::wstring const& path, std::wstring const& content)
{
    // 必须真正转成 UTF-8，不能用 std::string(content.begin(), content.end())
    // —— 那是 wchar_t→char 的窄化转换，会被 /WX 升级为错误。
    int required = ::WideCharToMultiByte(CP_UTF8, 0, content.data(),
        static_cast<int>(content.size()), nullptr, 0, nullptr, nullptr);
    if (required <= 0)
    {
        return;
    }

    std::string utf8(static_cast<size_t>(required), '\0');
    int written = ::WideCharToMultiByte(CP_UTF8, 0, content.data(),
        static_cast<int>(content.size()), utf8.data(), required, nullptr, nullptr);
    if (written <= 0)
    {
        return;
    }
    utf8.resize(static_cast<size_t>(written));

    HANDLE file = ::CreateFileW(path.c_str(), GENERIC_WRITE, 0, nullptr, CREATE_ALWAYS,
        FILE_ATTRIBUTE_NORMAL, nullptr);
    if (file == INVALID_HANDLE_VALUE)
    {
        return;
    }
    DWORD bytesWritten = 0;
    ::WriteFile(file, utf8.data(), static_cast<DWORD>(utf8.size()), &bytesWritten, nullptr);
    ::CloseHandle(file);
}

} // namespace

TEST(Settings, DefaultPathIsUnderLocalAppData)
{
    auto path = DefaultSettingsPath();
    EXPECT_FALSE(path.empty());
    EXPECT_NE(path.find(L"AudioBule"), std::wstring::npos);
    EXPECT_EQ(path.substr(path.size() - 13), std::wstring(L"settings.json"));
}

TEST(Settings, MissingFileYieldsDefaults)
{
    // Review Focus 第 2 条：用户首次启动，配置文件不存在，
    // 期望静默使用默认值正常启动，不弹任何错误。
    TempDir dir;
    auto settings = LoadSettings(dir.FilePath());
    EXPECT_TRUE(settings.autoReconnect);
    EXPECT_FALSE(settings.runAtStartup);
    EXPECT_TRUE(settings.lastConnectedDevices.empty());
}

TEST(Settings, RoundTripPreservesAllFields)
{
    TempDir dir;
    AppSettings original;
    original.autoReconnect = false;
    original.runAtStartup = true;
    original.lastConnectedDevices = { L"BTHENUM\\{AAA}\\0000", L"BTHENUM\\{BBB}\\0000" };

    ASSERT_TRUE(SaveSettings(original, dir.FilePath()));

    auto loaded = LoadSettings(dir.FilePath());
    EXPECT_FALSE(loaded.autoReconnect);
    EXPECT_TRUE(loaded.runAtStartup);
    ASSERT_EQ(loaded.lastConnectedDevices.size(), 2u);
    EXPECT_EQ(loaded.lastConnectedDevices[0], std::wstring(L"BTHENUM\\{AAA}\\0000"));
    EXPECT_EQ(loaded.lastConnectedDevices[1], std::wstring(L"BTHENUM\\{BBB}\\0000"));
}

TEST(Settings, CorruptJsonFallsBackToDefaults)
{
    // Review Focus 第 3 条：JSON 被手改坏，期望静默回落默认值，不崩溃。
    TempDir dir;
    WriteTextFile(dir.FilePath(), L"[[[{");

    auto settings = LoadSettings(dir.FilePath());
    EXPECT_TRUE(settings.autoReconnect);
    EXPECT_FALSE(settings.runAtStartup);
    EXPECT_TRUE(settings.lastConnectedDevices.empty());
}

TEST(Settings, TruncatedJsonFallsBackToDefaults)
{
    TempDir dir;
    WriteTextFile(dir.FilePath(), L"{\"autoReconnect\": fal");

    auto settings = LoadSettings(dir.FilePath());
    EXPECT_TRUE(settings.autoReconnect);
}

TEST(Settings, EmptyFileFallsBackToDefaults)
{
    TempDir dir;
    WriteTextFile(dir.FilePath(), L"");

    auto settings = LoadSettings(dir.FilePath());
    EXPECT_TRUE(settings.autoReconnect);
    EXPECT_TRUE(settings.lastConnectedDevices.empty());
}

TEST(Settings, UnknownFieldsIgnoredAndMissingFieldsUseDefaults)
{
    TempDir dir;
    WriteTextFile(dir.FilePath(), L"{\"autoReconnect\": false, \"futureField\": 123}");

    auto settings = LoadSettings(dir.FilePath());
    EXPECT_FALSE(settings.autoReconnect);   // 已知字段生效
    EXPECT_FALSE(settings.runAtStartup);    // 缺失字段回落默认
    EXPECT_TRUE(settings.lastConnectedDevices.empty());
}

TEST(Settings, WrongTypeFallsBackToDefault)
{
    // autoReconnect 写成了字符串而非布尔。期望：不崩溃，回落默认 true。
    TempDir dir;
    WriteTextFile(dir.FilePath(), L"{\"autoReconnect\": \"yes\"}");

    auto settings = LoadSettings(dir.FilePath());
    EXPECT_TRUE(settings.autoReconnect);
}

TEST(Settings, LastDevicesNotArrayFallsBackToEmpty)
{
    TempDir dir;
    WriteTextFile(dir.FilePath(), L"{\"lastConnectedDevices\": 42}");

    auto settings = LoadSettings(dir.FilePath());
    EXPECT_TRUE(settings.lastConnectedDevices.empty());
}

TEST(Settings, SaveCreatesMissingDirectory)
{
    TempDir dir;
    // 目标子目录尚不存在，Save 必须自己创建 —— 用户可能从未运行过旧版
    auto nested = dir.FilePath() + L".nested\\settings.json";
    AppSettings settings;
    settings.autoReconnect = false;
    ASSERT_TRUE(SaveSettings(settings, nested));

    auto loaded = LoadSettings(nested);
    EXPECT_FALSE(loaded.autoReconnect);
}

TEST(Settings, SaveDeduplicatesAndDropsEmptyIds)
{
    TempDir dir;
    AppSettings settings;
    settings.lastConnectedDevices = { L"devA", L"devA", L"", L"devB" };

    ASSERT_TRUE(SaveSettings(settings, dir.FilePath()));

    auto loaded = LoadSettings(dir.FilePath());
    ASSERT_EQ(loaded.lastConnectedDevices.size(), 2u);
    EXPECT_EQ(loaded.lastConnectedDevices[0], std::wstring(L"devA"));
    EXPECT_EQ(loaded.lastConnectedDevices[1], std::wstring(L"devB"));
}

TEST(Settings, SaveToUnwritablePathReturnsFalseWithoutThrowing)
{
    // 无效路径（盘符不存在）。期望：返回 false，不抛异常。
    bool result = true;
    bool threw = false;
    try
    {
        result = SaveSettings(AppSettings{}, L"Z:\\definitely\\not\\exist\\settings.json");
    }
    catch (...)
    {
        threw = true;
    }
    EXPECT_FALSE(threw);
    EXPECT_FALSE(result);
}

TEST(Settings, LoadFromEmptyPathReturnsDefaults)
{
    auto settings = LoadSettings(L"");
    EXPECT_TRUE(settings.autoReconnect);
}