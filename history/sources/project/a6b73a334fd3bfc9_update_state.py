#!/usr/bin/env python3
from pathlib import Path
import argparse,datetime,re,json
ap=argparse.ArgumentParser()
ap.add_argument("--root",required=True)
ap.add_argument("--phase",choices=["start","success","failure"],required=True)
ap.add_argument("--detail",default="")
a=ap.parse_args()
root=Path(a.root)
log=root/"log"
state=root/"PROJECT_STATE.md"
step=log/"steps"/"STEP_044.md"
step.parent.mkdir(parents=True,exist_ok=True)
now=datetime.datetime.now().astimezone().isoformat(timespec="seconds")
status={"start":"IN_PROGRESS","success":"VERIFIED","failure":"FAILED"}[a.phase]

txt=state.read_text(encoding="utf-8",errors="replace") if state.exists() else "# PROJECT STATE\n\nWorking Directory: PROJECT_ROOT\n"
block=f"""<!-- STEP_044_MANAGED_BEGIN -->
## STEP_044 Live State
Last Updated: {now}
Status: {status}
Goal: Export the next untranslated campaign mission from the canonical Stage38 Priority-B worklist.
Base Build: PROJECT_ROOT/BIA_STAGE43T_TITLE_PROMPT_FIX.iso
Canonical Campaign Source: PROJECT_ROOT/analysis/stage38_translation_worklist/stage38_translation_units.tsv
ISO modified in this step: NO
Remaining six movie validations resumed: NO
Detail: {a.detail}
<!-- STEP_044_MANAGED_END -->"""
pat=re.compile(r"<!-- STEP_044_MANAGED_BEGIN -->.*?<!-- STEP_044_MANAGED_END -->",re.S)
txt=pat.sub(block,txt) if pat.search(txt) else txt.rstrip()+"\n\n"+block+"\n"

# Keep the key technical finding outside the managed block so future steps retain it.
fact_marker="<!-- CAMPAIGN_MASTER_FACT_BEGIN -->"
fact=f"""<!-- CAMPAIGN_MASTER_FACT_BEGIN -->
## Campaign Master Worklist
CONFIRMED: The canonical 1302-unit Priority-B campaign source is:
`PROJECT_ROOT/analysis/stage38_translation_worklist/stage38_translation_units.tsv`

Mission membership is encoded in the `references` column as tokens such as
`D0_0700_EXIT4:...`, not necessarily literal `D0_0700_.MDI` filenames.
This is why STEP_044 FIX6's `.MDI`-only discovery found no remaining groups.
<!-- CAMPAIGN_MASTER_FACT_END -->"""
fpat=re.compile(r"<!-- CAMPAIGN_MASTER_FACT_BEGIN -->.*?<!-- CAMPAIGN_MASTER_FACT_END -->",re.S)
txt=fpat.sub(fact,txt) if fpat.search(txt) else txt.rstrip()+"\n\n"+fact+"\n"
state.write_text(txt,encoding="utf-8")

entry=f"""
## STEP_044 FIX7 — {now}
Status: {status}
Goal: Use the canonical Stage38 1302-unit Priority-B TSV directly.
Detail: {a.detail}
ISO modified: NO
Remaining movie playback validation resumed: NO
"""
with step.open("a",encoding="utf-8") as f:f.write(entry)
