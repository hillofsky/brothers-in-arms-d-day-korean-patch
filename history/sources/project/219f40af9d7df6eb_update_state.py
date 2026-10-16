#!/usr/bin/env python3
from pathlib import Path
import argparse,datetime,re
ap=argparse.ArgumentParser()
ap.add_argument("--root",required=True)
ap.add_argument("--phase",required=True,choices=["start","success","failure"])
ap.add_argument("--detail",default="")
a=ap.parse_args()
root=Path(a.root);log=root/"log";state=root/"PROJECT_STATE.md";step=log/"steps"/"STEP_068.md"
step.parent.mkdir(parents=True,exist_ok=True)
now=datetime.datetime.now().astimezone().isoformat(timespec="seconds")
status={"start":"IN_PROGRESS","success":"VERIFIED","failure":"FAILED"}[a.phase]
txt=state.read_text(encoding="utf-8",errors="replace") if state.exists() else "# PROJECT STATE\n\nWorking Directory: PROJECT_ROOT\n"
block=f"""<!-- STEP_068_MANAGED_BEGIN -->
## STEP_068 Live State
Last Updated: {now}
Status: {status}
Goal: Reconcile STEP067 movie evidence against exact Stage42A ST1 fields and split all 1165 untranslated-but-unapplied campaign IDs into compiled MDI, preserved movie ST1, and non-MDI runtime classes.
STEP066 D0_0700 canary: PASS 90/179
ISO modified in this step: NO
Deferred movie playback validation resumed: NO
Detail: {a.detail}
<!-- STEP_068_MANAGED_END -->"""
pat=re.compile(r"<!-- STEP_068_MANAGED_BEGIN -->.*?<!-- STEP_068_MANAGED_END -->",re.S)
txt=pat.sub(block,txt) if pat.search(txt) else txt.rstrip()+"\n\n"+block+"\n"
state.write_text(txt,encoding="utf-8")
if a.phase=="start":
    step.write_text("""# STEP 068

## Goal
Refine STEP067's broad movie evidence and establish the final static apply split.

Tasks:
- exact-match unresolved campaign strings to Stage42A's 133 ST1 subtitle fields
- compare all 8 movie ST1 files across original, Stage42H all-movies build, and Stage43T
- recover focused Stage42H / Stage43A lineage evidence
- refine the non-movie remainder into dynamic-INT and other runtime classes
- produce a 1165-ID final apply split

## Starting Facts
- compiled MDI IDs: 967
- STEP067 unresolved: 198
- STEP067 broad movie-history evidence: 72
- ISO modification: none

## Result
IN_PROGRESS
""",encoding="utf-8")
else:
    old=step.read_text(encoding="utf-8",errors="replace") if step.exists() else "# STEP 068\n"
    step.write_text(old.rstrip()+f"""

## Completion Update
Time: {now}
Result: {status}
Detail: {a.detail}

## Verification
Static reconciliation only. Stage43T is not modified and the six deferred
movie playback validations remain deferred.

## Next Step
Build the real ISO patch stage for the compiled-MDI and non-MDI/INT classes,
while preserving the movie ST1 files proven to descend from Stage42H.
""",encoding="utf-8")
