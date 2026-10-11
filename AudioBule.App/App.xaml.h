#pragma once

#include "App.xaml.g.h"

namespace winrt::AudioBule::App::implementation
{

struct App : AppT<App>
{
    App();

    // WinUI 3 用自己的 LaunchActivatedEventArgs（Microsoft.UI.Xaml 命名空间），
    // 不是 UWP 的 Windows::ApplicationModel::Activation 那个。
    void OnLaunched(Microsoft::UI::Xaml::LaunchActivatedEventArgs const& e);

private:
    winrt::Microsoft::UI::Xaml::Window window{ nullptr };
};

} // namespace winrt::AudioBule::App::implementation