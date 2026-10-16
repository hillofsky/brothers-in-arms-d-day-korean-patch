#!/usr/bin/env python3
from pathlib import Path
import argparse,datetime,re
ap=argparse.ArgumentParser()
ap.add_argument("--root",required=True)
ap.add_argument("--phase",choices=["start","success","failure"],required=True)
ap.add_argument("--detail",default="")
a=ap.parse_args()
root=Path(a.root);state=root/"PROJECT_STATE.md";log=root/"log"/"steps"/"STEP_080.md"
log.parent.mkdir(parents=True,exist_ok=True)
now=datetime.datetime.now().astimezone().isoformat(timespec="seconds")
st={"start":"IN_PROGRESS","success":"VERIFIED","failure":"FAILED"}[a.phase]
block=f"""<!-- STEP_080_MANAGED_BEGIN -->
## STEP_080 Live State
Last Updated: {now}
Status: {st}
Purpose: Runtime smoke for Stage79: exact ISO identity + independent PPSSPP title/main-menu signature, then observe Story-entry frames and select compiled-MDI RAM canaries.
Stage79 ISO: BIA_STAGE79_COMPILED967_STRUCTURAL_TEST.iso
Stage79 compile status: BUILT_UNVERIFIED
Compiled967 visual runtime verified: NO
INT92 visual runtime verified: NO
Six deferred movie playback validations: NOT_RESUMED
ISO modification: NO
Details: {a.detail}
<!-- STEP_080_MANAGED_END -->"""
txt=state.read_text(encoding="utf-8",errors="replace") if state.exists() else "# PROJECT STATE\n"
pat=re.compile(r"<!-- STEP_080_MANAGED_BEGIN -->.*?<!-- STEP_080_MANAGED_END -->",re.S)
txt=pat.sub(block,txt) if pat.search(txt) else txt.rstrip()+"\n\n"+block+"\n"
state.write_text(txt,encoding="utf-8")
if a.phase=="start":
    log.write_text("# STEP 080\n\nStatus: IN_PROGRESS\n\nDedicated PPSSPP instance and port, exact Stage79 ISO identity, verified known title/menu signatures, observed Story entry and read-only RAM canaries. No 967 runtime promotion without new visual evidence.\n",encoding="utf-8")
else:
    old=log.read_text(encoding="utf-8",errors="replace") if log.exists() else "# STEP 080\n"
    log.write_text(old.rstrip()+f"\n\nTime: {now}\nStatus: {st}\nDetail: {a.detail}\n",encoding="utf-8")
