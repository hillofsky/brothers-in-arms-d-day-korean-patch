$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$Root = 'PROJECT_ROOT'
$Iso = Join-Path $Root 'BIA_STAGE41A_FIRST_MOVIE_KO_SUB_TEST.iso'
$Analysis = Join-Path $Root 'analysis\stage41b_fix1_movie_subtitle_renderer'
$LogRoot = Join-Path $Root 'log'
$OldRoot = Join-Path $LogRoot 'old'
$Stamp = Get-Date -Format 'yyyyMMdd_HHmmss'

$RunLog = Join-Path $Analysis 'stage41b_fix1_run.log'
$Failure = Join-Path $Analysis 'FAILURE.txt'
$NormalZip = Join-Path $LogRoot 'bia_stage41b_fix1_upload.zip'
$FailZip = Join-Path $LogRoot 'fail_bia_stage41b_fix1_upload.zip'

$PyScript = Join-Path $PSScriptRoot 'stage41b_fix1_trace_movie_subtitle.py'
$OwnedProc = $null
$Succeeded = $false

New-Item -ItemType Directory -Force -Path $Analysis,$LogRoot,$OldRoot | Out-Null
Get-ChildItem $Analysis -File -ErrorAction SilentlyContinue |
    Remove-Item -Force -ErrorAction SilentlyContinue

function Find-PPSSPP {
    $candidates = @(
        'LOCAL_PATH',
        'PROJECT_ROOT\PPSSPPWindows64.exe'
    )
    foreach ($p in $candidates) {
        if (Test-Path $p) { return $p }
    }

    $base = 'LOCAL_PATH'
    if (Test-Path $base) {
        $f = Get-ChildItem $base -Filter 'PPSSPPWindows64.exe' -Recurse -File -ErrorAction SilentlyContinue |
            Sort-Object LastWriteTime -Descending |
            Select-Object -First 1
        if ($f) { return $f.FullName }
    }

    throw 'PPSSPPWindows64.exe not found.'
}

function Get-FreePort {
    foreach ($p in 26222..26350) {
        $l = $null
        try {
            $l = [System.Net.Sockets.TcpListener]::new(
                [System.Net.IPAddress]::Loopback, $p
            )
            $l.Start()
            $l.Stop()
            return $p
        }
        catch {
            if ($l) {
                try { $l.Stop() } catch {}
            }
        }
    }
    throw 'No free debugger port in 26222..26350.'
}

function Archive-ExistingZip([string]$Path) {
    if (Test-Path $Path) {
        $dir = Join-Path $OldRoot $Stamp
        New-Item -ItemType Directory -Force -Path $dir | Out-Null
        Move-Item $Path (Join-Path $dir ([IO.Path]::GetFileName($Path))) -Force
    }
}

function Pack-Result([bool]$Success) {
    $pkg = Join-Path $Analysis '_upload_package'
    Remove-Item $pkg -Recurse -Force -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Force -Path $pkg | Out-Null

    Get-ChildItem $Analysis -File -ErrorAction SilentlyContinue |
        ForEach-Object { Copy-Item $_.FullName $pkg -Force }

    Copy-Item $PyScript $pkg -Force
    Copy-Item $PSCommandPath $pkg -Force

    if ($Success) {
        Archive-ExistingZip $NormalZip
        Compress-Archive -Path (Join-Path $pkg '*') -DestinationPath $NormalZip -Force
        Write-Host ""
        Write-Host "Upload ZIP: $NormalZip" -ForegroundColor Green
    }
    else {
        Archive-ExistingZip $FailZip
        Compress-Archive -Path (Join-Path $pkg '*') -DestinationPath $FailZip -Force
        Write-Host ""
        Write-Host "Failure ZIP: $FailZip" -ForegroundColor Yellow
    }

    Remove-Item $pkg -Recurse -Force -ErrorAction SilentlyContinue
}

try {
    if (-not (Test-Path $Iso)) {
        throw "Missing Stage41A ISO: $Iso"
    }
    if (-not (Test-Path $PyScript)) {
        throw "Missing tracer: $PyScript"
    }

    $Ppsspp = Find-PPSSPP
    $Port = Get-FreePort

    "Stage41B Fix1 start $(Get-Date -Format o)" |
        Set-Content $RunLog -Encoding UTF8
    "ISO=$Iso`nPPSSPP=$Ppsspp`nPORT=$Port" |
        Add-Content $RunLog -Encoding UTF8

    Write-Host '=== BIA STAGE 41B FIX1: BINK/ST1 READER TRACE ==='
    Write-Host "ISO    : $Iso"
    Write-Host "PPSSPP : $Ppsspp"
    Write-Host "Port   : $Port"
    Write-Host ''
    Write-Host 'Stage41A ISO는 수정하지 않습니다.'
    Write-Host '초기 로고 Bink 종료를 감지한 뒤에만 메뉴 입력을 보냅니다.'
    Write-Host 'memory.search는 사용하지 않고 memory.read로 RAM을 직접 검사합니다.'
    Write-Host '자동 진입이 빗나가면 열린 PPSSPP 창에서 스토리 > 새 게임 > 난이도를 직접 선택해도 됩니다.'
    Write-Host ''

    # -i = interpreter.  Memory watchpoints are most reliable here.
    $argLine = "-i --debugger=$Port `"$Iso`""
    $OwnedProc = Start-Process -FilePath $Ppsspp -ArgumentList $argLine -PassThru
    Start-Sleep -Milliseconds 700

    $python = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($python) {
        & $python.Source -3 $PyScript `
            --port $Port `
            --pid $OwnedProc.Id `
            --out $Analysis `
            --iso $Iso 2>&1 |
            Tee-Object -FilePath $RunLog -Append
        $code = $LASTEXITCODE
    }
    else {
        $python = Get-Command python.exe -ErrorAction SilentlyContinue
        if (-not $python) {
            throw 'Python 3 not found.'
        }
        & $python.Source $PyScript `
            --port $Port `
            --pid $OwnedProc.Id `
            --out $Analysis `
            --iso $Iso 2>&1 |
            Tee-Object -FilePath $RunLog -Append
        $code = $LASTEXITCODE
    }

    if ($code -ne 0) {
        throw "stage41b_fix1 tracer exit code $code"
    }

    $Report = Join-Path $Analysis 'stage41b_fix1_report.json'
    if (-not (Test-Path $Report)) {
        throw 'stage41b_fix1_report.json missing'
    }

    $json = Get-Content $Report -Raw -Encoding UTF8 | ConvertFrom-Json
    if (-not $json.completed) {
        throw "stage41b_fix1 report says completed=false"
    }

    $Succeeded = $true
}
catch {
    $_ | Out-String | Set-Content $Failure -Encoding UTF8
    Write-Host "FAILED: $($_.Exception.Message)" -ForegroundColor Red
}
finally {
    if ($OwnedProc) {
        try {
            if (-not $OwnedProc.HasExited) {
                # Stop only the PPSSPP process started by this script.
                Stop-Process -Id $OwnedProc.Id -Force -ErrorAction SilentlyContinue
                Start-Sleep -Milliseconds 300
            }
        }
        catch {}
    }

    Pack-Result $Succeeded
}

if (-not $Succeeded) {
    exit 1
}

Write-Host ''
Write-Host 'STAGE 41B FIX1 SUCCESS' -ForegroundColor Green
exit 0
