#include "pch.h"
#include "App.xaml.h"
#include <shellapi.h>
#include <chrono>
#include <winrt/Microsoft.Windows.AppLifecycle.h>

using namespace winrt;
using namespace winrt::Microsoft::UI::Xaml;
namespace Tray = ::AudioBule::App::TrayService;
namespace Core = ::AudioBule::Core;
namespace UI = ::AudioBule::App::UI;

namespace winrt::AudioBule::App::implementation
{
App::App() : m_manager(m_provider)
{
    UnhandledException([](IInspectable const&, UnhandledExceptionEventArgs const& args) {
        ::OutputDebugStringW((L"AudioBule：" + std::wstring(args.Message()) + L"\n").c_str());
    });
}
App::~App()
{
    m_tray.reset(); m_quick.reset(); m_desktop.reset();
    m_manager.EntryChanged.Remove(m_entryToken);
    m_manager.EntriesChanged.Remove(m_entriesToken);
}
void App::OnLaunched([[maybe_unused]] LaunchActivatedEventArgs const& e)
{
    InitializeComponent();
    m_settings = Core::LoadSettings(Core::DefaultSettingsPath());
    m_text = std::make_unique<UI::UiText>();
    m_text->SetLanguage(m_settings.language);
    m_desktop = std::make_unique<UI::DesktopIntegration>();
    m_queue = Microsoft::UI::Dispatching::DispatcherQueue::GetForCurrentThread();
    m_window = make_self<MainWindow>();
    auto weak = get_weak();
    auto operate = [weak](std::wstring const& id, bool disconnect) {
        if (auto self = weak.get(); self && !self->m_stopping) self->OperateDevice(id, disconnect);
    };
    auto preferences = [weak](Core::AppSettings const& settings) {
        if (auto self = weak.get(); self && !self->m_stopping) self->ChangePreferences(settings);
    };
    auto bluetooth = [weak] { if (auto self = weak.get()) self->OpenBluetoothSettings(); };
    auto confirmExit = [weak] { if (auto self = weak.get()) self->m_window->ConfirmExit(); };
    m_window->Initialize(*m_text, [weak] { if (auto self = weak.get()) self->RefreshDevices(false); }, bluetooth,
        operate, [weak] { if (auto self = weak.get()) self->Shutdown(); }, preferences);
    UI::QuickPanel::Callbacks panelCallbacks;
    panelCallbacks.operate = operate; panelCallbacks.exit = confirmExit;
    panelCallbacks.navigate = [weak](std::wstring const& page) {
        if (auto self = weak.get()) { self->m_window->Navigate(page); self->m_window->Show(); }
    };
    panelCallbacks.restoreFocus = [weak] { if (auto self = weak.get(); self && self->m_tray) self->m_tray->RestoreFocus(); };
    m_quick = std::make_unique<UI::QuickPanel>(*m_text, std::move(panelCallbacks));
    auto queue = m_queue;
    m_notificationsAvailable = m_desktop->RegisterNotifications([weak, queue] {
        queue.TryEnqueue([weak] { if (auto self = weak.get(); self && !self->m_stopping) self->m_window->Show(); });
    });
    ApplyPreferences();
    if (!m_manager.IsSupported()) {
        ::MessageBoxW(m_window->Handle(), m_text->Get(L"UnsupportedBody").c_str(), m_text->Get(L"UnsupportedTitle").c_str(), MB_OK | MB_ICONWARNING);
        Shutdown(); return;
    }
    // 入队保留每一次状态变化，不能用最新快照吞掉快速发生的连接/断开通知。
    m_entryToken = m_manager.EntryChanged.Add([weak, queue](Core::ConnectionEntry const& entry) {
        queue.TryEnqueue([weak, entry] { if (auto self = weak.get(); self && !self->m_stopping) { self->EntryChanged(entry); self->RenderDevices(); } });
    });
    m_entriesToken = m_manager.EntriesChanged.Add([weak, queue] {
        queue.TryEnqueue([weak] { if (auto self = weak.get(); self && !self->m_stopping) self->RenderDevices(); });
    });
    Tray::TrayIconService::Callbacks callbacks;
    callbacks.onToggled = [weak](POINT point, bool keyboard) { if (auto self = weak.get(); self && !self->m_stopping) self->m_quick->Toggle(point, keyboard); };
    callbacks.onContextMenu = [weak](POINT point, bool keyboard) { if (auto self = weak.get(); self && !self->m_stopping) self->m_quick->ShowMenu(point, keyboard); };
    callbacks.onThemeShouldRefresh = [weak] {
        if (auto self = weak.get(); self && !self->m_stopping) {
            auto previousLocale = self->m_text->Locale();
            self->m_text->SetLanguage(self->m_settings.language);
            // WinUI 已跟随系统刷新主题；仅语言变化需要重建文字控件。
            if (previousLocale != self->m_text->Locale()) self->ApplyPreferences();
            else { self->ApplyTheme(); self->RenderDevices(); }
        }
    };
    try {
        m_tray = std::make_unique<Tray::TrayIconService>(m_queue, std::move(callbacks));
        if (!m_tray->WaitUntilReady()) m_tray.reset();
    } catch (...) { ::OutputDebugStringW(L"AudioBule：无法启动托盘服务。\n"); }
    m_window->SetTrayAvailable(static_cast<bool>(m_tray));
    ApplyTheme();
    bool startup = std::wstring_view(::GetCommandLineW()).find(L"--startup") != std::wstring_view::npos;
    try { startup |= Microsoft::Windows::AppLifecycle::AppInstance::GetCurrent().GetActivatedEventArgs().Kind() == Microsoft::Windows::AppLifecycle::ExtendedActivationKind::StartupTask; } catch (...) {}
    if (!startup || !m_tray) m_window->Show();
    RefreshStartup();
    RefreshDevices(true);
}
void App::ApplyTheme()
{
    if (!m_tray) return;
    DWORD light = 1, size = sizeof(light);
    ::RegGetValueW(HKEY_CURRENT_USER, L"Software\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize",
        L"SystemUsesLightTheme", RRF_RT_REG_DWORD, nullptr, &light, &size);
    m_tray->UpdateIcon(light == 0, !m_manager.ConnectedDeviceIds().empty());
}
void App::ApplyPreferences()
{
    m_window->ApplyPreferences(m_settings, m_startupPending, m_notificationsAvailable);
    if (m_quick) m_quick->ApplyPreferences(m_settings);
    ApplyTheme(); RenderDevices();
}
void App::ChangePreferences(Core::AppSettings const& settings)
{
    bool startupChanged = settings.runAtStartup != m_settings.runAtStartup;
    m_settings.autoReconnect = settings.autoReconnect;
    m_settings.connectionNotifications = settings.connectionNotifications;
    m_settings.theme = settings.theme;
    m_settings.language = settings.language;
    m_text->SetLanguage(m_settings.language);
    SaveConfiguration();
    // 清理并重建设置项必须离开发起事件的控件调用栈。
    auto weak = get_weak();
    m_queue.TryEnqueue([weak] { if (auto self = weak.get(); self && !self->m_stopping) self->ApplyPreferences(); });
    if (startupChanged && !m_startupPending) ChangeStartup(settings.runAtStartup);
}
fire_and_forget App::RefreshStartup()
{
    auto lifetime = get_strong();
    m_startupPending = true; ApplyPreferences();
    try { m_settings.runAtStartup = co_await m_desktop->StartupEnabled(); }
    catch (...) { m_settings.runAtStartup = false; }
    m_startupPending = false;
    if (!m_stopping) ApplyPreferences();
}
fire_and_forget App::ChangeStartup(bool enabled)
{
    auto lifetime = get_strong();
    m_startupPending = true;
    auto weak = get_weak();
    m_queue.TryEnqueue([weak] { if (auto self = weak.get(); self && !self->m_stopping) self->ApplyPreferences(); });
    try {
        m_settings.runAtStartup = co_await m_desktop->SetStartup(enabled);
        if (m_settings.runAtStartup != enabled) m_window->SetStatusKey(L"StartupDisabled");
    } catch (...) { m_window->SetStatusKey(L"StartupFailed"); }
    m_startupPending = false; SaveConfiguration();
    m_queue.TryEnqueue([weak] { if (auto self = weak.get(); self && !self->m_stopping) self->ApplyPreferences(); });
}
void App::EntryChanged(Core::ConnectionEntry const& entry)
{
    auto previous = m_previousStates.contains(entry.deviceId) ? m_previousStates.at(entry.deviceId) : Core::ConnectionState::Disconnected;
    if (m_settings.connectionNotifications && ((entry.state == Core::ConnectionState::Connected && previous != entry.state) ||
        (previous == Core::ConnectionState::Connected && entry.state == Core::ConnectionState::Disconnected))) m_desktop->Notify(entry, *m_text);
    m_previousStates[entry.deviceId] = entry.state;
}
void App::RenderDevices()
{
    auto entries = m_manager.Snapshot();
    m_window->Render(entries);
    if (m_quick) m_quick->Render(entries, m_pendingDevices);
    ApplyTheme(); if (m_tray) m_tray->UpdateTooltip(L"AudioBule · " + std::wstring(m_text->Count(m_manager.ConnectedDeviceIds().size())));
}
fire_and_forget App::RefreshDevices(bool reconnect)
{
    auto lifetime = get_strong();
    if (m_refreshing || m_stopping) co_return;
    m_refreshing = true; m_window->SetRefreshing(true);
    apartment_context ui;
    bool succeeded = true;
    auto autoReconnect = m_settings.autoReconnect;
    auto savedDevices = m_settings.lastConnectedDevices;
    co_await resume_background();
    try { m_manager.Refresh(); if (reconnect && autoReconnect) m_manager.ReconnectSavedDevices(savedDevices); }
    catch (...) { succeeded = false; }
    co_await ui;
    m_refreshing = false;
    if (!m_stopping) { RenderDevices(); m_window->SetRefreshing(false); if (!succeeded) m_window->SetStatusKey(L"RefreshFailed"); }
}
void App::OpenBluetoothSettings()
{
    if (reinterpret_cast<INT_PTR>(::ShellExecuteW(m_window->Handle(), L"open", L"ms-settings:bluetooth", nullptr, nullptr, SW_SHOWNORMAL)) <= 32) {
        m_window->Show(); m_window->SetStatusKey(L"BluetoothSettingsFailed");
    }
}
fire_and_forget App::OperateDevice(std::wstring id, bool disconnect)
{
    auto lifetime = get_strong();
    if (m_stopping) co_return;
    if (disconnect && m_manager.CancelConnection(id))
    {
        // 自动重连没有 OperateDevice 协程；取消时单独追踪其后台清理。
        if (!m_pendingDevices.contains(id))
        {
            apartment_context ui;
            m_pendingDevices.insert(id);
            m_window->SetOperationPending(id, true);
            RenderDevices();
            while (!m_stopping && m_manager.IsConnectionPending(id))
            {
                co_await resume_after(std::chrono::milliseconds(75));
                co_await ui;
            }
            m_pendingDevices.erase(id);
            if (!m_stopping) m_window->SetOperationPending(id, false);
        }
        if (!m_stopping) RenderDevices();
        co_return;
    }
    if (m_pendingDevices.contains(id)) co_return;
    m_pendingDevices.insert(id); m_window->SetOperationPending(id, true);
    apartment_context ui;
    bool succeeded = true;
    try {
        auto operation = disconnect ? m_manager.DisconnectAsync(id) : m_manager.ConnectAsync(id);
        RenderDevices();
        co_await resume_background(); operation.get();
    } catch (...) { succeeded = false; }
    co_await ui;
    m_pendingDevices.erase(id); m_window->SetOperationPending(id, false);
    if (!m_stopping) { RenderDevices(); if (!succeeded) m_window->SetStatusKey(L"OperationFailed"); }
}
void App::SaveConfiguration()
{
    if (!Core::SaveSettings(m_settings, Core::DefaultSettingsPath())) {
        ::OutputDebugStringW(L"AudioBule：保存配置失败。\n"); m_window->SetStatusKey(L"SettingsFailed");
    }
}
fire_and_forget App::Shutdown()
{
    auto lifetime = get_strong();
    if (m_stopping) co_return;
    m_stopping = true; m_window->SetStopping();
    m_tray.reset(); m_quick.reset();
    m_manager.EntryChanged.Remove(m_entryToken); m_manager.EntriesChanged.Remove(m_entriesToken);
    apartment_context ui;
    while (m_refreshing || m_startupPending) { co_await resume_after(std::chrono::milliseconds(50)); co_await ui; }
    co_await resume_background(); m_manager.WaitForIdle(); auto connected = m_manager.ConnectedDeviceIds();
    co_await ui;
    m_settings.lastConnectedDevices = std::move(connected); SaveConfiguration(); m_desktop.reset();
    m_window->CloseForExit(); Exit();
}
}
