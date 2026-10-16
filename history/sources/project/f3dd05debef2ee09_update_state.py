#!/usr/bin/env python3
from pathlib import Path
import argparse,datetime,re
ap=argparse.ArgumentParser()
ap.add_argument('--root',required=True)
ap.add_argument('--phase',required=True,choices=['start','success','failure'])
ap.add_argument('--detail',default='')
a=ap.parse_args()
root=Path(a.root);state=root/'PROJECT_STATE.md';step=root/'log'/'steps'/'STEP_081.md'
step.parent.mkdir(parents=True,exist_ok=True)
now=datetime.datetime.now().astimezone().isoformat(timespec='seconds')
status={'start':'IN_PROGRESS','success':'VERIFIED','failure':'FAILED'}[a.phase]
block=f'''<!-- STEP_081_MANAGED_BEGIN -->
## STEP_081 Runtime QA
Last Updated: {now}
Step execution status: {status}
Goal: Recognize the Story submenu separately from main menu; safely select highlighted New Game using isolated PPSSPP memory stick and collect 70s of post-selection evidence.
Stage79 ISO static build: BUILT_UNVERIFIED (967 compiled IDs)
Compiled967 visual runtime verified: NO
INT92 visual runtime verified: NO
Six deferred movie playback validations resumed: NO
User's original PPSSPP saves intended to remain untouched: YES; test-only memory stick
ISO modification: NO
Detail: {a.detail}
<!-- STEP_081_MANAGED_END -->'''
txt=state.read_text(encoding='utf-8',errors='replace') if state.exists() else '# PROJECT STATE\n'
pat=re.compile(r'<!-- STEP_081_MANAGED_BEGIN -->.*?<!-- STEP_081_MANAGED_END -->',re.S)
txt=pat.sub(block,txt) if pat.search(txt) else txt.rstrip()+'\n\n'+block+'\n'
state.write_text(txt,encoding='utf-8')
if a.phase=='start':
 step.write_text('''# STEP 081\n\nStatus: IN_PROGRESS\n\nSTEP080 showed an actual Story submenu (Continue, New Game, Chapter), wrongly classified as unchanged main menu by previous broad background signature. STEP081 independently verifies submenu using localized screen ROIs, isolates all save data with PPSSPP `--memstick`, selects New Game, and collects screenshots/RAM. No ISO writes.\n''',encoding='utf-8')
else:
 old=step.read_text(encoding='utf-8',errors='replace') if step.exists() else '# STEP 081\n'
 step.write_text(old.rstrip()+f'\n\nTime: {now}\nStatus: {status}\nDetail: {a.detail}\n',encoding='utf-8')
