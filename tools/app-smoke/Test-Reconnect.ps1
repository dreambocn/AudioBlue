param(
    [string]$Executable = (Join-Path $PSScriptRoot '..\..\artifacts\build\x64\Release\AudioBule.App\bin\AudioBule.exe'),
    [string]$OutputDirectory = (Join-Path $env:TEMP ('AudioBuleReconnect_' + [Guid]::NewGuid().ToString('N'))),
    [switch]$TestFilterTabs,
    [switch]$TestActionLayout
)

$ErrorActionPreference = 'Stop'
Write-Output '准备隔离的原生重连控件测试。'
$Executable = (Resolve-Path -LiteralPath $Executable).Path
$OutputDirectory = [IO.Path]::GetFullPath($OutputDirectory)
$null = New-Item -ItemType Directory -Path $OutputDirectory -Force
$testData = Join-Path $OutputDirectory ('data-' + [Guid]::NewGuid().ToString('N'))
$null = New-Item -ItemType Directory -Path (Join-Path $testData 'AudioBule') -Force
'{"language":"zh-CN","theme":"light","autoReconnect":false,"lastConnectedDevices":[]}' |
    Set-Content -LiteralPath (Join-Path $testData 'AudioBule\settings.json') -Encoding utf8
$runtime = Get-ChildItem "$env:ProgramFiles\dotnet\shared\Microsoft.WindowsDesktop.App" -Directory |
    Where-Object { $_.Name.StartsWith([Environment]::Version.Major.ToString() + '.') } |
    Sort-Object { [version]$_.Name } -Descending | Select-Object -First 1
