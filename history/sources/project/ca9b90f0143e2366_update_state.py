#!/usr/bin/env python3
from pathlib import Path
import argparse,datetime,re
ap=argparse.ArgumentParser()
ap.add_argument("--root",required=True)
ap.add_argument("--phase",required=True,choices=["start","success","failure"])
ap.add_argument("--detail",default="")
a=ap.parse_args()
root=Path(a.root);log=root/"log"
state=root/"PROJECT_STATE.md";step=log/"steps"/"STEP_062.md"
step.parent.mkdir(parents=True,exist_ok=True)
now=datetime.datetime.now().astimezone().isoformat(timespec="seconds")
status={"start":"IN_PROGRESS","success":"VERIFIED","failure":"FAILED"}[a.phase]

txt=state.read_text(encoding="utf-8",errors="replace") if state.exists() else "# PROJECT STATE\n\nWorking Directory: PROJECT_ROOT\n"
block=f"""<!-- STEP_062_MANAGED_BEGIN -->
## STEP_062 Live State
Last Updated: {now}
Status: {status}
Goal: Translate/review the final 162 campaign skirmish/system rows and close campaign translation discovery.
ISO modified in this step: NO
Remaining six movie validations resumed: NO
Detail: {a.detail}
<!-- STEP_062_MANAGED_END -->"""
pat=re.compile(r"<!-- STEP_062_MANAGED_BEGIN -->.*?<!-- STEP_062_MANAGED_END -->",re.S)
txt=pat.sub(block,txt) if pat.search(txt) else txt.rstrip()+"\n\n"+block+"\n"
state.write_text(txt,encoding="utf-8")

if a.phase=="start":
    step.write_text("""# STEP 062

## Goal
Translate/review the final 162 campaign rows. These are skirmish objectives,
hints, beacon labels, win/loss messages, and a small number of system strings.

## Starting State
- Campaign total: 1302
- VERIFIED_APPLIED: 137
- TRANSLATED_PENDING_APPLY: 90
- TRANSLATED_REVIEWED: 913
- NEEDS_TRANSLATION: 162
- ISO modification: none
- Remaining six movie playback validations: deferred

## Result
IN_PROGRESS
""",encoding="utf-8")
else:
    old=step.read_text(encoding="utf-8",errors="replace") if step.exists() else "# STEP 062\n"
    step.write_text(old.rstrip()+f"""

## Completion Update
Time: {now}
Result: {status}
Detail: {a.detail}

## Verification
Translation metadata only. No new campaign strings are claimed as ISO-applied
or runtime-verified in this step.

## Next Phase
If VERIFIED, campaign translation discovery/review is complete:
- NEEDS_TRANSLATION = 0
- 1165 campaign units remain ready for ISO application/verification
  (90 TRANSLATED_PENDING_APPLY + 1075 TRANSLATED_REVIEWED).
""",encoding="utf-8")
