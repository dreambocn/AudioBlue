#pragma once
#include "ConnectionEntry.h"
#include <winrt/Microsoft.Windows.ApplicationModel.Resources.h>
#include <string>

namespace AudioBule::App::UI
{
// 同一资源上下文供窗口、托盘、对话框和通知使用，切换语言不重建连接。
class UiText
{
public:
    UiText();
    void SetLanguage(std::wstring const& preference);
    winrt::hstring Get(wchar_t const* key) const;
    winrt::hstring Count(size_t count) const;
    winrt::hstring Error(Core::ConnectionEntry const& entry) const;
    winrt::hstring Locale() const;
private:
    winrt::Microsoft::Windows::ApplicationModel::Resources::ResourceManager m_manager;
    winrt::Microsoft::Windows::ApplicationModel::Resources::ResourceContext m_context{ nullptr };
    winrt::Microsoft::Windows::ApplicationModel::Resources::ResourceMap m_strings{ nullptr };
    std::wstring m_locale = L"zh-CN";
};
}
