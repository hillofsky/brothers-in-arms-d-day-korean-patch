#!/usr/bin/env python3
from pathlib import Path
import argparse,datetime,re
ap=argparse.ArgumentParser()
ap.add_argument("--root",required=True)
ap.add_argument("--phase",required=True,choices=["start","success","failure"])
ap.add_argument("--detail",default="")
a=ap.parse_args()
root=Path(a.root);log=root/"log";state=root/"PROJECT_STATE.md";step=log/"steps"/"STEP_064.md"
step.parent.mkdir(parents=True,exist_ok=True)
now=datetime.datetime.now().astimezone().isoformat(timespec="seconds")
status={"start":"IN_PROGRESS","success":"VERIFIED","failure":"FAILED"}[a.phase]
txt=state.read_text(encoding="utf-8",errors="replace") if state.exists() else "# PROJECT STATE\n\nWorking Directory: PROJECT_ROOT\n"
block=f"""<!-- STEP_064_MANAGED_BEGIN -->
## STEP_064 Live State
Last Updated: {now}
Status: {status}
Goal: Recover exact Stage38 per-occurrence campaign map and historical successful campaign ISO patch scripts from filesystem/log archives.
Campaign untranslated rows: 0
ISO modified in this step: NO
Remaining six movie validations resumed: NO
Detail: {a.detail}
<!-- STEP_064_MANAGED_END -->"""
pat=re.compile(r"<!-- STEP_064_MANAGED_BEGIN -->.*?<!-- STEP_064_MANAGED_END -->",re.S)
txt=pat.sub(block,txt) if pat.search(txt) else txt.rstrip()+"\n\n"+block+"\n"
state.write_text(txt,encoding="utf-8")
if a.phase=="start":
    step.write_text("""# STEP 064

## Why This Step Exists
STEP_063 proved the campaign translation corpus is complete but also showed
that summarized translation-unit references contain `+N more` truncation and
did not recover the historical Stage43 campaign patcher.

## Goal
- Read Stage38 `stage38_entry_map.tsv` to recover every exact source occurrence.
- Verify the 1165 unapplied IDs against exact reference counts.
- Snapshot and validate the corresponding extracted SYSTEM `.INT` files.
- Inventory Stage43T ISO campaign-related files.
- Search PROJECT_ROOT and historical ZIP logs for the actual first/second-mission
  campaign apply/rebuild scripts.

## Starting State
- VERIFIED_APPLIED: 137
- TRANSLATED_PENDING_APPLY: 90
- TRANSLATED_REVIEWED: 1075
- NEEDS_TRANSLATION: 0
- ISO modification: none

## Result
IN_PROGRESS
""",encoding="utf-8")
else:
    old=step.read_text(encoding="utf-8",errors="replace") if step.exists() else "# STEP 064\n"
    step.write_text(old.rstrip()+f"""

## Completion Update
Time: {now}
Result: {status}
Detail: {a.detail}

## Verification
Recovery/discovery only. No ISO/resource mutation is claimed.

## Next Step
Analyze the exact occurrence manifest and recovered historical patch scripts,
then build the bulk campaign ISO application stage without guessing.
""",encoding="utf-8")
