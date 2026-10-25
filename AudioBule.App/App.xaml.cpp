#include "pch.h"
#include "App.xaml.h"
#include <shellapi.h>
#include <chrono>
#include <winrt/Microsoft.Windows.Storage.Pickers.h>
#include <winrt/Microsoft.Windows.AppLifecycle.h>

using namespace winrt;
using namespace winrt::Microsoft::UI::Xaml;
namespace Tray = ::AudioBule::App::TrayService;
namespace Core = ::AudioBule::Core;
namespace UI = ::AudioBule::App::UI;

namespace winrt::AudioBule::App::implementation
{
// 连接资源可在日志停止前显式释放，同时保持 Manager 早于 Provider 析构。
struct App::ConnectionRuntime
{
    Core::WinRtDeviceProvider provider;
    Core::ConnectionManager manager;
    explicit ConnectionRuntime(Core::LogContext log) : provider(log), manager(provider, log) {}
};
App::App() : m_connections(std::make_unique<ConnectionRuntime>(m_logger.Context()))
{
    UnhandledException([log = m_logger.Context()](IInspectable const&, UnhandledExceptionEventArgs const& args) {
        log.Write(Core::LogEvent::UnhandledException, { .hresult = args.Exception() }, Core::LogLevel::Critical);
    });
}
App::~App()
{
    m_sessionIdentity.reset();
    m_tray.reset(); m_quick.reset(); m_desktop.reset();
    if (m_connections) { m_connections->manager.EntryChanged.Remove(m_entryToken); m_connections->manager.EntriesChanged.Remove(m_entriesToken); }
    if (m_diagnosticsTimer) m_diagnosticsTimer.Stop();
    if (m_diagnostics) m_diagnostics->Cancel();
    m_connections.reset();
}
void App::OnLaunched([[maybe_unused]] LaunchActivatedEventArgs const& e)
{
    InitializeComponent();
    m_settings = Core::LoadSettings(Core::DefaultSettingsPath(), m_logger.Context());
    m_text = std::make_unique<UI::UiText>(m_logger.Context());
    m_text->SetLanguage(m_settings.language);
    m_desktop = std::make_unique<UI::DesktopIntegration>(m_logger.Context());
    // 品牌图标适用于深浅主题；会话名称保留手机原名，不受界面语言影响。
    m_sessionIdentity = std::make_unique<Core::AudioSessionIdentity>(UI::DesktopIntegration::ExecutablePath(), m_logger.Context());
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
        operate, [weak] { if (auto self = weak.get()) self->Shutdown(); }, preferences, m_logger.Context(),
        [weak](UI::DiagnosticsAction action) { if (auto self = weak.get(); self && !self->m_stopping) self->PerformDiagnostics(action); });
    m_diagnostics = std::make_unique<UI::DiagnosticsController>(m_logger);
    m_diagnosticsTimer = m_queue.CreateTimer();
    m_diagnosticsTimer.Interval(std::chrono::seconds(1));
    m_diagnosticsTimer.Tick([weak](auto const&, auto const&) { if (auto self = weak.get(); self && !self->m_stopping) self->UpdateDiagnostics(); });
    m_diagnosticsTimer.Start();
    UpdateDiagnostics();
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
    if (!m_connections->manager.IsSupported()) {
        ::MessageBoxW(m_window->Handle(), m_text->Get(L"UnsupportedBody").c_str(), m_text->Get(L"UnsupportedTitle").c_str(), MB_OK | MB_ICONWARNING);
        Shutdown(); return;
    }
    // 入队保留每一次状态变化，不能用最新快照吞掉快速发生的连接/断开通知。
    m_entryToken = m_connections->manager.EntryChanged.Add([weak, queue](Core::ConnectionEntry const& entry) {
        queue.TryEnqueue([weak, entry] { if (auto self = weak.get(); self && !self->m_stopping) { self->EntryChanged(entry); self->RenderDevices(); } });
    });
    m_entriesToken = m_connections->manager.EntriesChanged.Add([weak, queue] {
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
        m_tray = std::make_unique<Tray::TrayIconService>(m_queue, std::move(callbacks), m_logger.Context());
        if (!m_tray->WaitUntilReady()) m_tray.reset();
    } catch (...) { m_logger.Context().Write(Core::LogEvent::TrayFailed, { .hresult = winrt::to_hresult() }, Core::LogLevel::Error); }
    m_window->SetTrayAvailable(static_cast<bool>(m_tray));
    ApplyTheme();
    bool startup = std::wstring_view(::GetCommandLineW()).find(L"--startup") != std::wstring_view::npos;
    try { startup |= Microsoft::Windows::AppLifecycle::AppInstance::GetCurrent().GetActivatedEventArgs().Kind() == Microsoft::Windows::AppLifecycle::ExtendedActivationKind::StartupTask; } catch (...) {}
    m_logger.Context().Operation(startup ? Core::LogTrigger::Startup : Core::LogTrigger::Manual).Write(Core::LogEvent::InitializationCompleted);
    if (!startup || !m_tray) m_window->Show();
    RefreshStartup();
    RefreshDevices(true);
}
void App::UpdateDiagnostics()
{
    if (m_window) m_window->SetDiagnostics(m_logger.Status(), m_diagnosticsBusy);
}
fire_and_forget App::PerformDiagnostics(UI::DiagnosticsAction action)
{
    auto lifetime = get_strong();
    if (m_stopping || !m_diagnostics) co_return;
    if (action == UI::DiagnosticsAction::ToggleDetailed)
    {
        m_logger.SetDetailed(!m_logger.Status().detailed); UpdateDiagnostics(); co_return;
    }
    if (action == UI::DiagnosticsAction::OpenFolder)
    {
        auto root = m_logger.Root();
        if (!m_logger.Status().available || root.empty() || reinterpret_cast<INT_PTR>(::ShellExecuteW(m_window->Handle(), L"open", root.c_str(), nullptr, nullptr, SW_SHOWNORMAL)) <= 32)
            m_window->SetStatusKey(L"DiagnosticsOpenFailed");
        co_return;
    }
    if (m_diagnosticsBusy) co_return;
    m_diagnosticsBusy = true; m_diagnostics->BeginExport(); UpdateDiagnostics();
    apartment_context ui;
    wchar_t const* status = nullptr;
    try
    {
        Microsoft::Windows::Storage::Pickers::FileSavePicker picker(m_window->AppWindow().Id());
        picker.SuggestedFileName(L"AudioBule-diagnostics");
        picker.FileTypeChoices().Insert(L"JSON Lines", single_threaded_vector<hstring>({ L".jsonl" }));
        auto operation = picker.PickSaveFileAsync();
        m_diagnosticsPicker = operation.as<Windows::Foundation::IAsyncInfo>();
        auto selected = co_await operation;
        m_diagnosticsPicker = nullptr;
        if (selected && !m_stopping)
        {
            auto target = std::wstring(selected.Path());
            co_await resume_background();
            auto result = m_diagnostics->Export(target);
            co_await ui;
            if (!result.cancelled) status = result.succeeded ? result.incomplete ? L"DiagnosticsExportPartial" : L"DiagnosticsExportSuccess" : L"DiagnosticsExportFailed";
        }
    }
    catch (...) { status = L"DiagnosticsExportFailed"; }
    // 后台导出若超出退出等待期限，强引用仍保护 App；调度器关闭后安静结束。
    try
    {
        co_await ui;
        m_diagnosticsPicker = nullptr; m_diagnosticsBusy = false;
        if (!m_stopping) { UpdateDiagnostics(); if (status) m_window->SetStatusKey(status); m_window->RestoreDiagnosticsFocus(); }
    }
    catch (...) {}
}
void App::ApplyTheme()
{
    if (!m_tray) return;
    DWORD light = 1, size = sizeof(light);
    ::RegGetValueW(HKEY_CURRENT_USER, L"Software\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize",
        L"SystemUsesLightTheme", RRF_RT_REG_DWORD, nullptr, &light, &size);
    m_tray->UpdateIcon(light == 0, !m_connections->manager.ConnectedDeviceIds().empty());
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
    if (m_settings.language != settings.language) {
        m_settings.language = settings.language;
        m_text->SetLanguage(m_settings.language);
    }
    SaveConfiguration();
    // 语言变化可能重建文案，统一离开发起事件的控件调用栈再同步界面。
    auto weak = get_weak();
    m_queue.TryEnqueue([weak] { if (auto self = weak.get(); self && !self->m_stopping) self->ApplyPreferences(); });
    if (startupChanged && !m_startupPending) ChangeStartup(settings.runAtStartup);
}
fire_and_forget App::RefreshStartup()
{
    auto lifetime = get_strong();
    m_startupPending = true; ApplyPreferences();
    try { m_settings.runAtStartup = co_await m_desktop->StartupEnabled(); }
    catch (...) { m_logger.Context().Write(Core::LogEvent::StartupFailed, { .hresult = winrt::to_hresult() }, Core::LogLevel::Warning); m_settings.runAtStartup = false; }
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
        m_logger.Context().Write(Core::LogEvent::StartupCompleted, { .outcome = m_settings.runAtStartup == enabled ? Core::LogOutcome::Succeeded : Core::LogOutcome::Failed });
    } catch (...) { m_logger.Context().Write(Core::LogEvent::StartupFailed, { .hresult = winrt::to_hresult() }, Core::LogLevel::Warning); m_window->SetStatusKey(L"StartupFailed"); }
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
    auto entries = m_connections->manager.Snapshot();
    if (m_sessionIdentity)
    {
        std::vector<Core::DeviceInfo> connected;
        for (auto const& entry : entries)
            if (entry.state == Core::ConnectionState::Connected) connected.push_back({ entry.deviceId, entry.displayName });
        m_sessionIdentity->SetDevices(std::move(connected));
    }
    m_window->Render(entries);
    if (m_quick) m_quick->Render(entries, m_pendingDevices);
    ApplyTheme(); if (m_tray) m_tray->UpdateTooltip(L"AudioBule · " + std::wstring(m_text->Count(m_connections->manager.ConnectedDeviceIds().size())));
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
    try { m_connections->manager.Refresh(); if (reconnect && autoReconnect) m_connections->manager.ReconnectSavedDevices(savedDevices); }
    catch (...) { m_logger.Context().Write(Core::LogEvent::RefreshFailed, { .hresult = winrt::to_hresult() }, Core::LogLevel::Warning); succeeded = false; }
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
    if (disconnect && m_connections->manager.CancelConnection(id))
    {
        // 自动重连没有 OperateDevice 协程；取消时单独追踪其后台清理。
        if (!m_pendingDevices.contains(id))
        {
            apartment_context ui;
            m_pendingDevices.insert(id);
            m_window->SetOperationPending(id, true);
            RenderDevices();
            while (!m_stopping && m_connections->manager.IsConnectionPending(id))
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
        auto operation = disconnect ? m_connections->manager.DisconnectAsync(id) : m_connections->manager.ConnectAsync(id);
        RenderDevices();
        co_await resume_background(); operation.get();
    } catch (...) { m_logger.Context().Write(Core::LogEvent::OperationFailed, { .hresult = winrt::to_hresult() }, Core::LogLevel::Warning); succeeded = false; }
    co_await ui;
    m_pendingDevices.erase(id); m_window->SetOperationPending(id, false);
    if (!m_stopping) { RenderDevices(); if (!succeeded) m_window->SetStatusKey(L"OperationFailed"); }
}
void App::SaveConfiguration()
{
    if (!Core::SaveSettings(m_settings, Core::DefaultSettingsPath(), m_logger.Context())) {
        m_window->SetStatusKey(L"SettingsFailed");
    }
}
fire_and_forget App::Shutdown()
{
    auto lifetime = get_strong();
    if (m_stopping) co_return;
    m_stopping = true; m_window->SetStopping();
    m_logger.Context().Write(Core::LogEvent::ShutdownRequested);
    if (m_diagnosticsTimer) m_diagnosticsTimer.Stop();
    m_diagnostics->Cancel();
    if (m_diagnosticsPicker) { try { m_diagnosticsPicker.Cancel(); } catch (...) {} }
    m_tray.reset(); m_quick.reset();
    m_connections->manager.EntryChanged.Remove(m_entryToken); m_connections->manager.EntriesChanged.Remove(m_entriesToken);
    apartment_context ui;
    auto diagnosticsDeadline = ::GetTickCount64() + 2000;
    while (m_refreshing || m_startupPending || (m_diagnosticsBusy && ::GetTickCount64() < diagnosticsDeadline)) { co_await resume_after(std::chrono::milliseconds(50)); co_await ui; }
    co_await resume_background(); m_connections->manager.WaitForIdle(); auto connected = m_connections->manager.ConnectedDeviceIds();
    m_sessionIdentity.reset();
    co_await ui;
    m_settings.lastConnectedDevices = std::move(connected); SaveConfiguration(); m_desktop.reset();
    co_await resume_background();
    m_connections.reset();
    m_logger.Context().Write(Core::LogEvent::ShutdownCompleted);
    m_logger.Stop();
    co_await ui;
    m_window->CloseForExit(); Exit();
}
}
