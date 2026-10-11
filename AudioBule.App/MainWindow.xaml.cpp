#include "pch.h"

#include "MainWindow.xaml.h"

#if __has_include("MainWindow.g.cpp")
#include "MainWindow.g.cpp"
#endif

using namespace winrt;
using namespace AudioBule::App::implementation;

namespace winrt::AudioBule::App::implementation
{

MainWindow::MainWindow() noexcept
{
    InitializeComponent();
}

} // namespace winrt::AudioBule::App::implementation