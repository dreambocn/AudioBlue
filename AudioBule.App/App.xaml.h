#pragma once
#include "App.xaml.g.h"
#include "MainWindow.xaml.h"
#include "TrayIconService.h"
#include "QuickPanel.h"
#include "DesktopIntegration.h"
#include <memory>

namespace winrt::AudioBule::App::implementation
{
struct App : AppT<App>
{
    App();
    ~App();
    void OnLaunched(Microsoft::UI::Xaml::LaunchActivatedEventArgs const& e);
private:
    void ApplyTheme();
    void ApplyPreferences();
    void ChangePreferences(::AudioBule::Core::AppSettings const& settings);
    winrt::fire_and_forget RefreshStartup();
    winrt::fire_and_forget ChangeStartup(bool enabled);
    void OpenBluetoothSettings();
    void RenderDevices();
    void EntryChanged(::AudioBule::Core::ConnectionEntry const& entry);
    void SaveConfiguration();
    winrt::fire_and_forget RefreshDevices(bool reconnect);
    winrt::fire_and_forget OperateDevice(std::wstring id, bool disconnect);
    winrt::fire_and_forget Shutdown();
    // 逆序析构：窗口/托盘停用后，manager 等待操作，provider 最后释放会话。
    ::AudioBule::Core::WinRtDeviceProvider m_provider;
    ::AudioBule::Core::ConnectionManager m_manager;
    ::AudioBule::Core::AppSettings m_settings;
    std::unique_ptr<::AudioBule::App::UI::UiText> m_text;
    std::unique_ptr<::AudioBule::App::UI::DesktopIntegration> m_desktop;
    com_ptr<MainWindow> m_window;
    Microsoft::UI::Dispatching::DispatcherQueue m_queue{ nullptr };
    std::unique_ptr<::AudioBule::App::UI::QuickPanel> m_quick;
    std::unique_ptr<::AudioBule::App::TrayService::TrayIconService> m_tray;
    std::map<std::wstring, ::AudioBule::Core::ConnectionState> m_previousStates;
    std::set<std::wstring> m_pendingDevices;
    ::AudioBule::Core::SimpleEvent<::AudioBule::Core::ConnectionEntry>::SubscriptionId m_entryToken = 0;
    ::AudioBule::Core::SimpleEvent<>::SubscriptionId m_entriesToken = 0;
    bool m_refreshing = false, m_stopping = false, m_startupPending = false, m_notificationsAvailable = false;
};
}
