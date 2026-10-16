param(
    [Parameter(Mandatory=$true)][string]$OutputDir
)
$ErrorActionPreference="Stop"
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

$candidates = New-Object System.Collections.Generic.List[object]

function Add-Candidate([string]$Path,[string]$Source) {
    if([string]::IsNullOrWhiteSpace($Path)){ return }
    try {
        $rp=(Resolve-Path -LiteralPath $Path -ErrorAction Stop).Path
        if(-not (Test-Path -LiteralPath $rp -PathType Leaf)){ return }
        $name=[IO.Path]::GetFileName($rp)
        if($name -notmatch '^PPSSPP.*\.exe$'){ return }
        $exists=$candidates | Where-Object { $_.Path -ieq $rp }
        if($exists){ return }

        $item=Get-Item -LiteralPath $rp
        $vi=$item.VersionInfo
        $verText=$vi.FileVersion
        if([string]::IsNullOrWhiteSpace($verText)){ $verText=$vi.ProductVersion }
        $vobj=$null
        try {
            $clean=($verText -replace '[^0-9\.].*$','').Trim('.')
            if($clean){ $vobj=[version]$clean }
        } catch {}

        $archScore=0
        if($name -ieq 'PPSSPPWindows64.exe'){ $archScore=3 }
        elseif($name -match '64'){ $archScore=2 }
        else { $archScore=1 }

        $candidates.Add([pscustomobject]@{
            Path=$rp
            Source=$Source
            FileName=$name
            FileVersion=$verText
            ParsedVersion=if($vobj){$vobj.ToString()}else{""}
            ArchScore=$archScore
            LastWriteTime=$item.LastWriteTime.ToString("o")
            Length=$item.Length
        }) | Out-Null
    } catch {}
}

# 1) Explicit override.
if($env:PPSSPP_EXE){
    Add-Candidate $env:PPSSPP_EXE "ENV:PPSSPP_EXE"
}

# 2) Existing PPSSPP processes: read executable path only.
Get-Process -ErrorAction SilentlyContinue |
    Where-Object { $_.ProcessName -match '^PPSSPP' } |
    ForEach-Object {
        try { Add-Candidate $_.MainModule.FileName ("RUNNING_PROCESS_PID_"+$_.Id) } catch {}
    }

# 3) Known direct locations.
$direct=@(
    "PROJECT_ROOT\PPSSPPWindows64.exe",
    "PROJECT_ROOT\PPSSPPWindows.exe",
    "PROJECT_ROOT\PPSSPPWindows64.exe",
    "PROJECT_ROOT\PPSSPPWindows.exe",
    "PROJECT_ROOT\ppsspp\PPSSPPWindows64.exe",
    "PROJECT_ROOT\ppsspp\PPSSPPWindows.exe",
    "LOCAL_PATH",
    "LOCAL_PATH",
    "$env:USERPROFILE\Downloads\PPSSPPWindows64.exe",
    "$env:USERPROFILE\Downloads\PPSSPPWindows.exe",
    "$env:USERPROFILE\Documents\PPSSPPWindows64.exe",
    "$env:USERPROFILE\Documents\PPSSPPWindows.exe",
    "$env:USERPROFILE\Desktop\PPSSPPWindows64.exe",
    "$env:USERPROFILE\Desktop\PPSSPPWindows.exe"
)
foreach($p in $direct){ Add-Candidate $p "KNOWN_DIRECT" }

# 4) Parse prior Naruto/bia scripts for explicit PPSSPP exe strings.
$scriptRoots=@(
    "PROJECT_ROOT",
    "PROJECT_ROOT"
)
$scriptRefs=New-Object System.Collections.Generic.List[object]
foreach($root in $scriptRoots){
    if(-not (Test-Path -LiteralPath $root)){ continue }
    Get-ChildItem -LiteralPath $root -File -Recurse -ErrorAction SilentlyContinue |
        Where-Object { $_.Extension -in @(".bat",".cmd",".ps1",".py",".txt",".md") -and $_.Length -lt 5MB } |
        ForEach-Object {
            try {
                $txt=Get-Content -LiteralPath $_.FullName -Raw -ErrorAction Stop
                if($txt -match 'PPSSPP(?:Windows64|Windows)?\.exe'){
                    $scriptRefs.Add([pscustomobject]@{
                        Script=$_.FullName
                        Match=($Matches[0])
                    }) | Out-Null

                    # Resolve quoted absolute Windows exe paths.
                    $m=[regex]::Matches($txt,'(?i)([A-Z]:\\[^"`''\r\n]*?PPSSPP(?:Windows64|Windows)?\.exe)')
                    foreach($x in $m){
                        Add-Candidate $x.Groups[1].Value ("SCRIPT_REF:"+$_.FullName)
                    }
                }
            } catch {}
        }
}
$scriptRefs | Export-Csv -LiteralPath (Join-Path $OutputDir "ppsspp_script_references.csv") -NoTypeInformation -Encoding UTF8

# 5) Targeted recursive filesystem search. Avoid a full LOCAL_PATH scan.
$roots=@(
    "PROJECT_ROOT",
    "PROJECT_ROOT",
    "$env:USERPROFILE\Downloads",
    "$env:USERPROFILE\Documents",
    "$env:USERPROFILE\Desktop",
    "$env:LOCALAPPDATA",
    "$env:ProgramFiles"
)
if(${env:ProgramFiles(x86)}){ $roots += ${env:ProgramFiles(x86)} }

foreach($root in $roots | Select-Object -Unique){
    if([string]::IsNullOrWhiteSpace($root) -or -not (Test-Path -LiteralPath $root)){ continue }
    foreach($pattern in @("PPSSPPWindows64.exe","PPSSPPWindows.exe")){
        Get-ChildItem -LiteralPath $root -Filter $pattern -File -Recurse -ErrorAction SilentlyContinue |
            ForEach-Object { Add-Candidate $_.FullName ("RECURSIVE:"+$root) }
    }
}

# 6) Registry uninstall records can expose InstallLocation.
$regRoots=@(
    "HKCLOCAL_PATH",
    "HKLLOCAL_PATH",
    "HKLLOCAL_PATH"
)
foreach($rr in $regRoots){
    try {
        Get-ItemProperty $rr -ErrorAction SilentlyContinue |
            Where-Object { $_.DisplayName -match 'PPSSPP' } |
            ForEach-Object {
                $loc=$_.InstallLocation
                if($loc){
                    Add-Candidate (Join-Path $loc "PPSSPPWindows64.exe") "REGISTRY_INSTALL"
                    Add-Candidate (Join-Path $loc "PPSSPPWindows.exe") "REGISTRY_INSTALL"
                }
            }
    } catch {}
}

$candidates |
    Sort-Object Path |
    Export-Csv -LiteralPath (Join-Path $OutputDir "ppsspp_candidates.csv") -NoTypeInformation -Encoding UTF8

if($candidates.Count -eq 0){
    throw "No PPSSPP executable candidate found after expanded search."
}

# Prefer 64-bit, then numeric version, then most recently modified.
$ranked=$candidates | Sort-Object `
    @{Expression={$_.ArchScore};Descending=$true}, `
    @{Expression={ try {[version]$_.ParsedVersion} catch {[version]"0.0"} };Descending=$true}, `
    @{Expression={[datetime]$_.LastWriteTime};Descending=$true}

$selected=$ranked | Select-Object -First 1
$selected | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $OutputDir "ppsspp_selected.json") -Encoding UTF8
$selected.Path
