#!/usr/bin/env python3
from pathlib import Path
import argparse,datetime,re
ap=argparse.ArgumentParser()
ap.add_argument("--root",required=True)
ap.add_argument("--phase",required=True,choices=["start","success","failure"])
ap.add_argument("--detail",default="")
a=ap.parse_args()
root=Path(a.root);log=root/"log";state=root/"PROJECT_STATE.md";step=log/"steps"/"STEP_065.md"
step.parent.mkdir(parents=True,exist_ok=True)
now=datetime.datetime.now().astimezone().isoformat(timespec="seconds")
status={"start":"IN_PROGRESS","success":"VERIFIED","failure":"FAILED"}[a.phase]
txt=state.read_text(encoding="utf-8",errors="replace") if state.exists() else "# PROJECT STATE\n\nWorking Directory: PROJECT_ROOT\n"
block=f"""<!-- STEP_065_MANAGED_BEGIN -->
## STEP_065 Live State
Last Updated: {now}
Status: {status}
Goal: Audit compiled FString coverage and per-MDI font/DSL/DSX requirements for the 1165 translated-but-unapplied campaign units.
Exact Stage38 occurrence recovery: VERIFIED in STEP_064
ISO modified in this step: NO
Remaining six movie validations resumed: NO
Detail: {a.detail}
<!-- STEP_065_MANAGED_END -->"""
pat=re.compile(r"<!-- STEP_065_MANAGED_BEGIN -->.*?<!-- STEP_065_MANAGED_END -->",re.S)
txt=pat.sub(block,txt) if pat.search(txt) else txt.rstrip()+"\n\n"+block+"\n"
state.write_text(txt,encoding="utf-8")
if a.phase=="start":
    step.write_text("""# STEP 065

## Goal
Scan every Stage43T MDI against the 1165 translated-but-unapplied campaign
resource IDs and determine the exact compiled FString/font patch surface.

Checks:
- English value + original INT key matching
- compiled FString stream/offset
- ambiguous duplicate source strings
- missing compiled strings vs raw payload presence
- mission font-object candidates
- per-MDI extra Hangul demand vs proven Stage43A 60-slot extension budget
- matching DSL/DSX pair presence

## Starting State
- Campaign NEEDS_TRANSLATION: 0
- Unapplied campaign units: 1165
- Exact Stage38 source occurrences: 1435, verified in STEP_064
- ISO modification: none

## Result
IN_PROGRESS
""",encoding="utf-8")
else:
    old=step.read_text(encoding="utf-8",errors="replace") if step.exists() else "# STEP 065\n"
    step.write_text(old.rstrip()+f"""

## Completion Update
Time: {now}
Result: {status}
Detail: {a.detail}

## Verification
Audit only. Stage43T ISO remains untouched.

## Next Step
If compiled coverage/font capacity is safe, construct the actual bulk campaign
MDI/DSL/DSX/INT patcher. Any unresolved records must be recovered explicitly
instead of guessed.
""",encoding="utf-8")
