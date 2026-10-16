#!/usr/bin/env python3
from pathlib import Path
import argparse, datetime, re

ap=argparse.ArgumentParser()
ap.add_argument('--project-root',required=True)
ap.add_argument('--phase',choices=['start','success','failure'],required=True)
ap.add_argument('--detail',default='')
a=ap.parse_args()
root=Path(a.project_root)
root.mkdir(parents=True,exist_ok=True)
(root/'logs'/'steps').mkdir(parents=True,exist_ok=True)
state=root/'PROJECT_STATE.md'
step=root/'logs'/'steps'/'STEP_044.md'
now=datetime.datetime.now().astimezone().isoformat(timespec='seconds')
status={'start':'IN_PROGRESS','success':'VERIFIED','failure':'FAILED'}[a.phase]

base='''# PROJECT STATE

Project: Brothers in Arms D-Day Korean Localization
Game: Brothers in Arms - D-Day (USA) (v1.01)
Working Directory: PROJECT_ROOT

## Current Goal
Complete Korean localization with reproducible translation/build/runtime records.

## Last Verified State
- Stage43T title prompt fix is visually VERIFIED on fresh boot.
- Stage43T menu entry after START is still PENDING; existing captures are transition-black frames.
- First campaign mission translation is applied and VERIFIED.
- Remaining six movie playback validations are deferred by user request.

## Important Technical Facts
- Current test ISO: PROJECT_ROOT/BIA_STAGE43T_TITLE_PROMPT_FIX.iso
- Stage43L discarded due to ELF error; R/R2 comparison-only; S intermediate-only.
- First mission D0_0130_.MDI: 137 units / 274 refs applied + verified.
- Second mission D0_0700_.MDI: 90 units / 179 refs translated + mapped, not applied.
- Campaign priority-B total: 1302 units; campaign is incomplete.
- UI/control priority-A 1082 is separately complete.
- `New Objective` remains English; mapping exists but is unapplied.
- Menu MDI base 0x08E2D020, stride 0x78000; campaign MDI base 0x08E03020.
- PSP RAM reads limited to 0x08000000..0x0A000000.
- BIA PPSSPP debugger ports: 26420..26439 only.

## Translation Status
- UI/control A: complete.
- Campaign B: first mission VERIFIED; second mission TRANSLATED_PENDING_APPLY; remainder untranslated.
- Movies: 8 static applications, first 2 runtime-verified; remaining 6 validation deferred.

## Known Problems
- Stage43T menu-after-START final visual/interaction verification pending.
- `New Objective` title remains English.
- Campaign is incomplete.

## Do Not Do
- Do not declare Stage43T or the game complete.
- Do not use Stage43L, R/R2, or S as final baseline.
- Do not resume remaining six movie playback validations.
- Do not stop unrelated PPSSPP processes.
- Do not read PSP RAM outside 0x08000000..0x0A000000.

## Critical Paths
Original game: PROJECT_ROOT/Brothers in Arms - D-Day (USA) (v1.01).iso
Current test build: PROJECT_ROOT/BIA_STAGE43T_TITLE_PROMPT_FIX.iso
First mission translation: work/campaign_first_ko.json
Second mission translation: work/campaign_second_ko.json
Latest progress: outputs/bia_campaign_progress.md
'''
text=state.read_text(encoding='utf-8',errors='replace') if state.exists() else base
block=f'''<!-- STEP_044_MANAGED_BEGIN -->
## STEP_044 Live State
Last Updated: {now}
Status: {status}
Goal: Discover the next untranslated priority-B campaign mission and export a stable TSV.
Base Build: PROJECT_ROOT/BIA_STAGE43T_TITLE_PROMPT_FIX.iso
ISO modification in this step: NO
Remaining movie validation resumed: NO
Detail: {a.detail or '(none)'}
<!-- STEP_044_MANAGED_END -->'''
pat=re.compile(r'<!-- STEP_044_MANAGED_BEGIN -->.*?<!-- STEP_044_MANAGED_END -->',re.S)
text=pat.sub(block,text) if pat.search(text) else text.rstrip()+'\n\n'+block+'\n'
state.write_text(text,encoding='utf-8')

if a.phase=='start':
    body=f'''# STEP 044

## Goal
Discover the next untranslated priority-B campaign mission and export a stable TSV for translation.

## Starting State
Base build: PROJECT_ROOT/BIA_STAGE43T_TITLE_PROMPT_FIX.iso
First mission: 137 units / 274 refs applied + VERIFIED.
Second mission: 90 units / 179 refs translated + mapped, not applied.
Stage43T menu-after-START verification: PENDING.
Remaining six movie playback validations: DEFERRED BY USER.

## Inputs
- work/campaign_first_ko.json
- work/first_campaign_units.json
- work/campaign_first_reference_audit.json
- work/campaign_second_ko.json
- work/campaign_second_units.json
- work/campaign_second_reference_audit.json
- other campaign/unit/reference datasets discovered under the project root

## Scripts
- scripts/update_state.py
- scripts/discover_campaign.py
- run.ps1

## Work Performed
Step started. ISO modification is not allowed in this Step.

## Findings
Pending discovery.

## Result
IN_PROGRESS

## Next Step
Translate/review the generated campaign_next_translation.tsv, then apply second/next missions in a later build Step.
'''
else:
    old=step.read_text(encoding='utf-8',errors='replace') if step.exists() else '# STEP 044\n'
    body=old.rstrip()+f'''\n\n## Completion Update\nTime: {now}\nResult: {status}\nDetail: {a.detail or '(none)'}\n'''
step.write_text(body,encoding='utf-8')
