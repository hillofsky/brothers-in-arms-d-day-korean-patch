#!/usr/bin/env python3
from pathlib import Path
import argparse,datetime,re
ap=argparse.ArgumentParser()
ap.add_argument("--root",required=True)
ap.add_argument("--phase",required=True,choices=["start","captured","failure"])
ap.add_argument("--detail",default="")
a=ap.parse_args()
root=Path(a.root);state=root/"PROJECT_STATE.md";step=root/"log"/"steps"/"STEP_071.md"
step.parent.mkdir(parents=True,exist_ok=True)
now=datetime.datetime.now().astimezone().isoformat(timespec="seconds")
status={"start":"IN_PROGRESS","captured":"BUILT_UNVERIFIED","failure":"FAILED"}[a.phase]
txt=state.read_text(encoding="utf-8",errors="replace") if state.exists() else "# PROJECT STATE\n\nWorking Directory: PROJECT_ROOT\n"
block=f"""<!-- STEP_071_MANAGED_BEGIN -->
## STEP_071 Live State
Last Updated: {now}
Status: {status}
Goal: Enter the verified Skirmish item once, compare all 92 INT targets in full PSP RAM before/after, and capture post-entry raw VRAM frames.
INT92 promoted to VERIFIED_APPLIED: NO
Compiled-MDI 967 applied: NO
Movie playback validation resumed: NO
Detail: {a.detail}
<!-- STEP_071_MANAGED_END -->"""
pat=re.compile(r"<!-- STEP_071_MANAGED_BEGIN -->.*?<!-- STEP_071_MANAGED_END -->",re.S)
txt=pat.sub(block,txt) if pat.search(txt) else txt.rstrip()+"\n\n"+block+"\n"
state.write_text(txt,encoding="utf-8")
if a.phase=="start":
    step.write_text("""# STEP 071

## Goal
Final INT92 runtime canary.

- deterministically reach title
- wait for verified Story-selected main menu
- one DOWN -> verify Skirmish signature
- one CROSS only
- no further navigation
- capture 10 post-entry raw-VRAM samples
- full 32MiB RAM search of all 92 INT translations before and after entry

## Status
IN_PROGRESS
""",encoding="utf-8")
else:
    old=step.read_text(encoding="utf-8",errors="replace") if step.exists() else "# STEP 071\n"
    step.write_text(old.rstrip()+f"""

## Completion Update
Time: {now}
Result: {status}
Detail: {a.detail}

## Boundary
Do not promote all 92 rows merely from static build or RAM presence. Visible
runtime evidence and source-path evidence remain distinct.
""",encoding="utf-8")
