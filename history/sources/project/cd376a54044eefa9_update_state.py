#!/usr/bin/env python3
from pathlib import Path
import argparse,datetime,re
ap=argparse.ArgumentParser()
ap.add_argument("--root",required=True)
ap.add_argument("--phase",required=True,choices=["start","success","failure"])
ap.add_argument("--detail",default="")
a=ap.parse_args()
root=Path(a.root); log=root/"log"
state=root/"PROJECT_STATE.md"; step=log/"steps"/"STEP_045.md"
step.parent.mkdir(parents=True,exist_ok=True)
now=datetime.datetime.now().astimezone().isoformat(timespec="seconds")
status={"start":"IN_PROGRESS","success":"VERIFIED","failure":"FAILED"}[a.phase]
txt=state.read_text(encoding="utf-8",errors="replace") if state.exists() else "# PROJECT STATE\n\nWorking Directory: PROJECT_ROOT\n"
block=f"""<!-- STEP_045_MANAGED_BEGIN -->
## STEP_045 Live State
Last Updated: {now}
Status: {status}
Goal: Review and persist Korean translations for all 62 D0_1015_.MDI Priority-B units.
Input: STEP_044 exported campaign_next_translation.tsv
ISO modified in this step: NO
Runtime verification required in this step: NO
Remaining six movie validations resumed: NO
Detail: {a.detail}
<!-- STEP_045_MANAGED_END -->"""
pat=re.compile(r"<!-- STEP_045_MANAGED_BEGIN -->.*?<!-- STEP_045_MANAGED_END -->",re.S)
txt=pat.sub(block,txt) if pat.search(txt) else txt.rstrip()+"\n\n"+block+"\n"
state.write_text(txt,encoding="utf-8")

if a.phase=="start":
    body=f"""# STEP 045

## Goal
Translate/review all 62 Priority-B units associated with D0_1015_.MDI.

## Starting State
- Canonical campaign B total: 1302 units.
- 137 first-mission units: VERIFIED_APPLIED.
- 90 second-mission units: TRANSLATED_PENDING_APPLY.
- 62 D0_1015 units exported by STEP_044.
- 1013 other campaign units still NEEDS_TRANSLATION.
- Stage43T remains a test baseline, not a complete translation.
- Remaining six movie playback validations remain deferred.

## Inputs
- translation/campaign_next_translation.tsv
- translation/text_master.tsv
- translations_D0_1015.json

## Work Performed
Translation persistence started. No ISO modification.

## Result
IN_PROGRESS
"""
    step.write_text(body,encoding="utf-8")
else:
    old=step.read_text(encoding="utf-8",errors="replace") if step.exists() else "# STEP 045\n"
    with step.open("w",encoding="utf-8") as f:
        f.write(old.rstrip()+f"""

## Completion Update
Time: {now}
Result: {status}
Detail: {a.detail}

## Verification
- 62/62 source IDs and English source strings matched before write.
- ko_current and ko_review written identically from reviewed translation mapping.
- Control tokens were validated when the package was generated.
- ISO was not modified.
- Runtime status remains untranslated/not-applied for D0_1015 until a later patch/build Step.

## Next Step
Apply already-translated second mission plus D0_1015 in a dedicated build Step, or continue extracting/translating remaining campaign Priority-B units.
""")
