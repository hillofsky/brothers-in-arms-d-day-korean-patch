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
step=root/"log"/"steps"/"STEP_044.md"
step.parent.mkdir(parents=True,exist_ok=True)
now=datetime.datetime.now().astimezone().isoformat(timespec="seconds")
status={"start":"IN_PROGRESS","success":"VERIFIED","failure":"FAILED"}[a.phase]

if state.exists():
    txt=state.read_text(encoding="utf-8",errors="replace")
else:
    txt="# PROJECT STATE\n\nProject: Brothers in Arms D-Day Korean Localization\nWorking Directory: PROJECT_ROOT\n"

block=f"""<!-- STEP_044_MANAGED_BEGIN -->
## STEP_044 Live State
Last Updated: {now}
Status: {status}
Goal: Discover the next untranslated campaign mission and export a stable TSV.
Base Build: PROJECT_ROOT/BIA_STAGE43T_TITLE_PROMPT_FIX.iso
ISO modification in this step: NO
Remaining movie validation resumed: NO
Detail: {a.detail or "(none)"}
<!-- STEP_044_MANAGED_END -->"""
pat=re.compile(r"<!-- STEP_044_MANAGED_BEGIN -->.*?<!-- STEP_044_MANAGED_END -->",re.S)
txt=pat.sub(block,txt) if pat.search(txt) else txt.rstrip()+"\n\n"+block+"\n"
state.write_text(txt,encoding="utf-8")

if a.phase=="start":
    body=f"""# STEP 044

## Goal
Discover the next untranslated campaign mission and export a stable TSV.

## Starting State
- Project root: PROJECT_ROOT
- Base build: PROJECT_ROOT/BIA_STAGE43T_TITLE_PROMPT_FIX.iso
- First mission D0_0130_.MDI: 137 units VERIFIED/APPLIED.
- Second mission D0_0700_.MDI: 90 units TRANSLATED_PENDING_APPLY.
- Remaining six movie playback validations: DEFERRED BY USER.

## Retry History
- FIX1 packaging layout error: run.ps1 nested one level too deep.
- FIX2: project path corrected to PROJECT_ROOT, but discovery only saw six handoff JSONs and found no remaining mission groups.
- FIX3: FAILED before discovery started because PowerShell Start-Process split the --detail argument on spaces.
- FIX4: same full structured-data scan, but Python is invoked directly with an argument array.

## Work Performed
Step started. No ISO modification.

## Result
IN_PROGRESS
"""
else:
    old=step.read_text(encoding="utf-8",errors="replace") if step.exists() else "# STEP 044\n"
    body=old.rstrip()+f"\n\n## Update {now}\nResult: {status}\nDetail: {a.detail}\n"
step.write_text(body,encoding="utf-8")
