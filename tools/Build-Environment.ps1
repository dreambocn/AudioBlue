# 构建与打包共用工具探测，支持标准安装路径和自定义磁盘。
function Find-MSBuild {
    $command = Get-Command MSBuild.exe -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }
    $vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
    if (-not (Test-Path -LiteralPath $vswhere)) { throw '找不到 vswhere.exe，请安装 Visual Studio C++ 桌面开发工具。' }
    $installation = & $vswhere -latest -products '*' -requires Microsoft.Component.MSBuild -property installationPath
    if ($LASTEXITCODE -ne 0 -or -not $installation) { throw '找不到可用的 Visual Studio MSBuild。' }
    $path = Join-Path $installation 'MSBuild\Current\Bin\MSBuild.exe'
    if (-not (Test-Path -LiteralPath $path)) { throw "找不到 MSBuild：$path" }
    return $path
}

function Find-WindowsSdkTool([string]$Name) {
    $kits = Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows Kits\Installed Roots' -ErrorAction Stop
    $hostArchitecture = if ([Runtime.InteropServices.RuntimeInformation]::OSArchitecture.ToString() -eq 'Arm64') { 'arm64' } else { 'x64' }
    $tool = Join-Path $kits.KitsRoot10 "bin\10.0.26100.0\$hostArchitecture\$Name"
    if (-not (Test-Path -LiteralPath $tool)) { throw "找不到 Windows SDK 26100 工具：$tool" }
    return $tool
}

function Get-PeArchitecture([string]$Path) {
    # 核对 PE 头，防止把其它架构的旧文件打进发布包。
    $stream = [IO.File]::OpenRead($Path)
    $reader = [IO.BinaryReader]::new($stream)
    try {
        if ($reader.ReadUInt16() -ne 0x5A4D) { throw "不是有效的 Windows 可执行文件：$Path" }
        $stream.Position = 0x3C
        $offset = $reader.ReadInt32()
        if ($offset -lt 0 -or $offset -gt ($stream.Length - 6)) { throw "PE 头偏移无效：$Path" }
        $stream.Position = $offset
        if ($reader.ReadUInt32() -ne 0x00004550) { throw "PE 签名无效：$Path" }
        switch ($reader.ReadUInt16()) {
            0x8664 { return 'x64' }
            0xAA64 { return 'ARM64' }
            default { throw "不支持的 PE 架构：$Path" }
        }
    } finally { $reader.Dispose() }
}
