param(
    [Parameter(Mandatory=$true)][UInt64]$Hwnd,
    [Parameter(Mandatory=$true)][string]$OutFile
)

$ErrorActionPreference = "Stop"

Add-Type -AssemblyName System.Drawing

$src = @"
using System;
using System.Runtime.InteropServices;

public static class BiaWin32 {
    [StructLayout(LayoutKind.Sequential)]
    public struct RECT {
        public int Left;
        public int Top;
        public int Right;
        public int Bottom;
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct POINT {
        public int X;
        public int Y;
    }

    [DllImport("user32.dll")]
    public static extern bool GetClientRect(IntPtr hWnd, out RECT lpRect);

    [DllImport("user32.dll")]
    public static extern bool ClientToScreen(IntPtr hWnd, ref POINT lpPoint);

    [DllImport("user32.dll")]
    public static extern bool SetForegroundWindow(IntPtr hWnd);

    [DllImport("user32.dll")]
    public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
}
"@

Add-Type -TypeDefinition $src

$h = [System.IntPtr]([System.Int64]$Hwnd)
Write-Host ("HWND: 0x{0:X}" -f $h.ToInt64())
[BiaWin32]::ShowWindow($h, 9) | Out-Null
[BiaWin32]::SetForegroundWindow($h) | Out-Null
Start-Sleep -Milliseconds 250

$rect = New-Object BiaWin32+RECT
if (-not [BiaWin32]::GetClientRect($h, [ref]$rect)) {
    throw "GetClientRect failed."
}

$pt = New-Object BiaWin32+POINT
$pt.X = 0
$pt.Y = 0
if (-not [BiaWin32]::ClientToScreen($h, [ref]$pt)) {
    throw "ClientToScreen failed."
}

$w = $rect.Right - $rect.Left
$hgt = $rect.Bottom - $rect.Top
if ($w -le 0 -or $hgt -le 0) {
    throw "Invalid PPSSPP client size: ${w}x${hgt}"
}

$bmp = New-Object System.Drawing.Bitmap $w, $hgt
$g = [System.Drawing.Graphics]::FromImage($bmp)

try {
    $g.CopyFromScreen(
        $pt.X, $pt.Y,
        0, 0,
        (New-Object System.Drawing.Size $w, $hgt),
        [System.Drawing.CopyPixelOperation]::SourceCopy
    )

    $dir = Split-Path -Parent $OutFile
    if ($dir) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }

    $bmp.Save(
        $OutFile,
        [System.Drawing.Imaging.ImageFormat]::Png
    )
}
finally {
    $g.Dispose()
    $bmp.Dispose()
}

Write-Host "Captured: $OutFile"
