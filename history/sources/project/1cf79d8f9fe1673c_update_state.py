#!/usr/bin/env python3
"""Conservative, append-only BIA STEP084 project status update."""
import argparse
import datetime
from pathlib import Path
import os
import re
import shutil
p=argparse.ArgumentParser()
p.add_argument('--root',required=True)
p.add_argument('--runid',required=True)
p.add_argument('--phase',choices=['success','failure'],required=True)
p.add_argument('--run-dir',required=True)
a=p.parse_args()
root=Path(a.root)
state=root/'PROJECT_STATE.md'
step=root/'log'/'steps'/'STEP_084.md'
run_dir=Path(a.run_dir)
step.parent.mkdir(parents=True,exist_ok=True)
now=datetime.datetime.now().astimezone().isoformat(timespec='seconds')
status='VERIFIED_OFFLINE_DIAGNOSTIC' if a.phase=='success' else 'FAILED'
text=f'''<!-- STEP_084_MANAGED_BEGIN -->
## STEP_084 offline font forensics from STEP 083 FIX1
Last Updated: {now}
Status: {status}
Run: {a.runid}
Evidence: STEP083 FIX1, RAM 32 MiB, Korean strings and 878-glyph font objects. Read-only.
Stage79 compiled967: BUILT_UNVERIFIED, second-mission Korean fallback UNRESOLVED.
INT92: BUILT_UNVERIFIED.
New Objective: UNRESOLVED.
Six deferred movie tests: NOT RESUMED.
No ISO changed. No PPSSPP launched. No glyph-render fix applied.
Visual QA: STEP083 FIX1 supplied frame did not display broken Korean text.
<!-- STEP_084_MANAGED_END -->'''
if not state.is_file():
    raise FileNotFoundError('Not creating incomplete PROJECT_STATE; expected '+str(state))
backup=run_dir/'PROJECT_STATE_BEFORE_STEP084.md'
if not backup.exists():shutil.copy2(state,backup)
raw=state.read_text(encoding='utf-8-sig')
pattern=re.compile(r'<!-- STEP_084_MANAGED_BEGIN -->.*?<!-- STEP_084_MANAGED_END -->',re.S)
updated=pattern.sub(lambda _:text,raw) if pattern.search(raw) else raw.rstrip()+'\n\n'+text+'\n'
tmp=state.with_name(state.name+'.STEP084.tmp')
tmp.write_text(updated,encoding='utf-8')
os.replace(tmp,state)
entry=f'{now} [{a.runid}] {status}: STEP083 RAM cross checked, Korean 26/26 mappings, actual broken frame not captured; no ISO writes.\n'
with step.open('a',encoding='utf-8') as f:f.write(entry)
print(entry.strip())
