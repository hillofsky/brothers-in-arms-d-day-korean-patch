#!/usr/bin/env python3
from pathlib import Path
import argparse,datetime,re
p=argparse.ArgumentParser()
p.add_argument('--root',required=True)
p.add_argument('--phase',required=True,choices=['start','success','failure'])
p.add_argument('--detail',default='')
a=p.parse_args()
root=Path(a.root);state=root/'PROJECT_STATE.md';step=root/'log'/'steps'/'STEP_077.md'
step.parent.mkdir(parents=True,exist_ok=True)
now=datetime.datetime.now().astimezone().isoformat(timespec='seconds')
status={'start':'IN_PROGRESS','success':'VERIFIED','failure':'FAILED'}[a.phase]
text=state.read_text(encoding='utf-8',errors='replace') if state.exists() else '# PROJECT STATE\n'
block=f'''<!-- STEP_077_MANAGED_BEGIN -->
## STEP_077 Relocation Payload Correlation
Updated: {now}
Status: {status}
Goal: Test actual relocation source/target payload fingerprints across 32 DSLs against the verified first mission; no unproven DSL patch locations will be applied.
ISO modified: NO
INT92 status: BUILT_UNVERIFIED
Compiled967 status: NOT_BUILT
Movie playback validation resumed: NO
Detail: {a.detail}
<!-- STEP_077_MANAGED_END -->'''
regex=re.compile(r'<!-- STEP_077_MANAGED_BEGIN -->.*?<!-- STEP_077_MANAGED_END -->',re.S)
text=regex.sub(block,text) if regex.search(text) else text.rstrip()+'\n\n'+block+'\n'
state.write_text(text,encoding='utf-8')
if a.phase=='start':
    step.write_text('# STEP_077\n\nStatus: IN_PROGRESS\n\nRead-only DSL pointer payload correlation.\n',encoding='utf-8')
else:
    old=step.read_text(encoding='utf-8',errors='replace') if step.exists() else '# STEP_077\n'
    step.write_text(old.rstrip()+f'\n\nTime: {now}\nResult: {status}\nDetail: {a.detail}\nISO modified: NO\n',encoding='utf-8')
