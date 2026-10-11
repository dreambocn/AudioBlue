#include "pch.h"

#include "App.xaml.h"

#include "MainWindow.xaml.h"

#if __has_include("App.xaml.g.cpp")
#include "App.xaml.g.cpp"
#endif

using namespace winrt;
using namespace Windows::ApplicationModel::Activation;
using namespace Windows::UI::Xaml;
using namespace AudioBule::App::implementation;

namespace winrt::AudioBule::App::implementation
{

App::App() noexcept
{
    InitializeComponent();
}

void App::OnLaunched(LaunchActivatedEventArgs const& e)
{
    auto window = Window();
    window.Activate();
}

} // namespace winrt::AudioBule::App::implementation