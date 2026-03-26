[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$TagName,
    [Parameter(Mandatory = $true)]
    [string]$OutputPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Get-PreviousTag {
    param(
        [Parameter(Mandatory = $true)]
        [string]$CurrentTag
    )

    $tags = git tag --sort=-creatordate
    if ($LASTEXITCODE -ne 0) {
        throw "无法读取 Git 标签列表。"
    }

    return ($tags | Where-Object { $_ -and $_ -ne $CurrentTag } | Select-Object -First 1)
}

function Normalize-CommitEntry {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Line
    )

    $parts = $Line -split "`t", 2
    if ($parts.Count -lt 2) {
        return @{
            Hash = ''
            Subject = $Line.Trim()
            Type = 'other'
            Summary = $Line.Trim()
        }
    }

    $subject = $parts[1].Trim()
    $match = [regex]::Match($subject, '^(?<type>[a-zA-Z]+)(\([^)]+\))?:\s*(?<summary>.+)$')

    if ($match.Success) {
        return @{
            Hash = $parts[0].Trim()
            Subject = $subject
            Type = $match.Groups['type'].Value.ToLowerInvariant()
            Summary = $match.Groups['summary'].Value.Trim()
        }
    }

    return @{
        Hash = $parts[0].Trim()
        Subject = $subject
        Type = 'other'
        Summary = $subject
    }
}

function Add-GroupedSummaryLine {
    param(
        [Parameter(Mandatory = $true)]
        [object]$Lines,
        [Parameter(Mandatory = $true)]
        [string]$Label,
        [Parameter(Mandatory = $true)]
        [object]$Items
    )

    if (-not $Items -or $Items.Count -eq 0) {
        return
    }

    $joinedItems = (@($Items | Select-Object -Unique)) -join '；'
    [void]$Lines.Add("- $Label：$joinedItems")
}

$resolvedOutputPath = [System.IO.Path]::GetFullPath($OutputPath)
$outputDirectory = Split-Path -Parent $resolvedOutputPath
if (-not (Test-Path $outputDirectory)) {
    New-Item -ItemType Directory -Path $outputDirectory | Out-Null
}

$previousTag = Get-PreviousTag -CurrentTag $TagName
$commitRange = if ($previousTag) { "$previousTag..HEAD" } else { 'HEAD' }
$commitLines = git log --format='%h%x09%s' $commitRange
if ($LASTEXITCODE -ne 0) {
    throw "无法读取提交记录：$commitRange"
}

$normalizedCommits = @()
foreach ($line in $commitLines) {
    if (-not [string]::IsNullOrWhiteSpace($line)) {
        $normalizedCommits += Normalize-CommitEntry -Line $line
    }
}

$featureSummaries = [System.Collections.Generic.List[string]]::new()
$fixSummaries = [System.Collections.Generic.List[string]]::new()
$buildSummaries = [System.Collections.Generic.List[string]]::new()
$docsSummaries = [System.Collections.Generic.List[string]]::new()
$otherSummaries = [System.Collections.Generic.List[string]]::new()

foreach ($commit in $normalizedCommits) {
    switch ($commit.Type) {
        'feat' { $featureSummaries.Add($commit.Summary); continue }
        'fix' { $fixSummaries.Add($commit.Summary); continue }
        'build' { $buildSummaries.Add($commit.Summary); continue }
        'docs' { $docsSummaries.Add($commit.Summary); continue }
        'test' { $docsSummaries.Add($commit.Summary); continue }
        default { $otherSummaries.Add($commit.Summary) }
    }
}

$releaseTitle = if ($TagName.StartsWith('v')) { $TagName } else { "v$TagName" }
$bodyLines = [System.Collections.Generic.List[string]]::new()
$bodyLines.Add("# $releaseTitle 发布摘要")
$bodyLines.Add('')
$bodyLines.Add('## 汇总摘要')

Add-GroupedSummaryLine -Lines $bodyLines -Label '功能更新' -Items $featureSummaries
Add-GroupedSummaryLine -Lines $bodyLines -Label '问题修复' -Items $fixSummaries
Add-GroupedSummaryLine -Lines $bodyLines -Label '发布与打包' -Items $buildSummaries
Add-GroupedSummaryLine -Lines $bodyLines -Label '文档与测试' -Items $docsSummaries
Add-GroupedSummaryLine -Lines $bodyLines -Label '其他更新' -Items $otherSummaries

if ($bodyLines.Count -eq 3) {
    $bodyLines.Add('- 本次版本未检测到可汇总的提交说明。')
}

$bodyLines.Add('')
$bodyLines.Add('## 提交明细')
if ($previousTag) {
    $bodyLines.Add("- 对比范围：$previousTag..$TagName")
}
else {
    $bodyLines.Add("- 对比范围：$TagName 首次发布")
}

foreach ($commit in $normalizedCommits) {
    $bodyLines.Add("- $($commit.Hash) $($commit.Subject)")
}

Set-Content -Path $resolvedOutputPath -Value $bodyLines -Encoding UTF8
