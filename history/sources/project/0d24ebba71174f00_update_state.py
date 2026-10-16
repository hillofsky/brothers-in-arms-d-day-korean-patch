#!/usr/bin/env python3
from pathlib import Path
import argparse,datetime,re
ap=argparse.ArgumentParser()
ap.add_argument("--root",required=True)
ap.add_argument("--phase",required=True,choices=["start","success","failure"])
ap.add_argument("--detail",default="")
a=ap.parse_args()
root=Path(a.root);state=root/"PROJECT_STATE.md";step=root/"log"/"steps"/"STEP_074_FIX6.md"
step.parent.mkdir(parents=True,exist_ok=True)
now=datetime.datetime.now().astimezone().isoformat(timespec="seconds")
status={"start":"IN_PROGRESS","success":"BUILT_UNVERIFIED","failure":"FAILED"}[a.phase]
txt=state.read_text(encoding="utf-8",errors="replace") if state.exists() else "# PROJECT STATE\n"
block=f"""<!-- STEP_074_FIX6_MANAGED_BEGIN -->
## STEP_074 FIX6 Live State
Last Updated: {now}
Status: {status}
Goal: Build compiled-MDI 967 with independently selected per-MDI role1 texture object and preserve Stage69 translations/movie resources.
Source baseline: BIA_STAGE69_FIX2_NONMDI_INT92_TEST.iso
INT92 runtime status: BUILT_UNVERIFIED
Compiled-MDI 967 runtime verified: NO
Movie playback validation resumed: NO
New Objective popup title fixed: NO
Detail: {a.detail}
<!-- STEP_074_FIX6_MANAGED_END -->"""
pat=re.compile(r"<!-- STEP_074_FIX6_MANAGED_BEGIN -->.*?<!-- STEP_074_FIX6_MANAGED_END -->",re.S)
txt=pat.sub(block,txt) if pat.search(txt) else txt.rstrip()+"\n\n"+block+"\n"
state.write_text(txt,encoding="utf-8")
if a.phase=="start":
    step.write_text("""# STEP 074 FIX6

## Cause and correction
FIX5 matched the two original TMR18 font roles successfully in 31 target MDIs,
but incorrectly required the Stage40Y first-mission texture-object address
0x09A8D6D0 to hold the exact same object at that same address in every MDI.
Those MDIs have different texture layouts and data at that fixed address.

FIX6 uses the exact matched second original font-role texture pointer from
that MDI's +0x488 table. In the verified first mission that pointer equals
Stage40Y's 0x09A8D6D0, but elsewhere it is MDI-specific.
The selected object must be readable, nonzero, and unchanged from the original
ISO to Stage69. First-mission byte similarity is logged but not misused as a
cross-mission invariant.

All 32 MDIs are dry-run before any output ISO exists.
Each MDI's outcome is persisted immediately to per_mdi_dryrun_progress.jsonl.

## Result
IN_PROGRESS
""",encoding="utf-8")
else:
    old=step.read_text(encoding="utf-8",errors="replace") if step.exists() else "# STEP 074 FIX6\n"
    step.write_text(old.rstrip()+f"\n\nTime: {now}\nResult: {status}\nDetail: {a.detail}\n",encoding="utf-8")
