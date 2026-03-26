[CmdletBinding()]
param(
    [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path,
    [string]$Version,
    [ValidateSet('x86', 'x64', 'arm64')]
    [string]$TargetArchitecture = 'x64'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Write-Step {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Message
    )

    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Get-ProjectVersion {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PyprojectPath
    )

    $content = Get-Content -Raw $PyprojectPath
    $match = [regex]::Match($content, '(?m)^version\s*=\s*"(?<version>[^"]+)"')
    if (-not $match.Success) {
        throw "无法从 pyproject.toml 解析项目版本。"
    }

    return $match.Groups['version'].Value
}

function Find-IsccPath {
    $command = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    $candidates = @(
        'C:\Program Files (x86)\Inno Setup 6\ISCC.exe'
        'C:\Program Files\Inno Setup 6\ISCC.exe'
        'D:\Applications\Scoop\apps\innosetup-np\current\ISCC.exe'
        'C:\Users\DreamBo\scoop\apps\innosetup-np\current\ISCC.exe'
    )

    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }

    throw "未找到 ISCC.exe，请先安装 Inno Setup 并确保编译器可用。"
}

function Invoke-CheckedCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Command,
        [Parameter(Mandatory = $true)]
        [string]$WorkingDirectory
    )

    Push-Location $WorkingDirectory
    try {
        Invoke-Expression $Command
        if ($LASTEXITCODE -ne 0) {
            throw "命令执行失败：$Command"
        }
    }
    finally {
        Pop-Location
    }
}

function Clear-NpmTransientDirectories {
    param(
        [Parameter(Mandatory = $true)]
        [string]$UiRoot
    )

    $transientDirectories = @(
        (Join-Path $UiRoot 'node_modules\.tmp')
        (Join-Path $UiRoot 'node_modules\.vite')
    )

    foreach ($directory in $transientDirectories) {
        if (Test-Path $directory) {
            Remove-Item -Recurse -Force $directory -ErrorAction SilentlyContinue
        }
    }
}

function Get-TargetArchitectureConfig {
    param(
        [Parameter(Mandatory = $true)]
        [ValidateSet('x86', 'x64', 'arm64')]
        [string]$Architecture
    )

    switch ($Architecture) {
        'x86' {
            return @{
                ReleaseArchitectureLabel = 'x86'
                ExpectedPlatformTag = 'win32'
                WebView2DownloadUrl = 'https://go.microsoft.com/fwlink/?linkid=2099617'
                WebView2InstallerFileName = 'MicrosoftEdgeWebView2RuntimeInstallerX86.exe'
            }
        }
        'x64' {
            return @{
                ReleaseArchitectureLabel = 'x64'
                ExpectedPlatformTag = 'win-amd64'
                WebView2DownloadUrl = 'https://go.microsoft.com/fwlink/?linkid=2124701'
                WebView2InstallerFileName = 'MicrosoftEdgeWebView2RuntimeInstallerX64.exe'
            }
        }
        'arm64' {
            return @{
                ReleaseArchitectureLabel = 'arm64'
                ExpectedPlatformTag = 'win-arm64'
                WebView2DownloadUrl = 'https://go.microsoft.com/fwlink/?linkid=2099616'
                WebView2InstallerFileName = 'MicrosoftEdgeWebView2RuntimeInstallerARM64.exe'
            }
        }
    }
}

function Save-WebView2RuntimeInstaller {
    param(
        [Parameter(Mandatory = $true)]
        [string]$DownloadUrl,
        [Parameter(Mandatory = $true)]
        [string]$DestinationPath
    )

    $destinationDirectory = Split-Path -Parent $DestinationPath

    if (-not (Test-Path $destinationDirectory)) {
        New-Item -ItemType Directory -Path $destinationDirectory | Out-Null
    }

    Write-Host "下载 WebView2 Runtime 离线安装器：$DestinationPath"
    Invoke-WebRequest -Uri $DownloadUrl -OutFile $DestinationPath

    if (-not (Test-Path $DestinationPath)) {
        throw "未找到 WebView2 Runtime 离线安装器：$DestinationPath"
    }

    $fileInfo = Get-Item $DestinationPath
    if ($fileInfo.Length -le 0) {
        throw "WebView2 Runtime 离线安装器下载结果为空：$DestinationPath"
    }
}

