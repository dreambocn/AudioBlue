#include <gtest/gtest.h>

#include "IconFactory.h"

#include <windows.h>

#include <vector>
#include <algorithm>

using namespace AudioBule::Core;

namespace {

// 读取某个主题的 RCDATA 资源原始字节。
std::vector<BYTE> ReadIconResource(int resourceId)
{
    std::vector<BYTE> bytes;

    HRSRC resource = FindResourceW(nullptr, MAKEINTRESOURCEW(resourceId), RT_RCDATA);
    if (resource == nullptr)
    {
        return bytes;
    }

    HGLOBAL handle = LoadResource(nullptr, resource);
    if (handle == nullptr)
    {
        return bytes;
    }

    auto* data = static_cast<BYTE*>(LockResource(handle));
    auto size = SizeofResource(nullptr, resource);
    if (data == nullptr || size == 0)
    {
        return bytes;
    }

    bytes.assign(data, data + size);
    return bytes;
}

} // namespace

TEST(IconFactory, BothThemeResourcesAreEmbedded)
{
    // 201 = 深色任务栏用（浅色图形），202 = 浅色任务栏用（深色图形）
    EXPECT_FALSE(ReadIconResource(201).empty());
    EXPECT_FALSE(ReadIconResource(202).empty());
}

TEST(IconFactory, ThemeResourcesAreDistinct)
{
    // 两套资源必须真的不同 —— 否则「深浅主题自适应托盘图标」是假的。
    auto dark = ReadIconResource(201);
    auto light = ReadIconResource(202);
    ASSERT_FALSE(dark.empty());
    ASSERT_FALSE(light.empty());
    EXPECT_NE(dark, light);
}

TEST(IconFactory, ResourcesAreMultiResolutionIco)
{
    // ICONDIR：reserved=0, type=1(icon), count>=1。Build-Icons.ps1 生成 16/24/32/48。
    auto dark = ReadIconResource(201);
    ASSERT_GE(dark.size(), static_cast<size_t>(6));
    EXPECT_EQ(dark[0], 0);
    EXPECT_EQ(dark[1], 0);
    EXPECT_EQ(dark[2], 1);                       // type = icon
    EXPECT_GE(dark[4], 4);                       // 至少 4 个尺寸
}

TEST(IconFactory, LightTrayIconIsCreated)
{
    TrayIcon icon = CreateTrayIcon(false);
    EXPECT_TRUE(static_cast<bool>(icon));
    DestroyTrayIcon(icon);
}

TEST(IconFactory, DarkTrayIconIsCreated)
{
    TrayIcon icon = CreateTrayIcon(true);
    EXPECT_TRUE(static_cast<bool>(icon));
    DestroyTrayIcon(icon);
}

TEST(IconFactory, IconHasPlausibleDimensions)
{
    // .ico 内含 16/24/32/48 四档，运行时按系统小图标尺寸选择并缩放。
    TrayIcon icon = CreateTrayIcon(false);
    ASSERT_TRUE(static_cast<bool>(icon));

    ICONINFO info = {};
    // 用 ASSERT_TRUE 而非 ASSERT_NE：后者的有符号/无符号比较
    // 会在 gtest 宏内部触发 C4389，而测试工程开了 /WX。
    ASSERT_TRUE(GetIconInfo(reinterpret_cast<HICON>(icon.handle), &info) != 0);

    ASSERT_NE(info.hbmColor, nullptr);
    BITMAP colorBitmap = {};
    GetObjectW(info.hbmColor, sizeof(colorBitmap), &colorBitmap);
    EXPECT_GE(colorBitmap.bmWidth, 16L);
    EXPECT_LE(colorBitmap.bmWidth, static_cast<LONG>((std::max)(48, GetSystemMetrics(SM_CXSMICON))));
    EXPECT_EQ(colorBitmap.bmHeight, colorBitmap.bmWidth);

    // 注意：带 alpha 通道的图标，其 hbmMask 与 hbmColor 同高（而不是 2 倍）。
    // 那只适用于 1bpp XOR/AND 掩码的老式图标，这里不能断言倍数。

    DeleteObject(info.hbmColor);
    if (info.hbmMask != nullptr)
    {
        DeleteObject(info.hbmMask);
    }
    DestroyTrayIcon(icon);
}

TEST(IconFactory, RepeatedCreationDoesNotCrash)
{
    // GDI 泄漏在托盘反复切换主题时会累积成用户可见的问题。
    // 这里验证「反复创建不崩」，真正的泄漏检测在手动验证清单里
    // （反复切主题后看任务管理器的 GDI 对象数）。
    for (int i = 0; i < 200; ++i)
    {
        TrayIcon icon = CreateTrayIcon((i % 2) == 0);
        EXPECT_TRUE(static_cast<bool>(icon));
        DestroyTrayIcon(icon);
    }
}

TEST(IconFactory, DestroyToleratesNull)
{
    DestroyTrayIcon(TrayIcon{});   // 不得崩溃
}
TEST(IconFactory, ConnectedBadgeResourcesLoadForBothTaskbarThemes)
{
    // 徽标资源必须独立存在，且能在运行时创建有效图标。
    for (auto dark : { false, true }) {
        auto resource = ReadIconResource(dark ? 203 : 204);
        ASSERT_FALSE(resource.empty());
        EXPECT_NE(resource, ReadIconResource(dark ? 201 : 202));
        auto icon = CreateTrayIcon(dark, true);
        EXPECT_TRUE(static_cast<bool>(icon));
        DestroyTrayIcon(icon);
    }
}
