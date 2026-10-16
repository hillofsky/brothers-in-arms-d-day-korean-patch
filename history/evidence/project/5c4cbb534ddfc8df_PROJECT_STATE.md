# PROJECT STATE

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

<!-- STEP_044_MANAGED_BEGIN -->
## STEP_044 Live State
Last Updated: 2026-10-07T21:35:23+09:00
Status: FAILED
Goal: Discover next untranslated campaign mission and export translation TSV.
Base Build: PROJECT_ROOT/BIA_STAGE43T_TITLE_PROMPT_FIX.iso
ISO modified in this step: NO
Remaining six movie validations resumed: NO
Detail: FIX6_failed_discovery_evidence_collected
<!-- STEP_044_MANAGED_END -->
