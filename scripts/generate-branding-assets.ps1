[CmdletBinding()]
param(
    [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Add-Type -AssemblyName System.Drawing

function New-RoundedRectanglePath {
    param(
        [Parameter(Mandatory = $true)]
        [System.Drawing.RectangleF]$Rectangle,
        [Parameter(Mandatory = $true)]
        [float]$Radius
    )

    $diameter = $Radius * 2
    $path = [System.Drawing.Drawing2D.GraphicsPath]::new()
    $path.StartFigure()
    $path.AddArc($Rectangle.X, $Rectangle.Y, $diameter, $diameter, 180, 90)
    $path.AddArc($Rectangle.Right - $diameter, $Rectangle.Y, $diameter, $diameter, 270, 90)
    $path.AddArc($Rectangle.Right - $diameter, $Rectangle.Bottom - $diameter, $diameter, $diameter, 0, 90)
    $path.AddArc($Rectangle.X, $Rectangle.Bottom - $diameter, $diameter, $diameter, 90, 90)
    $path.CloseFigure()
    return $path
}

function Add-ScaledBezier {
    param(
        [Parameter(Mandatory = $true)]
        [System.Drawing.Drawing2D.GraphicsPath]$Path,
        [float[]]$Points,
        [float]$Scale
    )

    $Path.AddBezier(
        $Points[0] * $Scale,
        $Points[1] * $Scale,
        $Points[2] * $Scale,
        $Points[3] * $Scale,
        $Points[4] * $Scale,
        $Points[5] * $Scale,
        $Points[6] * $Scale,
        $Points[7] * $Scale
    )
}

function New-IconBitmap {
    param(
        [Parameter(Mandatory = $true)]
        [int]$Size
    )

    $scale = $Size / 256.0
    $bitmap = [System.Drawing.Bitmap]::new($Size, $Size)
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    $graphics.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
    $graphics.Clear([System.Drawing.Color]::Transparent)

    $backgroundRect = [System.Drawing.RectangleF]::new(0, 0, $Size, $Size)
    $backgroundPath = New-RoundedRectanglePath -Rectangle $backgroundRect -Radius (62 * $scale)
    $backgroundBrush = [System.Drawing.Drawing2D.LinearGradientBrush]::new(
        [System.Drawing.PointF]::new(40 * $scale, 24 * $scale),
        [System.Drawing.PointF]::new(212 * $scale, 232 * $scale),
        [System.Drawing.Color]::FromArgb(255, 16, 35, 61),
        [System.Drawing.Color]::FromArgb(255, 6, 13, 24)
    )
    $graphics.FillPath($backgroundBrush, $backgroundPath)

    $borderRect = [System.Drawing.RectangleF]::new(10 * $scale, 10 * $scale, $Size - (20 * $scale), $Size - (20 * $scale))
    $borderPath = New-RoundedRectanglePath -Rectangle $borderRect -Radius (52 * $scale)
    $borderPen = [System.Drawing.Pen]::new([System.Drawing.Color]::FromArgb(36, 143, 225, 255), [Math]::Max(1, 2 * $scale))
    $graphics.DrawPath($borderPen, $borderPath)

    $strokeBrush = [System.Drawing.Drawing2D.LinearGradientBrush]::new(
        [System.Drawing.PointF]::new(64 * $scale, 72 * $scale),
        [System.Drawing.PointF]::new(196 * $scale, 184 * $scale),
        [System.Drawing.Color]::FromArgb(255, 125, 235, 255),
        [System.Drawing.Color]::FromArgb(255, 22, 108, 255)
    )

    $outerPen = [System.Drawing.Pen]::new($strokeBrush, 15 * $scale)
    $outerPen.StartCap = [System.Drawing.Drawing2D.LineCap]::Round
    $outerPen.EndCap = [System.Drawing.Drawing2D.LineCap]::Round

    $innerPen = [System.Drawing.Pen]::new([System.Drawing.Color]::FromArgb(255, 142, 240, 255), 9 * $scale)
    $innerPen.StartCap = [System.Drawing.Drawing2D.LineCap]::Round
    $innerPen.EndCap = [System.Drawing.Drawing2D.LineCap]::Round

    $outerLeft = [System.Drawing.Drawing2D.GraphicsPath]::new()
    Add-ScaledBezier -Path $outerLeft -Points @(88, 64, 40, 98, 40, 158, 88, 192) -Scale $scale
    $graphics.DrawPath($outerPen, $outerLeft)

    $innerLeft = [System.Drawing.Drawing2D.GraphicsPath]::new()
    Add-ScaledBezier -Path $innerLeft -Points @(115, 92, 84, 113, 84, 143, 115, 164) -Scale $scale
    $graphics.DrawPath($innerPen, $innerLeft)

    $outerRight = [System.Drawing.Drawing2D.GraphicsPath]::new()
    Add-ScaledBezier -Path $outerRight -Points @(168, 64, 216, 98, 216, 158, 168, 192) -Scale $scale
    $graphics.DrawPath($outerPen, $outerRight)

    $innerRight = [System.Drawing.Drawing2D.GraphicsPath]::new()
    Add-ScaledBezier -Path $innerRight -Points @(141, 92, 172, 113, 172, 143, 141, 164) -Scale $scale
    $graphics.DrawPath($innerPen, $innerRight)

    $outerGlowBrush = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(255, 234, 251, 255))
    $innerGlowBrush = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(255, 53, 200, 255))
    $graphics.FillEllipse($outerGlowBrush, 106 * $scale, 106 * $scale, 44 * $scale, 44 * $scale)
    $graphics.FillEllipse($innerGlowBrush, 118 * $scale, 118 * $scale, 20 * $scale, 20 * $scale)

    $outerLeft.Dispose()
    $innerLeft.Dispose()
    $outerRight.Dispose()
    $innerRight.Dispose()
    $outerGlowBrush.Dispose()
    $innerGlowBrush.Dispose()
    $outerPen.Dispose()
    $innerPen.Dispose()
    $strokeBrush.Dispose()
    $borderPen.Dispose()
    $borderPath.Dispose()
    $backgroundBrush.Dispose()
    $backgroundPath.Dispose()
    $graphics.Dispose()

    return $bitmap
}

