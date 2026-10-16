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
Last Updated: 2026-10-07T21:40:21+09:00
Status: VERIFIED
Goal: Export the next untranslated campaign mission from the canonical Stage38 Priority-B worklist.
Base Build: PROJECT_ROOT/BIA_STAGE43T_TITLE_PROMPT_FIX.iso
Canonical Campaign Source: PROJECT_ROOT/analysis/stage38_translation_worklist/stage38_translation_units.tsv
ISO modified in this step: NO
Remaining six movie validations resumed: NO
Detail: FIX7_selected_D0_1015_units_62
<!-- STEP_044_MANAGED_END -->

<!-- CAMPAIGN_MASTER_FACT_BEGIN -->
## Campaign Master Worklist
CONFIRMED: The canonical 1302-unit Priority-B campaign source is:
`PROJECT_ROOT/analysis/stage38_translation_worklist/stage38_translation_units.tsv`

Mission membership is encoded in the `references` column as tokens such as
`D0_0700_EXIT4:...`, not necessarily literal `D0_0700_.MDI` filenames.
This is why STEP_044 FIX6's `.MDI`-only discovery found no remaining groups.
<!-- CAMPAIGN_MASTER_FACT_END -->

<!-- STEP_045_MANAGED_BEGIN -->
## STEP_045 Live State
Last Updated: 2026-10-07T21:47:19+09:00
Status: VERIFIED
Goal: Review and persist Korean translations for all 62 D0_1015_.MDI Priority-B units.
Input: STEP_044 exported campaign_next_translation.tsv
ISO modified in this step: NO
Runtime verification required in this step: NO
Remaining six movie validations resumed: NO
Detail: D0_1015_62_units_TRANSLATED_REVIEWED_ISO_untouched
<!-- STEP_045_MANAGED_END -->

<!-- STEP_046_MANAGED_BEGIN -->
## STEP_046 Live State
Last Updated: 2026-10-07T21:54:31+09:00
Status: VERIFIED
Goal: Review/persist D1_0900_VIERVILLE (64) + D1_1830_DEADMANSCORNER (29), then export next untranslated campaign batch.
ISO modified in this step: NO
Remaining six movie validations resumed: NO
Detail: STEP046_93_TRANSLATED_next_D2_0630_CRACKOFDAWN_units_25
<!-- STEP_046_MANAGED_END -->

<!-- STEP_047_MANAGED_BEGIN -->
## STEP_047 Live State
Last Updated: 2026-10-07T21:58:51+09:00
Status: VERIFIED
Goal: Review/persist D2_0630_CRACKOFDAWN (25), then export the next untranslated campaign batch.
ISO modified in this step: NO
Remaining six movie validations resumed: NO
Detail: STEP047_25_TRANSLATED_next_D2_1000_FALLOFSTCOMEDUMONT_units_47
<!-- STEP_047_MANAGED_END -->

<!-- STEP_048_MANAGED_BEGIN -->
## STEP_048 Live State
Last Updated: 2026-10-07T22:03:06+09:00
Status: VERIFIED
Goal: Review/persist D2_1000_FALLOFSTCOMEDUMONT (47), then export the next untranslated campaign batch.
ISO modified in this step: NO
Remaining six movie validations resumed: NO
Detail: STEP048_47_TRANSLATED_next_D3_0900_BUYINGTHEFARM_units_36
<!-- STEP_048_MANAGED_END -->

<!-- STEP_049_MANAGED_BEGIN -->
## STEP_049 Live State
Last Updated: 2026-10-07T22:06:40+09:00
Status: VERIFIED
Goal: Review/persist D3_0900_BUYINGTHEFARM (36), then export the next untranslated campaign batch.
ISO modified in this step: NO
Remaining six movie validations resumed: NO
Detail: STEP049_36_TRANSLATED_next_D4_1800_PURPLEHEARTLANE_units_51
<!-- STEP_049_MANAGED_END -->

<!-- STEP_050_MANAGED_BEGIN -->
## STEP_050 Live State
Last Updated: 2026-10-07T22:09:52+09:00
Status: VERIFIED
Goal: Review/persist D4_1800_PURPLEHEARTLANE (51), then export next campaign batch.
ISO modified in this step: NO
Remaining six movie validations resumed: NO
Detail: STEP050_51_TRANSLATED_next_D5_0615_COLESCHARGE_units_45
<!-- STEP_050_MANAGED_END -->
