$ErrorActionPreference="Stop"
Copy-Item -LiteralPath "PROJECT_ROOT\backup\stage04\ON_MEMU_O.MDI" -Destination "PROJECT_ROOT\extracted\PSP_GAME\USRDIR\SYSTEM\ON_MEMU_O.MDI" -Force
Write-Host "Stage 04 extracted MDI restored."
