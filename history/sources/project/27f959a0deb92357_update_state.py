#!/usr/bin/env python3
from pathlib import Path
import argparse,datetime,re
ap=argparse.ArgumentParser()
ap.add_argument("--root",required=True)
ap.add_argument("--phase",required=True,choices=["start","built","failure"])
ap.add_argument("--detail",default="")
a=ap.parse_args()
root=Path(a.root);log=root/"log";state=root/"PROJECT_STATE.md";step=log/"steps"/"STEP_069.md"
step.parent.mkdir(parents=True,exist_ok=True)
now=datetime.datetime.now().astimezone().isoformat(timespec="seconds")
status={"start":"IN_PROGRESS","built":"BUILT_UNVERIFIED","failure":"FAILED"}[a.phase]
txt=state.read_text(encoding="utf-8",errors="replace") if state.exists() else "# PROJECT STATE\n\nWorking Directory: PROJECT_ROOT\n"
block=f"""<!-- STEP_069_MANAGED_BEGIN -->
## STEP_069 Live State
Last Updated: {now}
Status: {status}
Goal: Apply the 92 non-MDI/INT campaign rows (99 exact INT occurrences across 18 files) to a separate Stage43T-derived test ISO.
Source ISO preserved: YES
Compiled-MDI 967 applied in this step: NO
Movie-ST1 106 repatched in this step: NO
Runtime verification complete: NO
Deferred movie playback validation resumed: NO
Detail: {a.detail}
<!-- STEP_069_MANAGED_END -->"""
pat=re.compile(r"<!-- STEP_069_MANAGED_BEGIN -->.*?<!-- STEP_069_MANAGED_END -->",re.S)
txt=pat.sub(block,txt) if pat.search(txt) else txt.rstrip()+"\n\n"+block+"\n"
state.write_text(txt,encoding="utf-8")
if a.phase=="start":
    step.write_text("""# STEP 069

## Goal
Build a separate ISO containing only the 92 non-MDI/INT campaign translations.

Exact patch scope:
- 92 resource IDs
- 99 Stage38 INT occurrences
- 18 source INT files
- source: BIA_STAGE43T_TITLE_PROMPT_FIX.iso
- output: BIA_STAGE69_NONMDI_INT92_TEST.iso

The 967 compiled-MDI rows are intentionally not applied yet.
The 106 movie-ST1 rows are intentionally preserved exactly.

## Starting Status
IN_PROGRESS
""",encoding="utf-8")
else:
    old=step.read_text(encoding="utf-8",errors="replace") if step.exists() else "# STEP 069\n"
    step.write_text(old.rstrip()+f"""

## Completion Update
Time: {now}
Result: {status}
Detail: {a.detail}

## Verification Boundary
Static build/readback only. Do not mark these 92 rows VERIFIED_APPLIED until a
runtime test confirms the relevant dynamic INT path and font rendering.

## Next Step
Runtime canary on a visible skirmish/menu INT string, then proceed to the
967 compiled-MDI bulk patch path if the canary is sound.
""",encoding="utf-8")
