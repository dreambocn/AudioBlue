param(
    [ValidateSet('x64', 'ARM64')][string]$Platform = 'x64',
    [ValidateSet('Debug', 'Release')][string]$Configuration = 'Release'
)
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$build = Join-Path $repo "artifacts\build\$Platform\$Configuration\AudioBule.App\bin"
$executable = Join-Path $build 'AudioBule.exe'
$pdb = Join-Path $build 'AudioBule.pdb'
if (-not (Test-Path -LiteralPath $executable) -or -not (Test-Path -LiteralPath $pdb)) { throw '缺少同次构建的 EXE 或 PDB，请先完成构建。' }
[xml]$manifest = Get-Content -LiteralPath (Join-Path $repo 'assets\AudioBule.Package.appxmanifest') -Raw
$hash = (Get-FileHash -LiteralPath $executable -Algorithm SHA256).Hash.ToLowerInvariant()
$destination = Join-Path $repo "artifacts\symbols\$($manifest.Package.Identity.Version)\$Platform\$Configuration\$hash"
New-Item -ItemType Directory -Path $destination -Force | Out-Null
Copy-Item -LiteralPath $executable, $pdb -Destination $destination -Force
# 符号材料独立留存，不混入用户安装包；仅保存版本、架构与二进制摘要。
[ordered]@{
    version = $manifest.Package.Identity.Version
    architecture = $Platform
    configuration = $Configuration
    executable_sha256 = $hash
    pdb_sha256 = (Get-FileHash -LiteralPath $pdb -Algorithm SHA256).Hash.ToLowerInvariant()
} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $destination 'symbols.json') -Encoding utf8
Write-Output "符号材料已保存：$destination"
