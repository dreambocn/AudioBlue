// AudioBule 入口点。
//
// ⚠️ WinUI 3 的 wWinMain 签名是特殊的：第一个参数是 WinRT initInstance
// （由 WinUI 3 的 XAML 框架传入），不是 HINSTANCE / PSTR。
// 这是 Windows App SDK 定义的入口约定，不要改成传统 WinMain 形式。
//
// 生成的 App 类（winrt/AudioBule.App.h）由 XAML 编译器根据
// App.xaml 的 x:Class="AudioBule.App.App" 产生，因此 RootNamespace
// 必须是 AudioBule.App，否则找不到这个头。
#include "pch.h"

#include "winrt/AudioBule.App.h"

using namespace winrt;

int APIENTRY wWinMain(WinRT initInstance, _In_ HINSTANCE /*hInstance*/,
    _In_opt_ HINSTANCE /*hPrevInstance*/, _In_ LPWSTR /*lpCmdLine*/,
    _In_ int /*nCmdShow*/)
{
    // 初始化 COM apartment。WinUI 3 的 UI 线程必须是 STA。
    winrt::init_apartment(winrt::apartment_type::single_threaded);

    winrt::AudioBule::App::App().Launch(initInstance);
}