#pragma once
#include "App.xaml.g.h"
#include "MainWindow.xaml.h"
#include "TrayIconService.h"
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
    void HandleTrayCommand(int command);
    void OpenBluetoothSettings();
    void RenderDevices();
    void SaveConfiguration();
    winrt::fire_and_forget RefreshDevices(bool reconnect);
    winrt::fire_and_forget OperateDevice(std::wstring id, bool disconnect);
    winrt::fire_and_forget Shutdown();

    // 逆序析构：托盘先停，manager 等待操作结束，provider 最后释放。
    ::AudioBule::Core::WinRtDeviceProvider m_provider;
    ::AudioBule::Core::ConnectionManager m_manager;
    ::AudioBule::Core::AppSettings m_settings;
    com_ptr<MainWindow> m_window;
    Microsoft::UI::Dispatching::DispatcherQueue m_queue{ nullptr };
    std::unique_ptr<::AudioBule::App::TrayService::TrayIconService> m_tray;
    ::AudioBule::Core::SimpleEvent<::AudioBule::Core::ConnectionEntry>::SubscriptionId m_entryToken = 0;
    ::AudioBule::Core::SimpleEvent<>::SubscriptionId m_entriesToken = 0;
    bool m_refreshing = false;
    bool m_stopping = false;
};
}
