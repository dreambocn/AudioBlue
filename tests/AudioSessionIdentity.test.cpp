#include <gtest/gtest.h>
#include "AudioSessionIdentity.h"

using namespace AudioBule::Core;

TEST(AudioSessionIdentity, MatchesOriginalChineseAndEnglishNames)
{
    std::vector<DeviceInfo> devices{ { L"xiaomi", L"DreamBo的Xiaomi 15" }, { L"redmi", L"Redmi" } };
    EXPECT_EQ(MatchA2dpSessionDevice(L"麦克风 (DreamBo的Xiaomi 15 A2DP SNK)", devices), 0u);
    EXPECT_EQ(MatchA2dpSessionDevice(L"Microphone (Redmi A2DP SNK)", devices), 1u);
}

TEST(AudioSessionIdentity, DoesNotMatchOtherMicrophonesOrPartialPhoneNames)
{
    std::vector<DeviceInfo> devices{ { L"xiaomi", L"Xiaomi 15" } };
    EXPECT_FALSE(MatchA2dpSessionDevice(L"麦克风 (Xiaomi 15)", devices));
    EXPECT_FALSE(MatchA2dpSessionDevice(L"麦克风 (DreamBo的Xiaomi 15 A2DP SNK)", devices));
    EXPECT_FALSE(MatchA2dpSessionDevice(L"麦克风 (Xiaomi 15 Ultra A2DP SNK)", devices));
    EXPECT_FALSE(MatchA2dpSessionDevice(L"麦克风 (Xiaomi 15 A2DP SNK) extra", devices));
}

TEST(AudioSessionIdentity, RefusesAmbiguousDuplicateNames)
{
    // 相同手机名不等于相同设备；无法区分就保持系统显示。
    std::vector<DeviceInfo> devices{ { L"first", L"Phone" }, { L"second", L"Phone" } };
    EXPECT_FALSE(MatchA2dpSessionDevice(L"Microphone (Phone A2DP SNK)", devices));
}

TEST(AudioSessionIdentity, IgnoresEmptyIdentifiersAndNames)
{
    std::vector<DeviceInfo> devices{ { L"", L"Phone" }, { L"second", L"" } };
    EXPECT_FALSE(MatchA2dpSessionDevice(L"Microphone (Phone A2DP SNK)", devices));
    EXPECT_FALSE(MatchA2dpSessionDevice(L"Microphone ( A2DP SNK)", devices));
    EXPECT_FALSE(MatchA2dpSessionDevice(L"", devices));
}

TEST(AudioSessionIdentity, PreservesPunctuationAndUnicodeInPhoneNames)
{
    std::vector<DeviceInfo> devices{ { L"phone", L"手机 (工作) · 15" } };
    EXPECT_EQ(MatchA2dpSessionDevice(L"麦克风 (手机 (工作) · 15 A2DP SNK)", devices), 0u);
}
