param(
    [Parameter(Mandatory=$true)][int]$Pid,
    [Parameter(Mandatory=$true)][string]$OutFile
)
$ErrorActionPreference="Stop"

Add-Type -AssemblyName System.Drawing

if(-not ("BiaWindowCapture" -as [type])){
Add-Type @"
using System;
using System.Runtime.InteropServices;

public static class BiaWindowCapture {
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
    public static extern bool ShowWindowAsync(IntPtr hWnd, int nCmdShow);
}
"@
}

$p=Get-Process -Id $Pid -ErrorAction Stop

$hwnd=[IntPtr]::Zero
for($i=0;$i -lt 40;$i++){
    $p.Refresh()
    $hwnd=$p.MainWindowHandle
    if($hwnd -ne [IntPtr]::Zero){ break }
    Start-Sleep -Milliseconds 100
}
if($hwnd -eq [IntPtr]::Zero){
    throw "PID $Pid has no main window handle"
}

# Restore only this exact launched PPSSPP window and bring it forward.
[void][BiaWindowCapture]::ShowWindowAsync($hwnd,9) # SW_RESTORE
Start-Sleep -Milliseconds 120
[void][BiaWindowCapture]::SetForegroundWindow($hwnd)
Start-Sleep -Milliseconds 180

$rect=New-Object BiaWindowCapture+RECT
if(-not [BiaWindowCapture]::GetClientRect($hwnd,[ref]$rect)){
    throw "GetClientRect failed for PID $Pid"
}
$pt=New-Object BiaWindowCapture+POINT
$pt.X=0;$pt.Y=0
if(-not [BiaWindowCapture]::ClientToScreen($hwnd,[ref]$pt)){
    throw "ClientToScreen failed for PID $Pid"
}

$w=$rect.Right-$rect.Left
$h=$rect.Bottom-$rect.Top
if($w -lt 64 -or $h -lt 64){
    throw "Unexpected PPSSPP client size ${w}x${h}"
}

$dir=Split-Path -Parent $OutFile
if($dir){New-Item -ItemType Directory -Force -Path $dir|Out-Null}

$bmp=New-Object System.Drawing.Bitmap($w,$h,[System.Drawing.Imaging.PixelFormat]::Format24bppRgb)
$g=[System.Drawing.Graphics]::FromImage($bmp)
try{
    $g.CopyFromScreen($pt.X,$pt.Y,0,0,[System.Drawing.Size]::new($w,$h),[System.Drawing.CopyPixelOperation]::SourceCopy)
    $bmp.Save($OutFile,[System.Drawing.Imaging.ImageFormat]::Png)
}finally{
    $g.Dispose()
    $bmp.Dispose()
}

if(-not (Test-Path -LiteralPath $OutFile)){throw "PNG not created"}
if((Get-Item -LiteralPath $OutFile).Length -le 1000){throw "PNG unexpectedly small"}

"WIDTH=$w"
"HEIGHT=$h"
"X=$($pt.X)"
"Y=$($pt.Y)"
