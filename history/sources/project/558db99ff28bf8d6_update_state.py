#!/usr/bin/env python3
from pathlib import Path
import argparse,datetime,re
ap=argparse.ArgumentParser()
ap.add_argument("--root",required=True)
ap.add_argument("--phase",required=True,choices=["start","captured","failure"])
ap.add_argument("--detail",default="")
a=ap.parse_args()
root=Path(a.root);state=root/"PROJECT_STATE.md";step=root/"log"/"steps"/"STEP_070_FIX5.md"
step.parent.mkdir(parents=True,exist_ok=True)
now=datetime.datetime.now().astimezone().isoformat(timespec="seconds")
status={"start":"IN_PROGRESS","captured":"BUILT_UNVERIFIED","failure":"FAILED"}[a.phase]
txt=state.read_text(encoding="utf-8",errors="replace") if state.exists() else "# PROJECT STATE\n\nWorking Directory: PROJECT_ROOT\n"
block=f"""<!-- STEP_070_FIX5_MANAGED_BEGIN -->
## STEP_070 FIX5 Live State
Last Updated: {now}
Status: {status}
Goal: Runtime route discovery using the user's exact PPSSPP executable path; verify debugger TCP listener owner PID and launched process command line before any WebSocket input.
INT92 static build: BUILT_UNVERIFIED
INT92 promoted to VERIFIED_APPLIED: NO
Compiled-MDI 967 applied: NO
Movie playback validation resumed: NO
Detail: {a.detail}
<!-- STEP_070_FIX5_MANAGED_END -->"""
pat=re.compile(r"<!-- STEP_070_FIX5_MANAGED_BEGIN -->.*?<!-- STEP_070_FIX5_MANAGED_END -->",re.S)
txt=pat.sub(block,txt) if pat.search(txt) else txt.rstrip()+"\n\n"+block+"\n"
state.write_text(txt,encoding="utf-8")
if a.phase=="start":
    step.write_text("""# STEP 070 FIX3

## Goal
Use the exact user-supplied PPSSPP executable path. No discovery scan.

Before WebSocket control:
- launch a dedicated PPSSPP on a free 26420..26439 port
- verify that exact PID owns the listener
- verify launched process command line contains the exact Stage69 FIX2 ISO
- only then allow WebSocket input/capture

## Result
IN_PROGRESS
""",encoding="utf-8")
else:
    old=step.read_text(encoding="utf-8",errors="replace") if step.exists() else "# STEP 070 FIX3\n"
    step.write_text(old.rstrip()+f"""

## Completion Update
Time: {now}
Result: {status}
Detail: {a.detail}

## Boundary
Route discovery only. INT92 remains BUILT_UNVERIFIED until a visible runtime canary is confirmed.
""",encoding="utf-8")
