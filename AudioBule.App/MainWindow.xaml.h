#pragma once

// 包含 MainWindow.g.h（MIDL + C++/WinRT 生成），**不是** MainWindow.xaml.g.h。
// 前者先定义 implementation::MainWindow_base，末尾再自行 include
// MainWindow.xaml.g.h（其中的 MainWindowT 从 MainWindow_base 派生）。
// 直接包含 .xaml.g.h 会跳过 base 定义，报
//   "MainWindow_base" 不是 "winrt::AudioBule::App::implementation" 的成员。
#include "MainWindow.g.h"

namespace winrt::AudioBule::App::implementation
{

struct MainWindow : MainWindowT<MainWindow>
{
    MainWindow()
    {
        // 与 App 一样：不调用 InitializeComponent。
    }
};

} // namespace winrt::AudioBule::App::implementation

namespace winrt::AudioBule::App::factory_implementation
{

struct MainWindow : MainWindowT<MainWindow, implementation::MainWindow>
{
};

} // namespace winrt::AudioBule::App::factory_implementation