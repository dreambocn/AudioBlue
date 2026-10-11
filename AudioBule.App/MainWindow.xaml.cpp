#include "pch.h"

#include "MainWindow.xaml.h"

#if __has_include("MainWindow.g.cpp")
#include "MainWindow.g.cpp"
#endif

// 同 App.xaml.cpp：::Microsoft 与 winrt::Microsoft 并存，必须限定。
using namespace winrt;
using namespace winrt::Microsoft::UI::Xaml;

namespace winrt::AudioBule::App::implementation
{
    // MainWindow 目前是空窗口，设备列表界面在后续任务里加。
} // namespace winrt::AudioBule::App::implementation