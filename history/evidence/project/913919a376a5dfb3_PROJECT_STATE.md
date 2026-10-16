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

<!-- STEP_051_MANAGED_BEGIN -->
## STEP_051 Live State
Last Updated: 2026-10-07T22:12:37+09:00
Status: VERIFIED
Goal: Review/persist D5_0615_COLESCHARGE (45), then export next campaign batch.
ISO modified in this step: NO
Remaining six movie validations resumed: NO
Detail: STEP051_45_TRANSLATED_next_D6_0500_PUSHINTOCARENTAN_units_43
<!-- STEP_051_MANAGED_END -->

<!-- STEP_052_MANAGED_BEGIN -->
## STEP_052 Live State
Last Updated: 2026-10-07T22:15:45+09:00
Status: VERIFIED
Goal: Review/persist D6_0500_PUSHINTOCARENTAN (43), then export next campaign batch.
ISO modified in this step: NO
Remaining six movie validations resumed: NO
Detail: STEP052_43_TRANSLATED_next_D6_1200_CHURCHTOWER_units_63
<!-- STEP_052_MANAGED_END -->

<!-- STEP_053_MANAGED_BEGIN -->
## STEP_053 Live State
Last Updated: 2026-10-07T22:20:50+09:00
Status: VERIFIED
Goal: Review/persist D6_1200_CHURCHTOWER (63), then export next campaign batch.
ISO modified in this step: NO
Remaining six movie validations resumed: NO
Detail: STEP053_63_TRANSLATED_next_D7_1400_NOBETTERSPOT_units_75
<!-- STEP_053_MANAGED_END -->

<!-- STEP_054_MANAGED_BEGIN -->
## STEP_054 Live State
Last Updated: 2026-10-07T22:33:25+09:00
Status: VERIFIED
Goal: Review/persist all remaining No Better Spot to Die Part 1/2 campaign units (77 total), then export next batch.
ISO modified in this step: NO
Remaining six movie validations resumed: NO
Detail: STEP054_77_TRANSLATED_next_D07_1500_BLOODYGULCH_units_32
<!-- STEP_054_MANAGED_END -->

<!-- STEP_055_MANAGED_BEGIN -->
## STEP_055 Live State
Last Updated: 2026-10-07T22:36:51+09:00
Status: VERIFIED
Goal: Review/persist D07_1500_BLOODYGULCH (32), then export next campaign batch.
ISO modified in this step: NO
Remaining six movie validations resumed: NO
Detail: STEP055_32_TRANSLATED_next_D8_0930_VICTORYINCARENTAN_units_31
<!-- STEP_055_MANAGED_END -->

<!-- STEP_056_MANAGED_BEGIN -->
## STEP_056 Live State
Last Updated: 2026-10-07T22:40:23+09:00
Status: VERIFIED
Goal: Review/persist D8_0930_VICTORYINCARENTAN (31), then export next campaign batch.
ISO modified in this step: NO
Remaining six movie validations resumed: NO
Detail: STEP056_31_TRANSLATED_next_D08_1030_CLOSEQUARTERS_units_33
<!-- STEP_056_MANAGED_END -->

<!-- STEP_057_MANAGED_BEGIN -->
## STEP_057 Live State
Last Updated: 2026-10-07T22:43:22+09:00
Status: VERIFIED
Goal: Review/persist D08_1030_CLOSEQUARTERS (33), then export next campaign batch.
ISO modified in this step: NO
Remaining six movie validations resumed: NO
Detail: STEP057_33_TRANSLATED_next_D09_0800_BAUPTE_units_46
<!-- STEP_057_MANAGED_END -->

<!-- STEP_058_MANAGED_BEGIN -->
## STEP_058 Live State
Last Updated: 2026-10-07T22:47:26+09:00
Status: FAILED
Goal: Review/persist D09_0800_BAUPTE (46), then export next campaign batch.
ISO modified in this step: NO
Remaining six movie validations resumed: NO
Detail: STEP058_failed_no_ISO_change
<!-- STEP_058_MANAGED_END -->

