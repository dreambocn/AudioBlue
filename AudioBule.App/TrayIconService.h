#pragma once

#include <windows.h>
#include <shellapi.h>
#include <winrt/Microsoft.UI.Dispatching.h>

#include "IconFactory.h"
#include "Logger.h"
#include <atomic>
#include <condition_variable>
#include <functional>
#include <memory>
#include <mutex>
#include <thread>
#include <vector>

namespace AudioBule::App::TrayService
{
// 独立 STA 线程管理托盘；回调只在 WinUI 的 DispatcherQueue 上执行。
class TrayIconService
{
public:
    struct Callbacks
    {
        std::function<void(POINT, bool)> onToggled;
        std::function<void(POINT, bool)> onContextMenu;
        std::function<void()> onThemeShouldRefresh;
    };

    TrayIconService(winrt::Microsoft::UI::Dispatching::DispatcherQueue const& queue,
        Callbacks callbacks, Core::LogContext log = {});
    ~TrayIconService();
    TrayIconService(TrayIconService const&) = delete;
    TrayIconService& operator=(TrayIconService const&) = delete;

    bool WaitUntilReady(unsigned timeoutMs = 5000);
    void UpdateIcon(bool darkTheme, bool connected = false);
    void UpdateTooltip(std::wstring text);
    void RestoreFocus();

private:
    // 队列里可能仍有回调；共享开关让析构后的回调安全失效。
    struct CallbackState
    {
        Core::LogContext log;
        std::atomic<bool> active{ true };
        Callbacks callbacks;
    };
    static LRESULT CALLBACK WndProc(HWND window, UINT message, WPARAM wParam, LPARAM lParam);
    void ThreadMain() noexcept;
    void ProcessMessage(HWND window, UINT message, WPARAM wParam, LPARAM lParam);
    bool AddIcon();
    void Cleanup() noexcept;
    void PostWork(std::function<void()> work);
    void Dispatch(std::function<void(Callbacks const&)> callback);

    winrt::Microsoft::UI::Dispatching::DispatcherQueue m_queue;
    std::shared_ptr<CallbackState> m_callbacks;
    Core::LogContext m_log;
    std::thread m_thread;
    std::mutex m_mutex;
    std::condition_variable m_readyCondition;
    std::vector<std::function<void()>> m_work;
    HWND m_publishedWindow = nullptr;
    bool m_ready = false;
    bool m_started = false;
    std::atomic<bool> m_stopping{ false };

    // 以下成员只由托盘线程访问，广播窗口不显示、不进入任务栏。
    HWND m_window = nullptr;
    HWND m_broadcastWindow = nullptr;
    UINT m_taskbarCreated = 0;
    NOTIFYICONDATAW m_data{};
    Core::TrayIcon m_icon{};
    bool m_added = false;
    bool m_version4 = false;
    bool m_darkTheme = false, m_connected = false;
};
}
