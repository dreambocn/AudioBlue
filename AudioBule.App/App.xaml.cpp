#include "pch.h"

#include "App.xaml.h"

using namespace winrt;
using namespace winrt::Microsoft::UI::Xaml;
using namespace winrt::Microsoft::UI::Xaml::Controls;

// 同 App.xaml.cpp：::Microsoft 与 winrt::Microsoft 并存，必须限定。
namespace winrt::AudioBule::App::implementation
{

App::App()
{
    // 刻意**不**调用 InitializeComponent：WinUI 的 XAML 对象不应在构造函数里
    // 初始化，框架会在合适时机调用它。调用两次会导致重复加载 XAML 树。
    // 见 https://github.com/microsoft/cppwinrt/tree/master/nuget#initializecommit

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
    // 窗口用代码构造而非 XAML：<Page> 需要 MIDL 编译 .idl 得到
    // MainWindow_base，而闭合 Microsoft.UI.Xaml.Window 的依赖所需的
    // Microsoft.UI.Composition / Windowing / Dispatching winmd 只随已安装的
    // Windows App SDK 运行时分发，本机没有，MIDL 会一直报 MIDL2011。
    window = Window();

    TextBlock title;
    title.Text(L"AudioBule");
    title.FontSize(28);
    title.HorizontalAlignment(HorizontalAlignment::Center);
    title.VerticalAlignment(VerticalAlignment::Center);

    window.Content(title);
    window.Activate();
}

} // namespace winrt::AudioBule::App::implementation