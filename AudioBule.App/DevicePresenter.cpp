#include "pch.h"
#include "DevicePresenter.h"
#include <winrt/Microsoft.UI.Xaml.Automation.h>

using namespace winrt;
using namespace winrt::Microsoft::UI::Xaml;
using namespace winrt::Microsoft::UI::Xaml::Controls;

namespace AudioBule::App::UI
{
void DevicePresenter::Initialize(StackPanel const& target, UiText& text,
    std::function<void(std::wstring const&, DeviceAction)> operate, bool compact)
{
    m_target = target;
    m_text = &text;
    m_operate = std::move(operate);
    m_compact = compact;
}
size_t DevicePresenter::Update(std::vector<Core::ConnectionEntry> const& entries,
    std::set<std::wstring> const& pending, bool connectedOnly)
{
    bool rebuild = entries.size() != m_rows.size();
    for (auto const& entry : entries) rebuild |= !m_rows.contains(entry.deviceId);
    if (rebuild)
    {
        m_target.Children().Clear();
        m_rows.clear();
        for (auto const& entry : entries)
        {
            // 固定预留左侧重连位置，主要按钮在所有状态下保持同宽、靠右对齐。
            auto grid = Markup::XamlReader::Load(LR"(
                <Grid xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
                      xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml" MinHeight="76" Padding="16"
                      ColumnSpacing="16" Background="{ThemeResource CardBackgroundFillColorDefaultBrush}"
                      BorderBrush="{ThemeResource CardStrokeColorDefaultBrush}" BorderThickness="1" CornerRadius="4">
                    <Grid.ColumnDefinitions><ColumnDefinition Width="24"/><ColumnDefinition Width="*"/><ColumnDefinition Width="Auto"/></Grid.ColumnDefinitions>
                    <FontIcon Glyph="&#xE8EA;" FontSize="24" VerticalAlignment="Center"/>
                    <StackPanel Grid.Column="1" Spacing="4" VerticalAlignment="Center">
                        <TextBlock x:Name="Name" FontSize="14" TextTrimming="CharacterEllipsis"/>
                        <StackPanel Orientation="Horizontal" Spacing="6">
                            <Ellipse x:Name="Dot" Width="4" Height="4" VerticalAlignment="Center"/>
                            <ProgressRing x:Name="Progress" Width="14" Height="14" MinWidth="14" MinHeight="14" Visibility="Collapsed"/>
                            <TextBlock x:Name="Status" FontSize="12" Foreground="{ThemeResource TextFillColorSecondaryBrush}"/>
                        </StackPanel>
                        <TextBlock x:Name="Error" FontSize="12" TextWrapping="Wrap" Foreground="{ThemeResource TextFillColorSecondaryBrush}" Visibility="Collapsed"/>
                        <TextBlock x:Name="Hint" FontSize="12" TextWrapping="Wrap" Foreground="{ThemeResource TextFillColorSecondaryBrush}" Visibility="Collapsed"/>
                    </StackPanel>
                    <Grid Grid.Column="2" ColumnSpacing="4" VerticalAlignment="Center">
                        <Grid.ColumnDefinitions><ColumnDefinition Width="32"/><ColumnDefinition Width="96"/></Grid.ColumnDefinitions>
                        <Button x:Name="Reconnect" Width="32" Height="32" Padding="4" Background="Transparent" BorderThickness="0" Visibility="Collapsed"><FontIcon Glyph="&#xE72C;" FontSize="16"/></Button>
                        <Button x:Name="Action" Grid.Column="1" Width="96" MinHeight="32" Padding="12,4"/>
                    </Grid>
                </Grid>)").as<Grid>();
            if (m_compact)
            {
                grid.Padding({ 12, 12, 12, 12 });
                grid.BorderThickness({ 0, 0, 0, 1 });
                grid.CornerRadius({ 0 });
                grid.Background(nullptr);
            }
            Row row;
            row.root = grid; row.name = grid.FindName(L"Name").as<TextBlock>(); row.status = grid.FindName(L"Status").as<TextBlock>();
            row.error = grid.FindName(L"Error").as<TextBlock>(); row.hint = grid.FindName(L"Hint").as<TextBlock>();
            row.dot = grid.FindName(L"Dot").as<Shapes::Ellipse>(); row.action = grid.FindName(L"Action").as<Button>();
            row.reconnect = grid.FindName(L"Reconnect").as<Button>(); row.progress = grid.FindName(L"Progress").as<ProgressRing>();
            auto operate = m_operate;
            row.action.Click([operate, id = entry.deviceId](winrt::Windows::Foundation::IInspectable const& sender, auto const&) {
                operate(id, static_cast<DeviceAction>(unbox_value<int32_t>(sender.as<Button>().Tag())));
            });
            row.reconnect.Click([operate, id = entry.deviceId, action = row.action](auto const& sender, auto const&) {
                auto keyboard = sender.template as<Button>().FocusState() == FocusState::Keyboard;
                operate(id, DeviceAction::Reconnect);
                // 只为键盘操作转移焦点，后台自动化或鼠标触发不能抢占窗口激活。
                if (keyboard) action.Focus(FocusState::Keyboard);
            });
            m_target.Children().Append(grid);
            m_rows.emplace(entry.deviceId, std::move(row));
        }
    }
    size_t visible = 0;
    for (auto const& entry : entries)
    {
        auto& row = m_rows.at(entry.deviceId);
        bool active = entry.state == Core::ConnectionState::Connected;
        bool reconnecting = entry.state == Core::ConnectionState::Reconnecting;
        bool busy = entry.state == Core::ConnectionState::Connecting || reconnecting;
        bool failed = entry.state == Core::ConnectionState::Failed;
        bool processing = pending.contains(entry.deviceId) && !busy;
        bool show = !connectedOnly || active || busy;
        visible += show;
        row.root.Visibility(show ? Visibility::Visible : Visibility::Collapsed);
        row.name.Text(entry.displayName);
        row.status.Text(m_text->Get(reconnecting ? L"Reconnecting" : busy ? L"Connecting" : processing ? L"Processing" : active ? L"Connected" : failed ? L"Failed" : L"Disconnected"));
        auto dark = m_target.ActualTheme() == ElementTheme::Dark;
        auto color = active ? (dark ? Windows::UI::Color{ 255, 139, 214, 139 } : Windows::UI::Color{ 255, 15, 123, 15 }) :
            failed ? (dark ? Windows::UI::Color{ 255, 255, 153, 164 } : Windows::UI::Color{ 255, 196, 43, 28 }) :
            (dark ? Windows::UI::Color{ 255, 153, 153, 153 } : Windows::UI::Color{ 255, 117, 117, 117 });
        row.dot.Fill(Media::SolidColorBrush(color));
        row.dot.Visibility(busy ? Visibility::Collapsed : Visibility::Visible);
        row.progress.IsActive(busy);
        row.progress.Visibility(busy ? Visibility::Visible : Visibility::Collapsed);
        bool error = failed || entry.failure != Core::ConnectFailure::None;
        row.error.Text(error ? m_text->Error(entry) : L"");
        row.error.Visibility(error ? Visibility::Visible : Visibility::Collapsed);
        row.hint.Text(m_text->Get(L"ConnectedAudioHint"));
        row.hint.Visibility(active && !processing && !error && !m_compact ? Visibility::Visible : Visibility::Collapsed);
        row.reconnect.IsEnabled(active && !processing);
        row.reconnect.Visibility(active ? Visibility::Visible : Visibility::Collapsed);
        Automation::AutomationProperties::SetName(row.reconnect, entry.displayName + L": " + std::wstring(m_text->Get(L"Reconnect")));
        Automation::AutomationProperties::SetHelpText(row.reconnect, m_text->Get(L"ReconnectDescription"));
        Automation::AutomationProperties::SetHelpText(row.action, active ? m_text->Get(L"ConnectedAudioHint") : L"");
        ToolTipService::SetToolTip(row.reconnect, box_value(m_text->Get(L"Reconnect")));
        auto action = m_text->Get(busy ? L"Cancel" : active ? L"Disconnect" : failed ? L"Retry" : L"Connect");
        row.action.Content(box_value(action));
        row.action.Tag(box_value(static_cast<int32_t>(busy ? DeviceAction::Cancel : active ? DeviceAction::Disconnect : DeviceAction::Connect)));
        row.action.IsEnabled(!processing);
        Automation::AutomationProperties::SetName(row.action, hstring(entry.displayName + L": " + std::wstring(action)));
    }
    return visible;
}
}
