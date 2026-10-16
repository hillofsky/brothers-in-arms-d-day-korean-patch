#!/usr/bin/env python3
import argparse,re,datetime
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument("--root",required=True);p.add_argument("--phase",required=True,choices=["start","success","failure"])
p.add_argument("--detail",default="")
a=p.parse_args()
root=Path(a.root); state=root/"PROJECT_STATE.md";step=root/"log"/"steps"/"STEP_082.md"
step.parent.mkdir(parents=True,exist_ok=True)
now=datetime.datetime.now().astimezone().isoformat(timespec="seconds")
st={"start":"IN_PROGRESS","success":"VERIFIED","failure":"FAILED"}[a.phase]
block=f"""<!-- STEP_082_MANAGED_BEGIN -->
## STEP_082 screenshot-confirmed localization defect analysis
Last Updated: {now}
Status: {st}
Purpose: collect exact Stage69 versus Stage79 mission2 MDI/DSL/DSX and check font Unicode mapping vs Korean payloads; locate mission1 screenshot English residuals.
Screenshot visual QA: MISSION1_ENGLISH_RESIDUALS; MISSION2_KOREAN_TEXT_BROKEN_GT_FALLBACK
Stage79 static translation: BUILT_UNVERIFIED
Stage79 visual Korean for mission2: FAILED
Current ISO modification: NONE
Previous 6 deferred movies: NOT_RESUMED
Detail: {a.detail}
<!-- STEP_082_MANAGED_END -->"""
txt=state.read_text(encoding="utf-8",errors="replace") if state.exists() else "# PROJECT_STATE\n"
pat=re.compile(r"<!-- STEP_082_MANAGED_BEGIN -->.*?<!-- STEP_082_MANAGED_END -->",re.S)
txt=pat.sub(block,txt) if pat.search(txt) else txt.rstrip()+"\n\n"+block+"\n"
state.write_text(txt,encoding="utf-8")
if a.phase=="start":
    step.write_text("# STEP 082\n\nStatus: IN_PROGRESS\n\nUser screenshots show untranslated mission1 prompts and repeated > glyphs in mission2 cinematics. Collect raw read-only stage69/stage79 binary evidence. No ISO changes.\n",encoding="utf-8")
else:
    old=step.read_text(encoding="utf-8",errors="replace") if step.exists() else "# STEP 082\n"
    step.write_text(old.rstrip()+f"\n\nTime: {now}\nStatus: {st}\nDetail: {a.detail}\n",encoding="utf-8")
