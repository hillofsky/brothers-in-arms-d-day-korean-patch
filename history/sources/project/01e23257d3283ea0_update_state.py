#!/usr/bin/env python3
from pathlib import Path
import argparse,datetime,re
ap=argparse.ArgumentParser()
ap.add_argument("--root",required=True)
ap.add_argument("--phase",required=True,choices=["start","captured","failure"])
ap.add_argument("--detail",default="")
a=ap.parse_args()
root=Path(a.root);state=root/"PROJECT_STATE.md";step=root/"log"/"steps"/"STEP_070_FIX7.md"
step.parent.mkdir(parents=True,exist_ok=True)
now=datetime.datetime.now().astimezone().isoformat(timespec="seconds")
status={"start":"IN_PROGRESS","captured":"BUILT_UNVERIFIED","failure":"FAILED"}[a.phase]
txt=state.read_text(encoding="utf-8",errors="replace") if state.exists() else "# PROJECT STATE\n\nWorking Directory: PROJECT_ROOT\n"
block=f"""<!-- STEP_070_FIX7_MANAGED_BEGIN -->
## STEP_070 FIX7 Live State
Last Updated: {now}
Status: {status}
Goal: Use the proven raw-VRAM path plus FIX6 title-frame signature to reach the title deterministically, enter the main menu, and capture selection positions without confirming an item.
INT92 static build: BUILT_UNVERIFIED
INT92 promoted to VERIFIED_APPLIED: NO
Compiled-MDI 967 applied: NO
Movie playback validation resumed: NO
Detail: {a.detail}
<!-- STEP_070_FIX7_MANAGED_END -->"""
pat=re.compile(r"<!-- STEP_070_FIX7_MANAGED_BEGIN -->.*?<!-- STEP_070_FIX7_MANAGED_END -->",re.S)
txt=pat.sub(block,txt) if pat.search(txt) else txt.rstrip()+"\n\n"+block+"\n"
state.write_text(txt,encoding="utf-8")
if a.phase=="start":
    step.write_text("""# STEP 070 FIX7

## Goal
Reuse FIX6 raw-VRAM capture, but stop blindly sending navigation during logos.

- detect the exact stable title frame using the successful FIX6 reference
- press START only after title detection
- capture the main menu
- perform DOWN 0..6 capture sweep without CROSS confirmation
- replace unsupported `memory.search` with local search over the full 32MiB RAM

## Result
IN_PROGRESS
""",encoding="utf-8")
else:
    old=step.read_text(encoding="utf-8",errors="replace") if step.exists() else "# STEP 070 FIX7\n"
    step.write_text(old.rstrip()+f"""

## Completion Update
Time: {now}
Result: {status}
Detail: {a.detail}

## Boundary
Main-menu route discovery only. INT92 remains BUILT_UNVERIFIED.
""",encoding="utf-8")
