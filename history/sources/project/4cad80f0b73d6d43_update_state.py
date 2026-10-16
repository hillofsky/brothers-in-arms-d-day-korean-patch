#!/usr/bin/env python3
from pathlib import Path
import argparse,datetime,re
ap=argparse.ArgumentParser()
ap.add_argument('--root',required=True);ap.add_argument('--phase',required=True,choices=['start','success','failure']);ap.add_argument('--detail',default='')
a=ap.parse_args(); root=Path(a.root);state=root/'PROJECT_STATE.md'; step=root/'log'/'steps'/'STEP_076.md';step.parent.mkdir(parents=True,exist_ok=True)
now=datetime.datetime.now().astimezone().isoformat(timespec='seconds')
status={'start':'IN_PROGRESS','success':'VERIFIED','failure':'FAILED'}[a.phase]
txt=state.read_text(encoding='utf-8',errors='replace') if state.exists() else '# PROJECT STATE\n'
block=f"""<!-- STEP_076_MANAGED_BEGIN -->
## STEP_076 Targeted DSL Analysis
Last Updated: {now}
Status: {status}
Goal: Identify candidate DSL relocation-copy runs and TEXSIZE GPU command context per MDI using the original and Stage69 first-mission control, without mutation.
INT92: BUILT_UNVERIFIED
Compiled-MDI 967 applied: NO
Compiled-MDI 967 runtime verified: NO
Movie playback validations resumed: NO
ISO modified: NO
Detail: {a.detail}
<!-- STEP_076_MANAGED_END -->"""
pat=re.compile(r'<!-- STEP_076_MANAGED_BEGIN -->.*?<!-- STEP_076_MANAGED_END -->',re.S)
txt=pat.sub(block,txt) if pat.search(txt) else txt.rstrip()+'\n\n'+block+'\n';state.write_text(txt,encoding='utf-8')
if a.phase=='start':step.write_text('# STEP 076\n\nIN_PROGRESS: targeted DSL analysis only; no ISO writes.\n',encoding='utf-8')
else:
 old=step.read_text(encoding='utf-8',errors='replace') if step.exists() else '# STEP 076\n'
 step.write_text(old.rstrip()+f'\n\nTime: {now}\nStatus: {status}\nDetail: {a.detail}\nISO modified: NO\n',encoding='utf-8')
