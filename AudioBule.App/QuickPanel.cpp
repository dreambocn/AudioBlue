#include "pch.h"
#include "QuickPanel.h"
#include <microsoft.ui.xaml.window.h>
#include <winrt/Microsoft.UI.Xaml.Automation.h>
#include <winrt/Microsoft.UI.Xaml.Input.h>
#include <winrt/Windows.System.h>
#include <dwmapi.h>
#include <limits>
#include <cmath>

using namespace winrt;
using namespace winrt::Microsoft::UI::Xaml;
using namespace winrt::Microsoft::UI::Xaml::Controls;
using namespace winrt::Microsoft::UI::Windowing;

namespace AudioBule::App::UI
{
QuickPanel::QuickPanel(UiText& text, Callbacks callbacks) : m_text(text), m_callbacks(std::move(callbacks))
{
    m_window = Window();
    m_window.Title(L"AudioBule.QuickPanel");
    m_window.SystemBackdrop(Media::DesktopAcrylicBackdrop());
    check_hresult(m_window.as<::IWindowNative>()->get_WindowHandle(&m_handle));
    m_appWindow = m_window.AppWindow();
    auto presenter = m_appWindow.Presenter().as<OverlappedPresenter>();
    presenter.IsResizable(false); presenter.IsMaximizable(false); presenter.IsMinimizable(false);
    presenter.SetBorderAndTitleBar(false, false);
    // 禁用调整大小后宿主仍保留 WS_DLGFRAME；这层传统对话框边框不受 DWM 颜色控制。
    auto windowStyle = ::GetWindowLongPtrW(m_handle, GWL_STYLE);
    ::SetWindowLongPtrW(m_handle, GWL_STYLE, windowStyle & ~(WS_CAPTION | WS_THICKFRAME));
    ::SetWindowPos(m_handle, nullptr, 0, 0, 0, 0, SWP_FRAMECHANGED | SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE);
    auto style = ::GetWindowLongPtrW(m_handle, GWL_EXSTYLE);
    ::SetWindowLongPtrW(m_handle, GWL_EXSTYLE, (style | WS_EX_TOOLWINDOW) & ~WS_EX_APPWINDOW);
    // Windows 11 使用系统圆角和阴影；旧系统忽略该属性。
    DWM_WINDOW_CORNER_PREFERENCE corners = DWMWCP_ROUND;
    ::DwmSetWindowAttribute(m_handle, DWMWA_WINDOW_CORNER_PREFERENCE, &corners, sizeof(corners));
    // 工具浮层保留系统圆角和阴影，避免默认浅色非客户区边框穿透深色主题。
    COLORREF border = DWMWA_COLOR_NONE;
    ::DwmSetWindowAttribute(m_handle, DWMWA_BORDER_COLOR, &border, sizeof(border));
    m_root = Grid();
    m_devicesPage = Markup::XamlReader::Load(LR"(<Grid xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
        xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml" Padding="12" RowSpacing="8" CornerRadius="8"
        Background="{ThemeResource AcrylicBackgroundFillColorDefaultBrush}">
        <Grid.RowDefinitions><RowDefinition Height="56"/><RowDefinition Height="*"/><RowDefinition Height="44"/></Grid.RowDefinitions>
        <Grid ColumnSpacing="12" Padding="8,0">
            <Grid.ColumnDefinitions><ColumnDefinition Width="28"/><ColumnDefinition Width="*"/><ColumnDefinition Width="32"/></Grid.ColumnDefinitions>
            <Image Source="ms-appx:///Assets/AppIcon.png" Width="28" Height="28"/>
            <StackPanel Grid.Column="1" Spacing="4" VerticalAlignment="Center"><TextBlock Text="AudioBule" FontSize="14" FontWeight="SemiBold"/><TextBlock x:Name="Summary" FontSize="12" Foreground="{ThemeResource TextFillColorSecondaryBrush}"/></StackPanel>
            <Button x:Name="More" Grid.Column="2" Width="32" Height="32" Padding="4" Background="Transparent" BorderThickness="0"><FontIcon Glyph="&#xE712;" FontSize="16"/></Button>
        </Grid>
        <Grid Grid.Row="1"><ScrollViewer VerticalScrollBarVisibility="Auto"><StackPanel x:Name="Rows"/></ScrollViewer><TextBlock x:Name="Empty" Margin="16,20" TextWrapping="Wrap" Foreground="{ThemeResource TextFillColorSecondaryBrush}" VerticalAlignment="Center"/></Grid>
        <Button x:Name="Open" Grid.Row="2" HorizontalAlignment="Stretch" HorizontalContentAlignment="Left" Background="Transparent" BorderThickness="0"/>
        </Grid>)").as<Grid>();
    m_rows = m_devicesPage.FindName(L"Rows").as<StackPanel>();
    m_summary = m_devicesPage.FindName(L"Summary").as<TextBlock>();
    m_empty = m_devicesPage.FindName(L"Empty").as<TextBlock>();
    m_more = m_devicesPage.FindName(L"More").as<Button>();
    m_open = m_devicesPage.FindName(L"Open").as<Button>();
    m_root.Children().Append(m_devicesPage);
    m_window.Content(m_root);
    m_devices.Initialize(m_rows, m_text, m_callbacks.operate, true);
    m_more.Click([this](auto const&, auto const&) { ShowMenu(m_anchor, m_more.FocusState() == FocusState::Keyboard); });
    m_open.Click([this](auto const&, auto const&) { Hide(); m_callbacks.navigate(L"devices"); });
    m_window.Activated([this](auto const&, WindowActivatedEventArgs const& args) {
        if (args.WindowActivationState() == WindowActivationState::Deactivated) Hide();
    });
    m_appWindow.Closing([this](auto const&, AppWindowClosingEventArgs const& args) { if (!m_closing) { args.Cancel(true); Hide(); } });
    m_root.KeyDown([this](auto const&, Input::KeyRoutedEventArgs const& args) {
        if (args.Key() == Windows::System::VirtualKey::Escape) { args.Handled(true); Hide(); }
    });
}
QuickPanel::~QuickPanel() { m_closing = true; if (m_window) m_window.Close(); }
void QuickPanel::ApplyPreferences(Core::AppSettings const& settings)
{
    m_root.Language(m_text.Locale());
    m_root.RequestedTheme(settings.theme == L"dark" ? ElementTheme::Dark : settings.theme == L"light" ? ElementTheme::Light : ElementTheme::Default);
    m_open.Content(box_value(m_text.Get(L"OpenWindow")));
    m_empty.Text(m_text.Get(L"EmptyBody"));
    Automation::AutomationProperties::SetName(m_more, m_text.Get(L"More"));
    if (m_menuMode) BuildMenu();
}
void QuickPanel::Render(std::vector<Core::ConnectionEntry> const& entries, std::set<std::wstring> const& pending)
{
    m_count = entries.size();
    size_t count = 0;
    for (auto const& entry : entries) count += entry.state == Core::ConnectionState::Connected;
    m_summary.Text(m_text.Count(count));
    m_devices.Update(entries, pending);
    m_empty.Visibility(entries.empty() ? Visibility::Visible : Visibility::Collapsed);
    if (m_appWindow.IsVisible() && !m_menuMode) Position();
}
void QuickPanel::BuildMenu()
{
    if (m_menu) m_root.Children().RemoveAt(m_root.Children().Size() - 1);
    m_menu = Markup::XamlReader::Load(LR"(<MenuFlyoutPresenter xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
        CornerRadius="8" BorderThickness="1" BorderBrush="{ThemeResource SurfaceStrokeColorFlyoutBrush}"
        Background="{ThemeResource AcrylicBackgroundFillColorDefaultBrush}"/>)").as<MenuFlyoutPresenter>();
    m_menu.HorizontalAlignment(HorizontalAlignment::Stretch);
    auto action = [this](wchar_t const* key, wchar_t const* glyph, std::function<void()> callback) {
        MenuFlyoutItem item; item.Text(m_text.Get(key)); FontIcon icon; icon.Glyph(glyph); item.Icon(icon);
        item.Click([this, callback](auto const&, auto const&) { Hide(); callback(); }); m_menu.Items().Append(item);
    };
    action(L"OpenWindow", L"\xE8A7", [this] { m_callbacks.navigate(L"devices"); });
    // 托盘菜单只保留程序命令，可配置项统一在设置页修改。
    action(L"Settings", L"\xE713", [this] { m_callbacks.navigate(L"settings"); });
    action(L"About", L"\xE946", [this] { m_callbacks.navigate(L"about"); });
    m_menu.Items().Append(MenuFlyoutSeparator());
    action(L"Exit", L"\xE8BB", m_callbacks.exit);
    m_root.Children().Append(m_menu);
}
void QuickPanel::Position()
{
    MONITORINFO monitor{ sizeof(monitor) };
    ::GetMonitorInfoW(::MonitorFromPoint(m_anchor, MONITOR_DEFAULTTONEAREST), &monitor);
    auto work = monitor.rcWork;
    int dpi = static_cast<int>(::GetDpiForWindow(m_handle));
    int width = std::min(::MulDiv(m_menuMode ? 248 : 352, dpi, 96), static_cast<int>(work.right - work.left - 16));
    int logicalHeight = 140 + static_cast<int>(std::min<size_t>(m_count, 5)) * 76;
    if (m_menuMode) {
        // 菜单根据实际内容测量高度，避免固定窗口尺寸产生底部空白。
        m_menu.ApplyTemplate();
        m_menu.Measure({ static_cast<float>(width * 96.0 / dpi), std::numeric_limits<float>::infinity() });
        logicalHeight = static_cast<int>(std::ceil(m_menu.DesiredSize().Height));
    }
    int height = ::MulDiv(logicalHeight, dpi, 96);
    if (!m_menuMode && !m_count) height = ::MulDiv(260, dpi, 96);
    height = std::min(height, static_cast<int>(work.bottom - work.top - 16));
    // 坐标夹在当前显示器工作区，支持负坐标和不同任务栏位置。
    int x = std::clamp(static_cast<int>(m_anchor.x) - width + 20, static_cast<int>(work.left) + 8, std::max(static_cast<int>(work.left) + 8, static_cast<int>(work.right) - width - 8));
    int y = std::clamp(static_cast<int>(m_anchor.y) - height - 12, static_cast<int>(work.top) + 8, std::max(static_cast<int>(work.top) + 8, static_cast<int>(work.bottom) - height - 8));
    m_appWindow.MoveAndResize({ x, y, width, height });
    // 移到另一缩放比例的显示器后，重新计算一次物理尺寸。
    if (::GetDpiForWindow(m_handle) != static_cast<UINT>(dpi)) Position();
}
void QuickPanel::Toggle(POINT anchor, bool keyboard)
{
    if (m_appWindow.IsVisible() && !m_menuMode) { Hide(); return; }
    m_anchor = anchor; m_menuMode = false;
    if (m_menu) { m_root.Children().RemoveAt(m_root.Children().Size() - 1); m_menu = nullptr; }
    m_devicesPage.Visibility(Visibility::Visible);
    Position(); m_appWindow.Show(); m_window.Activate(); ::SetForegroundWindow(m_handle);
    // 鼠标打开不显示键盘焦点框；键盘打开保留可见焦点及 Tab 导航。
    m_open.Focus(keyboard ? FocusState::Keyboard : FocusState::Pointer);
}
void QuickPanel::ShowMenu(POINT anchor, bool keyboard)
{
    m_anchor = anchor; m_menuMode = true;
    m_devicesPage.Visibility(Visibility::Collapsed);
    BuildMenu(); Position(); m_appWindow.Show(); m_window.Activate(); ::SetForegroundWindow(m_handle);
    m_menu.Items().GetAt(0).as<Control>().Focus(keyboard ? FocusState::Keyboard : FocusState::Pointer);
}
void QuickPanel::Hide()
{
    if (!m_appWindow || !m_appWindow.IsVisible()) return;
    m_appWindow.Hide();
    if (!m_closing && m_callbacks.restoreFocus) m_callbacks.restoreFocus();
}
}
