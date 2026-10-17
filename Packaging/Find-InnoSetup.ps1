$ErrorActionPreference = 'Stop'

# 依次检查命令搜索路径和当前用户、系统的标准安装位置。
$command = Get-Command ISCC.exe -ErrorAction SilentlyContinue
if ($command) { Write-Output $command.Source; return }
foreach ($directory in @(
    (Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 6'),
    (Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6'),
    (Join-Path $env:ProgramFiles 'Inno Setup 6')
)) {
    $compiler = Join-Path $directory 'ISCC.exe'
    if (Test-Path -LiteralPath $compiler) { Write-Output $compiler; return }
}
throw '请先安装 Inno Setup 6：winget install --id JRSoftware.InnoSetup --exact --source winget'
