#include "pch.h"
#include "DesktopIntegration.h"
#include <appmodel.h>
#include <winrt/Windows.ApplicationModel.h>
#include <winrt/Microsoft.Windows.AppNotifications.Builder.h>

namespace AudioBule::App::UI
{
namespace
{
// Windows 启动应用中显式禁用时，不覆盖用户的系统设置。
bool DisabledInWindows()
{
    BYTE state[12]{};
    DWORD size = sizeof(state);
    auto code = ::RegGetValueW(HKEY_CURRENT_USER,
        L"Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\StartupApproved\\Run",
        L"AudioBule", RRF_RT_REG_BINARY, nullptr, state, &size);
    return code == ERROR_SUCCESS && size > 0 && (state[0] == 3 || state[0] == 7);
}
constexpr wchar_t kRunKey[] = L"Software\\Microsoft\\Windows\\CurrentVersion\\Run";
}
DesktopIntegration::DesktopIntegration(Core::LogContext log) : m_log(std::move(log))
{
    wchar_t flag[8]{};
    m_smoke = ::GetEnvironmentVariableW(L"AUDIOBULE_SMOKE_TEST", flag, 8) && std::wstring_view(flag) == L"1";
}
DesktopIntegration::~DesktopIntegration()
{
    if (m_registered) {
        try { m_notifications.NotificationInvoked(m_notificationToken); m_notifications.Unregister(); }
        catch (...) { m_log.Write(Core::LogEvent::NotificationCleanupFailed, { .hresult = winrt::to_hresult() }, Core::LogLevel::Warning); }
    }
}
bool DesktopIntegration::Packaged()
{
    UINT32 length = 0;
    return ::GetCurrentPackageFullName(&length, nullptr) == ERROR_INSUFFICIENT_BUFFER;
}
std::wstring DesktopIntegration::ExecutablePath()
{
    std::wstring path(32768, L'\0');
    auto length = ::GetModuleFileNameW(nullptr, path.data(), static_cast<DWORD>(path.size()));
    if (!length || length >= path.size()) winrt::throw_last_error();
    path.resize(length);
    return path;
}
winrt::Windows::Foundation::IAsyncOperation<bool> DesktopIntegration::StartupEnabled()
{
    using namespace winrt::Windows::ApplicationModel;
    if (m_smoke) co_return false;
    if (Packaged()) {
        auto task = co_await StartupTask::GetAsync(L"AudioBuleStartup");
        co_return task.State() == StartupTaskState::Enabled || task.State() == StartupTaskState::EnabledByPolicy;
    }
    wchar_t command[32768]{};
    DWORD size = sizeof(command);
    auto code = ::RegGetValueW(HKEY_CURRENT_USER, kRunKey, L"AudioBule", RRF_RT_REG_SZ, nullptr, command, &size);
    co_return !DisabledInWindows() && code == ERROR_SUCCESS && std::wstring(command) == L"\"" + ExecutablePath() + L"\" --startup";
}
winrt::Windows::Foundation::IAsyncOperation<bool> DesktopIntegration::SetStartup(bool enabled)
{
    using namespace winrt::Windows::ApplicationModel;
    if (m_smoke) winrt::throw_hresult(E_ACCESSDENIED);
    if (Packaged()) {
        auto task = co_await StartupTask::GetAsync(L"AudioBuleStartup");
        if (enabled) {
            auto state = co_await task.RequestEnableAsync();
            co_return state == StartupTaskState::Enabled || state == StartupTaskState::EnabledByPolicy;
        }
        task.Disable();
        co_return task.State() == StartupTaskState::Enabled || task.State() == StartupTaskState::EnabledByPolicy;
    }
    if (enabled && DisabledInWindows()) co_return false;
    HKEY key{};
    auto code = ::RegCreateKeyExW(HKEY_CURRENT_USER, kRunKey, 0, nullptr, 0, KEY_SET_VALUE, nullptr, &key, nullptr);
    if (code != ERROR_SUCCESS) winrt::throw_hresult(HRESULT_FROM_WIN32(code));
    if (enabled) {
        auto command = L"\"" + ExecutablePath() + L"\" --startup";
        code = ::RegSetValueExW(key, L"AudioBule", 0, REG_SZ, reinterpret_cast<BYTE const*>(command.c_str()), static_cast<DWORD>((command.size() + 1) * sizeof(wchar_t)));
    } else {
        code = ::RegDeleteValueW(key, L"AudioBule");
        if (code == ERROR_FILE_NOT_FOUND) code = ERROR_SUCCESS;
    }
    ::RegCloseKey(key);
    if (code != ERROR_SUCCESS) winrt::throw_hresult(HRESULT_FROM_WIN32(code));
    co_return enabled;
}
bool DesktopIntegration::RegisterNotifications(std::function<void()> activated)
{
    if (m_smoke) return false;
    try {
        m_notifications = winrt::Microsoft::Windows::AppNotifications::AppNotificationManager::Default();
        m_notificationToken = m_notifications.NotificationInvoked([activated](auto const&, auto const&) { activated(); });
        m_notifications.Register();
        m_registered = true;
        return true;
    } catch (...) { m_log.Write(Core::LogEvent::NotificationsUnavailable, { .hresult = winrt::to_hresult() }, Core::LogLevel::Warning); return false; }
}
void DesktopIntegration::Notify(Core::ConnectionEntry const& entry, UiText const& text)
{
    if (!m_registered) return;
    try {
        using namespace winrt::Microsoft::Windows::AppNotifications::Builder;
        auto notification = AppNotificationBuilder().AddArgument(L"action", L"open")
            .AddText(entry.displayName).AddText(text.Get(entry.state == Core::ConnectionState::Connected ? L"NotificationConnected" : L"NotificationDisconnected")).BuildNotification();
        m_notifications.Show(notification);
    } catch (...) { m_log.Write(Core::LogEvent::NotificationFailed, { .hresult = winrt::to_hresult() }, Core::LogLevel::Warning); }
}
}
