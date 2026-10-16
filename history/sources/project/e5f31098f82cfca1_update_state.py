#!/usr/bin/env python3
from pathlib import Path
import argparse,datetime,re
ap=argparse.ArgumentParser()
ap.add_argument("--root",required=True)
ap.add_argument("--phase",required=True,choices=["start","success","failure"])
ap.add_argument("--detail",default="")
a=ap.parse_args()

root=Path(a.root);log=root/"log"
state=root/"PROJECT_STATE.md";step=log/"steps"/"STEP_054.md"
step.parent.mkdir(parents=True,exist_ok=True)
now=datetime.datetime.now().astimezone().isoformat(timespec="seconds")
status={"start":"IN_PROGRESS","success":"VERIFIED","failure":"FAILED"}[a.phase]

txt=state.read_text(encoding="utf-8",errors="replace") if state.exists() else "# PROJECT STATE\n\nWorking Directory: PROJECT_ROOT\n"
block=f"""<!-- STEP_054_MANAGED_BEGIN -->
## STEP_054 Live State
Last Updated: {now}
Status: {status}
Goal: Review/persist all remaining No Better Spot to Die Part 1/2 campaign units (77 total), then export next batch.
ISO modified in this step: NO
Remaining six movie validations resumed: NO
Detail: {a.detail}
<!-- STEP_054_MANAGED_END -->"""
pat=re.compile(r"<!-- STEP_054_MANAGED_BEGIN -->.*?<!-- STEP_054_MANAGED_END -->",re.S)
txt=pat.sub(block,txt) if pat.search(txt) else txt.rstrip()+"\n\n"+block+"\n"
state.write_text(txt,encoding="utf-8")

if a.phase=="start":
    step.write_text("""# STEP 054

## Goal
Translate/review all remaining `No Better Spot to Die` campaign text:
- D7_1400_NOBETTERSPOT current export: 75 rows
- D7_1500_NOBETTERSPOT Part-2-only rows: 2
- union: 77 unique resource IDs

## Starting State
- Campaign total: 1302
- VERIFIED_APPLIED: 137
- TRANSLATED_PENDING_APPLY: 90
- TRANSLATED_REVIEWED: 465
- NEEDS_TRANSLATION: 610
- ISO modification: none
- Remaining six movie playback validations: deferred

## Result
IN_PROGRESS
""",encoding="utf-8")
else:
    old=step.read_text(encoding="utf-8",errors="replace") if step.exists() else "# STEP 054\n"
    step.write_text(old.rstrip()+f"""

## Completion Update
Time: {now}
Result: {status}
Detail: {a.detail}

## Verification
Translation metadata only. No Better Spot to Die Parts 1/2 are not claimed as ISO-applied or runtime-verified.

## Next Step
Translate the automatically exported next campaign batch, expected D07_1500_BLOODYGULCH.
""",encoding="utf-8")
