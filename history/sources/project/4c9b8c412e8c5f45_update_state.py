#!/usr/bin/env python3
from pathlib import Path
import argparse,datetime,re
ap=argparse.ArgumentParser()
ap.add_argument("--root",required=True)
ap.add_argument("--phase",required=True,choices=["start","built","failure"])
ap.add_argument("--detail",default="")
a=ap.parse_args()
root=Path(a.root);log=root/"log";state=root/"PROJECT_STATE.md";step=log/"steps"/"STEP_069_FIX1.md"
step.parent.mkdir(parents=True,exist_ok=True)
now=datetime.datetime.now().astimezone().isoformat(timespec="seconds")
status={"start":"IN_PROGRESS","built":"BUILT_UNVERIFIED","failure":"FAILED"}[a.phase]
txt=state.read_text(encoding="utf-8",errors="replace") if state.exists() else "# PROJECT STATE\n\nWorking Directory: PROJECT_ROOT\n"
block=f"""<!-- STEP_069_FIX1_MANAGED_BEGIN -->
## STEP_069 FIX1 Live State
Last Updated: {now}
Status: {status}
Goal: Retry the 92-ID / 99-occurrence INT-only test build using verified section+key identity as the primary locator and logging Stage43T value drift.
Original STEP069 failure: first unique section/key had a current value different from its Stage38 original.
Source Stage43T ISO preserved: YES
Compiled-MDI 967 applied: NO
Movie-ST1 106 repatched: NO
Runtime verification complete: NO
Detail: {a.detail}
<!-- STEP_069_FIX1_MANAGED_END -->"""
pat=re.compile(r"<!-- STEP_069_FIX1_MANAGED_BEGIN -->.*?<!-- STEP_069_FIX1_MANAGED_END -->",re.S)
txt=pat.sub(block,txt) if pat.search(txt) else txt.rstrip()+"\n\n"+block+"\n"
state.write_text(txt,encoding="utf-8")
if a.phase=="start":
    step.write_text("""# STEP 069 FIX1

## Failure Diagnosis
STEP_069 failed safely on the first Stage43T value that had drifted from the
Stage38 original English value:
- resource: BIA-02123
- file: D10_0802_THEALLAMERICANS.INT
- section/key: [LocalizedStrings] HINT_G

Stage38 exact occurrence recovery already verified section/key provenance.
Therefore FIX1 treats a unique section+key as authoritative, logs the current
value, and replaces it with the final Korean value. Duplicate keys retain
stricter disambiguation.

## Output
PROJECT_ROOT\\BIA_STAGE69_FIX1_NONMDI_INT92_TEST.iso

## Result
IN_PROGRESS
""",encoding="utf-8")
else:
    old=step.read_text(encoding="utf-8",errors="replace") if step.exists() else "# STEP 069 FIX1\n"
    step.write_text(old.rstrip()+f"""

## Completion Update
Time: {now}
Result: {status}
Detail: {a.detail}

## Verification Boundary
Static build/readback only. The 92 rows remain unverified at runtime.
""",encoding="utf-8")
