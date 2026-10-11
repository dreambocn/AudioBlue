#include "pch.h"
#include "MainWindow.xaml.h"
#include <microsoft.ui.xaml.window.h>
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
using ::AudioBule::Core::ConnectionState;

namespace winrt::AudioBule::App::implementation
{
void MainWindow::Initialize(std::function<void()> refresh, std::function<void()> addDevice,
    std::function<void(std::wstring const&, bool)> operate, std::function<void()> exit)
{
    InitializeComponent();
    Title(L"AudioBule · 蓝牙音频");
    m_operate = std::move(operate);
    m_exit = std::move(exit);
    auto weak = get_weak();
    RefreshButton().Click([refresh = std::move(refresh)](auto const&, auto const&) { refresh(); });
    AddDeviceButton().Click([addDevice = std::move(addDevice)](auto const&, auto const&) { addDevice(); });
    ExitButton().Click([weak](auto const&, auto const&) { if (auto self = weak.get()) self->m_exit(); });
    // AppWindow 使用物理像素，按当前窗口 DPI 缩放初始客户区。
    int dpi = static_cast<int>(::GetDpiForWindow(Handle()));
    AppWindow().ResizeClient({ ::MulDiv(540, dpi, 96), ::MulDiv(580, dpi, 96) });
    AppWindow().Closing([weak](auto const& window, AppWindowClosingEventArgs const& args) {
        if (auto self = weak.get(); self && !self->m_allowClose)
        {
            args.Cancel(true);
            window.Hide();
        }
    });
}

void MainWindow::Render(std::vector<::AudioBule::Core::ConnectionEntry> const& entries)
{
    if (m_stopping) return;
    bool rebuild = entries.size() != m_rows.size();
    for (auto const& entry : entries) rebuild = rebuild || !m_rows.contains(entry.deviceId);
    if (rebuild)
    {
        DeviceList().Items().Clear();
        m_rows.clear();
        for (auto const& entry : entries)
        {
            DeviceRow row;
            Grid grid;
            grid.Padding({ 12, 12, 12, 12 });
            grid.ColumnSpacing(12);
            ColumnDefinition details;
            details.Width({ 1, GridUnitType::Star });
            ColumnDefinition actions;
            actions.Width({ 1, GridUnitType::Auto });
            grid.ColumnDefinitions().Append(details);
            grid.ColumnDefinitions().Append(actions);
            StackPanel labels;
            labels.Spacing(6);
            row.name = TextBlock();
            row.name.FontSize(16);
            row.name.FontWeight(Windows::UI::Text::FontWeights::SemiBold());
            row.name.TextWrapping(TextWrapping::Wrap);
            row.status = TextBlock();
            row.status.FontSize(12);
            row.error = TextBlock();
            row.error.TextWrapping(TextWrapping::Wrap);
            row.error.FontSize(12);
            labels.Children().Append(row.name);
            labels.Children().Append(row.status);
            labels.Children().Append(row.error);
            StackPanel controls;
            controls.Spacing(8);
            controls.VerticalAlignment(VerticalAlignment::Center);
            Grid::SetColumn(controls, 1);
            row.progress = ProgressRing();
            row.progress.Width(24);
            row.progress.Height(24);
            row.action = Button();
            row.action.MinWidth(76);
            auto weak = get_weak();
            auto id = entry.deviceId;
            row.action.Click([weak, id](auto const&, auto const&) {
                if (auto self = weak.get(); self && !self->m_stopping)
                {
                    // Tag 随状态更新，避免按钮回调捕获旧状态。
                    auto found = self->m_rows.find(id);
                    if (found != self->m_rows.end())
                        self->m_operate(id, unbox_value<bool>(found->second.action.Tag()));
                }
            });
            controls.Children().Append(row.progress);
            controls.Children().Append(row.action);
            grid.Children().Append(labels);
            grid.Children().Append(controls);
            ListViewItem item;
            item.HorizontalContentAlignment(HorizontalAlignment::Stretch);
            item.Content(grid);
            DeviceList().Items().Append(item);
            m_rows.emplace(entry.deviceId, std::move(row));
        }
    }
    size_t connected = 0;
    for (auto const& entry : entries)
    {
        auto& row = m_rows.at(entry.deviceId);
        bool busy = entry.state == ConnectionState::Connecting;
        bool active = entry.state == ConnectionState::Connected;
        bool failed = entry.state == ConnectionState::Failed;
        if (active) ++connected;
        row.name.Text(entry.displayName);
        row.status.Text(active ? L"● 已连接" : busy ? L"正在连接…" : failed ? L"连接失败" : L"未连接");
        auto key = active ? L"SystemFillColorSuccessBrush" : failed ? L"SystemFillColorCriticalBrush" : L"TextFillColorSecondaryBrush";
        row.status.Foreground(Application::Current().Resources().Lookup(box_value(key)).as<Media::Brush>());
        row.error.Text(entry.errorMessage);
        row.error.Visibility(failed ? Visibility::Visible : Visibility::Collapsed);
        row.error.Foreground(row.status.Foreground());
        row.progress.IsActive(busy);
        row.progress.Visibility(busy ? Visibility::Visible : Visibility::Collapsed);
        row.action.Content(box_value(active ? L"断开" : failed ? L"重试" : L"连接"));
        row.action.Tag(box_value(active));
        row.action.IsEnabled(!busy && !m_pendingDevices.contains(entry.deviceId));
        Automation::AutomationProperties::SetName(row.action,
            hstring(entry.displayName + (active ? L"：断开连接" : L"：连接设备")));
    }
    EmptyState().Visibility(entries.empty() ? Visibility::Visible : Visibility::Collapsed);
    DeviceList().Visibility(entries.empty() ? Visibility::Collapsed : Visibility::Visible);
    SummaryText().Text(hstring(std::to_wstring(entries.size()) + L" 台设备 · " + std::to_wstring(connected) + L" 台已连接"));
}

void MainWindow::SetRefreshing(bool refreshing)
{
    RefreshButton().IsEnabled(!refreshing && !m_stopping);
    if (refreshing) SummaryText().Text(L"正在刷新设备…");
}
void MainWindow::SetOperationPending(std::wstring const& id, bool pending)
{
    if (pending) m_pendingDevices.insert(id);
    else m_pendingDevices.erase(id);
    // Render 在状态变化时会再次应用该集合，异步断开完成前不能重新连接。
    if (pending)
    {
        auto found = m_rows.find(id);
        if (found != m_rows.end()) found->second.action.IsEnabled(false);
    }
}
void MainWindow::SetStopping()
{
    m_stopping = true;
    RootPanel().IsHitTestVisible(false);
    RefreshButton().IsEnabled(false);
    AddDeviceButton().IsEnabled(false);
    ExitButton().IsEnabled(false);
    for (auto const& [id, row] : m_rows) row.action.IsEnabled(false);
    FooterText().Text(L"正在完成连接操作并退出…");
}
void MainWindow::SetStatus(std::wstring const& status) { FooterText().Text(status); }
void MainWindow::Show()
{
    AppWindow().Show();
    Activate();
    ::SetForegroundWindow(Handle());
}
void MainWindow::Toggle()
{
    if (AppWindow().IsVisible()) AppWindow().Hide();
    else Show();
}
void MainWindow::CloseForExit() { m_allowClose = true; Close(); }
HWND MainWindow::Handle() const
{
    HWND handle{};
    check_hresult(static_cast<Microsoft::UI::Xaml::Window>(*this).as<::IWindowNative>()->get_WindowHandle(&handle));
    return handle;
}
// 保留 IDL 占位属性，内部窗口操作无需进入 WinRT 元数据。
int32_t MainWindow::Placeholder() { return 0; }
void MainWindow::Placeholder(int32_t) {}
}
