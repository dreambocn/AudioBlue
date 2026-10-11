$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot

# 架构边界：Core 不依赖 WinUI；App 不直接调用蓝牙音频连接 API。
$rules = @(
    @{ Directory = 'AudioBule.Core'; Pattern = 'Microsoft[.:][.:]?UI[.:]|Microsoft\.UI\.'; Message = 'Core 不能引用 WinUI。' },
    @{ Directory = 'AudioBule.App'; Pattern = '\bAudioPlaybackConnection\b'; Message = 'App 必须通过 ConnectionManager 操作连接。' }
)
foreach ($rule in $rules) {
    $sources = Get-ChildItem -LiteralPath (Join-Path $repo $rule.Directory) -File |
        Where-Object { $_.Extension -in '.h', '.cpp' }
    $violations = $sources | Select-String -Pattern $rule.Pattern |
        Where-Object { -not $_.Line.TrimStart().StartsWith('//') }
    if ($violations) {
        $violations | ForEach-Object { Write-Output "$($_.Path):$($_.LineNumber): $($_.Line.Trim())" }
        throw $rule.Message
    }
}
Write-Output '架构边界检查通过。'
