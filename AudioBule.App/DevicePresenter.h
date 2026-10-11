#pragma once
#include "UiText.h"
#include <winrt/Microsoft.UI.Xaml.Controls.h>
#include <winrt/Microsoft.UI.Xaml.Shapes.h>
#include <functional>
#include <map>
#include <set>

namespace AudioBule::App::UI
{
// 两个界面复用同一行结构；状态变化只更新控件，保持键盘焦点。
class DevicePresenter
{
public:
    void Initialize(winrt::Microsoft::UI::Xaml::Controls::StackPanel const& target,
        UiText& text, std::function<void(std::wstring const&, bool)> operate, bool compact = false);
    size_t Update(std::vector<Core::ConnectionEntry> const& entries,
        std::set<std::wstring> const& pending, bool connectedOnly = false);
private:
    struct Row
    {
        winrt::Microsoft::UI::Xaml::Controls::Grid root{ nullptr };
        winrt::Microsoft::UI::Xaml::Controls::TextBlock name{ nullptr }, status{ nullptr }, error{ nullptr };
        winrt::Microsoft::UI::Xaml::Shapes::Ellipse dot{ nullptr };
        winrt::Microsoft::UI::Xaml::Controls::Button action{ nullptr };
        winrt::Microsoft::UI::Xaml::Controls::ProgressRing progress{ nullptr };
    };
    winrt::Microsoft::UI::Xaml::Controls::StackPanel m_target{ nullptr };
    UiText* m_text = nullptr;
    std::function<void(std::wstring const&, bool)> m_operate;
    std::map<std::wstring, Row> m_rows;
    bool m_compact = false;
};
}
