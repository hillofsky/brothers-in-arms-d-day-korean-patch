#!/usr/bin/env python3
from pathlib import Path
import argparse,datetime,re
ap=argparse.ArgumentParser();ap.add_argument("--root",required=True);ap.add_argument("--phase",required=True,choices=["start","success","failure"]);ap.add_argument("--detail",default="")
a=ap.parse_args();root=Path(a.root);log=root/"log";state=root/"PROJECT_STATE.md";step=log/"steps"/"STEP_059.md";step.parent.mkdir(parents=True,exist_ok=True)
now=datetime.datetime.now().astimezone().isoformat(timespec="seconds");status={"start":"IN_PROGRESS","success":"VERIFIED","failure":"FAILED"}[a.phase]
txt=state.read_text(encoding="utf-8",errors="replace") if state.exists() else "# PROJECT STATE\n\nWorking Directory: PROJECT_ROOT\n"
block=f"""<!-- STEP_059_MANAGED_BEGIN -->
## STEP_059 Live State
Last Updated: {now}
Status: {status}
Goal: Review/persist D10_0600_RUNOFTHEMILL (50), then export next campaign batch.
ISO modified in this step: NO
Remaining six movie validations resumed: NO
Detail: {a.detail}
<!-- STEP_059_MANAGED_END -->"""
pat=re.compile(r"<!-- STEP_059_MANAGED_BEGIN -->.*?<!-- STEP_059_MANAGED_END -->",re.S)
txt=pat.sub(block,txt) if pat.search(txt) else txt.rstrip()+"\n\n"+block+"\n";state.write_text(txt,encoding="utf-8")
if a.phase=="start":
    step.write_text("""# STEP 059

## Goal
Translate/review and persist D10_0600_RUNOFTHEMILL: 50 units, then export the next untranslated campaign group.

## Starting State
- Campaign total: 1302
- VERIFIED_APPLIED: 137
- TRANSLATED_PENDING_APPLY: 90
- TRANSLATED_REVIEWED: 684
- NEEDS_TRANSLATION: 391
- ISO modification: none
- Remaining six movie playback validations: deferred

## Result
IN_PROGRESS
""",encoding="utf-8")
else:
    old=step.read_text(encoding="utf-8",errors="replace") if step.exists() else "# STEP 059\n"
    step.write_text(old.rstrip()+f"""

## Completion Update
Time: {now}
Result: {status}
Detail: {a.detail}

## Verification
Translation metadata only. D10_0600 is not claimed as ISO-applied or runtime-verified.

## Next Step
Translate the automatically exported next campaign batch, expected D10_0801_THEALLAMERICANS.
""",encoding="utf-8")
