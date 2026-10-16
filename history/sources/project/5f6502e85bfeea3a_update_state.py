#!/usr/bin/env python3
from pathlib import Path
import argparse,datetime,re
ap=argparse.ArgumentParser()
ap.add_argument("--root",required=True)
ap.add_argument("--phase",required=True,choices=["start","success","failure"])
ap.add_argument("--detail",default="")
a=ap.parse_args()
root=Path(a.root);log=root/"log"
state=root/"PROJECT_STATE.md";step=log/"steps"/"STEP_061.md"
step.parent.mkdir(parents=True,exist_ok=True)
now=datetime.datetime.now().astimezone().isoformat(timespec="seconds")
status={"start":"IN_PROGRESS","success":"VERIFIED","failure":"FAILED"}[a.phase]
txt=state.read_text(encoding="utf-8",errors="replace") if state.exists() else "# PROJECT STATE\n\nWorking Directory: PROJECT_ROOT\n"
block=f"""<!-- STEP_061_MANAGED_BEGIN -->
## STEP_061 Live State
Last Updated: {now}
Status: {status}
Goal: Complete all four D15 Bookends translation groups (119 unique rows), then export remaining campaign skirmish/system pool.
ISO modified in this step: NO
Remaining six movie validations resumed: NO
Detail: {a.detail}
<!-- STEP_061_MANAGED_END -->"""
pat=re.compile(r"<!-- STEP_061_MANAGED_BEGIN -->.*?<!-- STEP_061_MANAGED_END -->",re.S)
txt=pat.sub(block,txt) if pat.search(txt) else txt.rstrip()+"\n\n"+block+"\n"
state.write_text(txt,encoding="utf-8")
if a.phase=="start":
    step.write_text("""# STEP 061

## Goal
Complete all four chronological Bookends groups in one metadata-only pass:
- D15_1130_BOOKENDS
- D15_1230_BOOKENDS2
- D15_1300_BOOKENDS4
- D15_1330_BOOKENDS3
- 119 unique untranslated resource IDs total.

## Starting State
- Campaign total: 1302
- VERIFIED_APPLIED: 137
- TRANSLATED_PENDING_APPLY: 90
- TRANSLATED_REVIEWED: 794
- NEEDS_TRANSLATION: 281
- ISO modification: none
- Remaining six movie playback validations: deferred

## Result
IN_PROGRESS
""",encoding="utf-8")
else:
    old=step.read_text(encoding="utf-8",errors="replace") if step.exists() else "# STEP 061\n"
    step.write_text(old.rstrip()+f"""

## Completion Update
Time: {now}
Result: {status}
Detail: {a.detail}

## Verification
Translation metadata only. Bookends is not claimed as ISO-applied or runtime-verified.

## Next Step
Translate the exported final 162-row campaign remainder (skirmish/system strings).
""",encoding="utf-8")
