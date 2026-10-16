[CmdletBinding()]
param()
$ErrorActionPreference='Stop';Set-StrictMode -Version 2.0
$root='PROJECT_ROOT';$log=Join-Path $root 'log';$runid=(Get-Date -Format 'yyyyMMdd_HHmmss_fff')+'_'+$PID
$dir=Join-Path (Join-Path $log 'STEP_095_FIX3') $runid
$good=Join-Path $log ('bia_STEP_095_FIX3_start_exit_capture_'+$runid+'.zip')
$bad=Join-Path $log ('fall_bia_STEP_095_FIX3_start_exit_capture_'+$runid+'.zip')
$child=$null;$childCode=$null;$ppid=0;$ppCreation='';$started=Get-Date;$zipDone=$false;$errorMessage='';$phase='init';$success=$false
function SaveJson($x,[string]$path){$x|ConvertTo-Json -Depth 8|Set-Content -LiteralPath $path -Encoding UTF8}
function ZipReadable([string]$path){
    if(!(Test-Path -LiteralPath $path -PathType Leaf)){return $false}
    try{
        Add-Type -AssemblyName System.IO.Compression.FileSystem -ErrorAction SilentlyContinue
        $zip=[System.IO.Compression.ZipFile]::OpenRead($path)
        try{
            $files=0
            foreach($item in $zip.Entries){
                if($item.FullName.EndsWith('/')){continue}
                $stream=$item.Open();try{$bytes=New-Object byte[] 65536;while($stream.Read($bytes,0,$bytes.Length) -gt 0){} }finally{$stream.Dispose()}
                $files++
            }
            return ($files -ge 4)
        }finally{$zip.Dispose()}
    }catch{return $false}
}
try{
    New-Item -ItemType Directory -Force -Path $dir,(Join-Path $dir 'outputs') | Out-Null
    SaveJson ([ordered]@{step='STEP_095_FIX3';runid=$runid;started=(Get-Date).ToString('o');supervisor_pid=$PID;capture='screenshot file event, not key hook';no_ppsspp_auto_kill=$true}) (Join-Path $dir 'SUPERVISOR_STARTED.json')
    $run=Join-Path $PSScriptRoot 'RUN.ps1';if(!(Test-Path $run)){throw 'RUN.ps1 missing'}
    $args=@('-NoProfile','-ExecutionPolicy','Bypass','-File',('"'+$run+'"'),'-RunDir',('"'+$dir+'"'),'-RunId',$runid)
    $child=Start-Process -FilePath 'powershell.exe' -ArgumentList $args -PassThru -RedirectStandardOutput (Join-Path $dir 'child_stdout.txt') -RedirectStandardError (Join-Path $dir 'child_stderr.txt')
    Write-Host "STEP095 FIX3 supervisor active, child PID=$($child.Id)." -ForegroundColor Cyan
    Write-Host 'In NEW PPSSPP: press START; at broken mission2 text press screenshot key 1.' -ForegroundColor Yellow
    Write-Host 'This version captures PPSSPP exit state even if child PowerShell disappears.' -ForegroundColor Yellow
    $phase='';$lastPidCheck=$null;$heartbeatLast=$null
    $end=(Get-Date).AddMinutes(18)
    while((Get-Date) -lt $end){
        $child.Refresh()
        if($child.HasExited){$childCode=$child.ExitCode;break}
        $hb=Join-Path $dir 'HEARTBEAT.json'
        if(Test-Path $hb){
            try{$doc=Get-Content -LiteralPath $hb -Raw|ConvertFrom-Json; if($doc.phase -ne $phase){$phase=$doc.phase;Write-Host "[STEP095 FIX3] $phase" -ForegroundColor Cyan}}catch{}
        }
        $own=Join-Path $dir 'outputs\owned_session.json'
        if($ppid -eq 0 -and (Test-Path -LiteralPath $own)){
            try{$sess=Get-Content -LiteralPath $own -Raw|ConvertFrom-Json;$ppid=[int]$sess.pid;$ppCreation=[string]$sess.created
                SaveJson ([ordered]@{time=(Get-Date).ToString('o');pid=$ppid;port=$sess.port;creation=$ppCreation;source=$sess.exe}) (Join-Path $dir 'SUPERVISOR_PPSSPP_IDENTIFIED.json')
                Write-Host "Owned PPSSPP PID=$ppid, WS PORT=$($sess.port)." -ForegroundColor Green
            }catch{}
        }
        if($ppid -gt 0){
            $alive=$false;$exitCode=$null
            try{$active=Get-Process -Id $ppid -ErrorAction SilentlyContinue;$alive=($null -ne $active)}catch{}
            $logline="$(Get-Date -Format o),$ppid,$alive,$phase`r`n"
            [System.IO.File]::AppendAllText((Join-Path $dir 'SUPERVISOR_PROCESS_LIFETIME.csv'),$logline)
            if(!$alive){
                SaveJson ([ordered]@{time=(Get-Date).ToString('o');pid=$ppid;alive=$false;phase=$phase;note='Observed process disappearance; exit code may be in child process report.'}) (Join-Path $dir 'SUPERVISOR_PROCESS_DISAPPEARED.json')
                Write-Host "PPSSPP PID=$ppid has exited. Capturing logs; never force-killing other PPSSPP processes." -ForegroundColor Red
                break
            }
        }
        Start-Sleep -Seconds 1
    }
    if($child -and !$child.HasExited){
        # Allow child to save its failure after PPSSPP exited. No touching PPSSPP process.
        if($ppid -gt 0 -and (Test-Path (Join-Path $dir 'SUPERVISOR_PROCESS_DISAPPEARED.json'))){
            [void]$child.WaitForExit(12000)
        }
        $child.Refresh()
        if($child.HasExited){$childCode=$child.ExitCode}
        else{ $childCode=$null;$errorMessage='Child still running when supervisor stopped; child left intact.' }
    }
} catch { $errorMessage=($_|Out-String);Write-Host "Supervisor issue: $errorMessage" -ForegroundColor Red }
finally{
    New-Item -ItemType Directory -Force -Path $dir,(Join-Path $dir 'outputs')|Out-Null
    $ppAlive=$null
    if($ppid -gt 0){try{$ppAlive=[bool](Get-Process -Id $ppid -ErrorAction SilentlyContinue)}catch{$ppAlive=$false}}
    $runDone=Join-Path $dir 'RUN_DONE.json';$done=$false
    if(Test-Path $runDone){try{$obj=Get-Content -LiteralPath $runDone -Raw|ConvertFrom-Json;$done=($obj.complete -eq $true)}catch{}}
    $img=@(Get-ChildItem -LiteralPath (Join-Path $dir 'outputs') -File -ErrorAction SilentlyContinue|Where-Object{$_.Name -match '^mission2_at_key1\.(jpg|jpeg|png)$'})
    $success=($done -and $img.Count -eq 1 -and $childCode -eq 0 -and !$errorMessage)
    SaveJson ([ordered]@{time=(Get-Date).ToString('o');success=$success;child_pid=$(if($child){$child.Id}else{$null});child_exit_code=$childCode;ppsspp_pid=$ppid;ppsspp_still_running=$ppAlive;phase_at_last_poll=$phase;child_done_marker=$done;screenshot_count=$img.Count;supervisor_error=$errorMessage;note='Child exit code 0 alone never indicates success';ppsspp_was_not_killed_by_launcher=$true}) (Join-Path $dir 'SUPERVISOR_RESULT.json')
    # Append-only project history. Do not replace or truncate any existing state content.
    $statePath=Join-Path $root 'PROJECT_STATE.md'
    $stateEntry="`r`n### STEP 095 FIX3 — $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz')`r`n- Run ID: $runid`r`n- Result: $(if($success){'CAPTURE_COLLECTED, runtime QA pending'}else{'FAILED/INCOMPLETE'})`r`n- Child exit: $childCode; PPSSPP PID: $ppid; alive at finish: $ppAlive`r`n- Screenshot files: $($img.Count); original ISO and saves untouched; no breakpoints or RAM writes`r`n- ZIP: $(if($success){$good}else{$bad})`r`n- Korean rendering fix: NOT APPLIED`r`n"
    Set-Content -LiteralPath (Join-Path $dir 'PROJECT_STATE_APPEND.md') -Value $stateEntry -Encoding UTF8
    try{
        if(Test-Path -LiteralPath $statePath -PathType Leaf){
            $match=Select-String -LiteralPath $statePath -SimpleMatch -Pattern $runid -Quiet -ErrorAction Stop
            if(!$match){Add-Content -LiteralPath $statePath -Value $stateEntry -Encoding UTF8}
        }else{Set-Content -LiteralPath (Join-Path $dir 'PROJECT_STATE_NOT_FOUND.txt') -Value "Existing PROJECT_STATE.md not found at $statePath; no replacement created." -Encoding UTF8}
    }catch{Set-Content -LiteralPath (Join-Path $dir 'PROJECT_STATE_APPEND_ERROR.txt') -Value ($_|Out-String) -Encoding UTF8}
    # Best-effort Windows crash evidence in narrow time window. Do not require admin.
    try{
        $events=@(Get-WinEvent -FilterHashtable @{LogName='Application';StartTime=$started.AddSeconds(-15);Id=1000,1001,1002} -ErrorAction Stop | Select-Object -First 20)
        $selected=@($events|Where-Object{$_.Message -match 'PPSSPP|PPSSPPWindows64.exe' -or $_.ProviderName -match 'Application Error|Windows Error Reporting'}|Select-Object -First 10|ForEach-Object{@{at=$_.TimeCreated.ToString('o');id=$_.Id;provider=$_.ProviderName;message=$_.Message.Substring(0,[Math]::Min(4000,$_.Message.Length))}})
        SaveJson $selected (Join-Path $dir 'WINDOWS_APPLICATION_EVENTS.json')
    }catch{Set-Content -LiteralPath (Join-Path $dir 'WINDOWS_EVENTS_UNAVAILABLE.txt') -Value "Event log read unavailable: $_" -Encoding UTF8}
    # Never copy saves, full RAM, ISO or unrelated user data into upload ZIP.
    $stage=Join-Path $dir 'zip_stage';$target=if($success){$good}else{$bad}
    try{
        New-Item -ItemType Directory -Force -Path $stage,(Join-Path $stage 'outputs'),(Join-Path $stage 'scripts_used')|Out-Null
        $top=@('SUPERVISOR_STARTED.json','SUPERVISOR_PPSSPP_IDENTIFIED.json','SUPERVISOR_PROCESS_LIFETIME.csv','SUPERVISOR_PROCESS_DISAPPEARED.json','SUPERVISOR_RESULT.json','WINDOWS_APPLICATION_EVENTS.json','WINDOWS_EVENTS_UNAVAILABLE.txt','PROJECT_STATE_APPEND.md','PROJECT_STATE_NOT_FOUND.txt','PROJECT_STATE_APPEND_ERROR.txt','RUN_DONE.json','RUN_ERROR.json','HEARTBEAT.json','child_stdout.txt','child_stderr.txt','ppsspp_append.ini')
        foreach($name in $top){$p=Join-Path $dir $name;if(Test-Path -LiteralPath $p -PathType Leaf){Copy-Item -LiteralPath $p -Destination (Join-Path $stage $name) -Force}}
        $out=Join-Path $dir 'outputs'
        foreach($f in @(Get-ChildItem -LiteralPath $out -File -ErrorAction SilentlyContinue)){
            if($f.Length -le 8388608){Copy-Item -LiteralPath $f.FullName -Destination (Join-Path $stage 'outputs') -Force}
        }
        foreach($name in @('RUN.ps1','LAUNCH.ps1','small_snapshot.py','ws_readonly.py','README.md','FINDINGS_STEP095_FIX2.md')){
            $p=Join-Path $PSScriptRoot $name;if(Test-Path -LiteralPath $p -PathType Leaf){Copy-Item -LiteralPath $p -Destination (Join-Path $stage 'scripts_used') -Force}
        }
        if(!$success){Set-Content -LiteralPath (Join-Path $stage 'FAILURE.txt') -Value "STEP095 FIX3 FAILED`r`nChild exit code: $childCode`r`nScreenshot: $($img.Count)`r`nPPSSPP still running: $ppAlive`r`nCheck SUPERVISOR_RESULT.json, child_stdout.txt, child_stderr.txt and Windows events." -Encoding UTF8}
        Compress-Archive -Path (Join-Path $stage '*') -DestinationPath $target -CompressionLevel Optimal -Force
        if(!(ZipReadable $target)){throw "ZIP failed readability verification: $target"}
        $zipDone=$true
        Remove-Item -LiteralPath $stage -Force -Recurse
        Write-Host "UPLOAD RESULT ZIP: $target" -ForegroundColor $(if($success){'Green'}else{'Yellow'})
    }catch{
        Write-Host "ZIP creation or verification failed: $_" -ForegroundColor Red
        try{
            $alternate=Join-Path (Join-Path $env:USERPROFILE 'Downloads') ('fall_bia_STEP_095_FIX3_RECOVERY_'+$runid+'.zip')
            Compress-Archive -Path (Join-Path $stage '*') -DestinationPath $alternate -Force
            if(ZipReadable $alternate){Write-Host "UPLOAD RECOVERY ZIP: $alternate" -ForegroundColor Yellow;$zipDone=$true}
        }catch{Write-Host "Preserved evidence folder: $dir" -ForegroundColor Red}
    }
}
if($success -and $zipDone){exit 0}else{exit 1}