function Convert-BitmapToPngBytes {
    param(
        [Parameter(Mandatory = $true)]
        [System.Drawing.Bitmap]$Bitmap
    )

    $memoryStream = [System.IO.MemoryStream]::new()
    $Bitmap.Save($memoryStream, [System.Drawing.Imaging.ImageFormat]::Png)
    return $memoryStream.ToArray()
}

function Write-IcoFile {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [Parameter(Mandatory = $true)]
        [System.Collections.Generic.List[object]]$Entries
    )

    $fileStream = [System.IO.File]::Open($Path, [System.IO.FileMode]::Create, [System.IO.FileAccess]::Write)
    $writer = [System.IO.BinaryWriter]::new($fileStream)
    try {
        $writer.Write([UInt16]0)
        $writer.Write([UInt16]1)
        $writer.Write([UInt16]$Entries.Count)

        $offset = 6 + (16 * $Entries.Count)
        foreach ($entry in $Entries) {
            $size = [int]$entry.Size
            $pngBytes = [byte[]]$entry.Bytes
            $writer.Write([byte]($(if ($size -ge 256) { 0 } else { $size })))
            $writer.Write([byte]($(if ($size -ge 256) { 0 } else { $size })))
            $writer.Write([byte]0)
            $writer.Write([byte]0)
            $writer.Write([UInt16]1)
            $writer.Write([UInt16]32)
            $writer.Write([UInt32]$pngBytes.Length)
            $writer.Write([UInt32]$offset)
            $offset += $pngBytes.Length
        }

        foreach ($entry in $Entries) {
            $writer.Write([byte[]]$entry.Bytes)
        }
    }
    finally {
        $writer.Dispose()
        $fileStream.Dispose()
    }
}

$resolvedProjectRoot = (Resolve-Path $ProjectRoot).Path
$brandingRoot = Join-Path $resolvedProjectRoot 'assets\branding'
New-Item -ItemType Directory -Force -Path $brandingRoot | Out-Null

$pngSizes = @(16, 32, 48, 64, 128, 256, 512)
$icoEntries = [System.Collections.Generic.List[object]]::new()

foreach ($size in $pngSizes) {
    $bitmap = New-IconBitmap -Size $size
    $pngPath = Join-Path $brandingRoot "audioblue-icon-$size.png"
    $bitmap.Save($pngPath, [System.Drawing.Imaging.ImageFormat]::Png)

    if ($size -in @(16, 32, 48, 64, 128, 256)) {
        $icoEntries.Add([PSCustomObject]@{
            Size = $size
            Bytes = Convert-BitmapToPngBytes -Bitmap $bitmap
        })
    }

    $bitmap.Dispose()
}

Write-IcoFile -Path (Join-Path $brandingRoot 'audioblue-icon.ico') -Entries $icoEntries
