#pragma once
#include "App.xaml.g.h"
#include "MainWindow.xaml.h"
#include "TrayIconService.h"
#include "QuickPanel.h"
#include "DesktopIntegration.h"
#include "AudioSessionIdentity.h"
#include "DiagnosticsController.h"
#include <memory>

namespace winrt::AudioBule::App::implementation
{
struct App : AppT<App>
{
    App();
    ~App();
    void OnLaunched(Microsoft::UI::Xaml::LaunchActivatedEventArgs const& e);
private:
    // 安装和卸载前要求退出应用，避免覆盖仍在使用的资源及连接。
    winrt::handle m_installationMutex{ ::CreateMutexW(nullptr, FALSE, L"Local\\AudioBule.Installation") };
    struct ConnectionRuntime;
    winrt::fire_and_forget PerformDiagnostics(::AudioBule::App::UI::DiagnosticsAction action);
    void UpdateDiagnostics();
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
    winrt::fire_and_forget OperateDevice(std::wstring id, ::AudioBule::App::UI::DeviceAction action);
    winrt::fire_and_forget Shutdown();
    // 逆序析构：窗口/托盘停用后，manager 等待操作，provider 最后释放会话。
    ::AudioBule::Core::Logger m_logger;
    std::unique_ptr<ConnectionRuntime> m_connections;
    std::unique_ptr<::AudioBule::App::UI::DiagnosticsController> m_diagnostics;
    Microsoft::UI::Dispatching::DispatcherQueueTimer m_diagnosticsTimer{ nullptr };
    Windows::Foundation::IAsyncInfo m_diagnosticsPicker{ nullptr };
    bool m_diagnosticsBusy = false;
    ::AudioBule::Core::AppSettings m_settings;
    std::unique_ptr<::AudioBule::Core::AudioSessionIdentity> m_sessionIdentity;
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
