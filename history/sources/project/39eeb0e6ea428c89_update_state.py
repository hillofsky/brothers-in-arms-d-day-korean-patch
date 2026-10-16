#!/usr/bin/env python3
from pathlib import Path
import argparse,datetime,re

ap=argparse.ArgumentParser()
ap.add_argument("--root",required=True)
ap.add_argument("--phase",required=True,choices=["start","success","failure"])
ap.add_argument("--detail",default="")
a=ap.parse_args()

root=Path(a.root)
state=root/"PROJECT_STATE.md"
step=root/"log"/"steps"/"STEP_074_FIX5.md"
step.parent.mkdir(parents=True,exist_ok=True)
now=datetime.datetime.now().astimezone().isoformat(timespec="seconds")
status={"start":"IN_PROGRESS","success":"BUILT_UNVERIFIED","failure":"FAILED"}[a.phase]

txt=state.read_text(encoding="utf-8",errors="replace") if state.exists() else "# PROJECT STATE\n"
block=f"""<!-- STEP_074_FIX5_MANAGED_BEGIN -->
## STEP_074 FIX5 Live State
Last Updated: {now}
Status: {status}
Goal: Match the two proven D0_0130_ original TMR18 font roles independently, preserving their distinct original metrics/textures, then dry-run/apply all 967 IDs across 32 MDIs.
Source baseline: BIA_STAGE69_FIX2_NONMDI_INT92_TEST.iso
INT92 runtime status: BUILT_UNVERIFIED
Compiled-MDI 967 runtime verified: NO
Movie playback validation resumed: NO
New Objective popup title fixed: NO
Detail: {a.detail}
<!-- STEP_074_FIX5_MANAGED_END -->"""
pat=re.compile(r"<!-- STEP_074_FIX5_MANAGED_BEGIN -->.*?<!-- STEP_074_FIX5_MANAGED_END -->",re.S)
txt=pat.sub(block,txt) if pat.search(txt) else txt.rstrip()+"\n\n"+block+"\n"
state.write_text(txt,encoding="utf-8")

if a.phase=="start":
    step.write_text("""# STEP 074 FIX5

## Root cause
The historical first-mission patch modifies TWO original campaign text-font
objects. They are not identical roles.

The failure sequence proves:
- one original role is 128x512;
- the other original role is 128x256.

FIX2 saw the 128x512 object first.
FIX3 then passed that metric check and reached the texture check.
FIX4 removed that texture equality check, continued to the second object, and
correctly observed 128x256.

The previous scripts incorrectly forced one shared metric and/or one shared
original texture onto both roles.

## FIX5
- derives both template metrics independently from the untouched D0_0130_ ISO;
- matches every target candidate to the corresponding template by exact metric
  plus normalized font-object similarity;
- does not require the two original texture objects to be equal;
- refuses ambiguous template-role matches;
- independently retains the Stage40Y expanded-Korean texture-object fingerprint;
- performs all 32 dry-runs before creating an ISO.

## Result
IN_PROGRESS
""",encoding="utf-8")
else:
    old=step.read_text(encoding="utf-8",errors="replace") if step.exists() else "# STEP 074 FIX5\n"
    step.write_text(old.rstrip()+f"\n\nTime: {now}\nResult: {status}\nDetail: {a.detail}\n",encoding="utf-8")
