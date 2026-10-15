param(
    [ValidateSet('x64', 'ARM64')][string]$Platform = 'x64',
    [ValidateSet('Debug', 'Release')][string]$Configuration = 'Release',
    [string]$OutputDirectory = (Join-Path $PSScriptRoot '..\artifacts\packages'),
    [string]$BuildRoot = (Join-Path $PSScriptRoot '..\artifacts\build'),
    [string]$CertificateThumbprint,
    [switch]$SkipBuild,
    [string]$BinaryDirectory
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '..\tools\Build-Environment.ps1')
$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$build = [IO.Path]::GetFullPath($BuildRoot)
if ($BinaryDirectory -and -not $SkipBuild) { throw '指定独立构建目录时，请先编译该目录，再使用 -SkipBuild 打包。' }
if (-not $SkipBuild) {
    & (Join-Path $repo 'tools\Build.ps1') -Platform $Platform -Configuration $Configuration -BuildRoot $build
}
$bin = if ($BinaryDirectory) { [IO.Path]::GetFullPath($BinaryDirectory) } else {
    Join-Path $build "$Platform\$Configuration\AudioBule.App\bin"
}
$exe = Join-Path $bin 'AudioBule.exe'
if (-not (Test-Path -LiteralPath $exe)) { throw "找不到应用：$exe" }
if ((Get-PeArchitecture $exe) -ne $Platform) { throw "可执行文件架构与 $Platform 不一致。" }
$objectDirectory = if ($BinaryDirectory) { Join-Path $repo 'AudioBule.App\obj' } else {
    Join-Path $build "$Platform\$Configuration\AudioBule.App\obj"
}
$state = Get-ChildItem -LiteralPath $objectDirectory -Filter '*.lastbuildstate' -Recurse | Select-Object -First 1
if (-not $state -or -not ([IO.File]::ReadAllText($state.FullName).Contains("$Configuration|$Platform"))) {
    throw "构建配置不是 $Configuration|$Platform，请先重新构建。"
}
$makeappx = Find-WindowsSdkTool 'makeappx.exe'
$output = [IO.Path]::GetFullPath($OutputDirectory)
$null = New-Item -ItemType Directory -Path $output -Force
$staging = Join-Path $output ('staging-' + [Guid]::NewGuid().ToString('N'))
$null = New-Item -ItemType Directory -Path $staging
try {
    # 保留运行资源的相对结构，排除调试符号、静态库和旧命名元数据。
    $extensions = '.exe', '.dll', '.pri', '.xbf', '.winmd', '.png', '.ico', '.json', '.manifest'
    Get-ChildItem -LiteralPath $bin -File -Recurse |
        Where-Object { $_.Extension -in $extensions -and $_.Name -ne 'AudioBule.winmd' } |
        ForEach-Object {
            $relative = [IO.Path]::GetRelativePath($bin, $_.FullName)
            $destination = Join-Path $staging $relative
            $null = New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force
            Copy-Item -LiteralPath $_.FullName -Destination $destination
        }
    foreach ($required in 'AudioBule.pri', 'AudioBule.App.winmd', 'App.xbf', 'MainWindow.xbf', 'Assets\AppIcon.ico', 'Microsoft.WindowsAppRuntime.Bootstrap.dll') {
        if (-not (Test-Path -LiteralPath (Join-Path $staging $required))) { throw "缺少运行文件：$required" }
    }
    Copy-Item -LiteralPath (Join-Path $repo 'LICENSE') -Destination $staging

    [xml]$manifest = [IO.File]::ReadAllText((Join-Path $repo 'assets\AudioBule.Package.appxmanifest'))
    $manifest.Package.Identity.ProcessorArchitecture = $Platform.ToLowerInvariant()
    if (-not $CertificateThumbprint) {
        # 未签名的开发包使用微软指定的 Publisher OID。
        $manifest.Package.Identity.Publisher = 'CN=AudioBule, OID.2.25.311729368913984317654407730594956997722=1'
    }
    $manifest.Save((Join-Path $staging 'AppxManifest.xml'))
    $assets = Join-Path $staging 'Assets'
    $null = New-Item -ItemType Directory -Path $assets -Force
    # 使用已提交的品牌 PNG，打包无需本机 ImageMagick 或图标重新生成。
    Add-Type -AssemblyName System.Drawing
    $source = [Drawing.Image]::FromFile((Join-Path $repo 'AudioBule.App\Assets\AppIcon.png'))
    try {
        foreach ($logo in @(
            @{ Name = 'StoreLogo.png'; Size = 50 },
            @{ Name = 'Square44x44Logo.png'; Size = 44 },
            @{ Name = 'Square150x150Logo.png'; Size = 150 }
        )) {
            $bitmap = [Drawing.Bitmap]::new($logo.Size, $logo.Size)
            $graphics = [Drawing.Graphics]::FromImage($bitmap)
            try {
                $graphics.InterpolationMode = [Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
                $graphics.DrawImage($source, 0, 0, $logo.Size, $logo.Size)
                $bitmap.Save((Join-Path $assets $logo.Name), [Drawing.Imaging.ImageFormat]::Png)
            } finally { $graphics.Dispose(); $bitmap.Dispose() }
        }
    } finally { $source.Dispose() }

    $version = ([version]$manifest.Package.Identity.Version).ToString(3)
    $architecture = $Platform.ToLowerInvariant()
    $suffix = if ($CertificateThumbprint) { 'signed' } else { 'unsigned' }
    $package = Join-Path $output "AudioBule_${version}_${architecture}_${suffix}.msix"
    # 保持清单和资源的完整校验，不使用 /nv。
    & $makeappx pack /d $staging /p $package /o
    if ($LASTEXITCODE -ne 0) { throw 'MSIX 打包或清单验证失败。' }
    if ($CertificateThumbprint) {
        $signtool = Find-WindowsSdkTool 'signtool.exe'
        & $signtool sign /fd SHA256 /sha1 $CertificateThumbprint $package
        if ($LASTEXITCODE -ne 0) { throw 'MSIX 签名失败，请核对证书主题与 Publisher。' }
        & $signtool verify /pa $package
        if ($LASTEXITCODE -ne 0) { throw 'MSIX 签名验证失败。' }
    }

    # 根据还原资产定位锁定版本的运行时，附上微软签名的离线依赖。
    $restoreAssets = Join-Path $repo 'AudioBule.App\obj\project.assets.json'
    $lock = Get-Content -LiteralPath $restoreAssets -Raw | ConvertFrom-Json -AsHashtable
    $runtimeKey = @($lock.libraries.Keys | Where-Object { $_ -like 'Microsoft.WindowsAppSDK.Runtime/*' })
    if ($runtimeKey.Count -ne 1) { throw '无法唯一确定 Windows App Runtime 版本。' }
    $runtime = $null
    foreach ($folder in $lock.packageFolders.Keys) {
        $candidate = Join-Path $folder $lock.libraries[$runtimeKey[0]].path
        if (Test-Path -LiteralPath $candidate) { $runtime = $candidate; break }
    }
    if (-not $runtime) { throw '找不到已还原的 Windows App Runtime 包。' }
    $dependencies = Join-Path $staging 'Dependencies'
    $null = New-Item -ItemType Directory -Path $dependencies
    $runtimePackages = @(Get-ChildItem -LiteralPath (Join-Path $runtime "tools\MSIX\win10-$architecture") -Filter '*.msix')
    if ($runtimePackages.Count -ne 4) { throw 'Windows App Runtime 离线依赖不完整。' }
    $runtimePackages | Copy-Item -Destination $dependencies
    Copy-Item -LiteralPath (Join-Path $runtime 'license.txt') -Destination (Join-Path $dependencies 'LICENSE-WindowsAppRuntime.txt')
    Copy-Item -LiteralPath (Join-Path $runtime 'NOTICE.txt') -Destination (Join-Path $dependencies 'NOTICE-WindowsAppRuntime.txt')
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'Install-Runtime.ps1') -Destination $staging
    # 便携版不带包身份，避免让用户把 AppxManifest.xml 当作安装入口。
    Remove-Item -LiteralPath (Join-Path $staging 'AppxManifest.xml')
    $instructions = @"
AudioBule $version ($architecture)

需要 Windows 10 2004 或更高版本及蓝牙硬件。
首次使用：在本目录打开 PowerShell，运行以下命令安装附带的微软签名运行时：
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Install-Runtime.ps1
执行策略仅作用于此安装进程，不更改系统策略。
安装过 Windows App Runtime 1.8 的电脑可直接运行 AudioBule.exe。
保留本目录全部文件，不要只复制 EXE。先在 Windows 设置中配对手机，再刷新、连接并播放音频。
关闭窗口后继续在托盘运行；退出请使用托盘菜单或应用设置。

同版本 MSIX 为未签名开发产物（除非文件名标有 signed），常规使用请选择本 ZIP。
项目：https://github.com/dreambocn/AudioBlue
"@
    [IO.File]::WriteAllText((Join-Path $staging '使用说明.txt'), $instructions, [Text.UTF8Encoding]::new($true))
    $zip = Join-Path $output "AudioBule_${version}_${architecture}.zip"
    Compress-Archive -Path (Join-Path $staging '*') -DestinationPath $zip -Force
    $hashes = foreach ($file in $zip, $package) {
        $hash = Get-FileHash -LiteralPath $file -Algorithm SHA256
        "$($hash.Hash.ToLowerInvariant())  $([IO.Path]::GetFileName($file))"
    }
    [IO.File]::WriteAllLines((Join-Path $output "AudioBule_${version}_${architecture}.sha256"), $hashes, [Text.UTF8Encoding]::new($false))
    Write-Output "已生成：$zip"
    Write-Output "已生成：$package"
} finally {
    # 仅清理本脚本在输出目录中创建的随机暂存目录。
    $resolved = [IO.Path]::GetFullPath($staging)
    if ($resolved.StartsWith($output.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase) -and
        [IO.Path]::GetFileName($resolved).StartsWith('staging-') -and (Test-Path -LiteralPath $resolved)) {
        Remove-Item -LiteralPath $resolved -Recurse -Force
    }
}
