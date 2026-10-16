#!/usr/bin/env python3
from pathlib import Path
import argparse,datetime,re
p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--phase',choices=['start','success','failure'],required=True);p.add_argument('--detail',default='');a=p.parse_args()
r=Path(a.root);s=r/'PROJECT_STATE.md';l=r/'log'/'steps'/'STEP_083.md';l.parent.mkdir(parents=True,exist_ok=True)
statuses={'start':'IN_PROGRESS','success':'VERIFIED_DIAGNOSTIC','failure':'FAILED'}
now=datetime.datetime.now().astimezone().isoformat(timespec='seconds')
block=f"""<!-- STEP_083_MANAGED_BEGIN -->
## STEP_083 live font probe
Last updated: {now}
Status: {statuses[a.phase]}
Purpose: collect a coherent LIVE PPSSPP snapshot of second-mission repeated `>` display, without modifying game ISO.
Stage79 compiled967: BUILT_UNVERIFIED with confirmed second-mission glyph-rendering failure.
First-mission English leftovers: known unresolved in MDI/INT; Stage82 evidence recorded.
Stage69/Stage79 ISO files: untouched.
Six deferred movie playback tests: NOT resumed.
Detail: {a.detail}
<!-- STEP_083_MANAGED_END -->"""
old=s.read_text(encoding='utf-8',errors='replace') if s.exists() else '# PROJECT STATE\n';pat=re.compile(r'<!-- STEP_083_MANAGED_BEGIN -->.*?<!-- STEP_083_MANAGED_END -->',re.S)
s.write_text(pat.sub(block,old) if pat.search(old) else old.rstrip()+'\n\n'+block+'\n',encoding='utf-8')
if a.phase=='start':l.write_text('# STEP 083\n\nIN_PROGRESS — live PSP RAM/VRAM font diagnostic only, no ISO modification.\n',encoding='utf-8')
else:l.write_text(l.read_text(encoding='utf-8',errors='replace')+f'\n{now}: {statuses[a.phase]} — {a.detail}\n',encoding='utf-8')
