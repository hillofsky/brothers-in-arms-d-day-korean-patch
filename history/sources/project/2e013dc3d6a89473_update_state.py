#!/usr/bin/env python3
from pathlib import Path
import argparse,datetime,re
ap=argparse.ArgumentParser()
ap.add_argument("--root",required=True)
ap.add_argument("--phase",required=True,choices=["start","built","failure"])
ap.add_argument("--detail",default="")
a=ap.parse_args()
root=Path(a.root);log=root/"log";state=root/"PROJECT_STATE.md";step=log/"steps"/"STEP_069_FIX2.md"
step.parent.mkdir(parents=True,exist_ok=True)
now=datetime.datetime.now().astimezone().isoformat(timespec="seconds")
status={"start":"IN_PROGRESS","built":"BUILT_UNVERIFIED","failure":"FAILED"}[a.phase]
txt=state.read_text(encoding="utf-8",errors="replace") if state.exists() else "# PROJECT STATE\n\nWorking Directory: PROJECT_ROOT\n"
block=f"""<!-- STEP_069_FIX2_MANAGED_BEGIN -->
## STEP_069 FIX2 Live State
Last Updated: {now}
Status: {status}
Goal: Rebuild the 92-ID INT-only Stage43T test ISO with corrected verified movie filenames and corrected ON_MEMU_O.MDI preservation target.
STEP069 FIX1 INT patch/readback loop reached completion before its preservation-name failure: YES
Source Stage43T ISO preserved: YES
Compiled-MDI 967 applied: NO
Movie-ST1 106 repatched: NO
Runtime verification complete: NO
Detail: {a.detail}
<!-- STEP_069_FIX2_MANAGED_END -->"""
pat=re.compile(r"<!-- STEP_069_FIX2_MANAGED_BEGIN -->.*?<!-- STEP_069_FIX2_MANAGED_END -->",re.S)
txt=pat.sub(block,txt) if pat.search(txt) else txt.rstrip()+"\n\n"+block+"\n"
state.write_text(txt,encoding="utf-8")
if a.phase=="start":
    step.write_text("""# STEP 069 FIX2

## Failure Diagnosis
STEP_069 FIX1 completed the 18-file INT patch/readback loop, then failed during
post-build preservation checks because two preservation names were guessed:
- wrong movie list included `EM_1130_BOOKENDS.ST1`
- wrong menu MDI name was `ON_MEMU.MDI`

Verified names from STEP_068 FIX1 / Stage43T inventory are now used.

## Output
PROJECT_ROOT\\BIA_STAGE69_FIX2_NONMDI_INT92_TEST.iso

## Result
IN_PROGRESS
""",encoding="utf-8")
else:
    old=step.read_text(encoding="utf-8",errors="replace") if step.exists() else "# STEP 069 FIX2\n"
    step.write_text(old.rstrip()+f"""

## Completion Update
Time: {now}
Result: {status}
Detail: {a.detail}

## Verification Boundary
Static INT patch + ISO readback + preservation checks only.
Runtime verification is still pending.
""",encoding="utf-8")
