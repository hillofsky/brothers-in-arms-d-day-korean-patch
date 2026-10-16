#!/usr/bin/env python3
from pathlib import Path
import argparse,datetime,re
ap=argparse.ArgumentParser()
ap.add_argument('--root',required=True);ap.add_argument('--phase',required=True,choices=['start','success','failure']);ap.add_argument('--detail',default='')
a=ap.parse_args();root=Path(a.root);state=root/'PROJECT_STATE.md';step=root/'log'/'steps'/'STEP_075.md'
step.parent.mkdir(parents=True,exist_ok=True)
now=datetime.datetime.now().astimezone().isoformat(timespec='seconds')
status={'start':'IN_PROGRESS','success':'VERIFIED','failure':'FAILED'}[a.phase]
txt=state.read_text(encoding='utf-8',errors='replace') if state.exists() else '# PROJECT STATE\n'
block=f"""<!-- STEP_075_MANAGED_BEGIN -->
## STEP_075 DSL Variant Audit
Last Updated: {now}
Status: {status}
Purpose: Characterize exact 32 MDI/DSL/DSX texture relocation variants; no ISO writes.
Stage69 INT92: BUILT_UNVERIFIED
Compiled MDI 967: NOT BUILT
Movie playback validation: DEFERRED
Detail: {a.detail}
<!-- STEP_075_MANAGED_END -->"""
pat=re.compile(r'<!-- STEP_075_MANAGED_BEGIN -->.*?<!-- STEP_075_MANAGED_END -->',re.S)
txt=pat.sub(block,txt) if pat.search(txt) else txt.rstrip()+'\n\n'+block+'\n'
state.write_text(txt,encoding='utf-8')
if a.phase=='start': step.write_text('# STEP 075\n\nNo ISO mutation. Investigate absent first-mission DSL relocation signature in 31 other MDIs.\n',encoding='utf-8')
else:
 old=step.read_text(encoding='utf-8',errors='replace') if step.exists() else '# STEP 075\n'
 step.write_text(old+f'\nTime: {now}\nStatus: {status}\nDetail: {a.detail}\n',encoding='utf-8')
