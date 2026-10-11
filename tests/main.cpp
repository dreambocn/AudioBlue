// 冒烟用例：验证 GoogleTest 工程本身配置正确、Core 库能链接进来。
// Task 2 起会被真正的用例覆盖。
#include <gtest/gtest.h>

TEST(Harness, SmokeTest)
{
    EXPECT_EQ(2 + 2, 4);
    EXPECT_NE(2 + 2, 5);
    EXPECT_TRUE(true);
}