if (-not $runtime) { throw '缺少与 PowerShell 对应的 Windows Desktop Runtime。' }
foreach ($assembly in 'WindowsBase.dll', 'UIAutomationTypes.dll', 'UIAutomationClient.dll') {
    Add-Type -Path (Join-Path $runtime.FullName $assembly)
}
Add-Type -AssemblyName System.Drawing
Write-Output '自动化程序集已加载，正在准备窗口接口。'
if (-not ('AudioBuleReconnect.Native' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
using System.Text;
namespace AudioBuleReconnect {
    public static class Native {
        public delegate bool EnumProc(IntPtr window, IntPtr parameter);
        [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc callback, IntPtr parameter);
        [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr window, out uint process);
        [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowText(IntPtr window, StringBuilder text, int count);
        [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern IntPtr FindWindowEx(IntPtr parent, IntPtr after, string name, string title);
        [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr window);
        [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
        [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr window, uint message, IntPtr wparam, IntPtr lparam);
        [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr window, out Rect rect);
        [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr window, IntPtr dc, uint flags);
        [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr window, IntPtr after, int x, int y, int width, int height, uint flags);
        [StructLayout(LayoutKind.Sequential)] public struct Rect { public int left, top, right, bottom; }
        public static IntPtr FindTitle(uint process, string title) {
            IntPtr found = IntPtr.Zero;
            EnumWindows((window, parameter) => {
                uint owner; GetWindowThreadProcessId(window, out owner);
                var text = new StringBuilder(256); GetWindowText(window, text, text.Capacity);
                if (owner == process && text.ToString() == title) { found = window; return false; }
                return true;
            }, IntPtr.Zero);
            return found;
        }
        // 仅接受本次进程的托盘回调窗口，避免操作正在运行的安装版。
        public static IntPtr FindCallback(uint process) {
            IntPtr window = IntPtr.Zero;
            while ((window = FindWindowEx(new IntPtr(-3), window, "AudioBule.Tray", "AudioBule.Tray.Callback")) != IntPtr.Zero) {
                uint owner; GetWindowThreadProcessId(window, out owner);
                if (owner == process) return window;
            }
            return IntPtr.Zero;
        }
    }
}
'@
}
$scope = [System.Windows.Automation.TreeScope]::Descendants
$script:passed = 0
function Assert-Condition([bool]$Condition, [string]$Description) {
    if (-not $Condition) { throw "验证失败：$Description" }
    $script:passed++
    Write-Output "通过：$Description"
}
function Wait-Condition([scriptblock]$Condition, [int]$TimeoutMs = 8000) {
    $deadline = [DateTime]::UtcNow.AddMilliseconds($TimeoutMs)
    do {
        if ($application.HasExited) { throw "测试应用提前退出：$($application.ExitCode)" }
        if (& $Condition) { return $true }
        Start-Sleep -Milliseconds 80
    } while ([DateTime]::UtcNow -lt $deadline)
    return $false
}
function Find-Ui($Root, [string]$Value, [switch]$Name) {
    $property = if ($Name) { [System.Windows.Automation.AutomationElement]::NameProperty } else { [System.Windows.Automation.AutomationElement]::AutomationIdProperty }
    $condition = [System.Windows.Automation.PropertyCondition]::new($property, $Value)
    $Root.FindFirst($scope, $condition)
}
function Find-Popup([string]$Name) {
    $condition = [System.Windows.Automation.AndCondition]::new(
        [System.Windows.Automation.PropertyCondition]::new([System.Windows.Automation.AutomationElement]::ProcessIdProperty, [int]$application.Id),
        [System.Windows.Automation.PropertyCondition]::new([System.Windows.Automation.AutomationElement]::NameProperty, $Name))
    [System.Windows.Automation.AutomationElement]::RootElement.FindFirst($scope, $condition)
}
function Invoke-Ui($Element) {
    if (-not $Element) { throw '目标控件不存在。' }
    $pattern = $null
    if ($Element.TryGetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern, [ref]$pattern)) { $pattern.Invoke() }
    elseif ($Element.TryGetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern, [ref]$pattern)) { $pattern.Select() }
    else { throw "控件无法调用：$($Element.Current.Name)" }
    Start-Sleep -Milliseconds 80
}
function Save-WindowImage([IntPtr]$Handle, [string]$Name) {
    $bounds = [AudioBuleReconnect.Native+Rect]::new()
    $null = [AudioBuleReconnect.Native]::GetWindowRect($Handle, [ref]$bounds)
    $bitmap = [Drawing.Bitmap]::new($bounds.right - $bounds.left, $bounds.bottom - $bounds.top)
    $graphics = [Drawing.Graphics]::FromImage($bitmap)
    $dc = $graphics.GetHdc()
    try { $null = [AudioBuleReconnect.Native]::PrintWindow($Handle, $dc, 2) }
    finally { $graphics.ReleaseHdc($dc); $graphics.Dispose() }
    try { $bitmap.Save((Join-Path $OutputDirectory ($Name + '.png')), [Drawing.Imaging.ImageFormat]::Png) }
    finally { $bitmap.Dispose() }
}
function Reconnect-Ui($Root, [string]$Action) {
    Assert-Condition (Wait-Condition { $button = Find-Ui $Root ($deviceName + ': ' + $Action) -Name; $button -and $button.Current.IsEnabled -and -not $button.Current.IsOffscreen }) '前次操作清理完成后重连按钮可用'
    $button = Find-Ui $Root ($deviceName + ': ' + $Action) -Name
    Assert-Condition ($button.Current.HelpText.Length -gt 0) '重连按钮提供可访问的帮助文本'
    Invoke-Ui $button
}
function Get-ActionGeometry($Root, [string]$Action) {
    $bounds = (Find-Ui $Root ($deviceName + ': ' + $Action) -Name).Current.BoundingRectangle
    $container = $Root.Current.BoundingRectangle
    [pscustomobject]@{ RightInset = $container.Right - $bounds.Right; Width = $bounds.Width }
}
function Test-ActionGeometry($Root, [string]$Action, $Reference, [string]$Description, [string]$Reconnect = '') {
    $geometry = Get-ActionGeometry $Root $Action
    Assert-Condition ([Math]::Abs($geometry.RightInset - $Reference.RightInset) -le 1 -and [Math]::Abs($geometry.Width - $Reference.Width) -le 1) ($Description + '：主要按钮宽度及右边距保持不变')
    if ($Reconnect) {
        $primary = (Find-Ui $Root ($deviceName + ': ' + $Action) -Name).Current.BoundingRectangle
        $secondary = Find-Ui $Root ($deviceName + ': ' + $Reconnect) -Name
        $bounds = $secondary.Current.BoundingRectangle
        Assert-Condition ($bounds.Width -gt 0 -and $bounds.Right -lt $primary.Left -and [Math]::Abs(($bounds.Top + $bounds.Height / 2) - ($primary.Top + $primary.Height / 2)) -le 1) ($Description + '：重连图标位于主要按钮左侧且垂直居中')
        Assert-Condition ($secondary.Current.IsKeyboardFocusable) ($Description + '：重连图标保留键盘入口')
    }
}
function Test-FilterSelection($Root, [string]$Suffix) {
    $all = Find-Ui $Root 'AllFilter'
    $connected = Find-Ui $Root 'ConnectedFilter'
    Assert-Condition ($all.Current.ControlType -eq [System.Windows.Automation.ControlType]::RadioButton -and $connected.Current.ControlType -eq [System.Windows.Automation.ControlType]::RadioButton) '文字页签保留原生单选角色'
    $allSelection = $all.GetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern)
    $connectedSelection = $connected.GetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern)
    Assert-Condition ($allSelection.Current.IsSelected -and -not $connectedSelection.Current.IsSelected) '全部设备默认选中且互斥'
    Save-WindowImage $window ('filters-' + $Suffix)
    $connectedSelection.Select()
    Assert-Condition (Wait-Condition { $connectedSelection.Current.IsSelected -and -not $allSelection.Current.IsSelected }) '已连接筛选可通过辅助技术选择'
    $allSelection.Select()
    Assert-Condition (Wait-Condition { $allSelection.Current.IsSelected -and -not $connectedSelection.Current.IsSelected }) '全部设备筛选可以恢复'
    Assert-Condition ($all.Current.IsKeyboardFocusable -and $connected.Current.IsKeyboardFocusable) '两个页签均暴露为键盘可聚焦控件'
    if ([AudioBuleReconnect.Native]::GetForegroundWindow() -eq $window) {
        $all.SetFocus()
        Assert-Condition (Wait-Condition { $all.Current.HasKeyboardFocus }) '全部设备页签可以获得键盘焦点'
        Save-WindowImage $window ('filters-focus-' + $Suffix)
        $connected.SetFocus()
        Assert-Condition (Wait-Condition { $connected.Current.HasKeyboardFocus }) '已连接页签可以获得键盘焦点'
    } else {
        Write-Output '测试窗口处于后台，仅核验可聚焦语义，不抢占用户前台焦点。'
    }
    $allSelection.Select()
}
function Select-ComboOption($Root, [string]$Id, [string]$Option) {
    $combo = Find-Ui $Root $Id
    $scroll = $null
    if ($combo.TryGetCurrentPattern([System.Windows.Automation.ScrollItemPattern]::Pattern,[ref]$scroll)) { $scroll.ScrollIntoView() }
    $combo.GetCurrentPattern([System.Windows.Automation.ExpandCollapsePattern]::Pattern).Expand()
    Assert-Condition (Wait-Condition { $null -ne (Find-Popup $Option) }) '主题选项可用'
    Invoke-Ui (Find-Popup $Option)
}
$application = $null
$deviceName = 'AudioBule 测试手机'
try {
    Write-Output '启动仅含虚拟设备的测试进程。'
    # 双标志只传入子进程，绕开 Shell 启动等待；父进程环境不变。
    $start = [Diagnostics.ProcessStartInfo]::new($Executable)
    $start.UseShellExecute = $false
    $start.WindowStyle = [Diagnostics.ProcessWindowStyle]::Hidden
    $start.WorkingDirectory = Split-Path -Parent $Executable
    $start.Environment['LOCALAPPDATA'] = $testData
    $start.Environment['AUDIOBULE_SMOKE_TEST'] = '1'
    $start.Environment['AUDIOBULE_SMOKE_SIMULATE_DEVICES'] = '1'
    $application = [Diagnostics.Process]::Start($start)
    Assert-Condition (Wait-Condition { [AudioBuleReconnect.Native]::FindTitle([uint32]$application.Id, 'AudioBule') -ne [IntPtr]::Zero }) '隔离测试主窗口建立'
    $window = [AudioBuleReconnect.Native]::FindTitle([uint32]$application.Id, 'AudioBule')
    $root = [System.Windows.Automation.AutomationElement]::FromHandle($window)
    # 先核验唯一虚拟设备，再执行任何连接操作。
    Assert-Condition (Wait-Condition { $null -ne (Find-Ui $root $deviceName -Name) }) '确认双标志启用虚拟设备'
    if ($TestFilterTabs) { Test-FilterSelection $root 'zh-light' }
    if ($TestActionLayout) { $mainGeometry = Get-ActionGeometry $root '连接'; Save-WindowImage $window 'actions-disconnected-zh' }
    Invoke-Ui (Find-Ui $root ($deviceName + ': 连接') -Name)
    Assert-Condition (Wait-Condition { $null -ne (Find-Ui $root ($deviceName + ': 断开') -Name) }) '虚拟设备连接成功'
    Start-Sleep -Milliseconds 1200
    Assert-Condition ($null -ne (Find-Ui $root ($deviceName + ': 断开') -Name)) '没有播放信号时仍保持连接'
    Save-WindowImage $window 'connected-zh'
    if ($TestActionLayout) { Test-ActionGeometry $root '断开' $mainGeometry '主窗口已连接' '重新连接' }
    Reconnect-Ui $root '重新连接'
    Assert-Condition (Wait-Condition { $null -ne (Find-Ui $root '重新连接中' -Name) }) '重连期间显示独立进度状态'
    Assert-Condition ((Find-Ui $root ($deviceName + ': 取消') -Name).Current.IsEnabled) '重连期间保留取消入口'
    Save-WindowImage $window 'reconnecting-zh'
    if ($TestActionLayout) { Test-ActionGeometry $root '取消' $mainGeometry '主窗口重连中' }
    Invoke-Ui (Find-Ui $root ($deviceName + ': 取消') -Name)
    Assert-Condition (Wait-Condition { $button = Find-Ui $root ($deviceName + ': 连接') -Name; $button -and $button.Current.IsEnabled }) '取消后清理完成并恢复连接按钮'
    if ($TestActionLayout) { Test-ActionGeometry $root '连接' $mainGeometry '主窗口取消后' }
    Invoke-Ui (Find-Ui $root ($deviceName + ': 连接') -Name)
    Assert-Condition (Wait-Condition { $null -ne (Find-Ui $root ($deviceName + ': 断开') -Name) }) '取消后可以再次连接'
    Reconnect-Ui $root '重新连接'
    Assert-Condition (Wait-Condition { $null -ne (Find-Ui $root '重新连接中' -Name) }) '主窗口重连开始'
    Assert-Condition (Wait-Condition { $null -ne (Find-Ui $root ($deviceName + ': 断开') -Name) }) '主窗口一次操作完成重连'

    # 直接模拟本进程回调以验证快速面板控件，不将其当作 Shell 登记成功的证据。
    $callback = [AudioBuleReconnect.Native]::FindCallback([uint32]$application.Id)
    Assert-Condition ($callback -ne [IntPtr]::Zero) '定位本次进程的托盘回调窗口'
    $null = [AudioBuleReconnect.Native]::PostMessage($callback, 0x8001, [IntPtr]0, [IntPtr]0x10400)
    $null = [AudioBuleReconnect.Native]::PostMessage($callback, 0x8001, [IntPtr]0, [IntPtr]0x202)
    Assert-Condition (Wait-Condition { $panel = [AudioBuleReconnect.Native]::FindTitle([uint32]$application.Id, 'AudioBule.QuickPanel'); $panel -ne [IntPtr]::Zero -and [AudioBuleReconnect.Native]::IsWindowVisible($panel) }) '虚拟设备快速面板打开'
    $panel = [AudioBuleReconnect.Native]::FindTitle([uint32]$application.Id, 'AudioBule.QuickPanel')
    $quick = [System.Windows.Automation.AutomationElement]::FromHandle($panel)
    Start-Sleep -Milliseconds 300
    Save-WindowImage $panel 'connected-tray'
    if ($TestActionLayout) {
        $quickGeometry = Get-ActionGeometry $quick '断开'
        Test-ActionGeometry $quick '断开' $quickGeometry '快速面板已连接' '重新连接'
    }
    Reconnect-Ui $quick '重新连接'
    Assert-Condition (Wait-Condition { $null -ne (Find-Ui $root '重新连接中' -Name) }) '快速面板按钮触发同一重连操作'
    # 自动化可能使面板失去激活；保留实际关闭策略，重新打开后验证共享状态。
    if (-not [AudioBuleReconnect.Native]::IsWindowVisible($panel)) {
        Write-Output '自动化操作后面板失去激活，重新打开核对状态。'
        $null = [AudioBuleReconnect.Native]::PostMessage($callback, 0x8001, [IntPtr]0, [IntPtr]0x10400)
        $null = [AudioBuleReconnect.Native]::PostMessage($callback, 0x8001, [IntPtr]0, [IntPtr]0x202)
    }
    Assert-Condition (Wait-Condition { $null -ne (Find-Ui $quick '重新连接中' -Name) }) '快速面板共享重连状态'
    Save-WindowImage $panel 'reconnecting-tray'
    if ($TestActionLayout) { Test-ActionGeometry $quick '取消' $quickGeometry '快速面板重连中' }
    Invoke-Ui (Find-Ui $quick ($deviceName + ': 取消') -Name)
    Assert-Condition (Wait-Condition { $button = Find-Ui $root ($deviceName + ': 连接') -Name; $button -and $button.Current.IsEnabled }) '快速面板可以取消重连'
    if (-not [AudioBuleReconnect.Native]::IsWindowVisible($panel)) {
        $null = [AudioBuleReconnect.Native]::PostMessage($callback, 0x8001, [IntPtr]0, [IntPtr]0x10400)
        $null = [AudioBuleReconnect.Native]::PostMessage($callback, 0x8001, [IntPtr]0, [IntPtr]0x202)
    }
    Assert-Condition (Wait-Condition { $null -ne (Find-Ui $quick ($deviceName + ': 连接') -Name) }) '快速面板同步取消后的断开状态'
    if ($TestActionLayout) {
        Test-ActionGeometry $quick '连接' $quickGeometry '快速面板取消后'
        Save-WindowImage $panel 'actions-disconnected-tray'
    }
    Invoke-Ui (Find-Ui $quick '打开设备窗口' -Name)
    Invoke-Ui (Find-Ui $root 'SettingsNav')
    $language = Find-Ui $root 'Language'
    $scroll = $null
    if ($language.TryGetCurrentPattern([System.Windows.Automation.ScrollItemPattern]::Pattern, [ref]$scroll)) { $scroll.ScrollIntoView() }
    $language.GetCurrentPattern([System.Windows.Automation.ExpandCollapsePattern]::Pattern).Expand()
    Assert-Condition (Wait-Condition { $null -ne (Find-Popup 'English') }) '语言选择提供英文'
    Invoke-Ui (Find-Popup 'English')
    Invoke-Ui (Find-Ui $root 'DevicesNav')
    Invoke-Ui (Find-Ui $root ($deviceName + ': Connect') -Name)
    Assert-Condition (Wait-Condition { $null -ne (Find-Ui $root ($deviceName + ': Disconnect') -Name) }) '英文连接按钮可用'
    if ($TestActionLayout) { Test-ActionGeometry $root 'Disconnect' $mainGeometry '英文主窗口' 'Reconnect' }
    Reconnect-Ui $root 'Reconnect'
    Assert-Condition (Wait-Condition { $null -ne (Find-Ui $root 'Reconnecting' -Name) }) '英文重连状态正确'
    Assert-Condition (Wait-Condition { $null -ne (Find-Ui $root ($deviceName + ': Disconnect') -Name) }) '英文重连完成'
    Save-WindowImage $window 'connected-en'
    if ($TestFilterTabs -or $TestActionLayout) {
        if ($TestFilterTabs) { Test-FilterSelection $root 'en-light' }
        Invoke-Ui (Find-Ui $root 'SettingsNav')
        Select-ComboOption $root 'Theme' 'Dark'
        Invoke-Ui (Find-Ui $root 'DevicesNav')
        if ($TestFilterTabs) { Test-FilterSelection $root 'en-dark' }
        $null = [AudioBuleReconnect.Native]::SetWindowPos($window,[IntPtr]::Zero,0,0,640,620,0x6)
        Start-Sleep -Milliseconds 200
        Save-WindowImage $window 'filters-en-dark-narrow'
        Assert-Condition (-not (Find-Ui $root 'AllFilter').Current.IsOffscreen -and -not (Find-Ui $root 'ConnectedFilter').Current.IsOffscreen) '窄窗口保留两个完整筛选入口'
        if ($TestActionLayout) {
            $narrowGeometry = Get-ActionGeometry $root 'Disconnect'
            Test-ActionGeometry $root 'Disconnect' $narrowGeometry '英文深色窄窗口' 'Reconnect'
            Invoke-Ui (Find-Ui $root ($deviceName + ': Disconnect') -Name)
            Assert-Condition (Wait-Condition { $button = Find-Ui $root ($deviceName + ': Connect') -Name; $button -and $button.Current.IsEnabled }) '英文窄窗口断开完成'
            Test-ActionGeometry $root 'Connect' $narrowGeometry '英文深色窄窗口断开后'
            Save-WindowImage $window 'actions-disconnected-en-dark-narrow'
        }
        $null = [AudioBuleReconnect.Native]::SetWindowPos($window,[IntPtr]::Zero,0,0,976,680,0x6)
    }
    Invoke-Ui (Find-Ui $root 'SettingsNav')
    $exit = Find-Ui $root 'Exit AudioBule' -Name
    $scroll = $null
    if ($exit.TryGetCurrentPattern([System.Windows.Automation.ScrollItemPattern]::Pattern, [ref]$scroll)) { $scroll.ScrollIntoView() }
    Invoke-Ui $exit
    Assert-Condition (Wait-Condition { $null -ne (Find-Ui $root 'Exit' -Name) }) '退出前显示确认框'
    Invoke-Ui (Find-Ui $root 'Exit' -Name)
    Assert-Condition ($application.WaitForExit(10000) -and $application.ExitCode -eq 0) '确认退出后完成清理'
    Write-Output "原生重连控件冒烟通过，共 $script:passed 项；证据目录：$OutputDirectory"
} finally {
    if ($application) {
        $application.Refresh()
        if (-not $application.HasExited) {
            # 只结束本次启动的隔离进程，测试数据保留供排查，不清理用户目录。
            Stop-Process -Id $application.Id
            $null = $application.WaitForExit(5000)
        }
        $application.Dispose()
    }
}
