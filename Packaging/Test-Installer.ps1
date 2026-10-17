param(
    [Parameter(Mandatory)][string]$Installer,
    [switch]$RunAppSmoke
)

$ErrorActionPreference = 'Stop'
# 快捷方式接口可能返回 DOS 短路径；比较前统一为实际长路径。
if (-not ('AudioBuleInstallerTest.Paths' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
using System.Text;
namespace AudioBuleInstallerTest {
    public static class Paths {
        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern uint GetLongPathName(string source, StringBuilder target, uint length);
        public static string Normalize(string path) {
            var buffer = new StringBuilder(32768);
            uint length = GetLongPathName(path, buffer, (uint)buffer.Capacity);
            if (length == 0 || length >= buffer.Capacity)
                throw new System.ComponentModel.Win32Exception(Marshal.GetLastWin32Error());
            return buffer.ToString().TrimEnd('\\');
        }
    }
}
'@
}
$Installer = (Resolve-Path -LiteralPath $Installer).Path
$registry = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\{9C798D70-A8E1-4485-904E-EBE558077E01}_is1'
$shortcut = Join-Path ([Environment]::GetFolderPath('Programs')) 'AudioBule\AudioBule.lnk'
$runKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
$startup = Get-ItemProperty -LiteralPath $runKey -Name AudioBule -ErrorAction SilentlyContinue
# 只在未安装本产品的环境中运行；已有其他目录的启动项保持原值。
if ((Test-Path -LiteralPath $registry) -or (Test-Path -LiteralPath $shortcut)) { throw '安装验证需要没有 AudioBule 安装记录和开始菜单快捷方式的环境。' }
$testRoot = Join-Path ([IO.Path]::GetTempPath()) ('AudioBuleInstaller_' + [Guid]::NewGuid().ToString('N'))
$applicationDirectory = Join-Path $testRoot '应用安装目录'
$null = New-Item -ItemType Directory -Path $testRoot
$uninstaller = Join-Path $applicationDirectory 'unins000.exe'
$logs = Join-Path $PSScriptRoot '..\artifacts\installer-tests'
$null = New-Item -ItemType Directory -Path $logs -Force

function Invoke-InstallerProcess([string]$File, [string[]]$Arguments) {
    $process = Start-Process -FilePath $File -ArgumentList $Arguments -WindowStyle Hidden -PassThru
    if (-not $process.WaitForExit(180000)) { Stop-Process -Id $process.Id; throw '安装或卸载超时。' }
    if ($process.ExitCode -ne 0) { throw "安装或卸载失败，退出码：$($process.ExitCode)" }
}

try {
    # 连续安装两次覆盖首次安装和同版本修复，检验运行时安装可重复执行。
    foreach ($attempt in 1, 2) {
        Invoke-InstallerProcess $Installer @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/SP-', "/DIR=`"$applicationDirectory`"", "/LOG=`"$(Join-Path $logs "install-$attempt.log")`"")
        foreach ($required in 'AudioBule.exe', 'AudioBule.pri', 'MainWindow.xbf', 'Assets\AppIcon.ico', 'unins000.exe') {
            if (-not (Test-Path -LiteralPath (Join-Path $applicationDirectory $required))) { throw "安装缺少文件：$required" }
        }
        $installed = Get-ItemProperty -LiteralPath $registry
        if ($installed.InstallLocation.TrimEnd('\') -ne $applicationDirectory) { throw '卸载记录的安装目录不一致。' }
        $shell = New-Object -ComObject WScript.Shell
        $shortcutTarget = $shell.CreateShortcut($shortcut).TargetPath
        $expectedTarget = Join-Path $applicationDirectory 'AudioBule.exe'
        if ([AudioBuleInstallerTest.Paths]::Normalize($shortcutTarget) -ne [AudioBuleInstallerTest.Paths]::Normalize($expectedTarget)) {
            throw "开始菜单快捷方式指向错误：$shortcutTarget，预期：$expectedTarget"
        }
        Write-Output "通过：第 $attempt 次安装、完整资源、快捷方式与卸载记录。"
    }
    if ($RunAppSmoke) {
        & (Join-Path $PSScriptRoot '..\tools\app-smoke\Test-App.ps1') -Executable (Join-Path $applicationDirectory 'AudioBule.exe')
    } else {
        # 流水线验证真实安装路径能够打开主窗口，测试进程使用独立设置。
        $previousLocalData = $env:LOCALAPPDATA
        $previousSmoke = $env:AUDIOBULE_SMOKE_TEST
        $application = $null
        try {
            $env:LOCALAPPDATA = Join-Path $testRoot '启动验证'
            $env:AUDIOBULE_SMOKE_TEST = '1'
            $application = Start-Process -FilePath (Join-Path $applicationDirectory 'AudioBule.exe') -WindowStyle Hidden -PassThru
            $deadline = [DateTime]::UtcNow.AddSeconds(20)
            do {
                Start-Sleep -Milliseconds 250
                $application.Refresh()
            } while (-not $application.HasExited -and $application.MainWindowTitle -ne 'AudioBule' -and [DateTime]::UtcNow -lt $deadline)
            if ($application.HasExited -or $application.MainWindowTitle -ne 'AudioBule') { throw '安装后无法启动应用主窗口。' }
            Write-Output '通过：安装后的应用能够启动主窗口。'
        } finally {
            $env:LOCALAPPDATA = $previousLocalData
            $env:AUDIOBULE_SMOKE_TEST = $previousSmoke
            if ($application) {
                if (-not $application.HasExited) { Stop-Process -Id $application.Id; $application.WaitForExit() }
                $application.Dispose()
            }
        }
    }
    # 模拟用户启用启动项，验证卸载仅清除本安装路径对应的值。
    if (-not $startup) {
        $null = New-Item -Path $runKey -Force
        Set-ItemProperty -LiteralPath $runKey -Name AudioBule -Value ('"' + (Join-Path $applicationDirectory 'AudioBule.exe') + '" --startup')
    }
    Invoke-InstallerProcess $uninstaller @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', "/LOG=`"$(Join-Path $logs 'uninstall.log')`"")
    # 卸载器可能由临时副本执行；等待文件清理完成后再核验。
    $deadline = [DateTime]::UtcNow.AddSeconds(15)
    while ((Test-Path -LiteralPath $uninstaller) -and [DateTime]::UtcNow -lt $deadline) { Start-Sleep -Milliseconds 250 }
    if ((Test-Path -LiteralPath $registry) -or (Test-Path -LiteralPath $shortcut) -or
        (Test-Path -LiteralPath (Join-Path $applicationDirectory 'AudioBule.exe'))) { throw '卸载没有完整清理应用、快捷方式或安装记录。' }
    $remainingStartup = Get-ItemProperty -LiteralPath $runKey -Name AudioBule -ErrorAction SilentlyContinue
    if (($startup -and $remainingStartup.AudioBule -ne $startup.AudioBule) -or (-not $startup -and $remainingStartup)) { throw '卸载没有正确处理启动项。' }
    Write-Output '通过：卸载清除应用、快捷方式、卸载记录及对应启动项。'
} finally {
    if (Test-Path -LiteralPath $uninstaller) {
        Invoke-InstallerProcess $uninstaller @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART')
    }
    # 限定清理本脚本生成的临时目录，日志保留在 artifacts。
    $resolved = [IO.Path]::GetFullPath($testRoot)
    $temporaryRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\') + '\'
    if ($resolved.StartsWith($temporaryRoot, [StringComparison]::OrdinalIgnoreCase) -and
        [IO.Path]::GetFileName($resolved).StartsWith('AudioBuleInstaller_') -and (Test-Path -LiteralPath $resolved)) {
        Remove-Item -LiteralPath $resolved -Recurse -Force
    }
}
