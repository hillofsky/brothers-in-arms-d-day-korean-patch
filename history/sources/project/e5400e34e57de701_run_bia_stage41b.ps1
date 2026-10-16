$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$Root = 'PROJECT_ROOT'
$Iso = Join-Path $Root 'BIA_STAGE41A_FIRST_MOVIE_KO_SUB_TEST.iso'
$Analysis = Join-Path $Root 'analysis\stage41b_movie_subtitle_renderer'
$LogRoot = Join-Path $Root 'log'
$OldRoot = Join-Path $LogRoot 'old'
$Stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$RunLog = Join-Path $Analysis 'stage41b_run.log'
$Failure = Join-Path $Analysis 'FAILURE.txt'
$NormalZip = Join-Path $LogRoot 'bia_stage41b_upload.zip'
$FailZip = Join-Path $LogRoot 'fail_bia_stage41b_upload.zip'
$PyScript = Join-Path $PSScriptRoot 'stage41b_trace_movie_subtitle.py'
$OwnedProc = $null

New-Item -ItemType Directory -Force -Path $Analysis,$LogRoot,$OldRoot | Out-Null
Get-ChildItem $Analysis -File -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue

function Find-PPSSPP {
    $candidates = @(
        'LOCAL_PATH',
        'PROJECT_ROOT\PPSSPPWindows64.exe'
    )
    foreach ($p in $candidates) { if (Test-Path $p) { return $p } }
    $base='LOCAL_PATH'
    if (Test-Path $base) {
        $f = Get-ChildItem $base -Filter 'PPSSPPWindows64.exe' -Recurse -File -ErrorAction SilentlyContinue |
            Sort-Object LastWriteTime -Descending | Select-Object -First 1
        if ($f) { return $f.FullName }
    }
    throw 'PPSSPPWindows64.exe not found.'
}
function Get-FreePort {
    foreach ($p in 26222..26350) {
        $l = $null
        try {
            $l = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback,$p)
            $l.Start(); $l.Stop(); return $p
        } catch { if ($l) { try { $l.Stop() } catch {} } }
    }
    throw 'No free debugger port in 26222..26350.'
}
function Pack-Result([bool]$Success) {
    $pkg = Join-Path $Analysis '_upload_package'
    Remove-Item $pkg -Recurse -Force -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Force -Path $pkg | Out-Null
    Get-ChildItem $Analysis -File -ErrorAction SilentlyContinue | ForEach-Object { Copy-Item $_.FullName $pkg -Force }
    Copy-Item $PyScript $pkg -Force
    Copy-Item $PSCommandPath $pkg -Force
    if ($Success) {
        if (Test-Path $NormalZip) {
            $old=Join-Path $OldRoot $Stamp; New-Item -ItemType Directory -Force -Path $old | Out-Null
            Move-Item $NormalZip (Join-Path $old 'bia_stage41b_upload.zip') -Force
        }
        Compress-Archive -Path (Join-Path $pkg '*') -DestinationPath $NormalZip -Force
        Write-Host "Upload ZIP: $NormalZip"
    } else {
        Compress-Archive -Path (Join-Path $pkg '*') -DestinationPath $FailZip -Force
        Write-Host "Failure ZIP: $FailZip"
    }
    Remove-Item $pkg -Recurse -Force -ErrorAction SilentlyContinue
}

$Succeeded=$false
try {
    if (-not (Test-Path $Iso)) { throw "Missing Stage41A ISO: $Iso" }
    if (-not (Test-Path $PyScript)) { throw "Missing tracer: $PyScript" }
    $Ppsspp = Find-PPSSPP
    $Port = Get-FreePort
    "Stage41B start $(Get-Date -Format o)" | Set-Content $RunLog -Encoding UTF8
    "ISO=$Iso`nPPSSPP=$Ppsspp`nPORT=$Port" | Add-Content $RunLog -Encoding UTF8
    Write-Host '=== BIA STAGE 41B: MOVIE SUBTITLE RENDERER TRACE ==='
    Write-Host "ISO    : $Iso"
    Write-Host "PPSSPP : $Ppsspp"
    Write-Host "Port   : $Port"
    Write-Host ''
    Write-Host 'Stage41A ISO는 수정하지 않습니다. 인터프리터(-i)에서 ST1 read watchpoint만 추적합니다.'
    Write-Host '자동 진입이 빗나가면 PPSSPP 창에서 직접 스토리 > 새 게임 > 난이도 선택으로 첫 영상을 시작하세요.'
    Write-Host ''
    $argLine = "-i --debugger=$Port `"$Iso`""
    $OwnedProc = Start-Process -FilePath $Ppsspp -ArgumentList $argLine -PassThru
    Start-Sleep -Milliseconds 700
    $python = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($python) {
        & $python.Source -3 $PyScript --port $Port --pid $OwnedProc.Id --out $Analysis --iso $Iso 2>&1 | Tee-Object -FilePath $RunLog -Append
        $code=$LASTEXITCODE
    } else {
        $python = Get-Command python.exe -ErrorAction SilentlyContinue
        if (-not $python) { throw 'Python 3 not found.' }
        & $python.Source $PyScript --port $Port --pid $OwnedProc.Id --out $Analysis --iso $Iso 2>&1 | Tee-Object -FilePath $RunLog -Append
        $code=$LASTEXITCODE
    }
    if ($code -ne 0) { throw "stage41b tracer exit code $code" }
    if (-not (Test-Path (Join-Path $Analysis 'stage41b_report.json'))) { throw 'stage41b_report.json missing' }
    $Succeeded=$true
}
catch {
    $_ | Out-String | Set-Content $Failure -Encoding UTF8
    Write-Host "FAILED: $($_.Exception.Message)" -ForegroundColor Red
}
finally {
    if ($OwnedProc) {
        try {
            if (-not $OwnedProc.HasExited) {
                Stop-Process -Id $OwnedProc.Id -Force -ErrorAction SilentlyContinue
                Start-Sleep -Milliseconds 300
            }
        } catch {}
    }
    Pack-Result $Succeeded
}
if (-not $Succeeded) { exit 1 }
Write-Host 'STAGE 41B SUCCESS'
exit 0
