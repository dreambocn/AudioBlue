#include "pch.h"
#include "UiText.h"
#include <winrt/Windows.Globalization.h>
#include <sstream>
#include <iomanip>

namespace AudioBule::App::UI
{
UiText::UiText()
{
    m_context = m_manager.CreateResourceContext();
    m_strings = m_manager.MainResourceMap().GetSubtree(L"Resources");
    SetLanguage(L"system");
}
void UiText::SetLanguage(std::wstring const& preference)
{
    auto desired = preference;
    if (desired == L"system")
    {
        auto languages = winrt::Windows::Globalization::ApplicationLanguages::Languages();
        desired = languages.Size() ? std::wstring(languages.GetAt(0)) : L"en-US";
    }
    m_locale = desired.starts_with(L"zh") ? L"zh-CN" : L"en-US";
    m_context.QualifierValues().Insert(L"Language", m_locale);
}
winrt::hstring UiText::Get(wchar_t const* key) const
{
    // 资源丢失不能使蓝牙连接退出；构建检查和冒烟会验证所有资源完整性。
    try { return m_strings.GetValue(key, m_context).ValueAsString(); }
    catch (...) { ::OutputDebugStringW(L"AudioBule：界面文字资源缺失。\n"); return key; }
}
winrt::hstring UiText::Count(size_t count) const
{
    auto text = std::wstring(Get(count == 1 ? L"ConnectedOne" : L"ConnectedMany"));
    auto placeholder = text.find(L"{count}");
    if (placeholder != std::wstring::npos) text.replace(placeholder, 7, std::to_wstring(count));
    return winrt::hstring(text);
}
winrt::hstring UiText::Error(Core::ConnectionEntry const& entry) const
{
    using Core::ConnectFailure;
    wchar_t const* key = L"ErrorUnknown";
    switch (entry.failure)
    {
    case ConnectFailure::DeviceNotSupported: key = L"ErrorUnsupported"; break;
    case ConnectFailure::RequestTimedOut: key = L"ErrorTimeout"; break;
    case ConnectFailure::DeniedBySystem: key = L"ErrorDenied"; break;
    case ConnectFailure::DeviceNotFound: key = L"ErrorMissing"; break;
    case ConnectFailure::GenericFailure:
        if (static_cast<DWORD>(entry.extendedError) == 0x8007001Fu) key = L"ErrorOtherAudio";
        break;
    default: break;
    }
    auto result = std::wstring(Get(key));
    if (entry.extendedError)
    {
        std::wostringstream code;
        code << L" (0x" << std::uppercase << std::hex << std::setw(8) << std::setfill(L'0')
             << static_cast<DWORD>(entry.extendedError) << L")";
        result += code.str();
    }
    return winrt::hstring(result);
}
winrt::hstring UiText::Locale() const { return winrt::hstring(m_locale); }
}
