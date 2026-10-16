#!/usr/bin/env python3
from pathlib import Path
import argparse,datetime,re
ap=argparse.ArgumentParser()
ap.add_argument("--root",required=True)
ap.add_argument("--phase",required=True,choices=["start","captured","failure"])
ap.add_argument("--detail",default="")
a=ap.parse_args()
root=Path(a.root);log=root/"log";state=root/"PROJECT_STATE.md";step=log/"steps"/"STEP_070_FIX1.md"
step.parent.mkdir(parents=True,exist_ok=True)
now=datetime.datetime.now().astimezone().isoformat(timespec="seconds")
status={"start":"IN_PROGRESS","captured":"BUILT_UNVERIFIED","failure":"FAILED"}[a.phase]
txt=state.read_text(encoding="utf-8",errors="replace") if state.exists() else "# PROJECT STATE\n\nWorking Directory: PROJECT_ROOT\n"
block=f"""<!-- STEP_070_FIX1_MANAGED_BEGIN -->
## STEP_070 FIX1 Live State
Last Updated: {now}
Status: {status}
Goal: Controlled runtime route discovery on BIA_STAGE69_FIX2_NONMDI_INT92_TEST.iso using a dedicated PPSSPP debugger port and exact PID/path verification.
INT92 static build: BUILT_UNVERIFIED
INT92 rows promoted to VERIFIED_APPLIED: NO
Compiled-MDI 967 applied: NO
Movie playback validation resumed: NO
Detail: {a.detail}
<!-- STEP_070_FIX1_MANAGED_END -->"""
pat=re.compile(r"<!-- STEP_070_FIX1_MANAGED_BEGIN -->.*?<!-- STEP_070_FIX1_MANAGED_END -->",re.S)
txt=pat.sub(block,txt) if pat.search(txt) else txt.rstrip()+"\n\n"+block+"\n"
state.write_text(txt,encoding="utf-8")
if a.phase=="start":
    step.write_text("""# STEP 070 FIX1

## Goal
Launch only the Stage69 FIX2 test ISO in a dedicated PPSSPP instance, verify
the debugger PID and ISO path, capture the title/main menu, and sweep main-menu
highlight positions without confirming any option.

Also search PSP RAM for:
- 스커미시 로비
- 게임 팁:
- 늪을 건너

A RAM hit means runtime loading only; it does NOT prove rendering.

## Safety
- ports restricted to 26420..26439
- temporary appendconfig only
- no normal ppsspp.ini modification
- no unrelated PPSSPP process is killed or controlled
- all input goes through the verified WebSocket instance

## Result
IN_PROGRESS
""",encoding="utf-8")
else:
    old=step.read_text(encoding="utf-8",errors="replace") if step.exists() else "# STEP 070\n"
    step.write_text(old.rstrip()+f"""

## Completion Update
Time: {now}
Result: {status}
Detail: {a.detail}

## Verification Boundary
This is route discovery / runtime-load evidence only.
The 92 INT rows remain BUILT_UNVERIFIED until an exact visible canary is
entered and confirmed on-screen.
""",encoding="utf-8")
