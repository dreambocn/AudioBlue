param([string]$Magick = 'magick')
$ErrorActionPreference = 'Stop'
$iconDirectory = $PSScriptRoot
$generated = Join-Path $iconDirectory 'generated'
$null = New-Item -ItemType Directory -Path $generated -Force
# 矢量源在构建时转换，不让托盘启动依赖 GPU。
foreach ($theme in 'light', 'dark') {
    $images = @()
    foreach ($size in 16, 24, 32, 48) {
        $image = Join-Path $generated "tray-$theme-$size.png"
        & $Magick -background none -density 384 (Join-Path $iconDirectory "tray-$theme.svg") -resize "${size}x${size}" $image
        if ($LASTEXITCODE -ne 0) { throw '托盘图标生成失败。' }
        $images += $image
    }
    & $Magick $images (Join-Path $iconDirectory "tray-$theme.ico")
    if ($LASTEXITCODE -ne 0) { throw '托盘 ICO 合成失败。' }
}
$images = @()
foreach ($size in 16, 24, 32, 48, 64, 128, 256) {
    $image = Join-Path $generated "app-$size.png"
    & $Magick -background none -density 384 (Join-Path $iconDirectory 'app.svg') -resize "${size}x${size}" $image
    if ($LASTEXITCODE -ne 0) { throw '应用图标生成失败。' }
    $images += $image
}
& $Magick $images (Join-Path $iconDirectory 'app.ico')
if ($LASTEXITCODE -ne 0) { throw '应用 ICO 合成失败。' }
$appAssets = Join-Path $PSScriptRoot '..\..\AudioBule.App\Assets'
$null = New-Item -ItemType Directory -Path $appAssets -Force
Copy-Item -LiteralPath (Join-Path $generated 'app-256.png') -Destination (Join-Path $appAssets 'AppIcon.png')
Copy-Item -LiteralPath (Join-Path $iconDirectory 'app.ico') -Destination (Join-Path $appAssets 'AppIcon.ico')
Write-Output '应用和托盘图标已生成。'
# 静态库和最终可执行文件共享这组嵌入资源。
$coreIcons = Join-Path $PSScriptRoot '..\..\AudioBule.Core\icons'
Copy-Item (Join-Path $iconDirectory 'app.ico') $coreIcons
Copy-Item (Join-Path $iconDirectory 'tray-dark.ico') $coreIcons
Copy-Item (Join-Path $iconDirectory 'tray-light.ico') $coreIcons

# 连接徽标烘焙进资源，与托盘颜色一起匹配系统任务栏主题。
foreach ($theme in 'light', 'dark') {
    $background = if ($theme -eq 'dark') { '#202020' } else { '#F3F3F3' }
    $foreground = if ($theme -eq 'dark') { '#8BD68B' } else { '#0F7B0F' }
    $svg = [IO.File]::ReadAllText((Join-Path $iconDirectory "tray-$theme.svg"))
    $svg = $svg.Replace('</svg>', "<circle cx=`"16`" cy=`"16`" r=`"3.2`" fill=`"$background`"/><circle cx=`"16`" cy=`"16`" r=`"2.2`" fill=`"$foreground`"/></svg>")
    $source = Join-Path $generated "tray-$theme-connected.svg"
    [IO.File]::WriteAllText($source, $svg, [Text.UTF8Encoding]::new($false))
    $images = @()
    foreach ($size in 16, 24, 32, 48) {
        $image = Join-Path $generated "tray-$theme-connected-$size.png"
        & $Magick -background none -density 384 $source -resize "${size}x${size}" $image
        if ($LASTEXITCODE -ne 0) { throw '连接徽标生成失败。' }
        $images += $image
    }
    $icon = Join-Path $iconDirectory "tray-$theme-connected.ico"
    & $Magick $images $icon
    if ($LASTEXITCODE -ne 0) { throw '连接图标合成失败。' }
    Copy-Item -LiteralPath $icon -Destination $coreIcons
}
