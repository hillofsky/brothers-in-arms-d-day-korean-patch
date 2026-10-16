#!/usr/bin/env python3
"""Append a non-destructive STEP_083_FIX1 block, preserving STEP_083 and all other history."""
from pathlib import Path
import argparse, datetime, re, shutil, os
ap=argparse.ArgumentParser()
ap.add_argument('--root',required=True)
ap.add_argument('--phase',choices=['start','success','failure'],required=True)
ap.add_argument('--detail',default='')
ap.add_argument('--runid',required=True)
a=ap.parse_args()
r=Path(a.root)
state=r/'PROJECT_STATE.md'
step=r/'log'/'steps'/'STEP_083_FIX1.md'
step.parent.mkdir(parents=True, exist_ok=True)
status={'start':'IN_PROGRESS','success':'VERIFIED_DIAGNOSTIC','failure':'FAILED'}[a.phase]
now=datetime.datetime.now().astimezone().isoformat(timespec='seconds')
entry=f'{now} [{a.runid}] {status}: {a.detail}'
managed=f'''<!-- STEP_083_FIX1_MANAGED_BEGIN -->
## STEP_083 FIX1 live mission2 font probe (no ISO mutation)
Last updated: {now}
Status: {status}
Run: {a.runid}
Stage79: BUILT_UNVERIFIED; mission2 glyph display user-confirmed FAILED (repeated `>`).
INT92 runtime: BUILT_UNVERIFIED.
Movie playback tests (six deferred): NOT RESUMED.
Live snapshot collection: {'COMPLETE_DIAGNOSTIC_ONLY' if a.phase=='success' else 'NOT_VERIFIED'}
Detail: {a.detail}
<!-- STEP_083_FIX1_MANAGED_END -->'''
backup=r/'log'/'STEP_083_FIX1'/a.runid/'PROJECT_STATE_BEFORE_FIX1.md'
if a.phase=='start' and state.is_file() and not backup.exists():
    backup.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(state,backup)
original=state.read_text(encoding='utf-8-sig',errors='replace') if state.exists() else '# BIA PROJECT_STATE\n'
pattern=re.compile(r'<!-- STEP_083_FIX1_MANAGED_BEGIN -->.*?<!-- STEP_083_FIX1_MANAGED_END -->',re.S)
updated=pattern.sub(lambda _m:managed,original) if pattern.search(original) else original.rstrip()+'\n\n'+managed+'\n'
temp=state.with_name(state.name+'.STEP083FIX1.tmp')
temp.write_text(updated,encoding='utf-8')
os.replace(temp,state)
with step.open('a',encoding='utf-8') as f:
    f.write(entry+'\n')
print(entry)
