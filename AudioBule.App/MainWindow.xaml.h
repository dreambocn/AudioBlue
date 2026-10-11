#pragma once

// 必须包含 MainWindow.g.h（MIDL + C++/WinRT 产物），**不是** MainWindow.xaml.g.h。
// 前者先定义 implementation::MainWindow_base，末尾再自行 include
// MainWindow.xaml.g.h（其中的 MainWindowT 从 MainWindow_base 派生）。
// 直接包含 .xaml.g.h 会跳过 base 定义并报 C2039。
#include "MainWindow.g.h"

namespace winrt::AudioBule::App::implementation
{

struct MainWindow : MainWindowT<MainWindow>
{
    MainWindow()
    {
        // 刻意不调用 InitializeComponent：WinUI 的 XAML 对象不应在构造函数里
        // 初始化，框架会在合适时机调用。
    }

    // IDL 里声明的属性会生成 Placeholder() / Placeholder(int32_t) 两个方法，
// 所以这里必须是方法，不能是字段。
    int32_t Placeholder();
    void Placeholder(int32_t value);
};

} // namespace winrt::AudioBule::App::implementation

namespace winrt::AudioBule::App::factory_implementation
{

struct MainWindow : MainWindowT<MainWindow, implementation::MainWindow>
{
};

} // namespace winrt::AudioBule::App::factory_implementation