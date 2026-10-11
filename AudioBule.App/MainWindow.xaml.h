#pragma once
#include "MainWindow.g.h"
#include "ConnectionEntry.h"
#include <functional>
#include <map>
#include <set>

namespace winrt::AudioBule::App::implementation
{
struct MainWindow : MainWindowT<MainWindow>
{
    MainWindow() = default;
    // make 完成后再加载 XAML，避免在构造期间初始化组件。
    void Initialize(std::function<void()> refresh, std::function<void()> addDevice,
        std::function<void(std::wstring const&, bool)> operate, std::function<void()> exit);
    void Render(std::vector<::AudioBule::Core::ConnectionEntry> const& entries);
    void SetRefreshing(bool refreshing);
    void SetOperationPending(std::wstring const& id, bool pending);
    void SetStopping();
    void SetStatus(std::wstring const& status);
    void Show();
    void Toggle();
    void CloseForExit();
    HWND Handle() const;
    int32_t Placeholder();
    void Placeholder(int32_t value);
private:
    struct DeviceRow
    {
        Microsoft::UI::Xaml::Controls::TextBlock name{ nullptr };
        Microsoft::UI::Xaml::Controls::TextBlock status{ nullptr };
        Microsoft::UI::Xaml::Controls::TextBlock error{ nullptr };
        Microsoft::UI::Xaml::Controls::Button action{ nullptr };
        Microsoft::UI::Xaml::Controls::ProgressRing progress{ nullptr };
    };
    std::map<std::wstring, DeviceRow> m_rows;
    std::set<std::wstring> m_pendingDevices;
    std::function<void(std::wstring const&, bool)> m_operate;
    std::function<void()> m_exit;
    bool m_allowClose = false;
    bool m_stopping = false;
};
}
namespace winrt::AudioBule::App::factory_implementation
{
struct MainWindow : MainWindowT<MainWindow, implementation::MainWindow> {};
}