<!-- STEP_058_FIX1_MANAGED_BEGIN -->
## STEP_058 FIX1 Live State
Last Updated: 2026-10-07T22:51:37+09:00
Status: VERIFIED
Goal: Retry D09_0800_BAUPTE (46) with corrected campaign counters, then export D10_0600.
Root cause: Original STEP_058 expected TRANSLATED_REVIEWED=605, but verified STEP_057 state is 638.
ISO modified in this step: NO
Remaining six movie validations resumed: NO
Detail: STEP058_FIX1_46_TRANSLATED_next_D10_0600_RUNOFTHEMILL_units_50
<!-- STEP_058_FIX1_MANAGED_END -->

<!-- STEP_059_MANAGED_BEGIN -->
## STEP_059 Live State
Last Updated: 2026-10-07T22:55:32+09:00
Status: VERIFIED
Goal: Review/persist D10_0600_RUNOFTHEMILL (50), then export next campaign batch.
ISO modified in this step: NO
Remaining six movie validations resumed: NO
Detail: STEP059_50_TRANSLATED_next_D10_0801_THEALLAMERICANS_units_24
<!-- STEP_059_MANAGED_END -->

<!-- STEP_060_MANAGED_BEGIN -->
## STEP_060 Live State
Last Updated: 2026-10-07T23:00:39+09:00
Status: VERIFIED
Goal: Review/persist all remaining D10_0801/D10_0802 THEALLAMERICANS text (60 unique units), then export next campaign batch.
ISO modified in this step: NO
Remaining six movie validations resumed: NO
Detail: STEP060_60_TRANSLATED_next_D15_1130_BOOKENDS_units_43
<!-- STEP_060_MANAGED_END -->

<!-- STEP_061_MANAGED_BEGIN -->
## STEP_061 Live State
Last Updated: 2026-10-07T23:06:38+09:00
Status: VERIFIED
Goal: Complete all four D15 Bookends translation groups (119 unique rows), then export remaining campaign skirmish/system pool.
ISO modified in this step: NO
Remaining six movie validations resumed: NO
Detail: STEP061_119_TRANSLATED_next_pool_SKIRMISH_AND_SYSTEM_CAMPAIGN_REMAINDER_units_162
<!-- STEP_061_MANAGED_END -->

<!-- STEP_062_MANAGED_BEGIN -->
## STEP_062 Live State
Last Updated: 2026-10-07T23:12:43+09:00
Status: VERIFIED
Goal: Translate/review the final 162 campaign skirmish/system rows and close campaign translation discovery.
ISO modified in this step: NO
Remaining six movie validations resumed: NO
Detail: STEP062_CAMPAIGN_TRANSLATION_COMPLETE_unapplied_1165
<!-- STEP_062_MANAGED_END -->

<!-- STEP_063_MANAGED_BEGIN -->
## STEP_063 Live State
Last Updated: 2026-10-07T23:16:57+09:00
Status: VERIFIED
Goal: Preflight the exact existing campaign MDI/DSL/DSX application pipeline for 1165 translated-but-unapplied campaign units.
Campaign translation corpus complete: YES
ISO modified in this step: NO
Remaining six movie validations resumed: NO
Detail: STEP063_PREFLIGHT_VERIFIED_unapplied_1165_candidates_67
<!-- STEP_063_MANAGED_END -->

<!-- STEP_064_MANAGED_BEGIN -->
## STEP_064 Live State
Last Updated: 2026-10-07T23:22:41+09:00
Status: VERIFIED
Goal: Recover exact Stage38 per-occurrence campaign map and historical successful campaign ISO patch scripts from filesystem/log archives.
Campaign untranslated rows: 0
ISO modified in this step: NO
Remaining six movie validations resumed: NO
Detail: STEP064_RECOVERY_VERIFIED_occurrences_1435_patchfiles_110
<!-- STEP_064_MANAGED_END -->

