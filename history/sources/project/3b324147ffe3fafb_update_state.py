#!/usr/bin/env python3
from pathlib import Path
import argparse,datetime,re
ap=argparse.ArgumentParser()
ap.add_argument("--root",required=True)
ap.add_argument("--phase",required=True,choices=["start","success","failure"])
ap.add_argument("--detail",default="")
a=ap.parse_args()
root=Path(a.root);log=root/"log";state=root/"PROJECT_STATE.md";step=log/"steps"/"STEP_067.md"
step.parent.mkdir(parents=True,exist_ok=True)
now=datetime.datetime.now().astimezone().isoformat(timespec="seconds")
status={"start":"IN_PROGRESS","success":"VERIFIED","failure":"FAILED"}[a.phase]
txt=state.read_text(encoding="utf-8",errors="replace") if state.exists() else "# PROJECT STATE\n\nWorking Directory: PROJECT_ROOT\n"
block=f"""<!-- STEP_067_MANAGED_BEGIN -->
## STEP_067 Live State
Last Updated: {now}
Status: {status}
Goal: Classify the 198 campaign rows that are not compiled FString values in Stage43T MDI assets.
STEP_066 canary D0_0700 90/179: VERIFIED
Resolved compiled campaign IDs: 967
Unresolved non-MDI-class IDs: 198
ISO modified in this step: NO
Deferred movie playback validation resumed: NO
Detail: {a.detail}
<!-- STEP_067_MANAGED_END -->"""
pat=re.compile(r"<!-- STEP_067_MANAGED_BEGIN -->.*?<!-- STEP_067_MANAGED_END -->",re.S)
txt=pat.sub(block,txt) if pat.search(txt) else txt.rstrip()+"\n\n"+block+"\n"
state.write_text(txt,encoding="utf-8")
if a.phase=="start":
    step.write_text("""# STEP 067

## Goal
Classify the remaining 198 campaign strings that STEP_066 proved are not
compiled FString values in the 57 Stage43T MDI files.

Checks:
- search their original INT keys through every decoded MDI stream
- search all non-audio ISO files for their raw English payloads
- search historical work/analysis/log files for prior movie/subtitle handling
- distinguish movie/subtitle evidence from menu/config/INT-only classes

## Starting State
- D0_0700 canary: PASS (90 units / 179 refs)
- compiled FString campaign IDs found: 967
- non-MDI-class unresolved IDs: 198
- ISO modification: none
- movie playback validation remains deferred

## Result
IN_PROGRESS
""",encoding="utf-8")
else:
    old=step.read_text(encoding="utf-8",errors="replace") if step.exists() else "# STEP 067\n"
    step.write_text(old.rstrip()+f"""

## Completion Update
Time: {now}
Result: {status}
Detail: {a.detail}

## Verification
Classification only. No ISO/resource mutation and no movie playback validation.

## Next Step
Reconcile IDs already handled by the movie subtitle pipeline, identify the
correct non-MDI localization path for the remainder, then construct the final
bulk ISO application manifest.
""",encoding="utf-8")
