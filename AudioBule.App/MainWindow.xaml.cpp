#include "pch.h"

#include "MainWindow.xaml.h"

#if __has_include("MainWindow.g.cpp")
#include "MainWindow.g.cpp"
#endif

using namespace winrt;
using namespace winrt::Microsoft::UI::Xaml;

namespace winrt::AudioBule::App::implementation
{

int32_t MainWindow::Placeholder()
{
    return 0;
}

void MainWindow::Placeholder(int32_t)
{
}

} // namespace winrt::AudioBule::App::implementation