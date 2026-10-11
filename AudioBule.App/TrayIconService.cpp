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
constexpr UINT_PTR kRetryTimer = 1;
}

TrayIconService::TrayIconService(
    winrt::Microsoft::UI::Dispatching::DispatcherQueue const& queue, Callbacks callbacks)
    : m_queue(queue), m_callbacks(std::make_shared<CallbackState>())
{
    if (!queue) throw std::invalid_argument("必须提供 UI 调度队列");
    m_callbacks->callbacks = std::move(callbacks);
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
        {
            std::lock_guard lock(m_mutex);
            m_publishedWindow = m_window;
            m_started = added;
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
        ::OutputDebugStringW(L"AudioBule：托盘线程初始化失败。\n");
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
    if (!m_icon || !::Shell_NotifyIconW(NIM_ADD, &m_data))
    {
        m_added = false;
        ::SetTimer(m_window, kRetryTimer, 1000, nullptr);
        return false;
    }
    m_added = true;
    m_data.uVersion = NOTIFYICON_VERSION_4;
    m_version4 = ::Shell_NotifyIconW(NIM_SETVERSION, &m_data) != FALSE;
    ::KillTimer(m_window, kRetryTimer);
    return true;
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
        // 异常不能越过 Win32 回调边界。
        try { self->ProcessMessage(window, message, wParam, lParam); }
        catch (...) { ::OutputDebugStringW(L"AudioBule：处理托盘消息失败。\n"); }
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
        catch (...) { ::OutputDebugStringW(L"AudioBule：托盘操作失败。\n"); }
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
