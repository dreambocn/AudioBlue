# Builds the tray icon resources.
#
# Architecture: the SVG is the single source of truth (assets/icons/bluetooth.svg,
# from Tabler Icons, MIT). The runtime does NOT render SVG -- Direct2D SVG
# support requires a hardware D3D11 device (Direct2D does not support WARP),
# which fails on machines without a usable GPU and blocks for 30+ seconds while
# creating the hardware device. That is a bad trade for a static 32x32 tray icon.
#
# So the SVG is rasterized once at build time into multi-resolution .ico files,
# and at runtime we only LoadImage + CreateIconFromResourceEx. The design stays
# vector (changing colour or size means editing the SVG), while the runtime has
# no D3D/Direct2D dependency and starts fast.
#
# NOTE: this file is intentionally ASCII-only. PowerShell 5.1 reads BOM-less
# .ps1 files as ANSI, which corrupts non-ASCII comments and can break parsing.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File assets\icons\Build-Icons.ps1
param(
    [string]$Magick = 'magick'
)

$ErrorActionPreference = 'Stop'

$iconDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$outDir = Join-Path $iconDir 'generated'
New-Item -ItemType Directory -Force $outDir | Out-Null

$sourceSvg = Join-Path $iconDir 'bluetooth.svg'
if (-not (Test-Path $sourceSvg)) {
    throw "source SVG not found: $sourceSvg"
}

# Two themes: light glyph for a dark taskbar, dark glyph for a light taskbar.
# These hex values must stay in sync with the constants in IconFactory.cpp.
$themes = @(
    @{ Name = 'dark';  Color = '#F5F5F5' },
    @{ Name = 'light'; Color = '#202020' }
)

# Tray sizes. 16 matters most (small icon area); 32 is used in the large area.
$sizes = @(16, 24, 32, 48)

foreach ($theme in $themes) {
    $svgText = Get-Content $sourceSvg -Raw
    $svgText = $svgText -replace 'stroke="currentColor"', ('stroke="' + $theme.Color + '"')
    # Tabler's 24x24 viewBox leaves a lot of padding: the bluetooth rune spans
    # only x 7..17, y 4..20 (~10x16 of the 24x24 box). At a 16px tray slot that
    # renders as a faint ~7px smudge, so scale it about the glyph centre to fill
    # the icon area.
    $svgText = $svgText -replace '<path d="([^"]+)"\s*/>', '<g transform="translate(12,12) scale(1.3) translate(-12,-12)"><path d="$1" /></g>'

    $themeSvg = Join-Path $outDir ('bluetooth-' + $theme.Name + '.svg')
    [System.IO.File]::WriteAllText($themeSvg, $svgText, (New-Object System.Text.UTF8Encoding($false)))

    $icoPath = Join-Path $iconDir ('tray-' + $theme.Name + '.ico')

    # Render each size separately, then combine. The "-define icon:N=" form is
    # unreliable across ImageMagick builds -- it silently produced a single
    # 24x24 entry here -- whereas passing several images to one .ico output is
    # the documented, portable way.
    $pngs = @()
    foreach ($size in $sizes) {
        $png = Join-Path $outDir ('bluetooth-' + $theme.Name + '-' + $size + '.png')
        & $Magick $themeSvg -background none -resize ($size.ToString() + 'x' + $size.ToString()) $png
        if ($LASTEXITCODE -ne 0) {
            throw ('ImageMagick failed for ' + $theme.Name + ' at ' + $size)
        }
        $pngs += $png
    }

    & $Magick $pngs -define 'icon:auto-resize=16,24,32,48' $icoPath
    if ($LASTEXITCODE -ne 0) {
        throw ('ImageMagick failed writing ' + $icoPath)
    }

    $generated = Get-Item $icoPath
    Write-Host ('{0,-6} {1,-24} {2} bytes' -f $theme.Name, $generated.Name, $generated.Length)
}

Write-Host 'done'