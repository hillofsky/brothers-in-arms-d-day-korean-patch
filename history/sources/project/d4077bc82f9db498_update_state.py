#!/usr/bin/env python3
from pathlib import Path
import argparse,datetime,re
ap=argparse.ArgumentParser()
ap.add_argument("--root",required=True)
ap.add_argument("--phase",required=True,choices=["start","success","failure"])
ap.add_argument("--detail",default="")
a=ap.parse_args()
root=Path(a.root);log=root/"log"
state=root/"PROJECT_STATE.md";step=log/"steps"/"STEP_047.md"
step.parent.mkdir(parents=True,exist_ok=True)
now=datetime.datetime.now().astimezone().isoformat(timespec="seconds")
status={"start":"IN_PROGRESS","success":"VERIFIED","failure":"FAILED"}[a.phase]
txt=state.read_text(encoding="utf-8",errors="replace") if state.exists() else "# PROJECT STATE\n\nWorking Directory: PROJECT_ROOT\n"
block=f"""<!-- STEP_047_MANAGED_BEGIN -->
## STEP_047 Live State
Last Updated: {now}
Status: {status}
Goal: Review/persist D2_0630_CRACKOFDAWN (25), then export the next untranslated campaign batch.
ISO modified in this step: NO
Remaining six movie validations resumed: NO
Detail: {a.detail}
<!-- STEP_047_MANAGED_END -->"""
pat=re.compile(r"<!-- STEP_047_MANAGED_BEGIN -->.*?<!-- STEP_047_MANAGED_END -->",re.S)
txt=pat.sub(block,txt) if pat.search(txt) else txt.rstrip()+"\n\n"+block+"\n"
state.write_text(txt,encoding="utf-8")
if a.phase=="start":
    step.write_text(f"""# STEP 047

## Goal
Translate/review and persist D2_0630_CRACKOFDAWN: 25 units, then export the next untranslated campaign group.

## Starting State
- Campaign total: 1302.
- VERIFIED_APPLIED: 137.
- TRANSLATED_PENDING_APPLY: 90.
- TRANSLATED_REVIEWED: 155.
- NEEDS_TRANSLATION: 920.
- ISO modification: none.
- Remaining six movie playback validations remain deferred.

## Result
IN_PROGRESS
""",encoding="utf-8")
else:
    old=step.read_text(encoding="utf-8",errors="replace") if step.exists() else "# STEP 047\n"
    step.write_text(old.rstrip()+f"""

## Completion Update
Time: {now}
Result: {status}
Detail: {a.detail}

## Verification
No ISO was modified. Runtime verification is not claimed for these newly translated rows.

## Next Step
Translate the automatically exported next campaign batch, or apply translated campaign batches later in a dedicated build/verification step.
""",encoding="utf-8")