function Get-UvPythonPlatformTag {
    param(
        [Parameter(Mandatory = $true)]
        [string]$WorkingDirectory
    )

    Push-Location $WorkingDirectory
    try {
        $platformTag = uv run python -c "import sysconfig; print(sysconfig.get_platform())"
        if ($LASTEXITCODE -ne 0) {
            throw "无法读取 uv 环境中的 Python 平台标签。"
        }

        return ($platformTag | Out-String).Trim()
    }
    finally {
        Pop-Location
    }
}

function Assert-BuildArchitectureMatchesTarget {
    param(
        [Parameter(Mandatory = $true)]
        [string]$WorkingDirectory,
        [Parameter(Mandatory = $true)]
        [string]$ExpectedPlatformTag,
        [Parameter(Mandatory = $true)]
        [string]$TargetArchitecture
    )

    $actualPlatformTag = Get-UvPythonPlatformTag -WorkingDirectory $WorkingDirectory
    if ($actualPlatformTag -ne $ExpectedPlatformTag) {
        throw "当前 uv Python 平台为 $actualPlatformTag，与目标架构 $TargetArchitecture 期望的 $ExpectedPlatformTag 不一致。"
    }
}

function Invoke-InnoCompiler {
    param(
        [Parameter(Mandatory = $true)]
        [string]$CompilerPath,
        [Parameter(Mandatory = $true)]
        [string]$ProjectRoot,
        [Parameter(Mandatory = $true)]
        [string]$InstallerScriptPath,
        [Parameter(Mandatory = $true)]
        [hashtable]$PreprocessorDefinitions
    )

    $arguments = @()
    foreach ($entry in $PreprocessorDefinitions.GetEnumerator()) {
        $arguments += "/D$($entry.Key)=$($entry.Value)"
    }
    $arguments += $InstallerScriptPath

    Push-Location $ProjectRoot
    try {
        & $CompilerPath @arguments
        if ($LASTEXITCODE -ne 0) {
            throw "Inno Setup 编译失败：$InstallerScriptPath"
        }
    }
    finally {
        Pop-Location
    }
}

$resolvedProjectRoot = (Resolve-Path $ProjectRoot).Path
$uiRoot = Join-Path $resolvedProjectRoot 'ui'
$pyprojectPath = Join-Path $resolvedProjectRoot 'pyproject.toml'
$installerScriptPath = Join-Path $resolvedProjectRoot 'installer\AudioBlue.iss'
$installerWithWebView2ScriptPath = Join-Path $resolvedProjectRoot 'installer\AudioBlue.WithWebView2.iss'
$installerCoreScriptPath = Join-Path $resolvedProjectRoot 'installer\AudioBlue.InstallerCore.iss'
$releaseRoot = Join-Path $resolvedProjectRoot 'dist\release'

$targetConfig = Get-TargetArchitectureConfig -Architecture $TargetArchitecture
$releaseArchitectureLabel = $targetConfig.ReleaseArchitectureLabel
$webView2InstallerFileName = $targetConfig.WebView2InstallerFileName
$webView2RuntimeInstallerPath = Join-Path $resolvedProjectRoot "dist\webview2\$webView2InstallerFileName"
$webView2RuntimeRelativePath = "..\dist\webview2\$webView2InstallerFileName"

$installerOutputs = @(
    @{
        ScriptPath = $installerScriptPath
        OutputBaseFileName = "AudioBlue-Setup-$releaseArchitectureLabel"
        ReleaseName = "AudioBlue-Setup-$releaseArchitectureLabel.exe"
        BundledReleaseFileName = "AudioBlue-Setup-With-WebView2-$releaseArchitectureLabel.exe"
    },
    @{
        ScriptPath = $installerWithWebView2ScriptPath
        OutputBaseFileName = "AudioBlue-Setup-With-WebView2-$releaseArchitectureLabel"
        ReleaseName = "AudioBlue-Setup-With-WebView2-$releaseArchitectureLabel.exe"
        BundledReleaseFileName = "AudioBlue-Setup-With-WebView2-$releaseArchitectureLabel.exe"
    }
)

