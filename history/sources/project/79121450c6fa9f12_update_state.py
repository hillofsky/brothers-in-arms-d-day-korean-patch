#!/usr/bin/env python3
from pathlib import Path
import argparse,datetime,re
ap=argparse.ArgumentParser()
ap.add_argument("--root",required=True)
ap.add_argument("--phase",required=True,choices=["start","success","failure"])
ap.add_argument("--detail",default="")
a=ap.parse_args()
root=Path(a.root);log=root/"log";state=root/"PROJECT_STATE.md";step=log/"steps"/"STEP_068_FIX1.md"
step.parent.mkdir(parents=True,exist_ok=True)
now=datetime.datetime.now().astimezone().isoformat(timespec="seconds")
status={"start":"IN_PROGRESS","success":"VERIFIED","failure":"FAILED"}[a.phase]
txt=state.read_text(encoding="utf-8",errors="replace") if state.exists() else "# PROJECT STATE\n\nWorking Directory: PROJECT_ROOT\n"
block=f"""<!-- STEP_068_FIX1_MANAGED_BEGIN -->
## STEP_068 FIX1 Live State
Last Updated: {now}
Status: {status}
Goal: Correct STEP068's invalid movie-count assumption and derive the final 1165-ID apply split directly from the 133 real Stage42A ST1 fields.
Original STEP068 failure: expected movie overlap 71, actual derived overlap 106.
ISO modified in this step: NO
Deferred movie playback validation resumed: NO
Detail: {a.detail}
<!-- STEP_068_FIX1_MANAGED_END -->"""
pat=re.compile(r"<!-- STEP_068_FIX1_MANAGED_BEGIN -->.*?<!-- STEP_068_FIX1_MANAGED_END -->",re.S)
txt=pat.sub(block,txt) if pat.search(txt) else txt.rstrip()+"\n\n"+block+"\n"
state.write_text(txt,encoding="utf-8")
if a.phase=="start":
    step.write_text("""# STEP 068 FIX1

## Failure Diagnosis
STEP_068 failed safely at its final assertion:
`Expected refined exact movie set of 71, got 106`.

The value 71 was inferred incorrectly from STEP067's broad historical-evidence
count. The authoritative source is Stage42A's actual 133 ST1 subtitle fields.

The failed STEP_068 made no ISO modifications.

## Goal
- derive exact/segment/normalized ST1 overlap from the actual Stage42A fields
- verify all 8 Stage42H ST1 files are preserved byte-for-byte in Stage43T
- refine the true non-movie remainder
- produce the complete 1165-ID apply split

## Result
IN_PROGRESS
""",encoding="utf-8")
else:
    old=step.read_text(encoding="utf-8",errors="replace") if step.exists() else "# STEP 068 FIX1\n"
    step.write_text(old.rstrip()+f"""

## Completion Update
Time: {now}
Result: {status}
Detail: {a.detail}

## Verification
Static reconciliation only. No ISO mutation and no deferred movie playback validation.

## Next Step
Build the actual patcher for 967 compiled-MDI IDs and the 92 non-MDI/INT IDs,
while preserving the 106 movie-ST1 IDs already carried by Stage43T.
""",encoding="utf-8")
