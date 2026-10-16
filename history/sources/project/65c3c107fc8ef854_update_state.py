#!/usr/bin/env python3
from pathlib import Path
import argparse,datetime,re
ap=argparse.ArgumentParser()
ap.add_argument("--root",required=True)
ap.add_argument("--phase",required=True,choices=["start","success","failure"])
ap.add_argument("--detail",default="")
a=ap.parse_args()
root=Path(a.root); log=root/"log"
state=root/"PROJECT_STATE.md"; step=log/"steps"/"STEP_044.md"
step.parent.mkdir(parents=True,exist_ok=True)
now=datetime.datetime.now().astimezone().isoformat(timespec="seconds")
status={"start":"IN_PROGRESS","success":"VERIFIED","failure":"FAILED"}[a.phase]
txt=state.read_text(encoding="utf-8",errors="replace") if state.exists() else "# PROJECT STATE\n\nWorking Directory: PROJECT_ROOT\n"
block=f"""<!-- STEP_044_MANAGED_BEGIN -->
## STEP_044 Live State
Last Updated: {now}
Status: {status}
Goal: Discover next untranslated campaign mission and export translation TSV.
Base Build: PROJECT_ROOT/BIA_STAGE43T_TITLE_PROMPT_FIX.iso
ISO modified in this step: NO
Remaining six movie validations resumed: NO
Detail: {a.detail}
<!-- STEP_044_MANAGED_END -->"""
pat=re.compile(r"<!-- STEP_044_MANAGED_BEGIN -->.*?<!-- STEP_044_MANAGED_END -->",re.S)
txt=pat.sub(block,txt) if pat.search(txt) else txt.rstrip()+"\n\n"+block+"\n"
state.write_text(txt,encoding="utf-8")
entry=f"""
## STEP_044 FIX5 Update — {now}
Status: {status}
Detail: {a.detail}
Notes:
- FIX1 packaging layout failed before execution.
- FIX2 searched only imported first/second mission datasets.
- FIX3 failed before discovery due Start-Process argv splitting.
- FIX4 failed in its own Korean/UTF-16 argv preflight; discovery again did not run.
- FIX5 uses fresh logs and no Korean argv preflight.
"""
with step.open("a",encoding="utf-8") as f:f.write(entry)
