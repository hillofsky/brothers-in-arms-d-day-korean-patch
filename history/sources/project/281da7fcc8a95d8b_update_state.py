#!/usr/bin/env python3
from pathlib import Path
import argparse,datetime,re
ap=argparse.ArgumentParser()
ap.add_argument("--root",required=True)
ap.add_argument("--phase",required=True,choices=["start","success","failure"])
ap.add_argument("--detail",default="")
a=ap.parse_args()
root=Path(a.root);state=root/"PROJECT_STATE.md";step=root/"log"/"steps"/"STEP_074_FIX1.md"
step.parent.mkdir(parents=True,exist_ok=True)
now=datetime.datetime.now().astimezone().isoformat(timespec="seconds")
status={"start":"IN_PROGRESS","success":"BUILT_UNVERIFIED","failure":"FAILED"}[a.phase]
txt=state.read_text(encoding="utf-8",errors="replace") if state.exists() else "# PROJECT STATE\n"
block=f"""<!-- STEP_074_FIX1_MANAGED_BEGIN -->
## STEP_074 FIX1 Live State
Last Updated: {now}
Status: {status}
Goal: Correct STEP074's false font assumption by installing the proven Stage39A/43A Korean font per target MDI, then apply all 967 IDs / 2333 exact FString refs across 32 MDIs.
Source baseline: BIA_STAGE69_FIX2_NONMDI_INT92_TEST.iso
INT92 runtime status: BUILT_UNVERIFIED
Compiled-MDI 967 runtime verified: NO
Movie 106 repatched: NO
Movie playback validation resumed: NO
New Objective popup title fixed: NO
Detail: {a.detail}
<!-- STEP_074_FIX1_MANAGED_END -->"""
pat=re.compile(r"<!-- STEP_074_FIX1_MANAGED_BEGIN -->.*?<!-- STEP_074_FIX1_MANAGED_END -->",re.S)
txt=pat.sub(block,txt) if pat.search(txt) else txt.rstrip()+"\n\n"+block+"\n"
state.write_text(txt,encoding="utf-8")
if a.phase=="start":
    step.write_text("""# STEP 074 FIX1

## Root cause fixed
STEP074 incorrectly assumed every untouched campaign/skirmish MDI already had
the Stage39A/43A Korean font mapping. The STEP066 `font_objects_found` table is
a structural candidate inventory, not proof that the Stage39A glyph map was
installed.

Only D0_0130_ currently has the proven Stage43A font.

FIX1:
- derives the original 151-glyph production-font fingerprint from the original
  D0_0130_ MDI's two known runtime-proven font objects;
- discovers the matching two font objects per untouched target MDI;
- derives that MDI's existing Latin16 texture object from its font texture array;
- installs Stage39A 847-glyph donor atlas/metadata plus that MDI's <=31 extra
  glyphs into streams34/35;
- patches the unique DSL relocation + B8 descriptor using the proven Stage40Y
  pattern;
- places translated payloads in stream35 from 0x10000;
- patches only the exact STEP066 FString metadata refs;
- dry-runs all 32 MDIs before creating an output ISO.

D0_0130_ preserves its existing Stage43A font/DSL and only appends the remaining
target payloads after existing stream35 data.

## Result
IN_PROGRESS
""",encoding="utf-8")
else:
    old=step.read_text(encoding="utf-8",errors="replace") if step.exists() else "# STEP 074 FIX1\n"
    step.write_text(old.rstrip()+f"\n\nTime: {now}\nResult: {status}\nDetail: {a.detail}\n",encoding="utf-8")
