#include "pch.h"

#include "App.xaml.h"

#include "MainWindow.xaml.h"

using namespace winrt;
// ::Microsoft（Windows SDK 头）与 winrt::Microsoft 并存，必须限定，否则 C2872。
using namespace winrt::Microsoft::UI::Xaml;

namespace winrt::AudioBule::App::implementation
{

App::App()
{
    // 刻意不调用 InitializeComponent：WinUI 的 XAML 对象不应在构造函数里
    // 初始化，框架会在合适时机调用它。
    // 见 https://github.com/microsoft/cppwinrt/tree/master/nuget#initializecomponent

#if defined _DEBUG && !defined DISABLE_XAML_GENERATED_BREAK_ON_UNHANDLED_EXCEPTION
    UnhandledException([](IInspectable const&, UnhandledExceptionEventArgs const&)
    {
        if (IsDebuggerPresent())
        {
            __debugbreak();
        }
    });
#endif
}

void App::OnLaunched([[maybe_unused]] LaunchActivatedEventArgs const& e)
{
    window = make<MainWindow>();
    window.Activate();
}

} // namespace winrt::AudioBule::App::implementation