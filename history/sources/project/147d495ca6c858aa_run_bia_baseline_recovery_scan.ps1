$ErrorActionPreference="Stop"

$Root="PROJECT_ROOT"
$Out=Join-Path $Root "analysis\baseline_recovery_scan"
$LogDir=Join-Path $Root "log"
$ZipOut=Join-Path $LogDir "bia_baseline_recovery_scan_upload.zip"

if(Test-Path $Out){Remove-Item $Out -Recurse -Force}
New-Item -ItemType Directory -Path $Out -Force | Out-Null
if(-not (Test-Path $LogDir)){New-Item -ItemType Directory -Path $LogDir -Force | Out-Null}

$Inv=Join-Path $Out "inventory.tsv"
$Summary=Join-Path $Out "summary.txt"
$Candidates=Join-Path $Out "candidate_tools.txt"

"kind`tname`tfull_path`tsize_bytes`tlast_write" | Set-Content $Inv -Encoding UTF8

function Add-Inv($kind,$f){
    "$kind`t$($f.Name)`t$($f.FullName)`t$($f.Length)`t$($f.LastWriteTime.ToString('s'))" |
        Add-Content $Inv -Encoding UTF8
}

$SearchRoots=@(
    "PROJECT_ROOT",
    "LOCAL_PATH",
    "LOCAL_PATH",
    "LOCAL_PATH"
)

$patterns=@(
    "*STAGE39*.iso",
    "*stage39*.iso",
    "*BIA*.iso",
    "*stage39*.zip",
    "*stage39*.py",
    "*stage39*.ps1",
    "*stage39*.tsv",
    "*stage39*.json",
    "*stage39*.bin",
    "*stage39*.mdi",
    "*ON_MEMU*.MDI",
    "*BIAON.PRX",
    "*BOOT.BIN"
)

$seen=@{}

foreach($r in $SearchRoots){
    if(-not (Test-Path $r)){continue}

    foreach($pat in $patterns){
        Get-ChildItem $r -Recurse -File -Filter $pat -ErrorAction SilentlyContinue | ForEach-Object {
            $k=$_.FullName.ToLowerInvariant()
            if($seen.ContainsKey($k)){return}
            $seen[$k]=$true

            $kind="other"
            if($_.Extension -ieq ".iso"){$kind="iso"}
            elseif($_.Extension -ieq ".zip"){$kind="zip"}
            elseif($_.Name -ieq "BIAON.PRX"){$kind="prx"}
            elseif($_.Name -ieq "BOOT.BIN"){$kind="boot"}
            elseif($_.Extension -ieq ".py"){$kind="python"}
            elseif($_.Extension -ieq ".ps1"){$kind="powershell"}
            elseif($_.Extension -ieq ".tsv"){$kind="tsv"}
            elseif($_.Extension -ieq ".json"){$kind="json"}
            elseif($_.Extension -ieq ".bin"){$kind="bin"}
            elseif($_.Extension -ieq ".mdi"){$kind="mdi"}

            Add-Inv $kind $_
        }
    }
}

# Find tool directories even when filenames don't match.
$toolDirs=Get-ChildItem $Root -Directory -ErrorAction SilentlyContinue |
    Where-Object {
        $_.Name -match 'stage39|stage40|bia_stage39|baseline|recover'
    } |
    Sort-Object Name

"Candidate directories:" | Set-Content $Candidates -Encoding UTF8
$toolDirs | ForEach-Object {
    $_.FullName | Add-Content $Candidates -Encoding UTF8
    Get-ChildItem $_.FullName -File -ErrorAction SilentlyContinue |
        Sort-Object Length -Descending |
        Select-Object -First 30 |
        ForEach-Object {
            ("    {0,12}  {1}" -f $_.Length,$_.Name) |
                Add-Content $Candidates -Encoding UTF8
        }
}

# Search scripts/text for literal baseline filenames and useful generator markers.
$Needles=@(
    "BIA_STAGE39F_CORRECT_NARROW_METADATA_TEST.iso",
    "BIA_STAGE39U_BOOT_RENDER_UTF8_TEST.iso",
    "BIA_STAGE39T_BOOT_RENDER_UTF8_TEST.iso",
    "stage39f",
    "stage39u",
    "stage39t",
    "0x093B1B40",
    "0x098F5020",
    "b58e6ef06af9555a23d8be1f70a0e8d65b2ce4c6"
)

$TextHits=Join-Path $Out "text_hits.txt"
"" | Set-Content $TextHits -Encoding UTF8

Get-ChildItem $Root -Recurse -File -ErrorAction SilentlyContinue |
    Where-Object {
        $_.Length -lt 20MB -and
        $_.Extension -in @(".py",".ps1",".txt",".md",".json",".tsv",".log")
    } |
    ForEach-Object {
        $p=$_.FullName
        try{
            $content=Get-Content $p -Raw -ErrorAction Stop
            foreach($n in $Needles){
                if($content -match [regex]::Escape($n)){
                    "$n`t$p" | Add-Content $TextHits -Encoding UTF8
                }
            }
        } catch {}
    }

$drive=Get-PSDrive -Name D
$isoCount=(Import-Csv $Inv -Delimiter "`t" | Where-Object {$_.kind -eq "iso"}).Count
$zipCount=(Import-Csv $Inv -Delimiter "`t" | Where-Object {$_.kind -eq "zip"}).Count

@"
BIA baseline recovery scan
==========================

Free D: $([math]::Round($drive.Free/1GB,2)) GiB
ISO candidates: $isoCount
ZIP candidates: $zipCount

IMPORTANT:
- This script deletes NOTHING.
- It only inventories files and generator artifacts.
- Stage39U/39F were already absent before the previous cleanup stopped.
- Do not delete more files until this scan is reviewed.

Upload:
$ZipOut
"@ | Set-Content $Summary -Encoding UTF8

if(Test-Path $ZipOut){Remove-Item $ZipOut -Force}
Compress-Archive -Path "$Out\*" -DestinationPath $ZipOut -Force

Write-Host ""
Write-Host "Recovery scan complete."
Write-Host "Upload:"
Write-Host $ZipOut
