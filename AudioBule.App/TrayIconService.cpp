#include "pch.h"
#include "TrayIconService.h"

#include <windowsx.h>
#include <chrono>

namespace AudioBule::App::TrayService
{
namespace
{
constexpr wchar_t kWindowClass[] = L"AudioBule.Tray";
constexpr UINT kCallback = WM_APP + 1;
constexpr UINT kWork = WM_APP + 2;
// 只读状态查询供原生冒烟区分 Shell 登记结果与图标矩形查询结果。
constexpr UINT kQueryAvailability = WM_APP + 3;
constexpr UINT_PTR kRetryTimer = 1;
}

TrayIconService::TrayIconService(
    winrt::Microsoft::UI::Dispatching::DispatcherQueue const& queue, Callbacks callbacks, Core::LogContext log)
    : m_queue(queue), m_callbacks(std::make_shared<CallbackState>()), m_log(std::move(log))
{
    if (!queue) throw std::invalid_argument("必须提供 UI 调度队列");
    m_callbacks->callbacks = std::move(callbacks);
    m_callbacks->log = m_log;
    wchar_t smoke[8]{}, fail[8]{};
    m_failFirstAdd = ::GetEnvironmentVariableW(L"AUDIOBULE_SMOKE_TEST", smoke, 8) == 1 && smoke[0] == L'1' &&
        ::GetEnvironmentVariableW(L"AUDIOBULE_SMOKE_FAIL_FIRST_TRAY_ADD", fail, 8) == 1 && fail[0] == L'1';
    m_thread = std::thread([this] { ThreadMain(); });
}

TrayIconService::~TrayIconService()
{
    m_callbacks->active = false;
    m_stopping = true;
    {
        std::lock_guard lock(m_mutex);
        // HWND 在锁内发布/撤销，避免把退出消息发给已回收的句柄。
        if (m_publishedWindow) ::PostMessageW(m_publishedWindow, WM_CLOSE, 0, 0);
    }
    if (m_thread.joinable()) m_thread.join();
}

bool TrayIconService::WaitUntilReady(unsigned timeoutMs)
{
    std::unique_lock lock(m_mutex);
    return m_readyCondition.wait_for(lock, std::chrono::milliseconds(timeoutMs),
        [this] { return m_ready; }) && m_started;
}

void TrayIconService::ThreadMain() noexcept
{
    bool apartment = false;
    try
    {
        winrt::init_apartment(winrt::apartment_type::single_threaded);
        apartment = true;
        auto instance = ::GetModuleHandleW(nullptr);
        WNDCLASSEXW windowClass{};
        windowClass.cbSize = sizeof(windowClass);
        windowClass.lpfnWndProc = WndProc;
        windowClass.hInstance = instance;
        windowClass.lpszClassName = kWindowClass;
        if (!::RegisterClassExW(&windowClass) && ::GetLastError() != ERROR_CLASS_ALREADY_EXISTS)
            winrt::throw_last_error();
        m_taskbarCreated = ::RegisterWindowMessageW(L"TaskbarCreated");
        if (!m_taskbarCreated) winrt::throw_last_error();
        m_window = ::CreateWindowExW(0, kWindowClass, L"AudioBule.Tray.Callback",
            0, 0, 0, 0, 0, HWND_MESSAGE, nullptr, instance, this);
        if (!m_window) winrt::throw_last_error();
        // message-only 窗口不接收广播；独立隐藏顶层窗口接收主题和 Explorer 通知。
        m_broadcastWindow = ::CreateWindowExW(WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE,
            kWindowClass, L"AudioBule.Tray.Broadcast", WS_POPUP,
            0, 0, 0, 0, nullptr, nullptr, instance, this);
        if (!m_broadcastWindow) winrt::throw_last_error();
        m_icon = Core::CreateTrayIcon(false);
        m_data.cbSize = sizeof(m_data);
        m_data.hWnd = m_window;
        m_data.uID = 1;
        m_data.uFlags = NIF_ICON | NIF_MESSAGE | NIF_TIP | NIF_SHOWTIP;
        m_data.uCallbackMessage = kCallback;
        m_data.hIcon = static_cast<HICON>(m_icon.handle);
        wcscpy_s(m_data.szTip, L"AudioBule · 蓝牙音频");
        bool added = AddIcon();
        m_log.Write(added ? Core::LogEvent::TrayReady : Core::LogEvent::TrayFailed, {}, added ? Core::LogLevel::Info : Core::LogLevel::Error);
        {
            std::lock_guard lock(m_mutex);
            m_publishedWindow = m_window;
            // 窗口与消息循环已就绪；Shell 暂未登记成功时仍保留重试服务。
            m_started = true;
            m_ready = true;
        }
        m_readyCondition.notify_all();
        MSG message{};
        while (!m_stopping && ::GetMessageW(&message, nullptr, 0, 0) > 0)
        {
            ::TranslateMessage(&message);
            ::DispatchMessageW(&message);
        }
    }
    catch (...)
    {
        m_log.Write(Core::LogEvent::TrayFailed, { .hresult = winrt::to_hresult() }, Core::LogLevel::Error);
    }
    Cleanup();
    if (apartment) winrt::uninit_apartment();
    {
        std::lock_guard lock(m_mutex);
        m_ready = true;
    }
    m_readyCondition.notify_all();
}

bool TrayIconService::AddIcon()
{
    if (!m_icon)
    {
        m_icon = Core::CreateTrayIcon(m_darkTheme, m_connected);
        m_data.hIcon = static_cast<HICON>(m_icon.handle);
    }
    if (std::exchange(m_failFirstAdd, false))
    {
        m_added = false;
        SetAvailable(false);
        ::SetTimer(m_window, kRetryTimer, 1000, nullptr);
        return false;
    }
    if (!m_icon || !::Shell_NotifyIconW(NIM_ADD, &m_data))
    {
        m_added = false;
        SetAvailable(false);
        ::SetTimer(m_window, kRetryTimer, 1000, nullptr);
        return false;
    }
    m_log.Write(Core::LogEvent::TrayRestored, {}, Core::LogLevel::Debug);
    m_added = true;
    SetAvailable(true);
    m_data.uVersion = NOTIFYICON_VERSION_4;
    m_version4 = ::Shell_NotifyIconW(NIM_SETVERSION, &m_data) != FALSE;
    ::KillTimer(m_window, kRetryTimer);
    return true;
}

void TrayIconService::SetAvailable(bool available)
{
    if (m_available.exchange(available) == available) return;
    Dispatch([available](Callbacks const& callbacks) { if (callbacks.onAvailabilityChanged) callbacks.onAvailabilityChanged(available); });
}

void TrayIconService::Cleanup() noexcept
{
    {
        std::lock_guard lock(m_mutex);
        m_publishedWindow = nullptr;
        m_work.clear();
    }
    if (m_added) ::Shell_NotifyIconW(NIM_DELETE, &m_data);
    Core::DestroyTrayIcon(m_icon);
    SetAvailable(false);
    m_icon = {};
    if (m_broadcastWindow) ::DestroyWindow(m_broadcastWindow);
    if (m_window) ::DestroyWindow(m_window);
    m_broadcastWindow = m_window = nullptr;
}

LRESULT CALLBACK TrayIconService::WndProc(HWND window, UINT message, WPARAM wParam, LPARAM lParam)
{
    if (message == WM_NCCREATE)
    {
        auto creation = reinterpret_cast<CREATESTRUCTW*>(lParam);
        ::SetWindowLongPtrW(window, GWLP_USERDATA, reinterpret_cast<LONG_PTR>(creation->lpCreateParams));
    }
    auto self = reinterpret_cast<TrayIconService*>(::GetWindowLongPtrW(window, GWLP_USERDATA));
    if (self)
    {
        if (message == kQueryAvailability) return self->IsAvailable() ? 1 : 0;
        // 异常不能越过 Win32 回调边界。
        try { self->ProcessMessage(window, message, wParam, lParam); }
        catch (...) { self->m_log.Write(Core::LogEvent::TrayMessageFailed, { .hresult = winrt::to_hresult() }, Core::LogLevel::Warning); }
        if (message == kWork || message == kCallback || message == WM_CLOSE) return 0;
    }
    return ::DefWindowProcW(window, message, wParam, lParam);
}

void TrayIconService::ProcessMessage(HWND window, UINT message, WPARAM wParam, LPARAM lParam)
{
    if (message == WM_CLOSE)
    {
        m_stopping = true;
        ::PostQuitMessage(0);
    }
    else if (message == kWork)
    {
        std::vector<std::function<void()>> work;
        { std::lock_guard lock(m_mutex); work.swap(m_work); }
        for (auto const& item : work) item();
    }
    else if (message == kCallback)
    {
        // 版本 4：事件和图标 ID 在 lParam，屏幕坐标在 wParam（支持负坐标）。
        UINT event = m_version4 ? LOWORD(lParam) : static_cast<UINT>(lParam);
        if (m_version4 && HIWORD(lParam) != m_data.uID) return;
        if (event == NIN_SELECT || event == NIN_KEYSELECT || (!m_version4 && event == WM_LBUTTONUP))
            {
            NOTIFYICONIDENTIFIER identifier{ sizeof(identifier), m_window, m_data.uID, {} };
            RECT bounds{};
            POINT point{ GET_X_LPARAM(wParam), GET_Y_LPARAM(wParam) };
            if (SUCCEEDED(::Shell_NotifyIconGetRect(&identifier, &bounds)))
                point = { (bounds.left + bounds.right) / 2, bounds.top };
            else if (!m_version4 || (point.x == -1 && point.y == -1)) ::GetCursorPos(&point);
            bool keyboard = event == NIN_KEYSELECT;
            Dispatch([point, keyboard](Callbacks const& callbacks) { if (callbacks.onToggled) callbacks.onToggled(point, keyboard); });
        }
        else if (event == WM_CONTEXTMENU || (!m_version4 && event == WM_RBUTTONUP))
        {
            POINT point{ GET_X_LPARAM(wParam), GET_Y_LPARAM(wParam) };
            bool keyboard = m_version4 && point.x == -1 && point.y == -1;
            if (!m_version4 || (point.x == -1 && point.y == -1)) ::GetCursorPos(&point);
            Dispatch([point, keyboard](Callbacks const& callbacks) {
                if (callbacks.onContextMenu) callbacks.onContextMenu(point, keyboard);
            });
        }
    }
    else if (window == m_broadcastWindow && message == WM_SETTINGCHANGE)
        Dispatch([](Callbacks const& callbacks) {
            if (callbacks.onThemeShouldRefresh) callbacks.onThemeShouldRefresh();
        });
    else if (window == m_broadcastWindow && message == m_taskbarCreated)
    {
        m_added = false;
        SetAvailable(false);
        AddIcon();
    }
    else if (message == WM_TIMER && wParam == kRetryTimer && !m_added) AddIcon();
}

void TrayIconService::Dispatch(std::function<void(Callbacks const&)> callback)
{
    auto state = m_callbacks;
    if (!state->active) return;
    if (!m_queue.TryEnqueue([state, callback = std::move(callback)] {
        if (!state->active) return;
        try { callback(state->callbacks); }
        catch (...) { state->log.Write(Core::LogEvent::TrayMessageFailed, { .hresult = winrt::to_hresult() }, Core::LogLevel::Warning); }
    }))
    {
        state->active = false;
        m_stopping = true;
        ::PostQuitMessage(0);
    }
}

void TrayIconService::PostWork(std::function<void()> work)
{
    std::lock_guard lock(m_mutex);
    if (m_stopping || !m_publishedWindow) return;
    m_work.push_back(std::move(work));
    if (!::PostMessageW(m_publishedWindow, kWork, 0, 0)) m_work.clear();
}

void TrayIconService::UpdateIcon(bool darkTheme, bool connected)
{
    PostWork([this, darkTheme, connected] {
        if (m_icon && m_darkTheme == darkTheme && m_connected == connected) return;
        auto replacement = Core::CreateTrayIcon(darkTheme, connected);
        if (!replacement) return;
        auto data = m_data;
        data.hIcon = static_cast<HICON>(replacement.handle);
        if (m_added && !::Shell_NotifyIconW(NIM_MODIFY, &data))
        {
            Core::DestroyTrayIcon(replacement);
            return;
        }
        Core::DestroyTrayIcon(m_icon);
        m_icon = replacement;
        m_darkTheme = darkTheme; m_connected = connected;
        m_data.hIcon = data.hIcon;
    });
}

void TrayIconService::UpdateTooltip(std::wstring text)
{
    PostWork([this, text = std::move(text)] {
        wcsncpy_s(m_data.szTip, text.c_str(), _TRUNCATE);
        if (m_added) ::Shell_NotifyIconW(NIM_MODIFY, &m_data);
    });
}

void TrayIconService::RestoreFocus()
{
    PostWork([this] { if (m_added) ::Shell_NotifyIconW(NIM_SETFOCUS, &m_data); });
}
}
