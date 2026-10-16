#!/usr/bin/env python3
from pathlib import Path
import argparse, datetime, re

ap=argparse.ArgumentParser()
ap.add_argument("--root",required=True)
ap.add_argument("--phase",required=True,choices=["start","success","failure"])
ap.add_argument("--detail",default="")
a=ap.parse_args()

root=Path(a.root)
state=root/"PROJECT_STATE.md"
step=root/"log"/"steps"/"STEP_073.md"
step.parent.mkdir(parents=True,exist_ok=True)
now=datetime.datetime.now().astimezone().isoformat(timespec="seconds")
status={"start":"IN_PROGRESS","success":"VERIFIED","failure":"FAILED"}[a.phase]

txt=state.read_text(encoding="utf-8",errors="replace") if state.exists() else "# PROJECT STATE\n"
block=f"""<!-- STEP_073_MANAGED_BEGIN -->
## STEP_073 Live State
Last Updated: {now}
Status: {status}
Goal: Recover the exact historical Stage43A/Stage40Y/Stage39B builder sources needed to construct the generalized 967 compiled-MDI ISO patcher.
ISO modified: NO
INT92: BUILT_UNVERIFIED
Compiled-MDI 967 applied: NO
Movie playback validation resumed: NO
Detail: {a.detail}
<!-- STEP_073_MANAGED_END -->"""
pat=re.compile(r"<!-- STEP_073_MANAGED_BEGIN -->.*?<!-- STEP_073_MANAGED_END -->",re.S)
txt=pat.sub(block,txt) if pat.search(txt) else txt.rstrip()+"\n\n"+block+"\n"
state.write_text(txt,encoding="utf-8")

if a.phase=="start":
    step.write_text("# STEP 073\n\nStatus: IN_PROGRESS\n\nExact historical builder-source recovery. No ISO modification.\n",encoding="utf-8")
else:
    old=step.read_text(encoding="utf-8",errors="replace") if step.exists() else "# STEP 073\n"
    step.write_text(old.rstrip()+f"\n\nTime: {now}\nResult: {status}\nDetail: {a.detail}\nISO modified: NO\n",encoding="utf-8")
