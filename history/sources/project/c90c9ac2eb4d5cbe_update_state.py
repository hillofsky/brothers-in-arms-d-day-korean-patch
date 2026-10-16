#!/usr/bin/env python3
from pathlib import Path
import argparse,datetime,re
ap=argparse.ArgumentParser()
ap.add_argument("--root",required=True)
ap.add_argument("--phase",required=True,choices=["start","success","failure"])
ap.add_argument("--detail",default="")
a=ap.parse_args()
root=Path(a.root); state=root/"PROJECT_STATE.md"; step=root/"log"/"steps"/"STEP_074.md"
step.parent.mkdir(parents=True,exist_ok=True)
now=datetime.datetime.now().astimezone().isoformat(timespec="seconds")
status={"start":"IN_PROGRESS","success":"BUILT_UNVERIFIED","failure":"FAILED"}[a.phase]
txt=state.read_text(encoding="utf-8",errors="replace") if state.exists() else "# PROJECT STATE\n"
block=f"""<!-- STEP_074_MANAGED_BEGIN -->
## STEP_074 Live State
Last Updated: {now}
Status: {status}
Goal: Apply all 967 compiled-MDI campaign IDs / 2333 exact FString references across 32 MDIs to a Stage69-derived bulk test ISO.
Source baseline: BIA_STAGE69_FIX2_NONMDI_INT92_TEST.iso
INT92 runtime status: BUILT_UNVERIFIED
Compiled-MDI 967 runtime verified: NO
Movie 106 repatched: NO
Movie playback validation resumed: NO
New Objective popup title fixed: NO
Detail: {a.detail}
<!-- STEP_074_MANAGED_END -->"""
pat=re.compile(r"<!-- STEP_074_MANAGED_BEGIN -->.*?<!-- STEP_074_MANAGED_END -->",re.S)
txt=pat.sub(block,txt) if pat.search(txt) else txt.rstrip()+"\n\n"+block+"\n"
state.write_text(txt,encoding="utf-8")
if a.phase=="start":
    step.write_text("""# STEP 074

## Goal
Actual 967 compiled-MDI bulk ISO build.

Pre-build gates:
- exact 967 IDs / 2333 refs / 32 MDIs
- source FString evidence still matches Stage69
- existing expanded Korean production-font coverage is sufficient per MDI
- all translated payloads fit inside existing FString allocation/slack regions
- no arbitrary all-zero runtime scratch stream is used

Build remains BUILT_UNVERIFIED until runtime tests.

## Result
IN_PROGRESS
""",encoding="utf-8")
else:
    old=step.read_text(encoding="utf-8",errors="replace") if step.exists() else "# STEP 074\n"
    step.write_text(old.rstrip()+f"\n\nTime: {now}\nResult: {status}\nDetail: {a.detail}\n",encoding="utf-8")
