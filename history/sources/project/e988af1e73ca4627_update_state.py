#!/usr/bin/env python3
from pathlib import Path
import argparse,datetime,re

ap=argparse.ArgumentParser()
ap.add_argument("--root",required=True)
ap.add_argument("--phase",required=True,choices=["start","success","failure"])
ap.add_argument("--detail",default="")
a=ap.parse_args()

root=Path(a.root);log=root/"log"
state=root/"PROJECT_STATE.md";step=log/"steps"/"STEP_058_FIX1.md"
step.parent.mkdir(parents=True,exist_ok=True)
now=datetime.datetime.now().astimezone().isoformat(timespec="seconds")
status={"start":"IN_PROGRESS","success":"VERIFIED","failure":"FAILED"}[a.phase]

txt=state.read_text(encoding="utf-8",errors="replace") if state.exists() else "# PROJECT STATE\n\nWorking Directory: PROJECT_ROOT\n"
block=f"""<!-- STEP_058_FIX1_MANAGED_BEGIN -->
## STEP_058 FIX1 Live State
Last Updated: {now}
Status: {status}
Goal: Retry D09_0800_BAUPTE (46) with corrected campaign counters, then export D10_0600.
Root cause: Original STEP_058 expected TRANSLATED_REVIEWED=605, but verified STEP_057 state is 638.
ISO modified in this step: NO
Remaining six movie validations resumed: NO
Detail: {a.detail}
<!-- STEP_058_FIX1_MANAGED_END -->"""
pat=re.compile(r"<!-- STEP_058_FIX1_MANAGED_BEGIN -->.*?<!-- STEP_058_FIX1_MANAGED_END -->",re.S)
txt=pat.sub(block,txt) if pat.search(txt) else txt.rstrip()+"\n\n"+block+"\n"
state.write_text(txt,encoding="utf-8")

if a.phase=="start":
    step.write_text("""# STEP 058 FIX1

## Failure Being Fixed
Original STEP_058 failed before mutation because its strict pre-state counter was stale:
`TRANSLATED_REVIEWED: actual 638 != expected 605`.

STEP_057 had already added 33 reviewed rows. The correct starting counts are:
- VERIFIED_APPLIED: 137
- TRANSLATED_PENDING_APPLY: 90
- TRANSLATED_REVIEWED: 638
- NEEDS_TRANSLATION: 437

The failed run did not apply any D09_0800 translation row.

## Goal
Persist the same reviewed D09_0800_BAUPTE 46-row translation using corrected
pre/post validation, then export D10_0600_RUNOFTHEMILL.

## Result
IN_PROGRESS
""",encoding="utf-8")
else:
    old=step.read_text(encoding="utf-8",errors="replace") if step.exists() else "# STEP 058 FIX1\n"
    step.write_text(old.rstrip()+f"""

## Completion Update
Time: {now}
Result: {status}
Detail: {a.detail}

## Verification
Metadata persistence only. D09_0800 is not claimed as ISO-applied or runtime-verified.
No ISO changes and no deferred movie validation were performed.
""",encoding="utf-8")
