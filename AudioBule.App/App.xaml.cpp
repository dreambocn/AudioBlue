#include "pch.h"

#include "App.xaml.h"

#include "MainWindow.xaml.h"

// 必须写成 winrt::Microsoft::UI::Xaml 而非 Microsoft::UI::Xaml：
// Windows SDK 头里也存在一个全局的 ::Microsoft 命名空间（C2872 歧义）。
using namespace winrt;
using namespace winrt::Microsoft::UI::Xaml;

namespace winrt::AudioBule::App::implementation
{

App::App()
{
    // 刻意**不**调用 InitializeComponent：WinUI 的 XAML 对象不应在构造函数里
    // 初始化，框架会在合适时机调用它。调用两次会导致重复加载 XAML 树。
    // 见 https://github.com/microsoft/cppwinrt/tree/master/nuget#initializecomponent

#if defined _DEBUG && !defined DISABLE_XAML_GENERATED_BREAK_ON_UNHANDLED_EXCEPTION
    UnhandledException([](IInspectable const&, UnhandledExceptionEventArgs const& e)
    {
        if (IsDebuggerPresent())
        {
            auto errorMessage = e.Message();
            (void)errorMessage;
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