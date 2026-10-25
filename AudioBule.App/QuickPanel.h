#pragma once
#include "DevicePresenter.h"
#include "Settings.h"
#include <winrt/Microsoft.UI.Windowing.h>

namespace AudioBule::App::UI
{
// 独立工具窗口承载托盘面板，不进入任务栏；所有设备操作仍经 App 调度。
class QuickPanel
{
public:
    struct Callbacks
    {
        std::function<void(std::wstring const&, DeviceAction)> operate;
        std::function<void(std::wstring const&)> navigate;
        std::function<void()> exit, restoreFocus;
    };
    QuickPanel(UiText& text, Callbacks callbacks);
    ~QuickPanel();
    void ApplyPreferences(Core::AppSettings const& settings);
    void Render(std::vector<Core::ConnectionEntry> const& entries, std::set<std::wstring> const& pending);
    void Toggle(POINT anchor, bool keyboard = false);
    void ShowMenu(POINT anchor, bool keyboard = false);
    void Hide();
private:
    void Position();
    void BuildMenu();
    UiText& m_text;
    Callbacks m_callbacks;
    winrt::Microsoft::UI::Xaml::Window m_window{ nullptr };
    winrt::Microsoft::UI::Windowing::AppWindow m_appWindow{ nullptr };
    winrt::Microsoft::UI::Xaml::Controls::Grid m_root{ nullptr }, m_devicesPage{ nullptr };
    winrt::Microsoft::UI::Xaml::Controls::StackPanel m_rows{ nullptr };
    winrt::Microsoft::UI::Xaml::Controls::TextBlock m_summary{ nullptr }, m_empty{ nullptr };
    winrt::Microsoft::UI::Xaml::Controls::Button m_more{ nullptr }, m_open{ nullptr };
    winrt::Microsoft::UI::Xaml::Controls::MenuFlyoutPresenter m_menu{ nullptr };
    DevicePresenter m_devices;
    HWND m_handle = nullptr;
    POINT m_anchor{};
    size_t m_count = 0;
    bool m_menuMode = false, m_closing = false;
};
}
