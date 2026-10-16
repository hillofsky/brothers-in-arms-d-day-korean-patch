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
step=root/"log"/"steps"/"STEP_074_FIX4.md"
step.parent.mkdir(parents=True,exist_ok=True)

now=datetime.datetime.now().astimezone().isoformat(timespec="seconds")
status={"start":"IN_PROGRESS","success":"BUILT_UNVERIFIED","failure":"FAILED"}[a.phase]

txt=state.read_text(encoding="utf-8",errors="replace") if state.exists() else "# PROJECT STATE\n"
block=f"""<!-- STEP_074_FIX4_MANAGED_BEGIN -->
## STEP_074 FIX4 Live State
Last Updated: {now}
Status: {status}
Goal: Generalize the proven campaign Korean font while keeping the original 151-glyph font texture object distinct from Stage40Y's independently identified expanded Korean texture object.
Source baseline: BIA_STAGE69_FIX2_NONMDI_INT92_TEST.iso
INT92 runtime status: BUILT_UNVERIFIED
Compiled-MDI 967 runtime verified: NO
Movie playback validation resumed: NO
New Objective popup title fixed: NO
Detail: {a.detail}
<!-- STEP_074_FIX4_MANAGED_END -->"""

pat=re.compile(r"<!-- STEP_074_FIX4_MANAGED_BEGIN -->.*?<!-- STEP_074_FIX4_MANAGED_END -->",re.S)
txt=pat.sub(block,txt) if pat.search(txt) else txt.rstrip()+"\n\n"+block+"\n"
state.write_text(txt,encoding="utf-8")

if a.phase=="start":
    step.write_text("""# STEP 074 FIX4

## Root cause
FIX3 incorrectly required the original 151-glyph font's currently selected
texture object to equal Stage40Y's runtime-proven Korean expanded texture
object.

Exact D0_0130_ evidence:
- original font +0x488 current object: 0x09A8D5E0
- Stage40Y expanded Korean target:    0x09A8D6D0

These have different roles.

FIX4:
- uses the original +0x488 object only for identifying the original font pair;
- fingerprints the actual object at 0x09A8D6D0 from untouched D0_0130_;
- normalizes in-MDI pointers in that object;
- requires every untouched target MDI to contain a structurally matching object
  at the same campaign runtime address before using it;
- only then installs the Stage39A/43A Korean font and patches text.

No output ISO is created unless all 32 dry-runs pass.

## Result
IN_PROGRESS
""",encoding="utf-8")
else:
    old=step.read_text(encoding="utf-8",errors="replace") if step.exists() else "# STEP 074 FIX4\n"
    step.write_text(old.rstrip()+f"\n\nTime: {now}\nResult: {status}\nDetail: {a.detail}\n",encoding="utf-8")
