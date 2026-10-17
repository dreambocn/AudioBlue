#include "pch.h"
#include "MainWindow.xaml.h"
#include "DesktopIntegration.h"
#include <filesystem>
#include <microsoft.ui.xaml.window.h>
#include <commctrl.h>
#include <winrt/Microsoft.UI.Xaml.Media.Imaging.h>
#include <winrt/Microsoft.UI.Windowing.h>
#include <winrt/Microsoft.UI.Xaml.Automation.h>
#include <winrt/Windows.UI.Text.h>
#if __has_include("MainWindow.g.cpp")
#include "MainWindow.g.cpp"
#endif

using namespace winrt;
using namespace winrt::Microsoft::UI::Xaml;
using namespace winrt::Microsoft::UI::Xaml::Controls;
using namespace winrt::Microsoft::UI::Windowing;
namespace Core = ::AudioBule::Core;

namespace
{
TextBlock Label(hstring const& text, double size = 14, bool heading = false)
{
    TextBlock label;
    label.Text(text);
    label.FontSize(size);
    label.TextWrapping(TextWrapping::Wrap);
    if (heading) label.FontWeight(Windows::UI::Text::FontWeights::SemiBold());
    return label;
}
// 设置卡片由真实的 ToggleSwitch / ComboBox 组成，文本自动换行。
Grid SettingsCard(hstring const& title, hstring const& description, wchar_t const* glyph, UIElement const& action = nullptr)
{
    auto card = Markup::XamlReader::Load(LR"(<Grid xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
        MinHeight="76" Padding="16" ColumnSpacing="16" CornerRadius="4" BorderThickness="1"
        BorderBrush="{ThemeResource CardStrokeColorDefaultBrush}" Background="{ThemeResource CardBackgroundFillColorDefaultBrush}">
        <Grid.ColumnDefinitions><ColumnDefinition Width="20"/><ColumnDefinition Width="*"/><ColumnDefinition Width="Auto"/></Grid.ColumnDefinitions>
        </Grid>)").as<Grid>();
    FontIcon icon;
    icon.Glyph(glyph);
    icon.FontSize(20);
    icon.VerticalAlignment(VerticalAlignment::Center);
    card.Children().Append(icon);
    StackPanel labels;
    labels.Spacing(4);
    labels.VerticalAlignment(VerticalAlignment::Center);
    labels.Children().Append(Label(title));
    auto caption = Label(description, 12);
    caption.Opacity(0.65);
    labels.Children().Append(caption);
    Grid::SetColumn(labels, 1);
    card.Children().Append(labels);
    if (action) {
        // 操作区域宽度一致；内部开关靠右，避免把原生开关的空白宽度当成可见对齐。
        card.ColumnDefinitions().GetAt(2).Width({ 160, GridUnitType::Pixel });
        auto control = action.as<FrameworkElement>();
        control.MinWidth(0); control.Width(160);
        control.HorizontalAlignment(HorizontalAlignment::Left);
        control.VerticalAlignment(VerticalAlignment::Center);
        Grid::SetColumn(control, 2);
        card.Children().Append(control);
    }
    return card;
}
}

