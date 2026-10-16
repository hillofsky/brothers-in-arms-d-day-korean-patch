#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from pathlib import Path
import argparse, datetime, re
ap=argparse.ArgumentParser()
ap.add_argument("--root",required=True)
ap.add_argument("--phase",choices=["start","success","failure"],required=True)
ap.add_argument("--detail",default="")
a=ap.parse_args()
root=Path(a.root)
state=root/"PROJECT_STATE.md"
step=root/"log"/"steps"/"STEP_079.md"
step.parent.mkdir(parents=True,exist_ok=True)
now=datetime.datetime.now().astimezone().isoformat(timespec="seconds")
state_type={"start":"IN_PROGRESS","success":"BUILT_UNVERIFIED","failure":"FAILED"}[a.phase]
txt=state.read_text(encoding="utf-8",errors="replace") if state.exists() else "# PROJECT STATE\n"
block=f"""<!-- STEP_079_MANAGED_BEGIN -->
## STEP_079 Compiled967 Structural DSL Build
Last Updated: {now}
Status: {state_type}
Goal: Stage69-based compiled967 bulk ISO. Per-MDI exact STEP076 relocation + GPU evidence. Dry-run all 32 before build, golden DSL control, preserved INT/movie/menu.
Source ISO: BIA_STAGE69_FIX2_NONMDI_INT92_TEST.iso
Output ISO: BIA_STAGE79_COMPILED967_STRUCTURAL_TEST.iso (only on complete success)
MDIs: 32; FString structural refs: 2333; Compiled IDs: 967
First mission Stage43A runtime result: previously VERIFIED, preserved (not re-tested)
INT92 runtime status: BUILT_UNVERIFIED
Compiled967 runtime status: NOT VERIFIED
Movies: 106 ST1 translation resources preserved, 6 movie playback tests deferred
New Objective popup English title: unresolved
Detail: {a.detail}
<!-- STEP_079_MANAGED_END -->"""
pat=re.compile(r"<!-- STEP_079_MANAGED_BEGIN -->.*?<!-- STEP_079_MANAGED_END -->",re.S)
txt=pat.sub(block,txt) if pat.search(txt) else txt.rstrip()+"\n\n"+block+"\n"
state.write_text(txt,encoding="utf-8")
if a.phase=="start":
 step.write_text("""# STEP 079
Status: IN_PROGRESS

Based on actual STEP078 original+patched first mission binaries and STEP076
per-MDI relocation/GPU context across all 32 MDIs.

Preflight:
- Original ISO/Stage69 SHA-256 exact
- Positive control: original D0_0130_ DSL + structural patch == Stage69 D0_0130_ DSL byte-for-byte
- Unique last-nine relocation candidate per STEP076 ranked-group neighborhoods
- Preserve original font role1 texture object pointer per MDI
- Exact measured relocation triple, contiguous trailing 8 records, TBP0/TBW0/TSIZE0
- 32 MDI full dry-run before creating any output file
- Final 967 IDs / 2333 refs / 32 MDI ISO static readbacks
- INT92, 8 movie ST1, menu/title preserved, source ISO hash stable

Success is BUILT_UNVERIFIED: not a runtime verification.
""",encoding="utf-8")
else:
 old=step.read_text(encoding="utf-8",errors="replace") if step.exists() else "# STEP 079\n"
 step.write_text(old.rstrip()+f"\n\nTime: {now}\nStatus: {state_type}\nDetail: {a.detail}\n",encoding="utf-8")
