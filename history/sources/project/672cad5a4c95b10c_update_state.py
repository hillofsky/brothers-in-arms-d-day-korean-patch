#!/usr/bin/env python3
from pathlib import Path
import argparse,datetime,re
ap=argparse.ArgumentParser()
ap.add_argument("--root",required=True)
ap.add_argument("--phase",required=True,choices=["start","captured","failure"])
ap.add_argument("--detail",default="")
a=ap.parse_args()
root=Path(a.root);state=root/"PROJECT_STATE.md";step=root/"log"/"steps"/"STEP_070_FIX6.md"
step.parent.mkdir(parents=True,exist_ok=True)
now=datetime.datetime.now().astimezone().isoformat(timespec="seconds")
status={"start":"IN_PROGRESS","captured":"BUILT_UNVERIFIED","failure":"FAILED"}[a.phase]
txt=state.read_text(encoding="utf-8",errors="replace") if state.exists() else "# PROJECT STATE\n\nWorking Directory: PROJECT_ROOT\n"
block=f"""<!-- STEP_070_FIX6_MANAGED_BEGIN -->
## STEP_070 FIX6 Live State
Last Updated: {now}
Status: {status}
Goal: Reuse the proven Stage40Y runtime method: software renderer, dedicated debugger WebSocket, input.buttons.send, and raw RGB565 VRAM captures at 0x04000000/0x04044000.
INT92 static build: BUILT_UNVERIFIED
INT92 promoted to VERIFIED_APPLIED: NO
Compiled-MDI 967 applied: NO
Movie playback validation resumed: NO
Detail: {a.detail}
<!-- STEP_070_FIX6_MANAGED_END -->"""
pat=re.compile(r"<!-- STEP_070_FIX6_MANAGED_BEGIN -->.*?<!-- STEP_070_FIX6_MANAGED_END -->",re.S)
txt=pat.sub(block,txt) if pat.search(txt) else txt.rstrip()+"\n\n"+block+"\n"
state.write_text(txt,encoding="utf-8")
if a.phase=="start":
    step.write_text("""# STEP 070 FIX6

## Goal
Return to the runtime method already proven in the earlier BIA Stage40Y work.

- Software renderer through temporary appendconfig
- Dedicated BIA debugger port 26420..26439
- Verify listener owner PID and exact ISO process command line
- WebSocket `input.buttons.send` on/off input
- Raw VRAM reads from 0x04000000 and 0x04044000
- RGB565, stride 512, visible 480x272
- No GPU screenshot/renderColor
- No Windows desktop/window screenshot

## Result
IN_PROGRESS
""",encoding="utf-8")
else:
    old=step.read_text(encoding="utf-8",errors="replace") if step.exists() else "# STEP 070 FIX6\n"
    step.write_text(old.rstrip()+f"""

## Completion Update
Time: {now}
Result: {status}
Detail: {a.detail}

## Boundary
Runtime route discovery only. INT92 remains BUILT_UNVERIFIED until a visible
target translation is confirmed in the intended screen.
""",encoding="utf-8")
