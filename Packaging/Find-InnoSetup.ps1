$ErrorActionPreference = 'Stop'

# 优先使用当前用户安装的固定版本，避免被运行器预装的其他版本抢先匹配。
foreach ($directory in @(
    (Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 6'),
    (Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6'),
    (Join-Path $env:ProgramFiles 'Inno Setup 6')
)) {
    $compiler = Join-Path $directory 'ISCC.exe'
    if (Test-Path -LiteralPath $compiler) { Write-Output $compiler; return }
}
$command = Get-Command ISCC.exe -ErrorAction SilentlyContinue
if ($command) { Write-Output $command.Source; return }
throw '请先安装 Inno Setup 6：winget install --id JRSoftware.InnoSetup --exact --source winget'
