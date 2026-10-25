[CmdletBinding(SupportsShouldProcess)]
param(
    [ValidateSet('Status', 'Enable', 'Restore')][string]$Mode = 'Status',
    [string]$Directory = (Join-Path $env:USERPROFILE 'Documents\Codex\work\AudioBule\crash-dumps'),
    [string]$BackupPath
)

$ErrorActionPreference = 'Stop'
$registryPath = 'HKLM:\SOFTWARE\Microsoft\Windows\Windows Error Reporting\LocalDumps\AudioBule.exe'
$names = @('DumpFolder', 'DumpCount', 'DumpType')
if ($BackupPath -and -not [IO.Path]::IsPathFullyQualified($BackupPath)) { throw '备份文件必须使用完整绝对路径。' }
if ($Mode -eq 'Status') {
    if (Test-Path -LiteralPath $registryPath) { Get-ItemProperty -LiteralPath $registryPath | Select-Object DumpFolder, DumpCount, DumpType }
    else { Write-Output 'AudioBule 未配置应用专用崩溃转储。' }
    return
}

# 只有显式执行启用或恢复才修改注册表，不在构建、测试或正常启动时调用。
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw '配置 Windows 崩溃转储需要管理员权限，请在管理员 PowerShell 中按需执行。'
}
if ($Mode -eq 'Enable') {
    if (-not [IO.Path]::IsPathFullyQualified($Directory)) { throw '转储目录必须是完整绝对路径。' }
    $Directory = [IO.Path]::GetFullPath($Directory)
    if (-not $BackupPath) { $BackupPath = Join-Path $Directory ('wer-backup-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.clixml') }
    if (Test-Path -LiteralPath $BackupPath) { throw '备份文件已存在，禁止覆盖原始注册表备份。' }
    if (-not $PSCmdlet.ShouldProcess($registryPath, '备份原值并为 AudioBule 启用最多 3 个本地小型转储')) { return }
    New-Item -ItemType Directory -Path $Directory -Force | Out-Null
    $values = @()
    $existed = Test-Path -LiteralPath $registryPath
    if ($existed) {
        $key = Get-Item -LiteralPath $registryPath
        foreach ($name in $names) {
            if ($name -in $key.GetValueNames()) {
                $values += [pscustomobject]@{ Name = $name; Kind = $key.GetValueKind($name).ToString(); Value = $key.GetValue($name, $null, [Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames) }
            }
        }
    }
    [pscustomobject]@{ RegistryPath = $registryPath; Existed = $existed; Values = $values } | Export-Clixml -LiteralPath $BackupPath
    if (-not (Test-Path -LiteralPath $registryPath)) { New-Item -Path $registryPath -Force | Out-Null }
    New-ItemProperty -LiteralPath $registryPath -Name DumpFolder -Value $Directory -PropertyType ExpandString -Force | Out-Null
    New-ItemProperty -LiteralPath $registryPath -Name DumpCount -Value 3 -PropertyType DWord -Force | Out-Null
    New-ItemProperty -LiteralPath $registryPath -Name DumpType -Value 1 -PropertyType DWord -Force | Out-Null
    Write-Output "已启用，备份保存在：$BackupPath。排查结束后用 Restore 恢复。"
}
else {
    if (-not $BackupPath -or -not (Test-Path -LiteralPath $BackupPath -PathType Leaf)) { throw '恢复操作需要现有备份文件的完整路径。' }
    $backup = Import-Clixml -LiteralPath $BackupPath
    if ($backup.RegistryPath -ne $registryPath) { throw '备份不属于 AudioBule，停止恢复。' }
    foreach ($item in $backup.Values) {
        if ($item.Name -notin $names -or $item.Kind -notin @('String', 'ExpandString', 'DWord', 'QWord', 'Binary', 'MultiString', 'None')) { throw '备份包含无效字段或类型。' }
    }
    if (-not $PSCmdlet.ShouldProcess($registryPath, '仅恢复 AudioBule 转储配置的原始值')) { return }
    if (-not (Test-Path -LiteralPath $registryPath)) { New-Item -Path $registryPath -Force | Out-Null }
    foreach ($name in $names) { Remove-ItemProperty -LiteralPath $registryPath -Name $name -ErrorAction SilentlyContinue }
    # 原生注册表接口可以准确恢复 REG_NONE 等非常规原值，不推断或更改类型。
    $restoreKey = [Microsoft.Win32.Registry]::LocalMachine.OpenSubKey('SOFTWARE\Microsoft\Windows\Windows Error Reporting\LocalDumps\AudioBule.exe', $true)
    try {
        foreach ($item in $backup.Values) {
            $kind = [Microsoft.Win32.RegistryValueKind]$item.Kind
            $value = switch ($item.Kind) {
                'DWord' { [int]$item.Value; break }
                'QWord' { [long]$item.Value; break }
                'Binary' { ,([byte[]]$item.Value); break }
                'None' { ,([byte[]]$item.Value); break }
                'MultiString' { ,([string[]]$item.Value); break }
                default { [string]$item.Value }
            }
            $restoreKey.SetValue($item.Name, $value, $kind)
        }
    }
    finally { if ($restoreKey) { $restoreKey.Dispose() } }
    $key = Get-Item -LiteralPath $registryPath
    if (-not $backup.Existed -and $key.ValueCount -eq 0 -and $key.SubKeyCount -eq 0) { Remove-Item -LiteralPath $registryPath }
    Write-Output 'AudioBule 转储配置已恢复；备份及已有转储保留供核对。'
}
