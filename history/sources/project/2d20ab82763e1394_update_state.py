#!/usr/bin/env python3
from pathlib import Path
import argparse,datetime,re
ap=argparse.ArgumentParser()
ap.add_argument("--phase",choices=["start","success","failure"],required=True)
ap.add_argument("--root",required=True)
ap.add_argument("--detail",default="")
a=ap.parse_args()
root=Path(a.root)
state=root/"PROJECT_STATE.md"
log=root/"log"/"steps"/"STEP_078.md"
log.parent.mkdir(parents=True,exist_ok=True)
t=datetime.datetime.now().astimezone().isoformat(timespec="seconds")
ss={"start":"IN_PROGRESS","success":"VERIFIED","failure":"FAILED"}[a.phase]
block=f"""<!-- STEP_078_MANAGED_BEGIN -->
## STEP_078 Live State
Last Updated: {t}
Status: {ss}
Purpose: Export verified original/patched first-mission MDI/DSL/DSX and representative other mission DSL/DSX/MDI binaries for offline semantic reverse engineering.
ISO modified: NO
Stage69 source: BIA_STAGE69_FIX2_NONMDI_INT92_TEST.iso
Compiled-MDI 967: NOT_BUILT
INT92 runtime status: BUILT_UNVERIFIED
Deferred movie tests: NOT_RESUMED
Detail: {a.detail}
<!-- STEP_078_MANAGED_END -->"""
s=state.read_text(encoding="utf-8",errors="replace") if state.exists() else "# PROJECT STATE\n"
pat=re.compile(r"<!-- STEP_078_MANAGED_BEGIN -->.*?<!-- STEP_078_MANAGED_END -->",re.S)
s=pat.sub(block,s) if pat.search(s) else s.rstrip()+"\n\n"+block+"\n"
state.write_text(s,encoding="utf-8")
if a.phase=="start":
    log.write_text("# STEP 078\n\nStatus: IN_PROGRESS\n\nExport representative original/modified BIA MDI/DSL/DSX for direct offline structural analysis. No ISO mutation.\n",encoding="utf-8")
else:
    old=log.read_text(encoding="utf-8",errors="replace") if log.exists() else "# STEP 078\n"
    log.write_text(old.rstrip()+f"\n\nTime: {t}\nStatus: {ss}\nDetail: {a.detail}\n",encoding="utf-8")
