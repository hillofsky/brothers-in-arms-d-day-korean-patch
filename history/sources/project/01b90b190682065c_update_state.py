#!/usr/bin/env python3
from pathlib import Path
import argparse,datetime,re
ap=argparse.ArgumentParser()
ap.add_argument("--root",required=True)
ap.add_argument("--phase",required=True,choices=["start","success","failure"])
ap.add_argument("--detail",default="")
a=ap.parse_args()
root=Path(a.root);state=root/"PROJECT_STATE.md";step=root/"log"/"steps"/"STEP_072.md"
step.parent.mkdir(parents=True,exist_ok=True)
now=datetime.datetime.now().astimezone().isoformat(timespec="seconds")
status={"start":"IN_PROGRESS","success":"VERIFIED","failure":"FAILED"}[a.phase]
txt=state.read_text(encoding="utf-8",errors="replace") if state.exists() else "# PROJECT STATE\n\nWorking Directory: PROJECT_ROOT\n"
block=f"""<!-- STEP_072_MANAGED_BEGIN -->
## STEP_072 Live State
Last Updated: {now}
Status: {status}
Goal: Collect and validate the existing STEP066/064/39A evidence needed to build the generalized 967 compiled-MDI patcher. No ISO modification.
INT92 status: BUILT_UNVERIFIED
Compiled-MDI 967 applied: NO
Movie 106 repatched: NO
Movie playback validation resumed: NO
Detail: {a.detail}
<!-- STEP_072_MANAGED_END -->"""
pat=re.compile(r"<!-- STEP_072_MANAGED_BEGIN -->.*?<!-- STEP_072_MANAGED_END -->",re.S)
txt=pat.sub(block,txt) if pat.search(txt) else txt.rstrip()+"\n\n"+block+"\n"
state.write_text(txt,encoding="utf-8")
if a.phase=="start":
    step.write_text("""# STEP 072

## Goal
Collect exact local evidence for generalized 967 compiled-MDI application.

No ISO is modified.

Required:
- allstream_fstring_refs.tsv
- allstream_font_objects.tsv
- allstream_mdi_glyph_demand.tsv
- stage39a_font_plan.json
- build_campaign43a.py
- campaign_final_apply_split.tsv
- stage38_translation_units.tsv
- stage38_entry_map.tsv
- bia_stage40i_actual_resource_trace.py

## Result
IN_PROGRESS
""",encoding="utf-8")
else:
    old=step.read_text(encoding="utf-8",errors="replace") if step.exists() else "# STEP 072\n"
    step.write_text(old.rstrip()+f"""

## Completion Update
Time: {now}
Result: {status}
Detail: {a.detail}

ISO modified: NO
""",encoding="utf-8")
