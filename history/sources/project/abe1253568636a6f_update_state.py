#!/usr/bin/env python3
"""Update only STEP_095_FIX1 section. Preserve every previously recorded stage."""
import argparse, datetime, os, re, shutil
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument('--root',required=True)
p.add_argument('--runid',required=True)
p.add_argument('--phase',choices=('success','failure'),required=True)
p.add_argument('--run-dir',required=True)
p.add_argument('--detail',default='')
a=p.parse_args()
root=Path(a.root)
state=root/'PROJECT_STATE.md'
folder=Path(a.run_dir)
if not state.is_file():
    raise FileNotFoundError('PROJECT_STATE.md missing: will not replace cumulative history')
backup=folder/'PROJECT_STATE_BEFORE_STEP095_FIX1.md'
if not backup.is_file(): shutil.copy2(state,backup)
now=datetime.datetime.now().astimezone().isoformat(timespec='seconds')
status='CAPTURED_UNVERIFIED' if a.phase=='success' else 'FAILED'
section=f'''<!-- STEP_095_FIX1_MANAGED_BEGIN -->
## STEP 095 FIX1 — Passive nonintrusive font-owner field sampling
Last Updated: {now}
Status: {status}
Run: {a.runid}
Probe: passive WebSocket memory.read of owner 0x09A69A90+0x28, NO breakpoints or CPU pause; no PSP RAM writes.
Stage79: BUILT_UNVERIFIED; Mission2 Korean > rendering UNRESOLVED.
INT92: BUILT_UNVERIFIED; New Objective: UNRESOLVED; six video checks DEFERRED.
Original ISO, Stage69/79 ISO and existing save data: NEVER MODIFIED OR DELETED.
No PSP RAM modification, no Korean render fix claimed. STEP091-093 confirmed missing Hangul in active 150-glyph font; STEP093 established RA=0x089F64C8, via wrapper 0x089F6430. STEP094 proved indirect JALR at 0x089F6F0C and owner+0x28=0x09A74150. STEP095 FIX1 samples field changes; no instruction writer provenance is claimed and no patch applied.
Detail: {a.detail}
<!-- STEP_095_FIX1_MANAGED_END -->'''
raw=state.read_text(encoding='utf-8-sig')
pattern=re.compile(r'<!-- STEP_095_FIX1_MANAGED_BEGIN -->.*?<!-- STEP_095_FIX1_MANAGED_END -->',re.S)
new=pattern.sub(lambda _:section,raw) if pattern.search(raw) else raw.rstrip()+'\n\n'+section+'\n'
tmp=state.with_name(state.name+'.STEP095FIX1.tmp')
tmp.write_text(new,encoding='utf-8')
os.replace(tmp,state)
logstep=root/'log'/'steps'/'STEP_095_FIX1.md'
logstep.parent.mkdir(parents=True,exist_ok=True)
with logstep.open('a',encoding='utf-8') as f:
    f.write(f'{now} [{a.runid}] {status}: {a.detail}\n')
print(status,a.runid)
