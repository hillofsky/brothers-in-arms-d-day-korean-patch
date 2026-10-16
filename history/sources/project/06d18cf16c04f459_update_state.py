#!/usr/bin/env python3
from pathlib import Path
import argparse,datetime,re
ap=argparse.ArgumentParser()
ap.add_argument("--root",required=True)
ap.add_argument("--phase",required=True,choices=["start","success","failure"])
ap.add_argument("--detail",default="")
a=ap.parse_args()
root=Path(a.root);log=root/"log";state=root/"PROJECT_STATE.md";step=log/"steps"/"STEP_066.md"
step.parent.mkdir(parents=True,exist_ok=True)
now=datetime.datetime.now().astimezone().isoformat(timespec="seconds")
status={"start":"IN_PROGRESS","success":"VERIFIED","failure":"FAILED"}[a.phase]
txt=state.read_text(encoding="utf-8",errors="replace") if state.exists() else "# PROJECT STATE\n\nWorking Directory: PROJECT_ROOT\n"
block=f"""<!-- STEP_066_MANAGED_BEGIN -->
## STEP_066 Live State
Last Updated: {now}
Status: {status}
Goal: Correct STEP_065's overly narrow scanner by reproducing the proven all-stream FString audit through payload-to-pointer reverse tracing.
STEP_064 exact source map: VERIFIED
ISO modified in this step: NO
Remaining six movie validations resumed: NO
Detail: {a.detail}
<!-- STEP_066_MANAGED_END -->"""
pat=re.compile(r"<!-- STEP_066_MANAGED_BEGIN -->.*?<!-- STEP_066_MANAGED_END -->",re.S)
txt=pat.sub(block,txt) if pat.search(txt) else txt.rstrip()+"\n\n"+block+"\n"
state.write_text(txt,encoding="utf-8")
if a.phase=="start":
    step.write_text("""# STEP 066

## Reason
STEP_065 executed successfully, but its candidate-ID resolution was too strict:
it required the FString preceding a target value to equal that target's own INT
key. The proven Stage43 campaign audit only required the preceding FString to
be a valid key from the global INT key set, and scanned all streams.

## Goal
Re-run compiled FString discovery using:
1. exact target UTF-8 payload discovery in every MDI stream,
2. reverse lookup of pointers to those payloads,
3. FString structure validation,
4. the historical global-INT-key confidence rule,
5. all 57 Stage43T MDI files.

The already-verified D0_0700 mapping (90 units / 179 refs) is used as a canary.

## Starting State
- Unapplied campaign IDs: 1165
- NEEDS_TRANSLATION: 0
- ISO modification: none

## Result
IN_PROGRESS
""",encoding="utf-8")
else:
    old=step.read_text(encoding="utf-8",errors="replace") if step.exists() else "# STEP 066\n"
    step.write_text(old.rstrip()+f"""

## Completion Update
Time: {now}
Result: {status}
Detail: {a.detail}

## Verification
Audit only. No ISO/resource mutation is claimed.

## Next Step
Use the all-stream structural results and D0_0700 canary result to construct
the exact bulk patch manifest, or isolate only the genuinely unresolved class.
""",encoding="utf-8")
