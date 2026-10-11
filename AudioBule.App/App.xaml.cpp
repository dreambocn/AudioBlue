#include "pch.h"
#include "App.xaml.h"
#include "TrayMenuBuilder.h"
#include <shellapi.h>
#include <chrono>
#include <winrt/Microsoft.UI.Windowing.h>

using namespace winrt;
using namespace winrt::Microsoft::UI::Xaml;
namespace Tray = ::AudioBule::App::TrayService;
namespace Core = ::AudioBule::Core;

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
    m_tray.reset();
    m_manager.EntryChanged.Remove(m_entryToken);
    m_manager.EntriesChanged.Remove(m_entriesToken);
}

void App::OnLaunched([[maybe_unused]] LaunchActivatedEventArgs const& e)
{
    InitializeComponent();
    m_settings = Core::LoadSettings(Core::DefaultSettingsPath());
    m_queue = Microsoft::UI::Dispatching::DispatcherQueue::GetForCurrentThread();
    m_window = make_self<MainWindow>();
    auto weak = get_weak();
    m_window->Initialize(
        [weak] { if (auto self = weak.get()) self->RefreshDevices(false); },
        [weak] { if (auto self = weak.get()) self->OpenBluetoothSettings(); },
        [weak](std::wstring const& id, bool disconnect) {
            if (auto self = weak.get(); self && !self->m_stopping)
            {
                self->OperateDevice(id, disconnect);
            }
        },
        [weak] { if (auto self = weak.get()) self->Shutdown(); });
    if (!m_manager.IsSupported())
    {
        ::MessageBoxW(m_window->Handle(), L"AudioBule 需要 Windows 10 2004 或更高版本。", L"系统版本不支持", MB_OK | MB_ICONWARNING);
        Shutdown();
        return;
    }
    // 工作线程只入队；快照读取和呈现均在 UI 线程，弱引用避免访问已退出的 App。
    auto queue = m_queue;
    m_entryToken = m_manager.EntryChanged.Add([weak, queue](Core::ConnectionEntry const&) {
        queue.TryEnqueue([weak] { if (auto self = weak.get(); self && !self->m_stopping) self->RenderDevices(); });
    });
    m_entriesToken = m_manager.EntriesChanged.Add([weak, queue] {
        queue.TryEnqueue([weak] { if (auto self = weak.get(); self && !self->m_stopping) self->RenderDevices(); });
    });
    Tray::TrayIconService::Callbacks callbacks;
    callbacks.onToggled = [weak] { if (auto self = weak.get(); self && !self->m_stopping) self->m_window->Toggle(); };
    callbacks.onContextMenu = [weak](POINT point) {
        if (auto self = weak.get(); self && !self->m_stopping)
        {
            int command = Tray::ShowTrayMenu(self->m_window->Handle(), point, self->m_settings.autoReconnect);
            if (self->m_tray) self->m_tray->RestoreFocus();
            self->HandleTrayCommand(command);
        }
    };
    callbacks.onThemeShouldRefresh = [weak] { if (auto self = weak.get()) self->ApplyTheme(); };
    try
    {
        m_tray = std::make_unique<Tray::TrayIconService>(m_queue, std::move(callbacks));
        if (!m_tray->WaitUntilReady())
        {
            ::OutputDebugStringW(L"AudioBule：托盘不可用，显示设备窗口。\n");
            m_tray.reset();
        }
    }
    catch (...) { ::OutputDebugStringW(L"AudioBule：无法启动托盘服务。\n"); }
    ApplyTheme();
    if (!m_tray) m_window->Show();
    RefreshDevices(true);
}

void App::ApplyTheme()
{
    if (!m_tray) return;
    // 任务栏使用系统主题；应用主题可单独配置，不能用应用背景色代替。
    DWORD light = 1;
    DWORD size = sizeof(light);
    ::RegGetValueW(HKEY_CURRENT_USER,
        L"Software\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize",
        L"SystemUsesLightTheme", RRF_RT_REG_DWORD, nullptr, &light, &size);
    m_tray->UpdateIcon(light == 0);
}
void App::RenderDevices()
{
    m_window->Render(m_manager.Snapshot());
    if (m_tray) m_tray->UpdateTooltip(L"AudioBule · " + std::to_wstring(m_manager.ConnectedDeviceIds().size()) + L" 台已连接");
}

