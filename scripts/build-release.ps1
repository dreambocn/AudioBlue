[CmdletBinding()]
param(
    [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path,
    [string]$Version
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

$resolvedProjectRoot = (Resolve-Path $ProjectRoot).Path
$uiRoot = Join-Path $resolvedProjectRoot 'ui'
$pyprojectPath = Join-Path $resolvedProjectRoot 'pyproject.toml'
$installerScriptPath = Join-Path $resolvedProjectRoot 'installer\AudioBlue.iss'
$releaseRoot = Join-Path $resolvedProjectRoot 'dist\release'
$installerOutputPath = Join-Path $resolvedProjectRoot 'dist\installer\AudioBlue-Setup.exe'

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

Write-Step '同步 Python 依赖'
Invoke-CheckedCommand -Command 'uv sync --frozen --all-groups' -WorkingDirectory $resolvedProjectRoot

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

Write-Step '校验打包产物'
Invoke-CheckedCommand -Command 'uv run python scripts\verify_packaging_assets.py --dist-root dist --installer-script installer\AudioBlue.iss --format text' -WorkingDirectory $resolvedProjectRoot

Write-Step '构建 Inno Setup 安装器'
Push-Location $resolvedProjectRoot
try {
    & $isccPath $installerScriptPath
    if ($LASTEXITCODE -ne 0) {
        throw "Inno Setup 编译失败。"
    }
}
finally {
    Pop-Location
}

if (-not (Test-Path $installerOutputPath)) {
    throw "未找到安装器产物：$installerOutputPath"
}

Copy-Item -Path $installerOutputPath -Destination (Join-Path $releaseRoot 'AudioBlue-Setup.exe') -Force

Write-Step '发布产物已准备完成'
Write-Host "安装器：$releaseRoot\AudioBlue-Setup.exe"
