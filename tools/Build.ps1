param(
    [ValidateSet('x64', 'ARM64')][string]$Platform = 'x64',
    [ValidateSet('Debug', 'Release')][string]$Configuration = 'Release',
    [string]$BuildRoot = (Join-Path $PSScriptRoot '..\artifacts\build'),
    [switch]$RunTests
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Build-Environment.ps1')
$repo = Split-Path -Parent $PSScriptRoot
$root = [IO.Path]::GetFullPath($BuildRoot).TrimEnd('\') + '\'
$msbuild = Find-MSBuild

# 每个架构、配置和工程使用独立目录，不覆盖正在运行的本机版本。
# 按顺序编译工程，降低 WinUI 和核心测试同时创建预编译头的内存峰值。
& $msbuild (Join-Path $repo 'AudioBule.sln') -restore -t:Build -m:1 `
    "-p:Configuration=$Configuration" "-p:Platform=$Platform" "-p:AudioBuleBuildRoot=$root" -v:minimal -nologo
if ($LASTEXITCODE -ne 0) { throw "构建失败：$Configuration|$Platform。" }

if ($RunTests) {
    $hostArchitecture = [Runtime.InteropServices.RuntimeInformation]::OSArchitecture.ToString()
    if ($Platform -eq 'ARM64' -and $hostArchitecture -ne 'Arm64') {
        throw 'ARM64 测试需要 ARM64 Windows，请在对应设备或 GitHub ARM64 运行器上执行。'
    }
    $testDirectory = Join-Path $root "$Platform\$Configuration\AudioBule.Core.Tests\bin"
    & (Join-Path $testDirectory 'AudioBule.Core.Tests.exe') --gtest_brief=1 "--gtest_output=xml:$testDirectory\test-results.xml"
    if ($LASTEXITCODE -ne 0) { throw '核心测试失败。' }
}
Write-Output "构建完成：$(Join-Path $root "$Platform\$Configuration\AudioBule.App\bin")"
