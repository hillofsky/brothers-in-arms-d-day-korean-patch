#!/usr/bin/env python3
from pathlib import Path
import argparse,datetime,re
ap=argparse.ArgumentParser()
ap.add_argument("--root",required=True)
ap.add_argument("--phase",required=True,choices=["start","success","failure"])
ap.add_argument("--detail",default="")
a=ap.parse_args()
root=Path(a.root); log=root/"log"; state=root/"PROJECT_STATE.md"; step=log/"steps"/"STEP_063.md"
step.parent.mkdir(parents=True,exist_ok=True)
now=datetime.datetime.now().astimezone().isoformat(timespec="seconds")
status={"start":"IN_PROGRESS","success":"VERIFIED","failure":"FAILED"}[a.phase]
txt=state.read_text(encoding="utf-8",errors="replace") if state.exists() else "# PROJECT STATE\n\nWorking Directory: PROJECT_ROOT\n"
block=f"""<!-- STEP_063_MANAGED_BEGIN -->
## STEP_063 Live State
Last Updated: {now}
Status: {status}
Goal: Preflight the exact existing campaign MDI/DSL/DSX application pipeline for 1165 translated-but-unapplied campaign units.
Campaign translation corpus complete: YES
ISO modified in this step: NO
Remaining six movie validations resumed: NO
Detail: {a.detail}
<!-- STEP_063_MANAGED_END -->"""
pat=re.compile(r"<!-- STEP_063_MANAGED_BEGIN -->.*?<!-- STEP_063_MANAGED_END -->",re.S)
txt=pat.sub(block,txt) if pat.search(txt) else txt.rstrip()+"\n\n"+block+"\n"
state.write_text(txt,encoding="utf-8")
if a.phase=="start":
    step.write_text("""# STEP 063

## Goal
Recover and audit the exact existing campaign application pipeline before
mass-applying the 1165 translated-but-unapplied campaign units.

## Starting State
- Campaign total: 1302
- VERIFIED_APPLIED: 137
- TRANSLATED_PENDING_APPLY: 90
- TRANSLATED_REVIEWED: 1075
- NEEDS_TRANSLATION: 0
- ISO modification: none
- Remaining six movie playback validations: deferred

## Result
IN_PROGRESS
""",encoding="utf-8")
else:
    old=step.read_text(encoding="utf-8",errors="replace") if step.exists() else "# STEP 063\n"
    step.write_text(old.rstrip()+f"""

## Completion Update
Time: {now}
Result: {status}
Detail: {a.detail}

## Verification
Discovery/preflight only. No ISO or resource mutation is claimed.

## Next Step
Use collected Stage38/work/helper evidence to build the exact bulk campaign
apply manifest and patcher.
""",encoding="utf-8")
