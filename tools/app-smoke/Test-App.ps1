param(
    [string]$Executable = (Join-Path $PSScriptRoot '..\..\AudioBule.App\bin\AudioBule.exe'),
    [string]$ScreenshotPath
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
        [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetClassName(IntPtr window, StringBuilder text, int count);
        [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern IntPtr FindWindowEx(IntPtr parent, IntPtr after, string name, string title);
        [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr window);
        [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr window, uint message, IntPtr wparam, IntPtr lparam);
        [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern uint RegisterWindowMessage(string text);
        [DllImport("user32.dll")] public static extern IntPtr SendMessage(IntPtr window, uint message, IntPtr wparam, IntPtr lparam);
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
        public static bool HasIcon(IntPtr window) {
            var identifier = new IconIdentifier { size = (uint)Marshal.SizeOf<IconIdentifier>(), window = window, id = 1 };
            Rect rect; return Shell_NotifyIconGetRect(ref identifier, out rect) == 0;
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

# 临时 LOCALAPPDATA 隔离测试配置，保留用户现有的重连设备与开关。
$testData = Join-Path ([IO.Path]::GetTempPath()) ('AudioBuleSmoke_' + [Guid]::NewGuid().ToString('N'))
$originalLocalAppData = $env:LOCALAPPDATA
$application = $null
try {
    $env:LOCALAPPDATA = $testData
    $application = Start-Process -FilePath $Executable -WindowStyle Hidden -PassThru
    $env:LOCALAPPDATA = $originalLocalAppData
    Assert-Condition (Wait-Condition {
        $application.Refresh()
        if ($application.HasExited) { throw ('应用启动崩溃，退出码：0x{0:X8}' -f $application.ExitCode) }
        [AudioBuleSmoke.Native]::Find([uint32]$application.Id, 'AudioBule.Tray') -ne [IntPtr]::Zero
    }) '应用启动且托盘线程建立窗口'
    $broadcast = [AudioBuleSmoke.Native]::Find([uint32]$application.Id, 'AudioBule.Tray')
    $callback = [AudioBuleSmoke.Native]::FindWindowEx([IntPtr](-3), [IntPtr]::Zero, 'AudioBule.Tray', 'AudioBule.Tray.Callback')
    Assert-Condition ($callback -ne [IntPtr]::Zero) 'message-only 托盘回调窗口存在'
    Assert-Condition ([AudioBuleSmoke.Native]::HasIcon($callback)) 'Shell 已登记托盘图标'
    $window = [AudioBuleSmoke.Native]::Find([uint32]$application.Id, 'WinUIDesktopWin32WindowClass')
    Assert-Condition ($window -ne [IntPtr]::Zero) '设备窗口已创建'
    Assert-Condition (-not [AudioBuleSmoke.Native]::IsWindowVisible($window)) '启动时窗口隐藏'

    # 版本 4 的 NIN_SELECT 在 lParam 低位，图标 ID 在高位。
    $null = [AudioBuleSmoke.Native]::PostMessage($callback, 0x8001, [IntPtr]0, [IntPtr]0x10400)
    Assert-Condition (Wait-Condition { [AudioBuleSmoke.Native]::IsWindowVisible($window) }) '托盘左键显示设备窗口'
    $null = [AudioBuleSmoke.Native]::PostMessage($window, 0x10, [IntPtr]0, [IntPtr]0)
    Assert-Condition (Wait-Condition { -not [AudioBuleSmoke.Native]::IsWindowVisible($window) }) '关闭按钮隐藏窗口'
    $application.Refresh()
    Assert-Condition (-not $application.HasExited) '关闭窗口后进程保持运行'

    # 隐藏状态下右键也必须能弹出菜单，Esc 取消后仍然可再次使用。
    $null = [AudioBuleSmoke.Native]::PostMessage($callback, 0x8001, [IntPtr]0x00640064, [IntPtr]0x1007B)
    Assert-Condition (Wait-Condition { [AudioBuleSmoke.Native]::Find([uint32]$application.Id, '#32768') -ne [IntPtr]::Zero }) '隐藏窗口时托盘右键菜单可用'
    $popup = [AudioBuleSmoke.Native]::Find([uint32]$application.Id, '#32768')
    $menu = [AudioBuleSmoke.Native]::SendMessage($popup, 0x01E1, [IntPtr]0, [IntPtr]0)
    Assert-Condition ([AudioBuleSmoke.Native]::GetMenuItemCount($menu) -eq 7) '菜单项目完整'
    $labels = for ($index = 0; $index -lt 7; $index++) {
        $text = [Text.StringBuilder]::new(128)
        $null = [AudioBuleSmoke.Native]::GetMenuString($menu, $index, $text, 128, 0x400)
        $text.ToString()
    }
    Assert-Condition ($labels -contains '退出' -and $labels -contains '启动时自动重连') '菜单文字正确'
    $null = [AudioBuleSmoke.Native]::PostMessage($popup, 0x100, [IntPtr]27, [IntPtr]0)
    Assert-Condition (Wait-Condition { [AudioBuleSmoke.Native]::Find([uint32]$application.Id, '#32768') -eq [IntPtr]::Zero }) 'Esc 取消菜单'

    # 模拟系统广播，验证恢复路径；避免结束用户的桌面进程。
    $gdiBefore = [AudioBuleSmoke.Native]::GetGuiResources($application.Handle, 0)
    $taskbarCreated = [AudioBuleSmoke.Native]::RegisterWindowMessage('TaskbarCreated')
    for ($index = 0; $index -lt 20; $index++) {
        $null = [AudioBuleSmoke.Native]::PostMessage($broadcast, $taskbarCreated, [IntPtr]0, [IntPtr]0)
        $null = [AudioBuleSmoke.Native]::PostMessage($broadcast, 0x1A, [IntPtr]0, [IntPtr]0)
    }
    Start-Sleep -Milliseconds 800
    Assert-Condition ([AudioBuleSmoke.Native]::HasIcon($callback)) 'TaskbarCreated 后托盘图标存在'
    $gdiAfter = [AudioBuleSmoke.Native]::GetGuiResources($application.Handle, 0)
    Assert-Condition ($gdiAfter -le $gdiBefore + 2) "重复广播无持续 GDI 泄漏（$gdiBefore → $gdiAfter）"

    # UI Automation 仅调用本进程的退出按钮，覆盖真实关闭和配置保存链路。
    $null = [AudioBuleSmoke.Native]::PostMessage($callback, 0x8001, [IntPtr]0, [IntPtr]0x10400)
    Assert-Condition (Wait-Condition { [AudioBuleSmoke.Native]::IsWindowVisible($window) }) '关闭后可再次从托盘显示窗口'
    # PowerShell Core 使用与自身 .NET 主版本一致的桌面运行时，不能加载旧 Framework 转发程序集。
    $desktopRuntime = Get-ChildItem -LiteralPath "$env:ProgramFiles\dotnet\shared\Microsoft.WindowsDesktop.App" -Directory |
        Where-Object { $_.Name.StartsWith([Environment]::Version.Major.ToString() + '.') } |
        Sort-Object { [version]$_.Name } -Descending | Select-Object -First 1
    if (-not $desktopRuntime) { throw '冒烟测试需要与 PowerShell 对应的 .NET Windows Desktop Runtime。' }
    foreach ($assembly in 'WindowsBase.dll', 'UIAutomationTypes.dll', 'UIAutomationClient.dll') {
        Add-Type -Path (Join-Path $desktopRuntime.FullName $assembly)
    }
    $root = [System.Windows.Automation.AutomationElement]::FromHandle($window)
    $summary = $root.FindFirst([System.Windows.Automation.TreeScope]::Descendants,
        [System.Windows.Automation.PropertyCondition]::new([System.Windows.Automation.AutomationElement]::AutomationIdProperty, 'SummaryText'))
    Assert-Condition ($null -ne $summary -and $summary.Current.Name -match '台设备') '设备枚举完成且窗口呈现设备数量'
    $refresh = $root.FindFirst([System.Windows.Automation.TreeScope]::Descendants,
        [System.Windows.Automation.PropertyCondition]::new([System.Windows.Automation.AutomationElement]::AutomationIdProperty, 'RefreshButton'))
    $refresh.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke()
    Assert-Condition (Wait-Condition { $summary.Current.Name -match '台设备' }) '刷新后界面保持响应并更新列表'
    if ($ScreenshotPath) {
        # 只渲染本次测试的设备窗口，不抓取整个桌面。
        Add-Type -AssemblyName System.Drawing
        $bounds = [AudioBuleSmoke.Native+Rect]::new()
        $null = [AudioBuleSmoke.Native]::GetWindowRect($window, [ref]$bounds)
        $bitmap = [Drawing.Bitmap]::new($bounds.right - $bounds.left, $bounds.bottom - $bounds.top)
        $graphics = [Drawing.Graphics]::FromImage($bitmap)
        $dc = $graphics.GetHdc()
        try {
            $null = [AudioBuleSmoke.Native]::PrintWindow($window, $dc, 2)
        } finally { $graphics.ReleaseHdc($dc); $graphics.Dispose() }
        try {
            $destination = [IO.Path]::GetFullPath($ScreenshotPath)
            $null = New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force
            $bitmap.Save($destination, [Drawing.Imaging.ImageFormat]::Png)
            Write-Output "窗口截图：$destination"
        } finally { $bitmap.Dispose() }
    }
    $condition = [System.Windows.Automation.PropertyCondition]::new([System.Windows.Automation.AutomationElement]::NameProperty, '退出')
    $button = $root.FindFirst([System.Windows.Automation.TreeScope]::Descendants, $condition)
    Assert-Condition ($null -ne $button) '设备窗口可访问退出按钮'
    $pattern = $button.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern)
    $pattern.Invoke()
    Assert-Condition ($application.WaitForExit(10000)) '正常退出无残留进程'
    Assert-Condition ($application.ExitCode -eq 0) '退出码为 0'
    Assert-Condition (-not [AudioBuleSmoke.Native]::HasIcon($callback)) '退出后托盘图标移除'
    $saved = Join-Path $testData 'AudioBule\settings.json'
    Assert-Condition (Test-Path -LiteralPath $saved) '退出时保存配置'
    $settings = [IO.File]::ReadAllText($saved) | ConvertFrom-Json
    Assert-Condition ($settings.autoReconnect -eq $true) '配置可解析且保留重连设置'
} finally {
    $env:LOCALAPPDATA = $originalLocalAppData
    if ($application) {
        $application.Refresh()
        if (-not $application.HasExited) { Stop-Process -Id $application.Id }
        $application.Dispose()
    }
    # 只清理本脚本创建的随机临时目录，并核验最终绝对路径。
    $resolved = [IO.Path]::GetFullPath($testData)
    $temporaryRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
    if ($resolved.StartsWith($temporaryRoot, [StringComparison]::OrdinalIgnoreCase) -and
        [IO.Path]::GetFileName($resolved).StartsWith('AudioBuleSmoke_') -and
        (Test-Path -LiteralPath $resolved)) {
        Remove-Item -LiteralPath $resolved -Recurse -Force
    }
}
