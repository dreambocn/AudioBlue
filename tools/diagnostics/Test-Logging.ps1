param(
    [string]$Executable = (Join-Path $PSScriptRoot '..\..\artifacts\build\x64\Release\AudioBule.Core.Tests\bin\AudioBule.Core.Tests.exe'),
    [string]$OutputDirectory = (Join-Path $env:USERPROFILE ('Documents\Codex\work\AudioBule\logging-system\' + (Get-Date -Format 'yyyyMMdd-HHmmss'))),
    [switch]$Benchmark,
    [ValidateRange(5, 120)][int]$Seconds = 60
)
$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $Executable -PathType Leaf)) { throw '找不到测试程序，请先构建 x64 Release。' }
if (-not [IO.Path]::IsPathFullyQualified($OutputDirectory)) { throw '测试输出目录必须为完整绝对路径。' }
New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
$previousRoot = $env:AUDIOBULE_TEST_ROOT
$previousSeconds = $env:AUDIOBULE_LOG_BENCH_SECONDS
$previousReport = $env:AUDIOBULE_LOG_BENCH_REPORT
try {
    # 环境覆盖仅对本轮测试生效，不改变日常应用日志或系统环境变量。
    $env:AUDIOBULE_TEST_ROOT = $OutputDirectory
    $env:AUDIOBULE_LOG_BENCH_SECONDS = $Seconds.ToString()
    $env:AUDIOBULE_LOG_BENCH_REPORT = Join-Path $OutputDirectory 'benchmark.json'
    $testFilter = if ($Benchmark) { 'LoggingBenchmark.*' } else { 'LoggingTest.*' }
    & $Executable "--gtest_filter=$testFilter" '--gtest_also_run_disabled_tests' "--gtest_output=xml:$(Join-Path $OutputDirectory 'test-results.xml')"
    if ($LASTEXITCODE -ne 0) { throw "日志验证失败，退出码：$LASTEXITCODE。" }
    Write-Output "日志验证材料保存在：$OutputDirectory"
}
finally {
    $env:AUDIOBULE_TEST_ROOT = $previousRoot
    $env:AUDIOBULE_LOG_BENCH_SECONDS = $previousSeconds
    $env:AUDIOBULE_LOG_BENCH_REPORT = $previousReport
}