$projectVersion = Get-ProjectVersion -PyprojectPath $pyprojectPath
if ($Version -and $Version -ne $projectVersion) {
    throw "版本不一致：tag 版本 $Version 与 pyproject.toml 版本 $projectVersion 不匹配。"
}

$null = Get-Command uv -ErrorAction Stop
$null = Get-Command npm -ErrorAction Stop
$isccPath = Find-IsccPath

if (Test-Path $releaseRoot) {
    Remove-Item -Recurse -Force $releaseRoot
}
New-Item -ItemType Directory -Path $releaseRoot | Out-Null

Write-Step "同步 Python 依赖（目标架构：$TargetArchitecture）"
Invoke-CheckedCommand -Command 'uv sync --frozen --all-groups' -WorkingDirectory $resolvedProjectRoot

Write-Step "校验当前 Python 架构（目标架构：$TargetArchitecture）"
Assert-BuildArchitectureMatchesTarget `
    -WorkingDirectory $resolvedProjectRoot `
    -ExpectedPlatformTag $targetConfig.ExpectedPlatformTag `
    -TargetArchitecture $TargetArchitecture

Write-Step '同步前端依赖'
Clear-NpmTransientDirectories -UiRoot $uiRoot
Invoke-CheckedCommand -Command 'npm ci' -WorkingDirectory $uiRoot

Write-Step '执行 Python 测试'
Invoke-CheckedCommand -Command 'uv run pytest -q' -WorkingDirectory $resolvedProjectRoot

Write-Step '执行前端测试'
Invoke-CheckedCommand -Command 'npm test' -WorkingDirectory $uiRoot

Write-Step '构建前端资源'
Invoke-CheckedCommand -Command 'npm run build' -WorkingDirectory $uiRoot

Write-Step '生成 PyInstaller 目录版'
Invoke-CheckedCommand -Command 'uv run pyinstaller AudioBlue.spec --noconfirm' -WorkingDirectory $resolvedProjectRoot

Write-Step "准备 WebView2 离线安装器（目标架构：$TargetArchitecture）"
Save-WebView2RuntimeInstaller `
    -DownloadUrl $targetConfig.WebView2DownloadUrl `
    -DestinationPath $webView2RuntimeInstallerPath

Write-Step '校验打包产物'
Invoke-CheckedCommand -Command "uv run python scripts\verify_packaging_assets.py --dist-root dist --installer-script installer\AudioBlue.iss --installer-script installer\AudioBlue.WithWebView2.iss --installer-core-script installer\AudioBlue.InstallerCore.iss --webview2-runtime-installer dist\webview2\$webView2InstallerFileName --format text" -WorkingDirectory $resolvedProjectRoot

Write-Step "构建 Inno Setup 安装器（目标架构：$TargetArchitecture）"
foreach ($installer in $installerOutputs) {
    $preprocessorDefinitions = @{
        InstallerOutputBaseFilename = $installer.OutputBaseFileName
        ReleaseArchitectureLabel = $releaseArchitectureLabel
        BundledReleaseFileName = $installer.BundledReleaseFileName
        WebView2RuntimeRelativePath = $webView2RuntimeRelativePath
        WebView2BundledInstallerName = $webView2InstallerFileName
    }

    Invoke-InnoCompiler `
        -CompilerPath $isccPath `
        -ProjectRoot $resolvedProjectRoot `
        -InstallerScriptPath $installer.ScriptPath `
        -PreprocessorDefinitions $preprocessorDefinitions
}

foreach ($installer in $installerOutputs) {
    $installerOutputPath = Join-Path $resolvedProjectRoot "dist\installer\$($installer.ReleaseName)"
    if (-not (Test-Path $installerOutputPath)) {
        throw "未找到安装器产物：$installerOutputPath"
    }

    Copy-Item -Path $installerOutputPath -Destination (Join-Path $releaseRoot $installer.ReleaseName) -Force
}

Write-Step "发布产物已准备完成（目标架构：$TargetArchitecture）"
foreach ($installer in $installerOutputs) {
    Write-Host "安装器：$(Join-Path $releaseRoot $installer.ReleaseName)"
}
