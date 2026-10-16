#!/usr/bin/env python3
from pathlib import Path
import argparse, datetime, re

ap = argparse.ArgumentParser()
ap.add_argument("--root", required=True)
ap.add_argument("--phase", required=True, choices=["start", "success", "failure"])
ap.add_argument("--detail", default="")
a = ap.parse_args()

root = Path(a.root)
state = root / "PROJECT_STATE.md"
step = root / "log" / "steps" / "STEP_074_FIX3.md"
step.parent.mkdir(parents=True, exist_ok=True)

now = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
status = {"start": "IN_PROGRESS", "success": "BUILT_UNVERIFIED", "failure": "FAILED"}[a.phase]

txt = state.read_text(encoding="utf-8", errors="replace") if state.exists() else "# PROJECT STATE\n"
block = f"""<!-- STEP_074_FIX3_MANAGED_BEGIN -->
## STEP_074 FIX3 Live State
Last Updated: {now}
Status: {status}
Goal: Retry compiled967 bulk build with campaign-original TMR18 metrics derived from the exact D0_0130_ original font (128x512), rather than reusing the Stage36 menu-font 128x256 metric.
Source baseline: BIA_STAGE69_FIX2_NONMDI_INT92_TEST.iso
INT92 runtime status: BUILT_UNVERIFIED
Compiled-MDI 967 runtime verified: NO
Movie playback validation resumed: NO
New Objective popup title fixed: NO
Detail: {a.detail}
<!-- STEP_074_FIX3_MANAGED_END -->"""

pat = re.compile(r"<!-- STEP_074_FIX3_MANAGED_BEGIN -->.*?<!-- STEP_074_FIX3_MANAGED_END -->", re.S)
txt = pat.sub(block, txt) if pat.search(txt) else txt.rstrip() + "\n\n" + block + "\n"
state.write_text(txt, encoding="utf-8")

if a.phase == "start":
    step.write_text("""# STEP 074 FIX3

## Root cause
FIX2 correctly changed the ORIGINAL TMR18 renderer-page arrays to one entry,
but then incorrectly reused Stage36's MENU-font logical-height expectation
(256) for the CAMPAIGN original font.

The exact original D0_0130_ font read during FIX2 is:
- width = 128
- height = 512

This does not conflict with the proven Korean expanded runtime form:
- four logical pages
- widths = [128,128,128,128]
- heights = [256,256,256,256]

FIX3 uses D0_0130_'s untouched original 128x512 font as the fingerprint for
discovering equivalent campaign font objects in the other MDIs.

## Result
IN_PROGRESS
""", encoding="utf-8")
else:
    old = step.read_text(encoding="utf-8", errors="replace") if step.exists() else "# STEP 074 FIX3\n"
    step.write_text(
        old.rstrip() + f"\n\nTime: {now}\nResult: {status}\nDetail: {a.detail}\n",
        encoding="utf-8"
    )
