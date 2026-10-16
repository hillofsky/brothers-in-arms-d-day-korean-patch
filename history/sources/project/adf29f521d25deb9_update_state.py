#!/usr/bin/env python3
"""Non-destructive STEP086 state tracking; does not promote a captured image to a verified fix."""
import argparse, datetime, re, os, shutil
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument('--root',required=True)
p.add_argument('--runid',required=True)
p.add_argument('--phase',choices=['success','failure'],required=True)
p.add_argument('--run-dir',required=True)
p.add_argument('--detail',default='')
a=p.parse_args()
root=Path(a.root);state=root/'PROJECT_STATE.md';folder=Path(a.run_dir)
if not state.is_file():
    raise FileNotFoundError('Expected existing PROJECT_STATE, will not regenerate it: '+str(state))
backup=folder/'PROJECT_STATE_BEFORE_STEP086.md'
if not backup.is_file():shutil.copy2(state,backup)
now=datetime.datetime.now().astimezone().isoformat(timespec='seconds')
status='WATCH_TRACE_COLLECTED_UNVERIFIED' if a.phase=='success' else 'FAILED'
text=f'''<!-- STEP_086_MANAGED_BEGIN -->
## STEP_086 Mission2 live RAM read-watch trace
Last Updated: {now}
Status: {status}
Run: {a.runid}
Capture: key-1 PPSSPP screenshot and nonpausing memory read watchpoints at 4 scene-specific addresses; interpreter mode.
Stage79 compiled967: BUILT_UNVERIFIED, second-mission Korean fallback UNRESOLVED.
INT92: BUILT_UNVERIFIED.
New Objective: UNRESOLVED.
Six deferred movie tests: NOT RESUMED.
Stage69/Stage79 ISO changes: NONE attempted.
No ISO/memory patch; hit counts are diagnostic and do not certify font selection or rendering.
Detail: {a.detail}
<!-- STEP_086_MANAGED_END -->'''
raw=state.read_text(encoding='utf-8-sig')
pat=re.compile(r'<!-- STEP_086_MANAGED_BEGIN -->.*?<!-- STEP_086_MANAGED_END -->',re.S)
upd=pat.sub(lambda _:text,raw) if pat.search(raw) else raw.rstrip()+'\n\n'+text+'\n'
tmp=state.with_name(state.name+'.STEP086.tmp')
tmp.write_text(upd,encoding='utf-8')
os.replace(tmp,state)
step=root/'log'/'steps'/'STEP_086.md';step.parent.mkdir(parents=True,exist_ok=True)
with step.open('a',encoding='utf-8') as f:
    f.write(f'{now} [{a.runid}] {status}: {a.detail}\n')
print('%s: %s'%(status,a.detail))
