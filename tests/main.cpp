// 测试入口。不直接用 gtest_main.cc 的默认 main，因为 Core 用的
// PathIO / JsonObject 等 WinRT 静态 API 需要已初始化的 apartment。
//
// gtest_main.cc 不参与编译（已在 vcxproj 中移除），入口在此自定义。
#include <gtest/gtest.h>

#include <winrt/Windows.Foundation.h>

int main(int argc, char** argv)
{
    // 多线程 apartment：测试里 ConnectionManager 会起后台线程跑
    // Connect/Disconnect，STA 会让这些调用互相阻塞。
    winrt::init_apartment(winrt::apartment_type::multi_threaded);

    ::testing::InitGoogleTest(&argc, argv);
    int result = RUN_ALL_TESTS();

    winrt::uninit_apartment();
    return result;
}