<!-- STEP_065_MANAGED_BEGIN -->
## STEP_065 Live State
Last Updated: 2026-10-07T23:33:49+09:00
Status: VERIFIED
Goal: Audit compiled FString coverage and per-MDI font/DSL/DSX requirements for the 1165 translated-but-unapplied campaign units.
Exact Stage38 occurrence recovery: VERIFIED in STEP_064
ISO modified in this step: NO
Remaining six movie validations resumed: NO
Detail: STEP065_AUDIT_VERIFIED_resolved_0_unresolved_1165_font_over_0
<!-- STEP_065_MANAGED_END -->

<!-- STEP_066_MANAGED_BEGIN -->
## STEP_066 Live State
Last Updated: 2026-10-07T23:45:09+09:00
Status: VERIFIED
Goal: Correct STEP_065's overly narrow scanner by reproducing the proven all-stream FString audit through payload-to-pointer reverse tracing.
STEP_064 exact source map: VERIFIED
ISO modified in this step: NO
Remaining six movie validations resumed: NO
Detail: STEP066_AUDIT_VERIFIED_highIDs_967_allIDs_967_D00700_canary_True
<!-- STEP_066_MANAGED_END -->

<!-- STEP_067_MANAGED_BEGIN -->
## STEP_067 Live State
Last Updated: 2026-10-07T23:54:23+09:00
Status: VERIFIED
Goal: Classify the 198 campaign rows that are not compiled FString values in Stage43T MDI assets.
STEP_066 canary D0_0700 90/179: VERIFIED
Resolved compiled campaign IDs: 967
Unresolved non-MDI-class IDs: 198
ISO modified in this step: NO
Deferred movie playback validation resumed: NO
Detail: STEP067_CLASSIFIED_moviehist_72_rawnonint_23_mdikey_132
<!-- STEP_067_MANAGED_END -->

<!-- STEP_068_MANAGED_BEGIN -->
## STEP_068 Live State
Last Updated: 2026-10-08T00:03:01+09:00
Status: FAILED
Goal: Reconcile STEP067 movie evidence against exact Stage42A ST1 fields and split all 1165 untranslated-but-unapplied campaign IDs into compiled MDI, preserved movie ST1, and non-MDI runtime classes.
STEP066 D0_0700 canary: PASS 90/179
ISO modified in this step: NO
Deferred movie playback validation resumed: NO
Detail: STEP068_failed_no_ISO_change
<!-- STEP_068_MANAGED_END -->

<!-- STEP_068_FIX1_MANAGED_BEGIN -->
## STEP_068 FIX1 Live State
Last Updated: 2026-10-08T00:07:49+09:00
Status: VERIFIED
Goal: Correct STEP068's invalid movie-count assumption and derive the final 1165-ID apply split directly from the 133 real Stage42A ST1 fields.
Original STEP068 failure: expected movie overlap 71, actual derived overlap 106.
ISO modified in this step: NO
Deferred movie playback validation resumed: NO
Detail: STEP068_FIX1_VERIFIED_compiled_967_movie_106_nonmdi_92
<!-- STEP_068_FIX1_MANAGED_END -->

<!-- STEP_069_MANAGED_BEGIN -->
## STEP_069 Live State
Last Updated: 2026-10-08T00:15:00+09:00
Status: FAILED
Goal: Apply the 92 non-MDI/INT campaign rows (99 exact INT occurrences across 18 files) to a separate Stage43T-derived test ISO.
Source ISO preserved: YES
Compiled-MDI 967 applied in this step: NO
Movie-ST1 106 repatched in this step: NO
Runtime verification complete: NO
Deferred movie playback validation resumed: NO
Detail: STEP069_failed_source_Stage43T_preserved
<!-- STEP_069_MANAGED_END -->

