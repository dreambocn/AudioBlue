param(
    [string]$Executable = (Join-Path $PSScriptRoot '..\..\AudioBule.App\bin\AudioBule.exe'),
    [string]$ScreenshotPath,
    [switch]$TestDiagnosticPicker
)

$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $Executable)) { throw "找不到应用：$Executable" }

# 只向本次启动的测试进程发消息，不操作其它应用或重启 Explorer。
if (-not ('AudioBuleSmoke.Native' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;
namespace AudioBuleSmoke {
    public static class Native {
        public delegate bool EnumProc(IntPtr window, IntPtr parameter);
        [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc callback, IntPtr parameter);
        [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr window, out uint process);
        [DllImport("user32.dll")] public static extern uint GetDpiForWindow(IntPtr window);
        [DllImport("user32.dll", EntryPoint="GetWindowLongPtrW")] public static extern IntPtr GetWindowLongPtr(IntPtr window, int index);
        [DllImport("user32.dll")] public static extern bool GetGUIThreadInfo(uint thread, ref ThreadInfo info);
        [StructLayout(LayoutKind.Sequential)] public struct ThreadInfo {
            public uint size, flags;
            public IntPtr active, focus, capture, menuOwner, moveSize, caret;
            public Rect caretRect;
        }
        [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetClassName(IntPtr window, StringBuilder text, int count);
        [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern IntPtr FindWindowEx(IntPtr parent, IntPtr after, string name, string title);
        [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr window);
        [DllImport("user32.dll")] public static extern IntPtr GetDlgItem(IntPtr window, int identifier);
        [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
        [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr window);
        [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr window, uint message, IntPtr wparam, IntPtr lparam);
        [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern uint RegisterWindowMessage(string text);
        [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern IntPtr SendMessage(IntPtr window, uint message, IntPtr wparam, IntPtr lparam);
        [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern IntPtr LoadImage(IntPtr instance, string name, uint type, int width, int height, uint flags);
        [DllImport("user32.dll")] public static extern bool DestroyIcon(IntPtr icon);
        [DllImport("user32.dll")] public static extern int GetMenuItemCount(IntPtr menu);
        [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetMenuString(IntPtr menu, uint item, StringBuilder text, int count, uint flags);
        [DllImport("user32.dll")] public static extern uint GetGuiResources(IntPtr process, uint flags);
        [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr window, out Rect rect);
        [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr window, IntPtr dc, uint flags);
        [DllImport("shell32.dll")] public static extern int Shell_NotifyIconGetRect(ref IconIdentifier identifier, out Rect rect);
        [StructLayout(LayoutKind.Sequential)] public struct Rect { public int left, top, right, bottom; }
        [StructLayout(LayoutKind.Sequential)] public struct IconIdentifier { public uint size; public IntPtr window; public uint id; public Guid guid; }
        public static IntPtr Find(uint process, string name) {
            IntPtr found = IntPtr.Zero;
            EnumWindows((window, parameter) => {
                uint owner; GetWindowThreadProcessId(window, out owner);
                var text = new StringBuilder(256); GetClassName(window, text, text.Capacity);
                if (owner == process && text.ToString() == name) { found = window; return false; }
                return true;
            }, IntPtr.Zero);
            return found;
        }
        [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowText(IntPtr window, StringBuilder text, int count);
        [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr window, IntPtr after, int x, int y, int width, int height, uint flags);
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
        public static bool HasIcon(IntPtr window) {
            var identifier = new IconIdentifier { size = (uint)Marshal.SizeOf<IconIdentifier>(), window = window, id = 1 };
            Rect rect; return Shell_NotifyIconGetRect(ref identifier, out rect) == 0;
        }
        // 消息窗口不在 EnumWindows 中，逐个查找并核验进程，避免影响用户正在运行的实例。
        public static IntPtr FindCallback(uint process) {
            IntPtr window = IntPtr.Zero;
            while ((window = FindWindowEx(new IntPtr(-3), window, "AudioBule.Tray", "AudioBule.Tray.Callback")) != IntPtr.Zero) {
                uint owner; GetWindowThreadProcessId(window, out owner);
                if (owner == process) return window;
            }
            return IntPtr.Zero;
        }
        public static bool SendEscape(IntPtr panel, uint process) {
            uint owner;
            uint thread = GetWindowThreadProcessId(panel, out owner);
            var info = new ThreadInfo { size = (uint)Marshal.SizeOf<ThreadInfo>() };
            if (owner != process || !GetGUIThreadInfo(thread, ref info) || info.focus == IntPtr.Zero) return false;
            GetWindowThreadProcessId(info.focus, out owner);
            // 键盘消息送到测试进程当前的输入窗口，不能直接送到顶层宿主。
            return owner == process && PostMessage(info.focus, 0x100, new IntPtr(0x1B), new IntPtr(1));
        }
    }
}
'@
}

function Assert-Condition([bool]$Condition, [string]$Description) {
    if (-not $Condition) { throw "验证失败：$Description" }
    Write-Output "通过：$Description"
}

function Wait-Condition([scriptblock]$Condition, [int]$TimeoutMs = 8000) {
    $deadline = [DateTime]::UtcNow.AddMilliseconds($TimeoutMs)
    do {
        if (& $Condition) { return $true }
        Start-Sleep -Milliseconds 100
    } while ([DateTime]::UtcNow -lt $deadline)
    return $false
}

# 临时目录隔离配置，测试不启用真实开机启动或注册系统通知。
$testData = Join-Path ([IO.Path]::GetTempPath()) ('AudioBuleSmoke_' + [Guid]::NewGuid().ToString('N'))
$originalLocalAppData = $env:LOCALAPPDATA
$originalSmoke = $env:AUDIOBULE_SMOKE_TEST
$application = $null
$runtime = Get-ChildItem "$env:ProgramFiles\dotnet\shared\Microsoft.WindowsDesktop.App" -Directory |
    Where-Object { $_.Name.StartsWith([Environment]::Version.Major.ToString() + '.') } |
    Sort-Object { [version]$_.Name } -Descending | Select-Object -First 1
if (-not $runtime) { throw '缺少与 PowerShell 对应的 Windows Desktop Runtime。' }
foreach ($assembly in 'WindowsBase.dll', 'UIAutomationTypes.dll', 'UIAutomationClient.dll') { Add-Type -Path (Join-Path $runtime.FullName $assembly) }
$scope = [System.Windows.Automation.TreeScope]::Descendants
function Find-Ui($Root, [string]$Value, [switch]$Name) {
    $property = if ($Name) { [System.Windows.Automation.AutomationElement]::NameProperty } else { [System.Windows.Automation.AutomationElement]::AutomationIdProperty }
    $Root.FindFirst($scope, [System.Windows.Automation.PropertyCondition]::new($property, $Value))
}
function Invoke-Ui($Element) {
    if (-not $Element) { throw '目标控件不存在。' }
    $pattern = $null
    if ($Element.TryGetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern, [ref]$pattern)) { $pattern.Invoke() }
    elseif ($Element.TryGetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern, [ref]$pattern)) { $pattern.Select() }
    else { throw "控件无法调用：$($Element.Current.Name)" }
    Start-Sleep -Milliseconds 250
}
function Save-WindowImage([IntPtr]$Handle, [string]$Suffix) {
    if (-not $ScreenshotPath) { return }
    Add-Type -AssemblyName System.Drawing
    Start-Sleep -Milliseconds 400
    $bounds = [AudioBuleSmoke.Native+Rect]::new()
    $null = [AudioBuleSmoke.Native]::GetWindowRect($Handle, [ref]$bounds)
    $bitmap = [Drawing.Bitmap]::new($bounds.right - $bounds.left, $bounds.bottom - $bounds.top)
    $graphics = [Drawing.Graphics]::FromImage($bitmap)
    $dc = $graphics.GetHdc()
    try { $null = [AudioBuleSmoke.Native]::PrintWindow($Handle, $dc, 2) }
    finally { $graphics.ReleaseHdc($dc); $graphics.Dispose() }
    try {
        $destination = [IO.Path]::GetFullPath($ScreenshotPath)
        if ($Suffix) { $destination = Join-Path (Split-Path $destination) ([IO.Path]::GetFileNameWithoutExtension($destination) + "-$Suffix.png") }
        $null = New-Item -ItemType Directory -Path (Split-Path $destination) -Force
        $bitmap.Save($destination, [Drawing.Imaging.ImageFormat]::Png)
        Write-Output "截图：$destination"
    } finally { $bitmap.Dispose() }
}
function Select-Combo($Root, [string]$Name, [string]$Option) {
    $combo = Find-Ui $Root $Name
    if (-not $combo) { throw "找不到下拉框：$Name" }
    $scroll = $null
    if ($combo.TryGetCurrentPattern([System.Windows.Automation.ScrollItemPattern]::Pattern, [ref]$scroll)) { $scroll.ScrollIntoView() }
    $combo.GetCurrentPattern([System.Windows.Automation.ExpandCollapsePattern]::Pattern).Expand()
    Start-Sleep -Milliseconds 200
    $optionElement = Find-Ui $Root $Option -Name
    if (-not $optionElement) { throw "找不到选项：$Option" }
    Invoke-Ui $optionElement
}
function Test-WindowIcon([IntPtr]$Window, [string]$Path, [int]$Kind) {
    # 对比实际窗口图标与品牌 ICO 像素，防止通用默认图标也通过非空检查。
    Add-Type -AssemblyName System.Drawing
    $handle = [AudioBuleSmoke.Native]::SendMessage($Window, 0x7F, [IntPtr]$Kind, [IntPtr]0)
    if ($handle -eq [IntPtr]::Zero) { return $false }
    $actual = [Drawing.Icon]::FromHandle($handle).ToBitmap()
    $reference = [AudioBuleSmoke.Native]::LoadImage([IntPtr]::Zero, $Path, 1, $actual.Width, $actual.Height, 0x10)
    $expected = $null
    try {
        if ($reference -eq [IntPtr]::Zero) { throw '无法加载对照品牌图标。' }
        $expected = [Drawing.Icon]::FromHandle($reference).ToBitmap()
        for ($y = 0; $y -lt $actual.Height; $y++) {
            for ($x = 0; $x -lt $actual.Width; $x++) {
                if ($actual.GetPixel($x, $y).ToArgb() -ne $expected.GetPixel($x, $y).ToArgb()) { return $false }
            }
        }
        return $true
    } finally {
        $actual.Dispose()
        if ($expected) { $expected.Dispose() }
        if ($reference -ne [IntPtr]::Zero) { $null = [AudioBuleSmoke.Native]::DestroyIcon($reference) }
    }
}
try {
    $null = New-Item -ItemType Directory -Path (Join-Path $testData 'AudioBule') -Force
    '{"language":"zh-CN","theme":"light","autoReconnect":true,"lastConnectedDevices":[]}' | Set-Content (Join-Path $testData 'AudioBule\settings.json') -Encoding utf8
    $env:LOCALAPPDATA = $testData; $env:AUDIOBULE_SMOKE_TEST = '1'
    $application = Start-Process -FilePath $Executable -ArgumentList '--startup' -WindowStyle Hidden -PassThru
    $env:LOCALAPPDATA = $originalLocalAppData; $env:AUDIOBULE_SMOKE_TEST = $originalSmoke
    Assert-Condition (Wait-Condition {
        $application.Refresh()
        if ($application.HasExited) { throw ('应用启动崩溃：0x{0:X8}' -f $application.ExitCode) }
        [AudioBuleSmoke.Native]::Find([uint32]$application.Id, 'AudioBule.Tray') -ne [IntPtr]::Zero
    }) '启动成功且托盘线程正常'
    $broadcast = [AudioBuleSmoke.Native]::Find([uint32]$application.Id, 'AudioBule.Tray')
    $callback = [AudioBuleSmoke.Native]::FindCallback([uint32]$application.Id)
    Assert-Condition ($callback -ne [IntPtr]::Zero) '托盘消息窗口属于本次测试进程'
    $window = [AudioBuleSmoke.Native]::FindTitle([uint32]$application.Id, 'AudioBule')
    $panel = [AudioBuleSmoke.Native]::FindTitle([uint32]$application.Id, 'AudioBule.QuickPanel')
    Assert-Condition ($window -ne [IntPtr]::Zero -and $panel -ne [IntPtr]::Zero) '主窗口与独立快速面板已创建'
    $iconPath = Join-Path (Split-Path ([IO.Path]::GetFullPath($Executable))) 'Assets\AppIcon.ico'
    Assert-Condition (Test-WindowIcon $window $iconPath 1) '主窗口大图标与品牌图标一致'
    Assert-Condition (Test-WindowIcon $window $iconPath 0) '主窗口小图标与品牌图标一致'
    Assert-Condition (-not [AudioBuleSmoke.Native]::IsWindowVisible($window)) '开机启动模式不弹出主窗口'
    Assert-Condition ([AudioBuleSmoke.Native]::HasIcon($callback)) 'Shell 已登记托盘图标'
    $null = [AudioBuleSmoke.Native]::PostMessage($callback, 0x8001, [IntPtr]0, [IntPtr]0x10400)
    Assert-Condition (Wait-Condition { [AudioBuleSmoke.Native]::IsWindowVisible($panel) }) '托盘左键显示快速面板'
    Assert-Condition (([AudioBuleSmoke.Native]::GetWindowLongPtr($panel, -16).ToInt64() -band 0xC40000) -eq 0) '托盘窗口没有传统对话框和调整大小边框'
    $quickRoot = [System.Windows.Automation.AutomationElement]::FromHandle($panel)
    Assert-Condition ($null -ne (Find-Ui $quickRoot '打开设备窗口' -Name)) '快速面板使用中文资源'
    Save-WindowImage $panel 'tray'
    Invoke-Ui (Find-Ui $quickRoot '打开设备窗口' -Name)
    Assert-Condition (Wait-Condition { [AudioBuleSmoke.Native]::IsWindowVisible($window) -and -not [AudioBuleSmoke.Native]::IsWindowVisible($panel) }) '快速面板打开主窗口并收起'
    $root = [System.Windows.Automation.AutomationElement]::FromHandle($window)
    Assert-Condition ($null -ne (Find-Ui $root '设备' -Name)) '主窗口设备页使用中文资源'
    Invoke-Ui (Find-Ui $root 'RefreshButton')
    Assert-Condition (Wait-Condition { (Find-Ui $root 'RefreshButton').Current.IsEnabled }) '真实设备枚举和刷新不阻塞界面'
    Save-WindowImage $window ''
    Invoke-Ui (Find-Ui $root 'SettingsNav')
    Assert-Condition ($null -ne (Find-Ui $root '启动时自动重连' -Name)) '设置页显示原生开关'
    Assert-Condition ($null -ne (Find-Ui $root 'DiagnosticsExport')) '设置页提供原生诊断导出按钮'
    Assert-Condition (Wait-Condition { (Find-Ui $root 'DiagnosticsStatus').Current.Name.Contains('本地日志存储正常') }) '本轮隔离实例日志存储可用'
    Invoke-Ui (Find-Ui $root 'DiagnosticsDetailed')
    Assert-Condition (Wait-Condition { (Find-Ui $root 'DiagnosticsStatus').Current.Name.Contains('剩余秒数') }) '详细日志可临时开启并显示剩余时间'
    Invoke-Ui (Find-Ui $root 'DiagnosticsDetailed')
    Assert-Condition (Wait-Condition { -not (Find-Ui $root 'DiagnosticsStatus').Current.Name.Contains('剩余秒数') }) '详细日志可关闭'
    $diagnosticsButton = Find-Ui $root 'DiagnosticsDetailed'
    $diagnosticsScroll = $null
    if ($diagnosticsButton.TryGetCurrentPattern([System.Windows.Automation.ScrollItemPattern]::Pattern, [ref]$diagnosticsScroll)) { $diagnosticsScroll.ScrollIntoView() }
    Save-WindowImage $window 'diagnostics'
    if ($TestDiagnosticPicker) {
        # 只操作本轮测试进程拥有的原生保存对话框。
        $exportButton = Find-Ui $root 'DiagnosticsExport'
        $null = [AudioBuleSmoke.Native]::SetForegroundWindow($window)
        Assert-Condition (Wait-Condition { [AudioBuleSmoke.Native]::GetForegroundWindow() -eq $window }) '模拟用户在前台主窗口发起诊断导出'
        $exportButton.SetFocus()
        Invoke-Ui $exportButton
        Assert-Condition (Wait-Condition { [AudioBuleSmoke.Native]::Find([uint32]$application.Id, '#32770') -ne [IntPtr]::Zero }) '诊断导出打开原生保存对话框'
        $saveDialog = [System.Windows.Automation.AutomationElement]::FromHandle([AudioBuleSmoke.Native]::Find([uint32]$application.Id, '#32770'))
        Write-Output ("保存对话框标题：{0}" -f $saveDialog.Current.Name)
        Save-WindowImage ([AudioBuleSmoke.Native]::Find([uint32]$application.Id, '#32770')) 'picker'
        # 本机 Shell 将可写文件名通过 SaveDialogLabel 暴露，不能假定角色为 Edit。
        $null = Wait-Condition {
            $candidate = Find-Ui $saveDialog 'SaveDialogLabel'
            $candidate -and $candidate.GetCurrentPropertyValue([System.Windows.Automation.AutomationElement]::IsValuePatternAvailableProperty)
        }
        $fileName = Find-Ui $saveDialog 'SaveDialogLabel'
        Assert-Condition ($null -ne $fileName) '原生保存对话框提供文件名编辑框'
        $exportPath = Join-Path $testData 'AudioBule\diagnostic-export.jsonl'
        $candidates = $saveDialog.FindAll($scope, [System.Windows.Automation.PropertyCondition]::new([System.Windows.Automation.AutomationElement]::AutomationIdProperty, '1001'))
        $nativeEdit = @($candidates | Where-Object { $_.Current.Name -eq 'AudioBule-diagnostics' -and $_.Current.ClassName -eq 'Edit' -and $_.Current.NativeWindowHandle -ne 0 }) | Select-Object -First 1
        Assert-Condition ($null -ne $nativeEdit) '保存对话框的文件名区域具有原生句柄'
        $textPointer = [Runtime.InteropServices.Marshal]::StringToHGlobalUni($exportPath)
        try {
            # 替换选区触发原生编辑通知，避免 Shell 沿用默认文件名。
            $null = [AudioBuleSmoke.Native]::SendMessage([IntPtr]$nativeEdit.Current.NativeWindowHandle, 0x00B1, [IntPtr]::Zero, [IntPtr](-1))
            $null = [AudioBuleSmoke.Native]::SendMessage([IntPtr]$nativeEdit.Current.NativeWindowHandle, 0x00C2, [IntPtr]1, $textPointer)
        }
        finally { [Runtime.InteropServices.Marshal]::FreeHGlobal($textPointer) }

        $readPointer = [Runtime.InteropServices.Marshal]::AllocHGlobal(65536)
        try {
            $null = [AudioBuleSmoke.Native]::SendMessage([IntPtr]$nativeEdit.Current.NativeWindowHandle, 0x000D, [IntPtr]32768, $readPointer)
            $selectedText = [Runtime.InteropServices.Marshal]::PtrToStringUni($readPointer)
        }
        finally { [Runtime.InteropServices.Marshal]::FreeHGlobal($readPointer) }
        Assert-Condition ($selectedText -eq $exportPath) '文件名输入只指向本轮隔离目录'
        $dialogHandle = [AudioBuleSmoke.Native]::Find([uint32]$application.Id, '#32770')
        $saveHandle = [AudioBuleSmoke.Native]::GetDlgItem($dialogHandle, 1)
        $buttonClass = [Text.StringBuilder]::new(256)
        $null = [AudioBuleSmoke.Native]::GetClassName($saveHandle, $buttonClass, $buttonClass.Capacity)
        Assert-Condition ($saveHandle -ne [IntPtr]::Zero -and $buttonClass.ToString() -eq 'Button') '保存操作定位到本对话框的原生确认按钮'
        $null = [AudioBuleSmoke.Native]::SendMessage($dialogHandle, 0x0028, $saveHandle, [IntPtr]1)
        $null = [AudioBuleSmoke.Native]::SendMessage($saveHandle, 0x00F5, [IntPtr]::Zero, [IntPtr]::Zero)
        $saved = Wait-Condition { (Test-Path -LiteralPath $exportPath) -and (Find-Ui $root 'DiagnosticsExport').Current.IsEnabled }
        if (-not $saved) {
            Write-Output ("导出按钮启用状态：{0}；目标文件存在：{1}" -f (Find-Ui $root 'DiagnosticsExport').Current.IsEnabled, (Test-Path -LiteralPath $exportPath))
            Get-ChildItem -LiteralPath (Join-Path $testData 'AudioBule') -File | Select-Object Name,Length | Format-Table | Out-String | Write-Output
            Get-ChildItem -LiteralPath (Join-Path $testData 'AudioBule\Logs') -Recurse -Filter '*.jsonl' | ForEach-Object { Get-Content -LiteralPath $_.FullName } | ForEach-Object { $_ | ConvertFrom-Json } | Where-Object { $_.event -eq 'diagnostics.export_completed' } | ConvertTo-Json -Compress | Write-Output
        }
        Assert-Condition $saved '原生保存操作完成诊断导出'
        $diagnostics = @(Get-Content -LiteralPath $exportPath | ForEach-Object { $_ | ConvertFrom-Json })
        Assert-Condition ($diagnostics.Count -gt 1 -and $diagnostics[0].record_type -eq 'manifest') '实际导出文件包含清单及可解析的日志'
        Assert-Condition (-not $diagnostics[0].incomplete) '本轮正常导出没有缺失说明'
        if ($ScreenshotPath) { Copy-Item -LiteralPath $exportPath -Destination (Join-Path (Split-Path ([IO.Path]::GetFullPath($ScreenshotPath))) 'diagnostics-sample.jsonl') -Force }

        Assert-Condition (@($diagnostics | Where-Object { $_.PSObject.Properties.Name -contains 'device_name' }).Count -eq 0) '实际导出不包含设备原名字段'
        $focusReturned = Wait-Condition { (Find-Ui $root 'DiagnosticsExport').Current.HasKeyboardFocus }
        if (-not $focusReturned) {
            $focused = [System.Windows.Automation.AutomationElement]::FocusedElement
            $foreground = [AudioBuleSmoke.Native]::GetForegroundWindow()
            Write-Output ("焦点诊断：前台是否主窗口={0}；焦点是否测试进程={1}" -f ($foreground -eq $window), ($focused -and $focused.Current.ProcessId -eq $application.Id))
            if ($focused -and $focused.Current.ProcessId -eq $application.Id) { Write-Output ("焦点标识：{0}；类型：{1}" -f $focused.Current.AutomationId, $focused.Current.ControlType.ProgrammaticName) }
        }
        Assert-Condition $focusReturned '导出完成后焦点回到原生导出按钮'
        Invoke-Ui (Find-Ui $root 'DiagnosticsExport')
        Assert-Condition (Wait-Condition { [AudioBuleSmoke.Native]::Find([uint32]$application.Id, '#32770') -ne [IntPtr]::Zero }) '可再次打开诊断保存对话框'
        $cancelDialog = [AudioBuleSmoke.Native]::Find([uint32]$application.Id, '#32770')
        $cancelButton = [AudioBuleSmoke.Native]::GetDlgItem($cancelDialog, 2)
        $null = [AudioBuleSmoke.Native]::SendMessage($cancelButton, 0x00F5, [IntPtr]::Zero, [IntPtr]::Zero)
        Assert-Condition (Wait-Condition { [AudioBuleSmoke.Native]::Find([uint32]$application.Id, '#32770') -eq [IntPtr]::Zero -and (Find-Ui $root 'DiagnosticsExport').Current.IsEnabled }) '取消保存对话框后恢复导出按钮'

    }

    $settingsScroll = (Find-Ui $root 'SettingsPage').GetCurrentPattern([System.Windows.Automation.ScrollPattern]::Pattern)
    if ($settingsScroll.Current.VerticallyScrollable) { $settingsScroll.SetScrollPercent(-1, 0) }


    $reconnect = Find-Ui $root 'AutoReconnect'
    $startup = Find-Ui $root 'RunAtStartup'
    $notifications = Find-Ui $root 'ConnectionNotifications'
    Assert-Condition ([Math]::Abs($reconnect.Current.BoundingRectangle.Right - $startup.Current.BoundingRectangle.Right) -lt 2 -and [Math]::Abs($reconnect.Current.BoundingRectangle.Right - $notifications.Current.BoundingRectangle.Right) -lt 2) '设置页所有开关右边缘对齐'
    Assert-Condition ($null -eq (Find-Ui $root '始终开启' -Name) -and $null -eq (Find-Ui $root '关闭窗口后继续运行' -Name)) '固定行为不再作为设置项展示'
    # 验证开关真实可修改且保存，然后恢复测试配置。
    $reconnect.GetCurrentPattern([System.Windows.Automation.TogglePattern]::Pattern).Toggle()
    Assert-Condition (Wait-Condition { -not ([IO.File]::ReadAllText((Join-Path $testData 'AudioBule\settings.json')) | ConvertFrom-Json).autoReconnect }) '自动重连开关可关闭并保存'
    (Find-Ui $root 'AutoReconnect').GetCurrentPattern([System.Windows.Automation.TogglePattern]::Pattern).Toggle()
    Assert-Condition (Wait-Condition { ([IO.File]::ReadAllText((Join-Path $testData 'AudioBule\settings.json')) | ConvertFrom-Json).autoReconnect }) '自动重连开关可重新开启'
    Save-WindowImage $window 'settings'
    Select-Combo $root 'Theme' '深色'
    Assert-Condition (Wait-Condition { ([IO.File]::ReadAllText((Join-Path $testData 'AudioBule\settings.json')) | ConvertFrom-Json).theme -eq 'dark' }) '深色主题即时生效并保存'
    $null = [AudioBuleSmoke.Native]::SetWindowPos($window, [IntPtr]::Zero, 0, 0, 976, 880, 0x6)
    Start-Sleep -Milliseconds 200
    $settingsScroll = (Find-Ui $root 'SettingsPage').GetCurrentPattern([System.Windows.Automation.ScrollPattern]::Pattern)
    if ($settingsScroll.Current.VerticallyScrollable) { $settingsScroll.SetScrollPercent(-1, 0) }
    Save-WindowImage $window 'settings-dark-zh'
    Select-Combo $root 'Language' 'English'
    Assert-Condition (Wait-Condition { $null -ne (Find-Ui $root 'Settings' -Name) }) '语言切换即时更新导航和设置'
    $null = [AudioBuleSmoke.Native]::SetWindowPos($window, [IntPtr]::Zero, 0, 0, 976, 880, 0x6)
    Start-Sleep -Milliseconds 200
    $settingsScroll = (Find-Ui $root 'SettingsPage').GetCurrentPattern([System.Windows.Automation.ScrollPattern]::Pattern)
    if ($settingsScroll.Current.VerticallyScrollable) { $settingsScroll.SetScrollPercent(-1, 0) }
    Start-Sleep -Milliseconds 300
    $reconnect = Find-Ui $root 'AutoReconnect'
    $theme = Find-Ui $root 'Theme'
    $language = Find-Ui $root 'Language'
    Save-WindowImage $window 'english-dark'
    # 原生下拉框自动化边界比可见边框向外扩展约 4 DIP，允许不同控件的交互区域差异。
    $columnTolerance = 6 * [AudioBuleSmoke.Native]::GetDpiForWindow($window) / 96
    Assert-Condition ([Math]::Abs($reconnect.Current.BoundingRectangle.Right - $theme.Current.BoundingRectangle.Right) -lt $columnTolerance -and [Math]::Abs($reconnect.Current.BoundingRectangle.Right - $language.Current.BoundingRectangle.Right) -lt $columnTolerance) '英文界面开关与下拉框右边缘对齐'
    $null = [AudioBuleSmoke.Native]::PostMessage($callback, 0x8001, [IntPtr]0, [IntPtr]0x10400)
    Assert-Condition (Wait-Condition { [AudioBuleSmoke.Native]::IsWindowVisible($panel) }) '深色快速面板正常打开'
    Save-WindowImage $panel 'tray-dark'
    Invoke-Ui (Find-Ui ([System.Windows.Automation.AutomationElement]::FromHandle($panel)) 'Open device window' -Name)
    Invoke-Ui (Find-Ui $root 'AboutNav')
    Assert-Condition ($null -ne (Find-Ui $root 'How to listen' -Name)) '使用介绍仅位于关于页'
    Save-WindowImage $window 'about'
    Invoke-Ui (Find-Ui $root 'DevicesNav')
    Save-WindowImage $window 'devices-english-dark'
    $null = [AudioBuleSmoke.Native]::SetWindowPos($window, [IntPtr]::Zero, 0, 0, 640, 620, 0x6)
    Save-WindowImage $window 'compact'
    Assert-Condition ($null -ne (Find-Ui $root 'NavigationButton')) '窄窗口保留标题栏导航入口'
    $null = [AudioBuleSmoke.Native]::SetWindowPos($window, [IntPtr]::Zero, 0, 0, 420, 620, 0x6)
    Invoke-Ui (Find-Ui $root 'NavigationButton')
    Assert-Condition ($null -ne (Find-Ui $root 'SettingsNav')) '最窄窗口可从标题栏打开导航'
    Save-WindowImage $window 'minimal-navigation'
    Invoke-Ui (Find-Ui $root 'NavigationButton')
    $null = [AudioBuleSmoke.Native]::SetWindowPos($window, [IntPtr]::Zero, 0, 0, 976, 680, 0x6)
    $null = [AudioBuleSmoke.Native]::PostMessage($window, 0x112, [IntPtr]0xF020, [IntPtr]0)
    Assert-Condition (Wait-Condition { -not [AudioBuleSmoke.Native]::IsWindowVisible($window) }) '最小化隐藏至托盘'
    $null = [AudioBuleSmoke.Native]::PostMessage($callback, 0x8001, [IntPtr]0x00640064, [IntPtr]0x1007B)
    Assert-Condition (Wait-Condition { [AudioBuleSmoke.Native]::IsWindowVisible($panel) }) '主窗口隐藏时右键菜单仍可用'
    $quickRoot = [System.Windows.Automation.AutomationElement]::FromHandle($panel)
    Assert-Condition ($null -ne (Find-Ui $quickRoot 'Settings' -Name) -and $null -ne (Find-Ui $quickRoot 'Exit AudioBule' -Name)) '右键菜单同步使用英文资源'
    Assert-Condition ($null -eq (Find-Ui $quickRoot 'Reconnect on launch' -Name) -and $null -eq (Find-Ui $quickRoot 'Run at startup' -Name)) '右键菜单不重复放置设置开关'
    Save-WindowImage $panel 'menu'
    Invoke-Ui (Find-Ui $quickRoot 'Open device window' -Name)
    $null = [AudioBuleSmoke.Native]::PostMessage($window, 0x10, [IntPtr]0, [IntPtr]0)
    Assert-Condition (Wait-Condition { -not [AudioBuleSmoke.Native]::IsWindowVisible($window) }) '关闭窗口保持托盘运行'
    Assert-Condition (-not $application.HasExited) '隐藏窗口不会退出进程'
    # 键盘打开仍可定位控件并用 Esc 关闭，鼠标模式不影响键盘可访问性。
    $null = [AudioBuleSmoke.Native]::PostMessage($callback, 0x8001, [IntPtr]0, [IntPtr]0x10401)
    Assert-Condition (Wait-Condition { [AudioBuleSmoke.Native]::IsWindowVisible($panel) }) '键盘托盘选择显示快速面板'
    $quickRoot = [System.Windows.Automation.AutomationElement]::FromHandle($panel)
    Assert-Condition (Wait-Condition { (Find-Ui $quickRoot 'Open device window' -Name).Current.HasKeyboardFocus }) '键盘打开面板保留操作焦点'
    Assert-Condition ([AudioBuleSmoke.Native]::SendEscape($panel, [uint32]$application.Id)) 'Esc 消息仅发送到测试进程的输入窗口'
    Assert-Condition (Wait-Condition { -not [AudioBuleSmoke.Native]::IsWindowVisible($panel) }) '键盘 Esc 关闭快速面板'
    $null = [AudioBuleSmoke.Native]::PostMessage($callback, 0x8001, [IntPtr](-1), [IntPtr]0x1007B)
    Assert-Condition (Wait-Condition { [AudioBuleSmoke.Native]::IsWindowVisible($panel) }) '键盘快捷菜单可以打开'
    $quickRoot = [System.Windows.Automation.AutomationElement]::FromHandle($panel)
    Assert-Condition (Wait-Condition { (Find-Ui $quickRoot 'Open device window' -Name).Current.HasKeyboardFocus }) '键盘菜单首项获得焦点'
    $null = [AudioBuleSmoke.Native]::SendEscape($panel, [uint32]$application.Id)
    Assert-Condition (Wait-Condition { -not [AudioBuleSmoke.Native]::IsWindowVisible($panel) }) '键盘 Esc 关闭菜单'
    # 模拟广播验证 Explorer 恢复路径，不终止桌面进程。
    $gdiBefore = [AudioBuleSmoke.Native]::GetGuiResources($application.Handle, 0)
    $taskbarCreated = [AudioBuleSmoke.Native]::RegisterWindowMessage('TaskbarCreated')
    for ($index = 0; $index -lt 10; $index++) {
        $null = [AudioBuleSmoke.Native]::PostMessage($broadcast, $taskbarCreated, [IntPtr]0, [IntPtr]0)
        $null = [AudioBuleSmoke.Native]::PostMessage($broadcast, 0x1A, [IntPtr]0, [IntPtr]0)
    }
    Start-Sleep -Milliseconds 600
    $gdiAfter = [AudioBuleSmoke.Native]::GetGuiResources($application.Handle, 0)
    Assert-Condition ([AudioBuleSmoke.Native]::HasIcon($callback)) 'Explorer 恢复广播后托盘存在'
    # 首轮会建立 WinUI/DWM 缓存，第二轮判断资源是否持续增长。
    Write-Output "系统资源预热：$gdiBefore → $gdiAfter"
    $gdiBefore = $gdiAfter
    for ($index = 0; $index -lt 10; $index++) {
        $null = [AudioBuleSmoke.Native]::PostMessage($broadcast, $taskbarCreated, [IntPtr]0, [IntPtr]0)
        $null = [AudioBuleSmoke.Native]::PostMessage($broadcast, 0x1A, [IntPtr]0, [IntPtr]0)
    }
    Start-Sleep -Milliseconds 600
    $gdiAfter = [AudioBuleSmoke.Native]::GetGuiResources($application.Handle, 0)
    Assert-Condition ($gdiAfter -le $gdiBefore + 2) "图标更新无 GDI 泄漏（$gdiBefore → $gdiAfter）"
    $null = [AudioBuleSmoke.Native]::PostMessage($callback, 0x8001, [IntPtr]0x00640064, [IntPtr]0x1007B)
    Assert-Condition (Wait-Condition { [AudioBuleSmoke.Native]::IsWindowVisible($panel) }) '菜单可以重复打开'
    $quickRoot = [System.Windows.Automation.AutomationElement]::FromHandle($panel)
    Invoke-Ui (Find-Ui $quickRoot 'Exit AudioBule' -Name)
    $root = [System.Windows.Automation.AutomationElement]::FromHandle($window)
    Assert-Condition (Wait-Condition { $null -ne (Find-Ui $root 'Cancel' -Name) }) '退出前显示原生确认框'
    Save-WindowImage $window 'exit-dialog'
    Invoke-Ui (Find-Ui $root 'Cancel' -Name)
    Assert-Condition (-not $application.HasExited) '取消退出后继续运行'
    Invoke-Ui (Find-Ui $root 'SettingsNav')
    $exit = Find-Ui $root 'Exit AudioBule' -Name
    $scroll = $null
    if ($exit.TryGetCurrentPattern([System.Windows.Automation.ScrollItemPattern]::Pattern, [ref]$scroll)) { $scroll.ScrollIntoView() }
    Invoke-Ui $exit
    Assert-Condition (Wait-Condition { $null -ne (Find-Ui $root 'Exit' -Name) }) '设置页退出同样经过确认'
    Invoke-Ui (Find-Ui $root 'Exit' -Name)
    Assert-Condition ($application.WaitForExit(10000)) '确认后正常退出无残留进程'
    Assert-Condition ($application.ExitCode -eq 0) '正常退出码为 0'
    Assert-Condition (-not [AudioBuleSmoke.Native]::HasIcon($callback)) '退出后托盘移除'
    $sessionDirectories = @(Get-ChildItem -LiteralPath (Join-Path $testData 'AudioBule\Logs') -Directory)
    Assert-Condition ($sessionDirectories.Count -eq 1 -and (Test-Path -LiteralPath (Join-Path $sessionDirectories[0].FullName 'complete'))) '正常退出写入完整结束标记'
    $logRecords = @(Get-ChildItem -LiteralPath $sessionDirectories[0].FullName -Filter '*.jsonl' | ForEach-Object { Get-Content -LiteralPath $_.FullName | ForEach-Object { $_ | ConvertFrom-Json } })
    Assert-Condition (@($logRecords | Where-Object event -eq 'app.shutdown_completed').Count -eq 1) '日志覆盖业务资源退出清理'
    Assert-Condition (@($logRecords | Where-Object event -eq 'diagnostics.detailed_enabled').Count -eq 1) '原生详细日志按钮记录真实事件'
    Assert-Condition (@($logRecords | Where-Object schema_version -ne 1).Count -eq 0) '运行日志逐行解析且版本正确'

    $settings = [IO.File]::ReadAllText((Join-Path $testData 'AudioBule\settings.json')) | ConvertFrom-Json
    Assert-Condition ($settings.language -eq 'en-US' -and $settings.theme -eq 'dark' -and $settings.autoReconnect) '退出保留语言、主题与重连设置'
    $application.Dispose()
    $env:LOCALAPPDATA = $testData; $env:AUDIOBULE_SMOKE_TEST = '1'
    $application = Start-Process -FilePath $Executable -WindowStyle Hidden -PassThru
    $env:LOCALAPPDATA = $originalLocalAppData; $env:AUDIOBULE_SMOKE_TEST = $originalSmoke
    Assert-Condition (Wait-Condition {
        $window = [AudioBuleSmoke.Native]::FindTitle([uint32]$application.Id, 'AudioBule')
        $window -ne [IntPtr]::Zero -and [AudioBuleSmoke.Native]::IsWindowVisible($window)
    }) '普通启动显示主窗口'
    $window = [AudioBuleSmoke.Native]::FindTitle([uint32]$application.Id, 'AudioBule')
    $root = [System.Windows.Automation.AutomationElement]::FromHandle($window)
    Assert-Condition ($null -ne (Find-Ui $root 'Devices' -Name)) '再次启动保留英文界面'
    Invoke-Ui (Find-Ui $root 'SettingsNav')
    $theme = Find-Ui $root 'Theme'
    $selection = $theme.GetCurrentPattern([System.Windows.Automation.SelectionPattern]::Pattern).Current.GetSelection()
    Assert-Condition ($selection[0].Current.Name -eq 'Dark') '再次启动保留深色设置'
    $exit = Find-Ui $root 'Exit AudioBule' -Name
    $scroll = $null
    if ($exit.TryGetCurrentPattern([System.Windows.Automation.ScrollItemPattern]::Pattern, [ref]$scroll)) { $scroll.ScrollIntoView() }
    Invoke-Ui $exit
    Invoke-Ui (Find-Ui $root 'Exit' -Name)
    Assert-Condition ($application.WaitForExit(10000) -and $application.ExitCode -eq 0) '第二次启动也正常退出'
} finally {
    $env:LOCALAPPDATA = $originalLocalAppData; $env:AUDIOBULE_SMOKE_TEST = $originalSmoke
    if ($application) {
        $application.Refresh()
        if (-not $application.HasExited) {
            Stop-Process -Id $application.Id
            # 日志线程的文件句柄要等进程退出后才能安全清理。
            $null = $application.WaitForExit(5000)
        }
        $application.Dispose()
    }
    $resolved = [IO.Path]::GetFullPath($testData)
    $temporaryRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
    if ($resolved.StartsWith($temporaryRoot, [StringComparison]::OrdinalIgnoreCase) -and [IO.Path]::GetFileName($resolved).StartsWith('AudioBuleSmoke_') -and (Test-Path -LiteralPath $resolved)) { Remove-Item -LiteralPath $resolved -Recurse -Force }
}
