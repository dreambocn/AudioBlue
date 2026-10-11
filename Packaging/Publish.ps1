param(
    [ValidateSet('Debug', 'Release')][string]$Configuration = 'Release',
    [string]$OutputDirectory = (Join-Path $PSScriptRoot 'AppPackages'),
    [string]$Magick = 'D:\Applications\Scoop\apps\imagemagick\current\magick.exe',
    [string]$CertificateThumbprint,
    [switch]$SkipBuild
)

$ErrorActionPreference = 'Stop'
$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$msbuild = 'D:\Applications\Microsoft Visual Studio\18\Community\MSBuild\Current\Bin\MSBuild.exe'
$sdkBin = 'D:\Windows Kits\10\bin\10.0.26100.0\x64'
$makeappx = Join-Path $sdkBin 'makeappx.exe'
$signtool = Join-Path $sdkBin 'signtool.exe'
foreach ($tool in $msbuild, $makeappx, $Magick) {
    if (-not (Test-Path -LiteralPath $tool)) { throw "找不到构建工具：$tool" }
}
if (-not $env:NUGET_PACKAGES) { $env:NUGET_PACKAGES = 'D:\NuGetPackages' }
if (-not $SkipBuild) {
    & $msbuild (Join-Path $repo 'AudioBule.sln') -restore -t:Rebuild "-p:Configuration=$Configuration" -p:Platform=x64 -v:minimal -nologo
    if ($LASTEXITCODE -ne 0) { throw '解决方案构建失败。' }
}

$bin = Join-Path $repo 'AudioBule.App\bin'
$exe = Join-Path $bin 'AudioBule.exe'
if (-not (Test-Path -LiteralPath $exe)) { throw '构建未生成 AudioBule.exe。' }
# 跳过构建时验证上一轮配置，避免把 Debug 当成 Release 打包。
$state = Get-ChildItem (Join-Path $repo 'AudioBule.App\obj') -Filter '*.lastbuildstate' -Recurse | Select-Object -First 1
if (-not $state -or -not ([IO.File]::ReadAllText($state.FullName).Contains("$Configuration|x64"))) {
    throw "构建配置不是 $Configuration|x64，请先重新构建。"
}

$output = [IO.Path]::GetFullPath($OutputDirectory)
$null = New-Item -ItemType Directory -Path $output -Force
$staging = Join-Path $output ('staging-' + [Guid]::NewGuid().ToString('N'))
$null = New-Item -ItemType Directory -Path $staging
try {
    # 明确选择运行文件，排除调试符号、库、链接中间产物及过期元数据。
    $extensions = '.exe', '.dll', '.pri', '.xbf', '.winmd'
    Get-ChildItem -LiteralPath $bin -File -Recurse |
        Where-Object { $_.Extension -in $extensions -and $_.Name -ne 'AudioBule.winmd' } |
        ForEach-Object {
            $relative = [IO.Path]::GetRelativePath($bin, $_.FullName)
            $destination = Join-Path $staging $relative
            $null = New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force
            Copy-Item -LiteralPath $_.FullName -Destination $destination
        }

    [xml]$manifest = [IO.File]::ReadAllText((Join-Path $repo 'assets\AudioBule.Package.appxmanifest'))
    if (-not $CertificateThumbprint) {
        # Windows 11 开发用未签名包需要微软定义的 OID，正式签名包保留原 Publisher。
        $manifest.Package.Identity.Publisher = 'CN=AudioBule, OID.2.25.311729368913984317654407730594956997722=1'
    }
    $manifest.Save((Join-Path $staging 'AppxManifest.xml'))
    $assets = Join-Path $staging 'Assets'
    $null = New-Item -ItemType Directory -Path $assets
    $svg = [IO.File]::ReadAllText((Join-Path $repo 'assets\icons\bluetooth.svg')).Replace('currentColor', '#F5F5F5')
    $svgPath = Join-Path $staging 'logo.svg'
    [IO.File]::WriteAllText($svgPath, $svg, [Text.UTF8Encoding]::new($false))
    foreach ($logo in @(
        @{ Name = 'StoreLogo.png'; Size = 50 },
        @{ Name = 'Square44x44Logo.png'; Size = 44 },
        @{ Name = 'Square150x150Logo.png'; Size = 150 }
    )) {
        $glyphSize = [int]($logo.Size * 0.68)
        & $Magick -background none -density 600 $svgPath -resize "${glyphSize}x${glyphSize}" `
            -gravity center -background '#206AC4' -extent "$($logo.Size)x$($logo.Size)" (Join-Path $assets $logo.Name)
        if ($LASTEXITCODE -ne 0) { throw "生成图标失败：$($logo.Name)" }
    }
    Remove-Item -LiteralPath $svgPath

    $version = $manifest.Package.Identity.Version
    $suffix = if ($CertificateThumbprint) { 'signed' } else { 'unsigned' }
    $package = Join-Path $output "AudioBule_${version}_x64_${Configuration}_${suffix}.msix"
    # 保持完整的清单和资源校验，不能通过 /nv 跳过验证。
    & $makeappx pack /d $staging /p $package /o
    if ($LASTEXITCODE -ne 0) { throw 'MSIX 打包或清单验证失败。' }
    if ($CertificateThumbprint) {
        & $signtool sign /fd SHA256 /sha1 $CertificateThumbprint $package
        if ($LASTEXITCODE -ne 0) { throw 'MSIX 签名失败，请核对证书主题与 Publisher。' }
        & $signtool verify /pa $package
        if ($LASTEXITCODE -ne 0) { throw 'MSIX 签名验证失败。' }
    }
    Write-Output "已生成包：$package"
    if (-not $CertificateThumbprint) { Write-Output '此包用于 Windows 11 开发验证；正式分发需指定签名证书。' }
} finally {
    # 核验随机 staging 目录处于输出目录内，再使用原生 PowerShell 清理。
    $resolved = [IO.Path]::GetFullPath($staging)
    if ($resolved.StartsWith($output.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase) -and
        [IO.Path]::GetFileName($resolved).StartsWith('staging-') -and (Test-Path -LiteralPath $resolved)) {
        Remove-Item -LiteralPath $resolved -Recurse -Force
    }
}
