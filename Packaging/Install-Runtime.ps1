param([string]$LogPath)

$ErrorActionPreference = 'Stop'

# Appx 模块需要 Windows PowerShell；从 pwsh 启动时自动转交系统自带宿主。
if ($PSVersionTable.PSEdition -eq 'Core') {
    & "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File $PSCommandPath -LogPath $LogPath
    if ($LASTEXITCODE -ne 0) { throw '安装 Windows App Runtime 失败。' }
    return
}

# 安装器指定日志时保留 Appx 错误，失败后可直接排查。
if ($LogPath) { $null = Start-Transcript -LiteralPath $LogPath -Force }
try {
    # 先安装框架，再注册依赖框架的运行时组件；不需要管理员权限。
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    foreach ($name in 'Microsoft.WindowsAppRuntime.1.8.msix', 'Microsoft.WindowsAppRuntime.DDLM.1.8.msix',
        'Microsoft.WindowsAppRuntime.Main.1.8.msix', 'Microsoft.WindowsAppRuntime.Singleton.1.8.msix') {
        $package = Join-Path $PSScriptRoot "Dependencies\$name"
        if (-not (Test-Path -LiteralPath $package)) { throw "缺少运行时依赖：$package" }
        # 已安装较新版本时直接复用，避免离线包触发降级错误。
        $archive = [IO.Compression.ZipFile]::OpenRead($package)
        try {
            $reader = [IO.StreamReader]::new($archive.GetEntry('AppxManifest.xml').Open())
            try { [xml]$manifest = $reader.ReadToEnd() } finally { $reader.Dispose() }
        } finally { $archive.Dispose() }
        $identity = $manifest.Package.Identity
        $installed = Get-AppxPackage -Name $identity.Name | Where-Object {
            [version]$_.Version -ge [version]$identity.Version -and $_.Architecture -eq $identity.ProcessorArchitecture
        }
        if (-not $installed) { Add-AppxPackage -Path $package }
    }
    Write-Output 'Windows App Runtime 1.8 已安装，可以运行 AudioBule.exe。'
} finally {
    if ($LogPath) { $null = Stop-Transcript }
}
