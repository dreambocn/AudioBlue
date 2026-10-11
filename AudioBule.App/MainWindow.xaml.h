#pragma once

#include "MainWindow.xaml.g.h"

namespace winrt::AudioBule::App::implementation
{

struct MainWindow : MainWindowT<MainWindow>
{
    MainWindow() noexcept;
};

} // namespace winrt::AudioBule::App::implementation

namespace winrt::AudioBule::App::factory_implementation
{

struct MainWindow : MainWindowT<MainWindow, implementation::MainWindow>
{
};

} // namespace winrt::AudioBule::App::factory_implementation