<!-- STEP_069_FIX1_MANAGED_BEGIN -->
## STEP_069 FIX1 Live State
Last Updated: 2026-10-08T10:00:07+09:00
Status: FAILED
Goal: Retry the 92-ID / 99-occurrence INT-only test build using verified section+key identity as the primary locator and logging Stage43T value drift.
Original STEP069 failure: first unique section/key had a current value different from its Stage38 original.
Source Stage43T ISO preserved: YES
Compiled-MDI 967 applied: NO
Movie-ST1 106 repatched: NO
Runtime verification complete: NO
Detail: STEP069_FIX1_failed_source_Stage43T_preserved
<!-- STEP_069_FIX1_MANAGED_END -->

<!-- STEP_069_FIX2_MANAGED_BEGIN -->
## STEP_069 FIX2 Live State
Last Updated: 2026-10-08T10:04:21+09:00
Status: BUILT_UNVERIFIED
Goal: Rebuild the 92-ID INT-only Stage43T test ISO with corrected verified movie filenames and corrected ON_MEMU_O.MDI preservation target.
STEP069 FIX1 INT patch/readback loop reached completion before its preservation-name failure: YES
Source Stage43T ISO preserved: YES
Compiled-MDI 967 applied: NO
Movie-ST1 106 repatched: NO
Runtime verification complete: NO
Detail: STEP069_FIX2_BUILT_UNVERIFIED_changed_99_drifted_13
<!-- STEP_069_FIX2_MANAGED_END -->

<!-- STEP_070_MANAGED_BEGIN -->
## STEP_070 Live State
Last Updated: 2026-10-08T10:11:07+09:00
Status: FAILED
Goal: Controlled runtime route discovery on BIA_STAGE69_FIX2_NONMDI_INT92_TEST.iso using a dedicated PPSSPP debugger port and exact PID/path verification.
INT92 static build: BUILT_UNVERIFIED
INT92 rows promoted to VERIFIED_APPLIED: NO
Compiled-MDI 967 applied: NO
Movie playback validation resumed: NO
Detail: STEP070_failed_no_campaign_status_promotion
<!-- STEP_070_MANAGED_END -->

<!-- STEP_070_FIX1_MANAGED_BEGIN -->
## STEP_070 FIX1 Live State
Last Updated: 2026-10-08T10:16:45+09:00
Status: IN_PROGRESS
Goal: Controlled runtime route discovery on BIA_STAGE69_FIX2_NONMDI_INT92_TEST.iso using a dedicated PPSSPP debugger port and exact PID/path verification.
INT92 static build: BUILT_UNVERIFIED
INT92 rows promoted to VERIFIED_APPLIED: NO
Compiled-MDI 967 applied: NO
Movie playback validation resumed: NO
Detail: STEP070_FIX1_runtime_route_discovery_started
<!-- STEP_070_FIX1_MANAGED_END -->

<!-- STEP_070_FIX2_MANAGED_BEGIN -->
## STEP_070 FIX2 Live State
Last Updated: 2026-10-08T11:10:04+09:00
Status: FAILED
Goal: Controlled runtime route discovery on BIA_STAGE69_FIX2_NONMDI_INT92_TEST.iso using a dedicated PPSSPP debugger port and exact PID/path verification.
INT92 static build: BUILT_UNVERIFIED
INT92 rows promoted to VERIFIED_APPLIED: NO
Compiled-MDI 967 applied: NO
Movie playback validation resumed: NO
Detail: STEP070_FIX1_failed_no_campaign_status_promotion
<!-- STEP_070_FIX2_MANAGED_END -->

<!-- STEP_070_FIX3_MANAGED_BEGIN -->
## STEP_070 FIX3 Live State
Last Updated: 2026-10-08T12:26:05+09:00
Status: FAILED
Goal: Runtime route discovery using the user's exact PPSSPP executable path; verify debugger TCP listener owner PID and launched process command line before any WebSocket input.
INT92 static build: BUILT_UNVERIFIED
INT92 promoted to VERIFIED_APPLIED: NO
Compiled-MDI 967 applied: NO
Movie playback validation resumed: NO
Detail: STEP070_FIX3_failed_no_status_promotion
<!-- STEP_070_FIX3_MANAGED_END -->
