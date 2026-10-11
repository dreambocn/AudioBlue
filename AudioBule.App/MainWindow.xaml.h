#pragma once
#include "MainWindow.g.h"
#include "DevicePresenter.h"
#include "Settings.h"
#include <functional>
#include <set>

namespace winrt::AudioBule::App::implementation
{
struct MainWindow : MainWindowT<MainWindow>
{
    MainWindow() = default;
    // 组件初始化在 make_self 完成以后执行。
    void Initialize(::AudioBule::App::UI::UiText& text, std::function<void()> refresh,
        std::function<void()> addDevice, std::function<void(std::wstring const&, bool)> operate,
        std::function<void()> exit, std::function<void(::AudioBule::Core::AppSettings const&)> preferences);
    void ApplyPreferences(::AudioBule::Core::AppSettings const& settings, bool startupPending = false, bool notificationsAvailable = true);
    void Navigate(std::wstring const& page);
    void Render(std::vector<::AudioBule::Core::ConnectionEntry> const& entries);
    void SetRefreshing(bool refreshing);
    void SetOperationPending(std::wstring const& id, bool pending);
    void SetStopping();
    void SetStatus(std::wstring const& status);
    void SetStatusKey(wchar_t const* key);
    void Show();
    void Toggle();
    winrt::fire_and_forget ConfirmExit();
    void CloseForExit();
    void SetTrayAvailable(bool available) { m_trayAvailable = available; }
    HWND Handle() const;
    int32_t Placeholder();
    void Placeholder(int32_t value);
private:
    void BuildSettings();
    void BuildAbout();
    void UpdateCaption();
    static LRESULT CALLBACK WindowProcedure(HWND, UINT, WPARAM, LPARAM, UINT_PTR, DWORD_PTR);
    ::AudioBule::App::UI::UiText* m_text = nullptr;
    ::AudioBule::App::UI::DevicePresenter m_devices;
    ::AudioBule::Core::AppSettings m_settings;
    std::vector<::AudioBule::Core::ConnectionEntry> m_entries;
    std::set<std::wstring> m_pendingDevices;
    std::wstring m_statusKey;
    std::function<void()> m_addDevice, m_exit;
    std::function<void(::AudioBule::Core::AppSettings const&)> m_preferences;
    bool m_allowClose = false, m_stopping = false, m_filtered = false, m_refreshing = false;
    bool m_trayAvailable = true;
    bool m_updating = false, m_startupPending = false, m_notificationsAvailable = true, m_confirming = false;
};
}
namespace winrt::AudioBule::App::factory_implementation
{
struct MainWindow : MainWindowT<MainWindow, implementation::MainWindow> {};
}
