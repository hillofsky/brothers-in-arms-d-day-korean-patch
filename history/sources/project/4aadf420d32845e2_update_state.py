#!/usr/bin/env python3
from pathlib import Path
import argparse,datetime,re
ap=argparse.ArgumentParser()
ap.add_argument("--root",required=True)
ap.add_argument("--phase",required=True,choices=["start","success","failure"])
ap.add_argument("--detail",default="")
a=ap.parse_args()
root=Path(a.root);state=root/"PROJECT_STATE.md";step=root/"log"/"steps"/"STEP_074_FIX2.md"
step.parent.mkdir(parents=True,exist_ok=True)
now=datetime.datetime.now().astimezone().isoformat(timespec="seconds")
status={"start":"IN_PROGRESS","success":"BUILT_UNVERIFIED","failure":"FAILED"}[a.phase]
txt=state.read_text(encoding="utf-8",errors="replace") if state.exists() else "# PROJECT STATE\n"
block=f"""<!-- STEP_074_FIX2_MANAGED_BEGIN -->
## STEP_074 FIX2 Live State
Last Updated: {now}
Status: {status}
Goal: Retry compiled967 bulk build with the original TMR18 renderer-page arrays interpreted exactly as proven by Stage36: one u16 width, one u16 height, one u32 texture-object entry before expansion.
Source baseline: BIA_STAGE69_FIX2_NONMDI_INT92_TEST.iso
INT92 runtime status: BUILT_UNVERIFIED
Compiled-MDI 967 runtime verified: NO
Movie playback validation resumed: NO
New Objective popup title fixed: NO
Detail: {a.detail}
<!-- STEP_074_FIX2_MANAGED_END -->"""
pat=re.compile(r"<!-- STEP_074_FIX2_MANAGED_BEGIN -->.*?<!-- STEP_074_FIX2_MANAGED_END -->",re.S)
txt=pat.sub(block,txt) if pat.search(txt) else txt.rstrip()+"\n\n"+block+"\n"
state.write_text(txt,encoding="utf-8")
if a.phase=="start":
    step.write_text("""# STEP 074 FIX2

## Root cause
FIX1 incorrectly read FOUR entries from each original 151-glyph TMR18
width/height/texture renderer-page array.

Stage36 already proved the original font has exactly ONE valid entry:
- u16 width = 128
- u16 height = 256
- u32 texture object
Four renderer-page entries are created only by the Korean font expansion.

FIX2 corrects this interpretation and keeps the proven Stage39A/40Y/43A
generalization path.

## Result
IN_PROGRESS
""",encoding="utf-8")
else:
    old=step.read_text(encoding="utf-8",errors="replace") if step.exists() else "# STEP 074 FIX2\n"
    step.write_text(old.rstrip()+f"\n\nTime: {now}\nResult: {status}\nDetail: {a.detail}\n",encoding="utf-8")
