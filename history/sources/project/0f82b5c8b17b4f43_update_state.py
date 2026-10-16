#!/usr/bin/env python3
from pathlib import Path
import argparse,datetime,re
ap=argparse.ArgumentParser()
ap.add_argument("--root",required=True)
ap.add_argument("--phase",required=True,choices=["start","success","failure"])
ap.add_argument("--detail",default="")
a=ap.parse_args()
root=Path(a.root);log=root/"log"
state=root/"PROJECT_STATE.md";step=log/"steps"/"STEP_060.md"
step.parent.mkdir(parents=True,exist_ok=True)
now=datetime.datetime.now().astimezone().isoformat(timespec="seconds")
status={"start":"IN_PROGRESS","success":"VERIFIED","failure":"FAILED"}[a.phase]
txt=state.read_text(encoding="utf-8",errors="replace") if state.exists() else "# PROJECT STATE\n\nWorking Directory: PROJECT_ROOT\n"
block=f"""<!-- STEP_060_MANAGED_BEGIN -->
## STEP_060 Live State
Last Updated: {now}
Status: {status}
Goal: Review/persist all remaining D10_0801/D10_0802 THEALLAMERICANS text (60 unique units), then export next campaign batch.
ISO modified in this step: NO
Remaining six movie validations resumed: NO
Detail: {a.detail}
<!-- STEP_060_MANAGED_END -->"""
pat=re.compile(r"<!-- STEP_060_MANAGED_BEGIN -->.*?<!-- STEP_060_MANAGED_END -->",re.S)
txt=pat.sub(block,txt) if pat.search(txt) else txt.rstrip()+"\n\n"+block+"\n"
state.write_text(txt,encoding="utf-8")
if a.phase=="start":
    step.write_text("""# STEP 060

## Goal
Complete translation metadata for both `The All Americans` mission parts:
- D10_0801 current export: 24 rows
- D10_0802 current remaining refs: 41 rows
- shared between the two: 5 rows
- Part-2-only extra rows: 36
- total unique rows translated this step: 60

## Starting State
- Campaign total: 1302
- VERIFIED_APPLIED: 137
- TRANSLATED_PENDING_APPLY: 90
- TRANSLATED_REVIEWED: 734
- NEEDS_TRANSLATION: 341
- ISO modification: none
- Remaining six movie playback validations: deferred

## Result
IN_PROGRESS
""",encoding="utf-8")
else:
    old=step.read_text(encoding="utf-8",errors="replace") if step.exists() else "# STEP 060\n"
    step.write_text(old.rstrip()+f"""

## Completion Update
Time: {now}
Result: {status}
Detail: {a.detail}

## Verification
Translation metadata only. Neither All Americans part is claimed as ISO-applied or runtime-verified.

## Next Step
Translate the automatically exported next campaign batch, expected D15_1130_BOOKENDS.
""",encoding="utf-8")