namespace winrt::AudioBule::App::implementation
{
void MainWindow::Initialize(::AudioBule::App::UI::UiText& text, std::function<void()> refresh,
    std::function<void()> addDevice, std::function<void(std::wstring const&, bool)> operate,
    std::function<void()> exit, std::function<void(Core::AppSettings const&)> preferences)
{
    InitializeComponent();
    m_text = &text;
    m_addDevice = std::move(addDevice);
    m_exit = std::move(exit);
    m_preferences = std::move(preferences);
    Title(L"AudioBule");
    // 标题栏图片和 EXE 资源不会自动设置任务栏图标，必须设置窗口图标。
    auto iconPath = std::filesystem::path(::AudioBule::App::UI::DesktopIntegration::ExecutablePath()).parent_path() / L"Assets" / L"AppIcon.ico";
    try { AppWindow().SetIcon(hstring(iconPath.wstring())); }
    catch (hresult_error const&) {
        // 外部图标丢失时回退到嵌入资源，避免因图标文件影响程序启动。
        for (auto type : { ICON_BIG, ICON_SMALL }) {
            int size = type == ICON_BIG ? 32 : 16;
            auto icon = ::LoadImageW(::GetModuleHandleW(nullptr), MAKEINTRESOURCEW(101), IMAGE_ICON, size, size, LR_SHARED);
            if (icon) ::SendMessageW(Handle(), WM_SETICON, type, reinterpret_cast<LPARAM>(icon));
        }
        ::OutputDebugStringW(L"AudioBule：窗口图标已回退到嵌入资源。\n");
    }
    ExtendsContentIntoTitleBar(true);
    SetTitleBar(TitleDragRegion());
    SystemBackdrop(Media::MicaBackdrop());
    AppWindow().TitleBar().PreferredHeightOption(TitleBarHeightOption::Tall);
    int dpi = static_cast<int>(::GetDpiForWindow(Handle()));
    AppWindow().ResizeClient({ ::MulDiv(960, dpi, 96), ::MulDiv(640, dpi, 96) });
    ::SetWindowSubclass(Handle(), WindowProcedure, 1, reinterpret_cast<DWORD_PTR>(this));
    auto weak = get_weak();
    RefreshButton().Click([refresh](auto const&, auto const&) { refresh(); });
    AddDeviceButton().Click([weak](auto const&, auto const&) { if (auto self = weak.get()) self->m_addDevice(); });
    EmptyAction().Click([weak](auto const&, auto const&) {
        if (auto self = weak.get()) { if (self->m_filtered) { self->m_filtered = false; self->Render(self->m_entries); } else self->m_addDevice(); }
    });
    NavigationButton().Click([weak](auto const&, auto const&) { if (auto self = weak.get()) self->Navigation().IsPaneOpen(!self->Navigation().IsPaneOpen()); });
    Navigation().SelectionChanged([weak](auto const&, NavigationViewSelectionChangedEventArgs const& args) {
        if (auto self = weak.get(); self && args.SelectedItem()) self->Navigate(std::wstring(unbox_value<hstring>(args.SelectedItem().as<NavigationViewItem>().Tag())));
    });
    AllFilter().Click([weak](auto const&, auto const&) { if (auto self = weak.get()) { self->m_filtered = false; self->Render(self->m_entries); } });
    ConnectedFilter().Click([weak](auto const&, auto const&) { if (auto self = weak.get()) { self->m_filtered = true; self->Render(self->m_entries); } });
    RootPanel().ActualThemeChanged([weak](auto const&, auto const&) { if (auto self = weak.get()) { self->UpdateCaption(); self->Render(self->m_entries); } });
    DevicesPage().SizeChanged([weak](auto const&, auto const&) {
        if (auto self = weak.get()) self->RefreshLabel().Visibility(self->DevicesPage().ActualWidth() < 380 ? Visibility::Collapsed : Visibility::Visible);
    });
    AppWindow().Closing([weak](auto const& window, AppWindowClosingEventArgs const& args) {
        if (auto self = weak.get(); self && !self->m_allowClose) {
            args.Cancel(true);
            if (self->m_trayAvailable) window.Hide();
            else self->ConfirmExit();
        }
    });
    m_devices.Initialize(DeviceRows(), text, std::move(operate));
    Navigation().SelectedItem(DevicesNav());
}
void MainWindow::ApplyPreferences(Core::AppSettings const& settings, bool startupPending, bool notificationsAvailable)
{
    m_updating = true;
    m_settings = settings;
    m_startupPending = startupPending;
    m_notificationsAvailable = notificationsAvailable;
    RootPanel().Language(m_text->Locale());
    RootPanel().RequestedTheme(settings.theme == L"dark" ? ElementTheme::Dark : settings.theme == L"light" ? ElementTheme::Light : ElementTheme::Default);
    DevicesNav().Content(box_value(m_text->Get(L"Devices")));
    SettingsNav().Content(box_value(m_text->Get(L"Settings")));
    AboutNav().Content(box_value(m_text->Get(L"About")));
    PageTitle().Text(m_text->Get(L"Devices"));
    PageDescription().Text(m_text->Get(L"DeviceDescription"));
    if (!m_statusKey.empty()) StatusBar().Message(m_text->Get(m_statusKey.c_str()));
    AddDeviceButton().Content(box_value(m_text->Get(L"AddDevice")));
    Automation::AutomationProperties::SetName(NavigationButton(), m_text->Get(L"ToggleNavigation"));
    BuildSettings();
    BuildAbout();
    UpdateCaption();
    Render(m_entries);
    SetRefreshing(m_refreshing);
    m_updating = false;
}
void MainWindow::BuildSettings()
{
    auto panel = SettingsRows();
    panel.Children().Clear();
    panel.Children().Append(Label(m_text->Get(L"Settings"), 28, true));
    auto description = Label(m_text->Get(L"SettingsDescription"));
    description.Opacity(0.65);
    description.Margin({ 0, 0, 0, 20 });
    panel.Children().Append(description);
    auto group = [this, panel](wchar_t const* key) {
        auto title = Label(m_text->Get(key), 14, true); title.Margin({ 0, 20, 0, 8 }); panel.Children().Append(title);
    };
    auto toggle = [this, panel](wchar_t const* key, wchar_t const* descriptionKey, wchar_t const* glyph, bool Core::AppSettings::*member, bool enabled) {
        ToggleSwitch control;
        control.MinWidth(0);
        control.Width(40);
        control.IsOn(m_settings.*member);
        // 状态文字放在开关左侧，开关轨道右边缘与下拉框统一对齐。
        control.OnContent(box_value(L""));
        control.OffContent(box_value(L""));
        control.IsEnabled(enabled);
        auto action = Markup::XamlReader::Load(LR"(<Grid xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation" ColumnSpacing="12">
            <Grid.ColumnDefinitions><ColumnDefinition Width="*"/><ColumnDefinition Width="40"/></Grid.ColumnDefinitions>
            </Grid>)").as<Grid>();
        auto state = Label(m_text->Get(control.IsOn() ? L"On" : L"Off"));
        state.HorizontalAlignment(HorizontalAlignment::Right);
        state.VerticalAlignment(VerticalAlignment::Center);
        state.Opacity(enabled ? 1.0 : 0.4);
        Automation::AutomationProperties::SetAccessibilityView(state, Automation::Peers::AccessibilityView::Raw);
        action.Children().Append(state);
        Grid::SetColumn(control, 1);
        control.VerticalAlignment(VerticalAlignment::Center);
        action.Children().Append(control);
        Automation::AutomationProperties::SetName(control, m_text->Get(key)); Automation::AutomationProperties::SetAutomationId(control, key);
        auto weak = get_weak();
        control.Toggled([weak, member, state](auto const& sender, auto const&) {
            if (auto self = weak.get(); self && !self->m_updating) {
                auto settings = self->m_settings; settings.*member = sender.template as<ToggleSwitch>().IsOn();
                state.Text(self->m_text->Get(settings.*member ? L"On" : L"Off"));
                self->m_preferences(settings);
            }
        });
        panel.Children().Append(SettingsCard(m_text->Get(key), m_text->Get(descriptionKey), glyph, action));
    };
    group(L"ConnectionStartup");
    toggle(L"AutoReconnect", L"AutoReconnectDescription", L"\xE72C", &Core::AppSettings::autoReconnect, true);
    toggle(L"RunAtStartup", L"StartupDescription", L"\xE7E8", &Core::AppSettings::runAtStartup, !m_startupPending);
    group(L"Notifications");
    toggle(L"ConnectionNotifications", m_notificationsAvailable ? L"NotificationsDescription" : L"NotificationsUnavailable", L"\xEA8F", &Core::AppSettings::connectionNotifications, m_notificationsAvailable);
    group(L"Personalization");
    auto combo = [this, panel](wchar_t const* key, wchar_t const* descriptionKey, wchar_t const* glyph,
        std::wstring Core::AppSettings::*member, std::initializer_list<std::pair<wchar_t const*, wchar_t const*>> options) {
        ComboBox control;
        control.MinWidth(160);
        Automation::AutomationProperties::SetName(control, m_text->Get(key)); Automation::AutomationProperties::SetAutomationId(control, key);
        for (auto const& [value, label] : options) {
            ComboBoxItem item; item.Content(box_value(m_text->Get(label))); item.Tag(box_value(hstring(value))); control.Items().Append(item);
            if (m_settings.*member == value) control.SelectedItem(item);
        }
        auto weak = get_weak();
        control.SelectionChanged([weak, member](auto const& sender, auto const&) {
            if (auto self = weak.get(); self && !self->m_updating) {
                auto selected = sender.template as<ComboBox>().SelectedItem().template try_as<ComboBoxItem>();
                if (selected) { auto settings = self->m_settings; settings.*member = unbox_value<hstring>(selected.Tag()); self->m_preferences(settings); }
            }
        });
        panel.Children().Append(SettingsCard(m_text->Get(key), m_text->Get(descriptionKey), glyph, control));
    };
    combo(L"Theme", L"ThemeDescription", L"\xE790", &Core::AppSettings::theme, { {L"system",L"System"}, {L"light",L"Light"}, {L"dark",L"Dark"} });
    combo(L"Language", L"LanguageDescription", L"\xE774", &Core::AppSettings::language, { {L"system",L"System"}, {L"zh-CN",L"Chinese"}, {L"en-US",L"English"} });
    Button exit;
    exit.Content(box_value(m_text->Get(L"Exit")));
    exit.Margin({ 0, 20, 0, 8 });
    auto weak = get_weak();
    exit.Click([weak](auto const&, auto const&) { if (auto self = weak.get()) self->ConfirmExit(); });
    panel.Children().Append(exit);
}
void MainWindow::BuildAbout()
{
    auto panel = AboutRows();
    panel.Children().Clear();
    panel.Children().Append(Label(m_text->Get(L"About"), 28, true));
    Image image;
    image.Source(Media::Imaging::BitmapImage(Windows::Foundation::Uri(L"ms-appx:///Assets/AppIcon.png")));
    image.Width(80); image.Height(80); image.Margin({ 0, 24, 0, 8 }); image.HorizontalAlignment(HorizontalAlignment::Left);
    panel.Children().Append(image);
    panel.Children().Append(Label(L"AudioBule", 24, true));
    panel.Children().Append(Label(m_text->Get(L"Version"), 12));
    auto description = Label(m_text->Get(L"AboutDescription")); description.Margin({ 0, 4, 0, 16 }); description.Opacity(0.65); panel.Children().Append(description);
    panel.Children().Append(SettingsCard(m_text->Get(L"DesignedForWindows"), m_text->Get(L"NativeAudio"), L"\xE782"));
    panel.Children().Append(SettingsCard(m_text->Get(L"Independent"), m_text->Get(L"IndependentDescription"), L"\xE8EA"));
    panel.Children().Append(SettingsCard(m_text->Get(L"HowToListen"), m_text->Get(L"ListenDescription"), L"\xE946"));
    // 固定的窗口关闭行为属于使用说明，不作为无法修改的设置项展示。
    panel.Children().Append(SettingsCard(m_text->Get(L"CloseBehavior"), m_text->Get(L"CloseDescription"), L"\xE8BB"));
}
void MainWindow::Navigate(std::wstring const& page)
{
    DevicesPage().Visibility(page == L"devices" ? Visibility::Visible : Visibility::Collapsed);
    SettingsPage().Visibility(page == L"settings" ? Visibility::Visible : Visibility::Collapsed);
    AboutPage().Visibility(page == L"about" ? Visibility::Visible : Visibility::Collapsed);
    auto item = page == L"settings" ? SettingsNav() : page == L"about" ? AboutNav() : DevicesNav();
    if (Navigation().SelectedItem() != item) Navigation().SelectedItem(item);
    if (Navigation().DisplayMode() == NavigationViewDisplayMode::Minimal && RootPanel().ActualWidth() > 0) Navigation().IsPaneOpen(false);
    SummaryText().Visibility(page == L"devices" ? Visibility::Visible : Visibility::Collapsed);
}
void MainWindow::Render(std::vector<Core::ConnectionEntry> const& entries)
{
    if (m_stopping) return;
    m_entries = entries;
    size_t count = 0;
    for (auto const& entry : entries) count += entry.state == Core::ConnectionState::Connected;
    auto visible = m_devices.Update(entries, m_pendingDevices, m_filtered);
    AllFilter().Content(box_value(m_text->Get(L"AllDevices") + L"  " + to_hstring(entries.size())));
    ConnectedFilter().Content(box_value(m_text->Get(L"ConnectedDevices") + L"  " + to_hstring(count)));
    AllIndicator().Visibility(m_filtered ? Visibility::Collapsed : Visibility::Visible);
    ConnectedIndicator().Visibility(m_filtered ? Visibility::Visible : Visibility::Collapsed);
    EmptyState().Visibility(visible ? Visibility::Collapsed : Visibility::Visible);
    EmptyTitle().Text(m_text->Get(m_filtered ? L"FilteredTitle" : L"EmptyTitle"));
    EmptyDescription().Text(m_text->Get(m_filtered ? L"FilteredBody" : L"EmptyBody"));
    EmptyAction().Content(box_value(m_text->Get(m_filtered ? L"ViewAll" : L"BluetoothSettings")));
    SummaryText().Text(m_text->Count(count));
}
void MainWindow::SetRefreshing(bool refreshing)
{
    m_refreshing = refreshing;
    RefreshButton().IsEnabled(!refreshing && !m_stopping);
    RefreshLabel().Text(m_text->Get(refreshing ? L"Refreshing" : L"Refresh"));
}
void MainWindow::SetOperationPending(std::wstring const& id, bool pending)
{
    if (pending) m_pendingDevices.insert(id); else m_pendingDevices.erase(id);
    Render(m_entries);
}
void MainWindow::SetStopping()
{
    m_stopping = true;
    RootPanel().IsHitTestVisible(false);
    SummaryText().Text(m_text->Get(L"Stopping"));
}
void MainWindow::SetStatus(std::wstring const& status) { StatusBar().Message(status); StatusBar().IsOpen(true); }
void MainWindow::SetStatusKey(wchar_t const* key) { m_statusKey = key; SetStatus(std::wstring(m_text->Get(key))); }
void MainWindow::UpdateCaption()
{
    auto dark = RootPanel().ActualTheme() == ElementTheme::Dark;
    AppWindow().TitleBar().ButtonBackgroundColor(Windows::UI::Color{ 0, 0, 0, 0 });
    AppWindow().TitleBar().ButtonInactiveBackgroundColor(Windows::UI::Color{ 0, 0, 0, 0 });
    AppWindow().TitleBar().ButtonForegroundColor(dark ? Windows::UI::Color{ 255, 255, 255, 255 } : Windows::UI::Color{ 255, 0, 0, 0 });
}
LRESULT CALLBACK MainWindow::WindowProcedure(HWND window, UINT message, WPARAM wParam, LPARAM lParam, UINT_PTR, DWORD_PTR data)
{
    // 最小化与关闭都回到托盘；退出必须走确认和异步连接清理。
    auto self = reinterpret_cast<MainWindow*>(data);
    if (message == WM_SYSCOMMAND && (wParam & 0xfff0) == SC_MINIMIZE && self->m_trayAvailable) { ::ShowWindow(window, SW_HIDE); return 0; }
    if (message == WM_GETMINMAXINFO) {
        auto limits = reinterpret_cast<MINMAXINFO*>(lParam);
        int dpi = static_cast<int>(::GetDpiForWindow(window));
        limits->ptMinTrackSize = { ::MulDiv(400, dpi, 96), ::MulDiv(420, dpi, 96) };
        return 0;
    }
    if (message == WM_NCDESTROY) ::RemoveWindowSubclass(window, WindowProcedure, 1);
    return ::DefSubclassProc(window, message, wParam, lParam);

}
void MainWindow::Show() { AppWindow().Show(); Activate(); ::SetForegroundWindow(Handle()); }
void MainWindow::Toggle() { if (AppWindow().IsVisible()) AppWindow().Hide(); else Show(); }
fire_and_forget MainWindow::ConfirmExit()
{
    auto lifetime = get_strong();
    if (m_confirming || m_stopping) co_return;
    m_confirming = true;
    Show();
    try {
        ContentDialog dialog;
        dialog.XamlRoot(RootPanel().XamlRoot());
        dialog.RequestedTheme(RootPanel().ActualTheme());
        dialog.Title(box_value(m_text->Get(L"ExitTitle")));
        dialog.Content(box_value(m_text->Get(L"ExitBody")));
        dialog.PrimaryButtonText(m_text->Get(L"ExitAction"));
        dialog.CloseButtonText(m_text->Get(L"Cancel"));
        dialog.DefaultButton(ContentDialogButton::Close);
        if (co_await dialog.ShowAsync() == ContentDialogResult::Primary) m_exit();
    } catch (...) { ::OutputDebugStringW(L"AudioBule：退出确认无法显示。\n"); }
    m_confirming = false;
}
void MainWindow::CloseForExit() { m_allowClose = true; Close(); }
HWND MainWindow::Handle() const
{
    HWND handle{};
    check_hresult(static_cast<Window>(*this).as<::IWindowNative>()->get_WindowHandle(&handle));
    return handle;
}
int32_t MainWindow::Placeholder() { return 0; }
void MainWindow::Placeholder(int32_t) {}
}
