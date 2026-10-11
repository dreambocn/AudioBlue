#include <gtest/gtest.h>

#include "StringUtil.h"

#include <string>

using namespace AudioBule::Core;

TEST(StringUtil, AsciiRoundTrip)
{
    EXPECT_EQ(WideToUtf8(L"hello"), std::string("hello"));
    EXPECT_EQ(Utf8ToWide("hello"), std::wstring(L"hello"));
}

TEST(StringUtil, EmptyStringRoundTrip)
{
    EXPECT_TRUE(WideToUtf8(L"").empty());
    EXPECT_TRUE(Utf8ToWide("").empty());
}

TEST(StringUtil, ChineseRoundTrip)
{
    // 宽字符是主表示；窄字符只是日志/调试用的次要表示。
    EXPECT_EQ(Utf8ToWide("蓝牙音频"), std::wstring(L"蓝牙音频"));
    EXPECT_EQ(WideToUtf8(L"蓝牙音频"), std::string("蓝牙音频"));
}

TEST(StringUtil, SurrogatePairRoundTrip)
{
    // U+1F50A 扬声器 emoji，需 UTF-16 代理对处理正确
    auto s = Utf8ToWide("\xF0\x9F\x94\x8A");
    ASSERT_EQ(s.size(), static_cast<size_t>(2)); // 代理对 = 2 个 wchar
    EXPECT_EQ(WideToUtf8(s), std::string("\xF0\x9F\x94\x8A"));
}

TEST(StringUtil, EmbeddedNulIsTruncatedByCStringConvention)
{
    // WideToUtf8 按 wcslen 语义处理，遇 NUL 停止。这是刻意的：
    // 错误文案与设备名在实践中不含内嵌 NUL。
    EXPECT_EQ(WideToUtf8(L"ab\0cd").size(), static_cast<size_t>(2));
}

TEST(StringUtil, InvalidUtf8DoesNotThrow)
{
    // 0xFF 不是合法的 UTF-8 起始字节。期望：替换为 U+FFFD，不抛异常。
    auto s = Utf8ToWide("\xFF\xFE");
    EXPECT_FALSE(s.empty());
}

TEST(StringUtil, FormatWin32ErrorIsUppercaseHex)
{
    EXPECT_EQ(FormatWin32Error(0x8007001Fu), std::wstring(L"0x8007001F"));
    EXPECT_EQ(FormatWin32Error(0u), std::wstring(L"0x00000000"));
}

TEST(StringUtil, FormatMessageForHresultIsNeverEmpty)
{
    // 系统有本地化文本的码
    auto known = FormatMessageForHresult(static_cast<HRESULT>(0x8007001Fu));
    EXPECT_FALSE(known.empty());

    // 人为构造的几乎不可能有本地化文本的码，用来验证十六进制回落路径
    auto fallback = FormatMessageForHresult(static_cast<HRESULT>(0x00001234u));
    EXPECT_FALSE(fallback.empty());

    // 回落时不应带尾随空白
    auto trimmed = fallback;
    while (!trimmed.empty() &&
           (trimmed.back() == L'\r' || trimmed.back() == L'\n' || trimmed.back() == L' '))
    {
        trimmed.pop_back();
    }
    EXPECT_EQ(trimmed, fallback);
}