#pragma once

#include "App.xaml.g.h"

namespace winrt::AudioBule::App::implementation
{

struct App : AppT<App>
{
    App() noexcept;

    void OnLaunched(Windows::ApplicationModel::Activation::LaunchActivatedEventArgs const& e);
};

} // namespace winrt::AudioBule::App::implementation