fire_and_forget App::RefreshDevices(bool reconnect)
{
    auto lifetime = get_strong();
    if (m_refreshing || m_stopping) co_return;
    m_refreshing = true;
    m_window->SetRefreshing(true);
    apartment_context ui;
    bool succeeded = true;
    // 配置由 UI 线程维护，切到后台前取副本，避免菜单开关与重连读取发生数据竞争。
    bool autoReconnect = m_settings.autoReconnect;
    auto savedDevices = m_settings.lastConnectedDevices;
    co_await resume_background();
    try
    {
        // FindAllAsync().get() 只能在后台调用，不能阻塞 WinUI STA。
        m_manager.Refresh();
        if (reconnect && autoReconnect)
            m_manager.ReconnectSavedDevices(savedDevices);
    }
    catch (...) { succeeded = false; }
    co_await ui;
    m_refreshing = false;
    if (!m_stopping)
    {
        RenderDevices();
        m_window->SetRefreshing(false);
        if (!succeeded) m_window->SetStatus(L"刷新设备失败，请稍后重试。");
    }
}
void App::OpenBluetoothSettings()
{
    if (reinterpret_cast<INT_PTR>(::ShellExecuteW(m_window->Handle(), L"open", L"ms-settings:bluetooth", nullptr, nullptr, SW_SHOWNORMAL)) <= 32)
    {
        m_window->Show();
        m_window->SetStatus(L"无法打开蓝牙设置，请从系统设置手动打开。");
    }
}

fire_and_forget App::OperateDevice(std::wstring id, bool disconnect)
{
    auto lifetime = get_strong();
    if (m_stopping) co_return;
    apartment_context ui;
    m_window->SetOperationPending(id, true);
    bool succeeded = true;
    try
    {
        auto operation = disconnect ? m_manager.DisconnectAsync(id) : m_manager.ConnectAsync(id);
        co_await resume_background();
        operation.get();
    }
    catch (...) { succeeded = false; }
    co_await ui;
    m_window->SetOperationPending(id, false);
    if (!m_stopping)
    {
        RenderDevices();
        if (!succeeded) m_window->SetStatus(L"设备操作失败，请稍后重试。");
    }
}

void App::SaveConfiguration()
{
    if (!Core::SaveSettings(m_settings, Core::DefaultSettingsPath()))
    {
        ::OutputDebugStringW(L"AudioBule：保存配置失败。\n");
        m_window->SetStatus(L"配置保存失败，请检查配置目录的写入权限。");
    }
}
void App::HandleTrayCommand(int command)
{
    switch (command)
    {
    case Tray::kCmdShowDevices: m_window->Show(); break;
    case Tray::kCmdBluetoothSettings: OpenBluetoothSettings(); break;
    case Tray::kCmdAutoReconnect:
        m_settings.autoReconnect = !m_settings.autoReconnect;
        SaveConfiguration();
        break;
    case Tray::kCmdAbout:
        ::MessageBoxW(m_window->Handle(), L"AudioBule\n让电脑接收来自手机的蓝牙音频。\n\n关闭窗口后继续在托盘运行。", L"关于 AudioBule", MB_OK | MB_ICONINFORMATION);
        break;
    case Tray::kCmdExit: Shutdown(); break;
    default: break;
    }
}

fire_and_forget App::Shutdown()
{
    auto lifetime = get_strong();
    if (m_stopping) co_return;
    m_stopping = true;
    m_window->SetStopping();
    m_tray.reset();
    m_manager.EntryChanged.Remove(m_entryToken);
    m_manager.EntriesChanged.Remove(m_entriesToken);
    apartment_context ui;
    // 刷新协程持有 App；等待期间保持窗口和 UI 消息循环存活。
    while (m_refreshing)
    {
        co_await resume_after(std::chrono::milliseconds(50));
        co_await ui;
    }
    co_await resume_background();
    m_manager.WaitForIdle();
    auto connected = m_manager.ConnectedDeviceIds();
    co_await ui;
    m_settings.lastConnectedDevices = std::move(connected);
    SaveConfiguration();
    m_window->CloseForExit();
    Exit();
}
}
