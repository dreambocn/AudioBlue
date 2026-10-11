#pragma once
#include "UiText.h"
#include <winrt/Windows.Foundation.h>
#include <winrt/Microsoft.Windows.AppNotifications.h>
#include <functional>

namespace AudioBule::App::UI
{
class DesktopIntegration
{
public:
    DesktopIntegration();
    ~DesktopIntegration();
    winrt::Windows::Foundation::IAsyncOperation<bool> StartupEnabled();
    winrt::Windows::Foundation::IAsyncOperation<bool> SetStartup(bool enabled);
    bool RegisterNotifications(std::function<void()> activated);
    void Notify(Core::ConnectionEntry const& entry, UiText const& text);
    static bool Packaged();
    static std::wstring ExecutablePath();
private:
    winrt::Microsoft::Windows::AppNotifications::AppNotificationManager m_notifications{ nullptr };
    winrt::event_token m_notificationToken{};
    bool m_registered = false, m_smoke = false;
};
}
