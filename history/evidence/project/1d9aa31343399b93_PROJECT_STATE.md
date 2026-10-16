# PROJECT STATE

Project: Brothers in Arms D-Day Korean Localization
Game: Brothers in Arms - D-Day (USA) (v1.01)
Working Directory: PROJECT_ROOT

## Latest Working State — STEP099 (2026-10-13)
Latest ISO: PROJECT_ROOT/BIA_STEP099_COMPLETION_SAVE_KO_TEST.iso
Retains all STEP098 native UIFont fixes. Adds Korean for completion title, medal award, save confirmation, Confirm/No/Yes/Quit/Continue through474 localization value refs across32 maps. ISO independent readback and all new glyph availability passed; UI runtime replay remains user QA. Original key/section identifiers and font/atlas/PRX preserved. SourceSTEP098 ISO unchanged. Save current progress before restarting with new ISO.


## Latest Working State — STEP098 (2026-10-13)
- Latest verification ISO: PROJECT_ROOT/BIA_STEP098_ALL_CHAPTER_UFONT_TEST.iso
- All32 translated map resources (20 campaign/12 skirmish): native UIFont expansion applied;64 fonts,54,848 hash lookups verified from ISO readback.
- Existing chapter1/2 fixes preserved;30 further map resources/60 fonts expanded. Original Latin, icons, strings and atlas preserved.
- Chapter2 native Korean display user-confirmed on STEP097; full chapter gameplay QA pending.
- New Objective and English residuals unchanged; six movie validations deferred.
- Detailed files: SESSION_SESSION_OUTPUTS/step098.


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

<!-- STEP_070_FIX4_MANAGED_BEGIN -->
## STEP_070 FIX4 Live State
Last Updated: 2026-10-08T12:34:54+09:00
Status: FAILED
Goal: Runtime route discovery using the user's exact PPSSPP executable path; verify debugger TCP listener owner PID and launched process command line before any WebSocket input.
INT92 static build: BUILT_UNVERIFIED
INT92 promoted to VERIFIED_APPLIED: NO
Compiled-MDI 967 applied: NO
Movie playback validation resumed: NO
Detail: STEP070_FIX3_failed_no_status_promotion
<!-- STEP_070_FIX4_MANAGED_END -->

<!-- STEP_070_FIX5_MANAGED_BEGIN -->
## STEP_070 FIX5 Live State
Last Updated: 2026-10-08T12:42:46+09:00
Status: FAILED
Goal: Runtime route discovery using the user's exact PPSSPP executable path; verify debugger TCP listener owner PID and launched process command line before any WebSocket input.
INT92 static build: BUILT_UNVERIFIED
INT92 promoted to VERIFIED_APPLIED: NO
Compiled-MDI 967 applied: NO
Movie playback validation resumed: NO
Detail: STEP070_FIX3_failed_no_status_promotion
<!-- STEP_070_FIX5_MANAGED_END -->

<!-- STEP_070_FIX6_MANAGED_BEGIN -->
## STEP_070 FIX6 Live State
Last Updated: 2026-10-08T12:49:14+09:00
Status: BUILT_UNVERIFIED
Goal: Reuse the proven Stage40Y runtime method: software renderer, dedicated debugger WebSocket, input.buttons.send, and raw RGB565 VRAM captures at 0x04000000/0x04044000.
INT92 static build: BUILT_UNVERIFIED
INT92 promoted to VERIFIED_APPLIED: NO
Compiled-MDI 967 applied: NO
Movie playback validation resumed: NO
Detail: STEP070_FIX6_RAW_VRAM_CAPTURED_runtimeLoadedKO_False_renderVerified_FALSE
<!-- STEP_070_FIX6_MANAGED_END -->

<!-- STEP_070_FIX7_MANAGED_BEGIN -->
## STEP_070 FIX7 Live State
Last Updated: 2026-10-08T12:56:10+09:00
Status: BUILT_UNVERIFIED
Goal: Use the proven raw-VRAM path plus FIX6 title-frame signature to reach the title deterministically, enter the main menu, and capture selection positions without confirming an item.
INT92 static build: BUILT_UNVERIFIED
INT92 promoted to VERIFIED_APPLIED: NO
Compiled-MDI 967 applied: NO
Movie playback validation resumed: NO
Detail: STEP070_FIX7_MAIN_MENU_ROUTE_CAPTURED_no_confirm
<!-- STEP_070_FIX7_MANAGED_END -->

<!-- STEP_071_MANAGED_BEGIN -->
## STEP_071 Live State
Last Updated: 2026-10-08T13:05:37+09:00
Status: BUILT_UNVERIFIED
Goal: Enter the verified Skirmish item once, compare all 92 INT targets in full PSP RAM before/after, and capture post-entry raw VRAM frames.
INT92 promoted to VERIFIED_APPLIED: NO
Compiled-MDI 967 applied: NO
Movie playback validation resumed: NO
Detail: STEP071_INT92_CANARY_SCAN_COMPLETE_newlyLoaded_0
<!-- STEP_071_MANAGED_END -->

<!-- STEP_072_MANAGED_BEGIN -->
## STEP_072 Live State
Last Updated: 2026-10-08T13:24:23+09:00
Status: FAILED
Goal: Collect and validate the existing STEP066/064/39A evidence needed to build the generalized 967 compiled-MDI patcher. No ISO modification.
INT92 status: BUILT_UNVERIFIED
Compiled-MDI 967 applied: NO
Movie 106 repatched: NO
Movie playback validation resumed: NO
Detail: STEP072 evidence collection failed; no ISO modified.
<!-- STEP_072_MANAGED_END -->

<!-- STEP_072_FIX1_MANAGED_BEGIN -->
## STEP_072 FIX1 Live State
Last Updated: 2026-10-08T13:30:55+09:00
Status: VERIFIED
Goal: Recover historical build_campaign43a.py from archives if available and independently verify all prerequisites for generalized 967 compiled-MDI application.
ISO modified: NO
INT92: BUILT_UNVERIFIED / canary work stopped
Compiled-MDI 967 applied: NO
Movie playback validation resumed: NO
Detail: compiled967_ready refs=2333 mdis=32 historical43a=False
<!-- STEP_072_FIX1_MANAGED_END -->

<!-- STEP_073_MANAGED_BEGIN -->
## STEP_073 Live State
Last Updated: 2026-10-08T13:44:39+09:00
Status: VERIFIED
Goal: Recover the exact historical Stage43A/Stage40Y/Stage39B builder sources needed to construct the generalized 967 compiled-MDI ISO patcher.
ISO modified: NO
INT92: BUILT_UNVERIFIED
Compiled-MDI 967 applied: NO
Movie playback validation resumed: NO
Detail: campaign43a=True manifest=6
<!-- STEP_073_MANAGED_END -->

<!-- STEP_074_MANAGED_BEGIN -->
## STEP_074 Live State
Last Updated: 2026-10-08T13:56:44+09:00
Status: FAILED
Goal: Apply all 967 compiled-MDI campaign IDs / 2333 exact FString references across 32 MDIs to a Stage69-derived bulk test ISO.
Source baseline: BIA_STAGE69_FIX2_NONMDI_INT92_TEST.iso
INT92 runtime status: BUILT_UNVERIFIED
Compiled-MDI 967 runtime verified: NO
Movie 106 repatched: NO
Movie playback validation resumed: NO
New Objective popup title fixed: NO
Detail: STEP074 failed safely. Source ISO preserved; inspect reports before retry.
<!-- STEP_074_MANAGED_END -->

<!-- STEP_074_FIX1_MANAGED_BEGIN -->
## STEP_074 FIX1 Live State
Last Updated: 2026-10-08T14:11:49+09:00
Status: FAILED
Goal: Correct STEP074's false font assumption by installing the proven Stage39A/43A Korean font per target MDI, then apply all 967 IDs / 2333 exact FString refs across 32 MDIs.
Source baseline: BIA_STAGE69_FIX2_NONMDI_INT92_TEST.iso
INT92 runtime status: BUILT_UNVERIFIED
Compiled-MDI 967 runtime verified: NO
Movie 106 repatched: NO
Movie playback validation resumed: NO
New Objective popup title fixed: NO
Detail: STEP074 FIX1 failed safely. Source Stage69 ISO preserved; inspect blocked_mdis/report.
<!-- STEP_074_FIX1_MANAGED_END -->

<!-- STEP_074_FIX2_MANAGED_BEGIN -->
## STEP_074 FIX2 Live State
Last Updated: 2026-10-08T14:34:27+09:00
Status: FAILED
Goal: Retry compiled967 bulk build with the original TMR18 renderer-page arrays interpreted exactly as proven by Stage36: one u16 width, one u16 height, one u32 texture-object entry before expansion.
Source baseline: BIA_STAGE69_FIX2_NONMDI_INT92_TEST.iso
INT92 runtime status: BUILT_UNVERIFIED
Compiled-MDI 967 runtime verified: NO
Movie playback validation resumed: NO
New Objective popup title fixed: NO
Detail: STEP074 FIX2 failed safely; inspect blocked evidence. Source Stage69 preserved.
<!-- STEP_074_FIX2_MANAGED_END -->

<!-- STEP_074_FIX3_MANAGED_BEGIN -->
## STEP_074 FIX3 Live State
Last Updated: 2026-10-08T14:52:24+09:00
Status: FAILED
Goal: Retry compiled967 bulk build with campaign-original TMR18 metrics derived from the exact D0_0130_ original font (128x512), rather than reusing the Stage36 menu-font 128x256 metric.
Source baseline: BIA_STAGE69_FIX2_NONMDI_INT92_TEST.iso
INT92 runtime status: BUILT_UNVERIFIED
Compiled-MDI 967 runtime verified: NO
Movie playback validation resumed: NO
New Objective popup title fixed: NO
Detail: STEP074 FIX3 failed safely; source Stage69 preserved. Inspect blocked evidence.
<!-- STEP_074_FIX3_MANAGED_END -->

<!-- STEP_074_FIX4_MANAGED_BEGIN -->
## STEP_074 FIX4 Live State
Last Updated: 2026-10-08T15:00:08+09:00
Status: FAILED
Goal: Generalize the proven campaign Korean font while keeping the original 151-glyph font texture object distinct from Stage40Y's independently identified expanded Korean texture object.
Source baseline: BIA_STAGE69_FIX2_NONMDI_INT92_TEST.iso
INT92 runtime status: BUILT_UNVERIFIED
Compiled-MDI 967 runtime verified: NO
Movie playback validation resumed: NO
New Objective popup title fixed: NO
Detail: STEP074 FIX4 failed safely; source Stage69 preserved. Inspect exact blocked MDI evidence.
<!-- STEP_074_FIX4_MANAGED_END -->

<!-- STEP_074_FIX5_MANAGED_BEGIN -->
## STEP_074 FIX5 Live State
Last Updated: 2026-10-08T15:29:24+09:00
Status: FAILED
Goal: Match the two proven D0_0130_ original TMR18 font roles independently, preserving their distinct original metrics/textures, then dry-run/apply all 967 IDs across 32 MDIs.
Source baseline: BIA_STAGE69_FIX2_NONMDI_INT92_TEST.iso
INT92 runtime status: BUILT_UNVERIFIED
Compiled-MDI 967 runtime verified: NO
Movie playback validation resumed: NO
New Objective popup title fixed: NO
Detail: STEP074 FIX5 failed safely. Source Stage69 preserved; inspect template-role/blocked evidence.
<!-- STEP_074_FIX5_MANAGED_END -->

<!-- STEP_074_FIX6_MANAGED_BEGIN -->
## STEP_074 FIX6 Live State
Last Updated: 2026-10-08T15:35:00+09:00
Status: FAILED
Goal: Build compiled-MDI 967 with independently selected per-MDI role1 texture object and preserve Stage69 translations/movie resources.
Source baseline: BIA_STAGE69_FIX2_NONMDI_INT92_TEST.iso
INT92 runtime status: BUILT_UNVERIFIED
Compiled-MDI 967 runtime verified: NO
Movie playback validation resumed: NO
New Objective popup title fixed: NO
Detail: STEP074 FIX5 failed safely. Source Stage69 preserved; inspect template-role/blocked evidence.
<!-- STEP_074_FIX6_MANAGED_END -->

<!-- STEP_075_MANAGED_BEGIN -->
## STEP_075 DSL Variant Audit
Last Updated: 2026-10-08T15:43:11+09:00
Status: VERIFIED
Purpose: Characterize exact 32 MDI/DSL/DSX texture relocation variants; no ISO writes.
Stage69 INT92: BUILT_UNVERIFIED
Compiled MDI 967: NOT BUILT
Movie playback validation: DEFERRED
Detail: 32 MDI DSL variants recorded; no ISO changed; next determine per-MDI texture binding.
<!-- STEP_075_MANAGED_END -->

<!-- STEP_076_MANAGED_BEGIN -->
## STEP_076 Targeted DSL Analysis
Last Updated: 2026-10-08T15:49:33+09:00
Status: VERIFIED
Goal: Identify candidate DSL relocation-copy runs and TEXSIZE GPU command context per MDI using the original and Stage69 first-mission control, without mutation.
INT92: BUILT_UNVERIFIED
Compiled-MDI 967 applied: NO
Compiled-MDI 967 runtime verified: NO
Movie playback validations resumed: NO
ISO modified: NO
Detail: All 32 DSL analyzed; candidate offsets are hypotheses only; no ISO changed.
<!-- STEP_076_MANAGED_END -->

<!-- STEP_077_MANAGED_BEGIN -->
## STEP_077 Relocation Payload Correlation
Updated: 2026-10-08T15:56:28+09:00
Status: VERIFIED
Goal: Test actual relocation source/target payload fingerprints across 32 DSLs against the verified first mission; no unproven DSL patch locations will be applied.
ISO modified: NO
INT92 status: BUILT_UNVERIFIED
Compiled967 status: NOT_BUILT
Movie playback validation resumed: NO
Detail: Read-only 32-DSL payload correlation done; exact C128 matches in other MDIs=0; semantic patch targets not yet verified.
<!-- STEP_077_MANAGED_END -->

<!-- STEP_078_MANAGED_BEGIN -->
## STEP_078 Live State
Last Updated: 2026-10-08T16:01:02+09:00
Status: VERIFIED
Purpose: Export verified original/patched first-mission MDI/DSL/DSX and representative other mission DSL/DSX/MDI binaries for offline semantic reverse engineering.
ISO modified: NO
Stage69 source: BIA_STAGE69_FIX2_NONMDI_INT92_TEST.iso
Compiled-MDI 967: NOT_BUILT
INT92 runtime status: BUILT_UNVERIFIED
Deferred movie tests: NOT_RESUMED
Detail: Exported 15 exact binaries, byte identity and 6 DSX/DSL checks verified; no ISO modified.
<!-- STEP_078_MANAGED_END -->

<!-- STEP_079_MANAGED_BEGIN -->
## STEP_079 Compiled967 Structural DSL Build
Last Updated: 2026-10-08T16:13:32+09:00
Status: BUILT_UNVERIFIED
Goal: Stage69-based compiled967 bulk ISO. Per-MDI exact STEP076 relocation + GPU evidence. Dry-run all 32 before build, golden DSL control, preserved INT/movie/menu.
Source ISO: BIA_STAGE69_FIX2_NONMDI_INT92_TEST.iso
Output ISO: BIA_STAGE79_COMPILED967_STRUCTURAL_TEST.iso (only on complete success)
MDIs: 32; FString structural refs: 2333; Compiled IDs: 967
First mission Stage43A runtime result: previously VERIFIED, preserved (not re-tested)
INT92 runtime status: BUILT_UNVERIFIED
Compiled967 runtime status: NOT VERIFIED
Movies: 106 ST1 translation resources preserved, 6 movie playback tests deferred
New Objective popup English title: unresolved
Detail: STEP079_BUILT_UNVERIFIED ids=967 refs=2333 mdis=32 runtime_FALSE
<!-- STEP_079_MANAGED_END -->

<!-- STEP_080_MANAGED_BEGIN -->
## STEP_080 Live State
Last Updated: 2026-10-08T16:23:08+09:00
Status: VERIFIED
Purpose: Runtime smoke for Stage79: exact ISO identity + independent PPSSPP title/main-menu signature, then observe Story-entry frames and select compiled-MDI RAM canaries.
Stage79 ISO: BIA_STAGE79_COMPILED967_STRUCTURAL_TEST.iso
Stage79 compile status: BUILT_UNVERIFIED
Compiled967 visual runtime verified: NO
INT92 visual runtime verified: NO
Six deferred movie playback validations: NOT_RESUMED
ISO modification: NO
Details: Stage79 verified title/menu; story_transition=False; compiled967 visual render still UNVERIFIED
<!-- STEP_080_MANAGED_END -->

<!-- STEP_081_MANAGED_BEGIN -->
## STEP_081 Runtime QA
Last Updated: 2026-10-08T16:32:55+09:00
Step execution status: VERIFIED
Goal: Recognize the Story submenu separately from main menu; safely select highlighted New Game using isolated PPSSPP memory stick and collect 70s of post-selection evidence.
Stage79 ISO static build: BUILT_UNVERIFIED (967 compiled IDs)
Compiled967 visual runtime verified: NO
INT92 visual runtime verified: NO
Six deferred movie playback validations resumed: NO
User's original PPSSPP saves intended to remain untouched: YES; test-only memory stick
ISO modification: NO
Detail: Story submenu independently verified; isolated New Game selected; status=NEW_GAME_NEXT_SCREEN_CAPTURED_VISUAL_REVIEW; 967 visual unverified
<!-- STEP_081_MANAGED_END -->

<!-- STEP_082_MANAGED_BEGIN -->
## STEP_082 screenshot-confirmed localization defect analysis
Last Updated: 2026-10-08T17:07:11+09:00
Status: VERIFIED
Purpose: collect exact Stage69 versus Stage79 mission2 MDI/DSL/DSX and check font Unicode mapping vs Korean payloads; locate mission1 screenshot English residuals.
Screenshot visual QA: MISSION1_ENGLISH_RESIDUALS; MISSION2_KOREAN_TEXT_BROKEN_GT_FALLBACK
Stage79 static translation: BUILT_UNVERIFIED
Stage79 visual Korean for mission2: FAILED
Current ISO modification: NONE
Previous 6 deferred movies: NOT_RESUMED
Detail: Exact mission2 Stage69/79 binary evidence + mission1 English search done, 7 resources, runtime font defect remains UNRESOLVED.
<!-- STEP_082_MANAGED_END -->

<!-- STEP_083_MANAGED_BEGIN -->
## STEP_083 live font probe
Last updated: 2026-10-08T17:53:59+09:00
Status: FAILED
Purpose: collect a coherent LIVE PPSSPP snapshot of second-mission repeated `>` display, without modifying game ISO.
Stage79 compiled967: BUILT_UNVERIFIED with confirmed second-mission glyph-rendering failure.
First-mission English leftovers: known unresolved in MDI/INT; Stage82 evidence recorded.
Stage69/Stage79 ISO files: untouched.
Six deferred movie playback tests: NOT resumed.
Detail: STEP083 failed at ownership; no ISO modified.
<!-- STEP_083_MANAGED_END -->

<!-- STEP_083_FIX1_MANAGED_BEGIN -->
## STEP_083 FIX1 live mission2 font probe (no ISO mutation)
Last updated: 2026-10-08T18:12:08+09:00
Status: VERIFIED_DIAGNOSTIC
Run: 20261008_181126_131_15568
Stage79: BUILT_UNVERIFIED; mission2 glyph display user-confirmed FAILED (repeated `>`).
INT92 runtime: BUILT_UNVERIFIED.
Movie playback tests (six deferred): NOT RESUMED.
Live snapshot collection: COMPLETE_DIAGNOSTIC_ONLY
Detail: 32MiB live PSP RAM + 2 VRAM previews captured (run=20261008_181126_131_15568). No glyph-render fix applied; analyze report and screenshot next.
<!-- STEP_083_FIX1_MANAGED_END -->

<!-- STEP_084_MANAGED_BEGIN -->
## STEP_084 offline font forensics from STEP 083 FIX1
Last Updated: 2026-10-08T18:18:56+09:00
Status: VERIFIED_OFFLINE_DIAGNOSTIC
Run: 20261008_181856_309_18140
Evidence: STEP083 FIX1, RAM 32 MiB, Korean strings and 878-glyph font objects. Read-only.
Stage79 compiled967: BUILT_UNVERIFIED, second-mission Korean fallback UNRESOLVED.
INT92: BUILT_UNVERIFIED.
New Objective: UNRESOLVED.
Six deferred movie tests: NOT RESUMED.
No ISO changed. No PPSSPP launched. No glyph-render fix applied.
Visual QA: STEP083 FIX1 supplied frame did not display broken Korean text.
<!-- STEP_084_MANAGED_END -->

<!-- STEP_085_MANAGED_BEGIN -->
## STEP_085 mission2 native screenshot key-1 focused capture
Last Updated: 2026-10-08T18:40:45+09:00
Status: CAPTURE_COLLECTED_VISUAL_UNVERIFIED
Run: 20261008_184010_011_7080
Capture: foreground-owned PPSSPP key-1 screenshot, native JPG/PNG + host PNG + VRAM previews + 32MiB RAM (if captured).
Stage79 compiled967: BUILT_UNVERIFIED, second-mission Korean fallback UNRESOLVED.
INT92: BUILT_UNVERIFIED.
New Objective: UNRESOLVED.
Six deferred movie tests: NOT RESUMED.
Stage69/Stage79 ISO changes: NONE attempted.
No Korean render-fix claimed and no capture classified as verified without visual review.
Detail: run=20261008_184010_011_7080; phase=postflight_hash; key1 screenshot + RAM/VRAM evidence requires visual review; no ISO writes
<!-- STEP_085_MANAGED_END -->

<!-- STEP_086_MANAGED_BEGIN -->
## STEP_086 Mission2 live RAM read-watch trace
Last Updated: 2026-10-08T19:03:31+09:00
Status: FAILED
Run: 20261008_190254_224_24600
Capture: key-1 PPSSPP screenshot and nonpausing memory read watchpoints at 4 scene-specific addresses; interpreter mode.
Stage79 compiled967: BUILT_UNVERIFIED, second-mission Korean fallback UNRESOLVED.
INT92: BUILT_UNVERIFIED.
New Objective: UNRESOLVED.
Six deferred movie tests: NOT RESUMED.
Stage69/Stage79 ISO changes: NONE attempted.
No ISO/memory patch; hit counts are diagnostic and do not certify font selection or rendering.
Detail: run=20261008_190254_224_24600; phase=read_only_live_watchpoints; key1 screenshot + scene-specific nonpausing memory font-argument; no ISO writes
<!-- STEP_086_MANAGED_END -->

<!-- STEP_087_MANAGED_BEGIN -->
## STEP_087 Offline trace analysis and safe cleanup
# BIA STEP 087 — Offline Trace Analysis & Verified Duplicate Cleanup

Status: COMPLETE_OFFLINE_DIAGNOSTIC_CLEANUP

Verified duplicate bytes reclaimed (not drive-wide prediction): 36,183,959
Deleted duplicate items: 9
Mission 2 UTF-8 string read hits: 18093
Font page and glyph pointer read hits: [('hangul_page_index_peu', 0), ('mission2_fontA_glyph_pointer', 0), ('mission2_fontB_glyph_pointer', 0)]
Top sampled PCs: [('0x08CA04B0', 60), ('0x08E02E98', 20), ('0x089F6064', 20), ('0x089F60B0', 19), ('0x089F60C4', 19), ('0x08E02EB4', 15), ('0x08E02ED4', 15), ('0x089F6070', 15)]

No ISO, save, project state, or evidence ZIP automatically removed. Large-file candidates are for manual review only; the mission 2 Korean `>` issue remains unresolved.

<!-- STEP_087_MANAGED_END -->

<!-- STEP_088_FIX1_MANAGED_BEGIN -->
## STEP 088 FIX1 — Second mission font argument / pause diagnostics
Last Updated: 2026-10-13T12:37:37+09:00
Status: CAPTURED_UNVERIFIED
Run: 20261013_123635_568_2784
Probe: CPU exec log-only breakpoints; capture CPU pause PC/regs on unexpected stop before cleanup.
Stage79: BUILT_UNVERIFIED; Mission2 Korean > rendering UNRESOLVED.
INT92: BUILT_UNVERIFIED; New Objective: UNRESOLVED; six video checks DEFERRED.
Original ISO, Stage69/79 ISO and existing save data: NEVER MODIFIED OR DELETED.
No PSP RAM modification, no Korean render fix claimed.
Detail: run=20261013_123635_568_2784; phase=postflight_hash; key1 screenshot + scene-specific nonpausing memory font-argument; no ISO writes
<!-- STEP_088_FIX1_MANAGED_END -->

<!-- STEP_089_MANAGED_BEGIN -->
## STEP 089 — Controlled renderer-entry context snapshots
Last Updated: 2026-10-13T12:46:38+09:00
Status: CAPTURED_UNVERIFIED
Run: 20261013_124555_670_16824
Probe: one-shot controlled stop at MIPS renderer entry, registers plus bounded pointer regions, immediate resume; no memory writes.
Stage79: BUILT_UNVERIFIED; Mission2 Korean > rendering UNRESOLVED.
INT92: BUILT_UNVERIFIED; New Objective: UNRESOLVED; six video checks DEFERRED.
Original ISO, Stage69/79 ISO and existing save data: NEVER MODIFIED OR DELETED.
No PSP RAM modification, no Korean render fix claimed.
Detail: run=20261013_124555_670_16824; phase=postflight_hash; key1 screenshot + single controlled renderer breakpoint + bounded memory samples; ISO/RAM unchanged
<!-- STEP_089_MANAGED_END -->

<!-- STEP_090_MANAGED_BEGIN -->
## STEP 089 — Controlled Korean UTF-8 source read snapshots
Last Updated: 2026-10-13T12:57:14+09:00
Status: CAPTURED_UNVERIFIED
Run: 20261013_125626_064_7396
Probe: three one-shot stops on Korean string source reads, registers plus bounded pointer regions, immediate resume; no memory writes.
Stage79: BUILT_UNVERIFIED; Mission2 Korean > rendering UNRESOLVED.
INT92: BUILT_UNVERIFIED; New Objective: UNRESOLVED; six video checks DEFERRED.
Original ISO, Stage69/79 ISO and existing save data: NEVER MODIFIED OR DELETED.
No PSP RAM modification, no Korean render fix claimed.
Detail: run=20261013_125626_064_7396; phase=postflight_hash; key1 screenshot + Korean UTF-8 source readwatch + bounded memory samples; ISO/RAM unchanged
<!-- STEP_090_MANAGED_END -->

<!-- STEP_091_MANAGED_BEGIN -->
## STEP 091 — Unicode glyph font-selection capture
Last Updated: 2026-10-13T13:19:57+09:00
Status: CAPTURED_UNVERIFIED
Run: 20261013_131908_803_16796
Probe: conditional post-UTF-8 Unicode renderer entry; capture font object and glyph records; safe resume; no memory writes.
Stage79: BUILT_UNVERIFIED; Mission2 Korean > rendering UNRESOLVED.
INT92: BUILT_UNVERIFIED; New Objective: UNRESOLVED; six video checks DEFERRED.
Original ISO, Stage69/79 ISO and existing save data: NEVER MODIFIED OR DELETED.
No PSP RAM modification, no Korean render fix claimed. Mission2 font selection must be proven.
Detail: run=20261013_131908_803_16796; phase=postflight_hash; key1 screenshot + Unicode decoded-glyph selective code breakpoint; font struct and bounded memory; ISO/RAM unchanged
<!-- STEP_091_MANAGED_END -->

<!-- STEP_092_MANAGED_BEGIN -->
## STEP 092 — Read-only mission2 font owner provenance
Last Updated: 2026-10-13T13:29:20+09:00
Status: CAPTURED_UNVERIFIED
Run: 20261013_132832_369_9560
Probe: mission2 caller RA at renderer entry, Unicode font owner, 878-glyph resource descriptors; no memory writes.
Stage79: BUILT_UNVERIFIED; Mission2 Korean > rendering UNRESOLVED.
INT92: BUILT_UNVERIFIED; New Objective: UNRESOLVED; six video checks DEFERRED.
Original ISO, Stage69/79 ISO and existing save data: NEVER MODIFIED OR DELETED.
No PSP RAM modification, no Korean render fix claimed. Wrong 150-glyph font selection proven in STEP091; caller/resource linkage not yet proven. No patch applied.
Detail: run=20261013_132832_369_9560; phase=postflight_hash; key1 screenshot + Korean caller/font-owner and resource provenance, read-only; ISO/RAM unchanged
<!-- STEP_092_MANAGED_END -->

<!-- STEP_093_MANAGED_BEGIN -->
## STEP 093 — Read-only mission2 upstream font argument source
Last Updated: 2026-10-13T13:40:51+09:00
Status: CAPTURED_UNVERIFIED
Run: 20261013_133951_693_17716
Probe: mission2 renderer font a1 and upstream font t0 source at 0x089F5E24, original caller RA; no memory writes.
Stage79: BUILT_UNVERIFIED; Mission2 Korean > rendering UNRESOLVED.
INT92: BUILT_UNVERIFIED; New Objective: UNRESOLVED; six video checks DEFERRED.
Original ISO, Stage69/79 ISO and existing save data: NEVER MODIFIED OR DELETED.
No PSP RAM modification, no Korean render fix claimed. STEP091/092 confirmed missing Hangul in active 150-glyph renderer font and MIPS source via t0. Upstream font provider is probe target; no patch applied.
Detail: run=20261013_133951_693_17716; phase=postflight_hash; key1 screenshot + live renderer a1 and upstream t0 source, read-only; ISO/RAM unchanged
<!-- STEP_093_MANAGED_END -->

<!-- STEP_094_MANAGED_BEGIN -->
## STEP 094 — Read-only mission2 wrapper caller origin
Last Updated: 2026-10-13T13:47:13+09:00
Status: CAPTURED_UNVERIFIED
Run: 20261013_134621_216_4152
Probe: mission2 renderer font a1 and wrapper 0x089F6430 calling instruction/RA; no memory writes.
Stage79: BUILT_UNVERIFIED; Mission2 Korean > rendering UNRESOLVED.
INT92: BUILT_UNVERIFIED; New Objective: UNRESOLVED; six video checks DEFERRED.
Original ISO, Stage69/79 ISO and existing save data: NEVER MODIFIED OR DELETED.
No PSP RAM modification, no Korean render fix claimed. STEP091-093 confirmed missing Hangul in active 150-glyph font; STEP093 established RA=0x089F64C8, via wrapper 0x089F6430. Wrapper caller is probe target; no patch applied.
Detail: run=20261013_134621_216_4152; phase=postflight_hash; key1 screenshot + live renderer a1 and font forwarding wrapper caller RA, read-only; ISO/RAM unchanged
<!-- STEP_094_MANAGED_END -->

<!-- STEP_095_FIX1_MANAGED_BEGIN -->
## STEP 095 FIX1 — Passive nonintrusive font-owner field sampling
Last Updated: 2026-10-13T14:26:15+09:00
Status: FAILED
Run: 20261013_142608_834_28916
Probe: passive WebSocket memory.read of owner 0x09A69A90+0x28, NO breakpoints or CPU pause; no PSP RAM writes.
Stage79: BUILT_UNVERIFIED; Mission2 Korean > rendering UNRESOLVED.
INT92: BUILT_UNVERIFIED; New Objective: UNRESOLVED; six video checks DEFERRED.
Original ISO, Stage69/79 ISO and existing save data: NEVER MODIFIED OR DELETED.
No PSP RAM modification, no Korean render fix claimed. STEP091-093 confirmed missing Hangul in active 150-glyph font; STEP093 established RA=0x089F64C8, via wrapper 0x089F6430. STEP094 proved indirect JALR at 0x089F6F0C and owner+0x28=0x09A74150. STEP095 FIX1 samples field changes; no instruction writer provenance is claimed and no patch applied.
Detail: run=20261013_142608_834_28916; phase=arm_passive_owner_observer_before_mission; PASSIVE no-breakpoint owner+0x28 polling; key1 screenshot; ISO/RAM unchanged; Korean render not fixed
<!-- STEP_095_FIX1_MANAGED_END -->

### STEP 095 FIX3 ??2026-10-13 15:23:18 +09:00
- Run ID: 20261013_152233_064_16448
- Result: FAILED/INCOMPLETE
- Child exit: ; PPSSPP PID: 31528; alive at finish: True
- Screenshot files: 1; original ISO and saves untouched; no breakpoints or RAM writes
- ZIP: PROJECT_ROOT\log\fall_bia_STEP_095_FIX3_start_exit_capture_20261013_152233_064_16448.zip
- Korean rendering fix: NOT APPLIED


### STEP 096 ??2026-10-13 15:33:46 +09:00
- Run ID: 20261013_153259_912_25344
- Result: CAPTURE_COLLECTED, runtime QA pending
- Child exit: ; PPSSPP PID: 32376; alive at finish: True
- Screenshot files: 1; original ISO and saves untouched; no breakpoints or RAM writes
- ZIP: PROJECT_ROOT\log\bia_STEP_096_dynamic_font_discovery_20261013_153259_912_25344.zip
- Korean rendering fix: NOT APPLIED



<!-- STEP097_CODEX_NATIVE_UFONT_BEGIN -->
## STEP097 — Mission2 actual native UIFont expansion
Date: 2026-10-13
Status: VERIFIED_CHAPTER2_INTRO_AND_3D_CAPTIONS
Latest candidate ISO: PROJECT_ROOT/BIA_STEP097_MISSION2_UFONT_TEST.iso
Source: Stage79 compiled967; source SHA-256 unchanged.
Native UIFonts 0x09A74150 and 0x08FC3CA0: original Latin150 + per-MDI Hangul727 =877 each. Selection/call forwarding and PRX unchanged. Original strings, atlas and Latin records preserved.
Fresh ISO launch: PPSSPP v1.20.4, software renderer, isolated copied saves, START -> X -> X -> X. No PSP RAM/register writes or breakpoints. Chapter2 location line, Baker introduction caption and Leggett/Hartsock 3D scene captions visually verified in Korean instead of >>>. Both live fonts877 and Korean lookup samples verified.
Not claimed: all967 runtime QA, other missions fixed, every objective/top hint verified, hardware renderer verified. New Objective unresolved; six movie checks still deferred.
Evidence/workspace: SESSION_SESSION_OUTPUTS/step097 and outputs/step097_validation.
<!-- STEP097_CODEX_NATIVE_UFONT_END -->

STEP097 추가 확인: 챕터2 플레이 화면의 상단 사격조 튜토리얼 문구도 한글 표시됨. 사용자가 “한글 잘 나오네”로 확인. 전체 캠페인 검수는 사용자 플레이로 진행 예정이며 다른 미션의 native UIFont 확장은 아직 미적용. 현재 실행은 테스트용 복사 memstick을 사용하므로 본 검수는 사용자의 평소 PPSSPP에서 STEP097 ISO를 열어 진행 권장.

<!-- STEP098_CODEX_NATIVE_UFONT_ALL_BEGIN -->
STEP098: 모든32개 번역 맵 native UIFont64개 적용/재읽기검사 완료. SOURCE STEP097 SHA-256 보존. 신규30개맵60글꼴 확장, 기존 챕터1·2 유지. 모든 맵 번역문에 필요한 문자 조회 검증 통과. 평소 PPSSPP에서 BIA_STEP098_ALL_CHAPTER_UFONT_TEST.iso를 열어 플레이 검수. 모든챕터 실기검수 완료를 주장하지 않음. 초기 VRAM 잔상 때문에 STEP098 캡처는 새 화면 증거에서 제외.
<!-- STEP098_CODEX_NATIVE_UFONT_ALL_END -->

STEP099: 사용자 ULUS10193_00030/00031 스크린샷의 영어잔여를 수정. 전체32맵474값번역참조 적용 및 독립ISO재읽기검증. 자세한 기록 SESSION_SESSION_OUTPUTS/step099. 새UI실행화면검증은 미완료.


STEP100 제보(2026-10-13): 비에르빌 전투 끝부분에 ton만 표시되는 자막 화면 ULUS10193_00032.jpg. 해당미션 끝리스너 대사번역은파일에있음. 원본MDI에도ton단편이있으므로단편삭제/추정번역을하지않음. 현재플레이RAM을멈춤/쓰기권한없이읽었으나이미다음미션(D1_1830로추정)으로넘어가재현장면의문장참조를확정못함. 수정미적용/STEP099최신유지. 정확한장면의RAM 또는앞뒤음성대사/상태저장이추가단서. 보고서 SESSION_SESSION_OUTPUTS/step100_probe/issue_report.json.

## STEP101 — Save loading localization (2026-10-13)
Latest ISO: PROJECT_ROOT/BIA_STEP101_SAVE_LOADING_KO_TEST.iso (source STEP099 preserved).
User screenshot ULUS10193_00033: LOAD_PROFILE is external MEMORYSTICK.INT, not a compiled campaign FString. Updated LOAD_PROFILE, CHECKING_MEMORYSTICK, SAVE_FAILED, CONTINUE_WITHOUT_SAVING (both sections), M_LOADERROR and M_DATACORRUPTED to UTF-8 Korean, preserving keys. Also patched 24 verified STARTING_LOAD_PROFILE compiled value references across maps using unused stream35 space at 0x32000; native glyph coverage and unchanged font/atlas/PRX/menu data verified. ISO readback passed. Actual boot loading UI still requires user visual verification; no user PPSSPP control or save edits performed. STEP100 Vierville 'ton' remains unresolved.
Build/audit evidence: outputs/step101, scripts work/audit101_loading.py, build101_loading.py, verify101_loading.py.

## STEP102 — Chapter failed menu localization (2026-10-13)
Latest ISO: PROJECT_ROOT/BIA_STEP102_CHAPTER_FAILED_KO_TEST.iso; source STEP101 preserved.
Screenshot ULUS10193_00034 reported untranslated Chapter Failed / Reload Checkpoint / Restart Chapter / Quit Chapter / Select. Applied 챕터 실패 / 체크포인트 불러오기 / 챕터 재시작 / 챕터 종료 / 선택 to 390 verified compiled value references in 30 map resources. Metadata keys excluded, native glyph coverage verified, payloads use previously empty stream35 0x33000. Font data, atlas, PRX and prior fixes preserved. Independent ISO readback passed. Runtime visual verification pending; user PPSSPP and saves untouched. STEP100 ton remains unresolved.
Evidence outputs/step102; work/audit102_failed.py, build102_failed.py, verify102_failed.py.

## STEP103 — Reload/restart/quit confirmation localization (2026-10-13)
Latest ISO PROJECT_ROOT/BIA_STEP103_RELOAD_CONFIRM_KO_TEST.iso, source STEP102 preserved.
Screenshot ULUS10193_00035: reload confirmation English. Translated five related full confirmation messages (checkpoint reload, chapter restart, mission restart, main menu quit, skirmish menu quit), 145 verified value references in 30 map resources. Payload storage stream35 0x34000; original identifiers/font/atlas/PRX preserved and required glyph availability verified. ISO readback passed; runtime visual verification pending. Evidence outputs/step103 and work/*103* scripts. User game and saves untouched. Vierville ton issue still unresolved.

## STEP104 — Checkpoint reload crash investigation, incomplete
User screenshot ULUS10193_00036 reports STEP103 crash in chapter after Vierville (D1_1830), Unknown access 0x38313144, PC 0x088B9C8C. Disassembly places PC inside FString archive serialization loop; cause unproven. Initial read-only capture from PID21908 is not crash-state evidence (log/current code disagrees); do not infer root cause from it. Created isolated portable PPSSPP with copied ULUS10193 savedata, confirmed log memstick uses outputs/step104_runtime/portable/memstick. Owned runtime PID28548/debug26431, STEP103 boot; paused before mission, input timed out. No crash reproduction or fix yet. Computer Use stopped by physical Escape during screen recovery; no further UI actions taken. Queued owned harness quit. No user saves changed. Latest ISO remains STEP103, checkpoint reload defect unresolved. Evidence outputs/step104_runtime, outputs/step104_crash (non-crash capture), work/runtime104.py and analyze104_crash.py. Need resume isolated reproduction; user PPSSPP window must not be operated.

STEP104 user reproduced checkpoint reload crash on monitored STEP103, portable own PID24280, port26431. Captured outputs/step104_user_repro/paused_088b9c8c_regs.json and 32MiB paused_088b9c8c_ram.bin. PC088B9C8C, attempted address305F3244 (ASCII D2_0), FString object s1=09A857E4 has pointer overwritten with map-name characters and n=cap23. Static matching MDI is D2_0630_.MDI stream26 offset527C4, not D1_1830. Root cause not proven. Custom string pool allocator88B9518 and free88B91B4 involved. Current user reproduction PPSSPP is crashed; debugger CPU breakpoint.add now returns CPU not started. No binary fix built. Initial outputs/step104_crash RAM was unrelated live state; only user_repro snapshot is valid crash evidence. Need trace allocator return before 088B9C48 and oldptr at088B9C20 on another reproduction to establish overlapping allocation/free corruption, not mask invalid accesses. Monitor script work/monitor104_user.py remains attached until emulator closes or1h. Do not terminate user recreation window automatically.

## STEP104 — Candidate static translation string lifetime fix (2026-10-13)
Built PROJECT_ROOT/BIA_STEP104_CHECKPOINT_STRING_LIFETIME_TEST.iso from STEP103; source preserved. User second reproduction outputs/step104_alloc_repro again crashed at088B9C8C with invalid string-pool allocation pointer5A09D000. Overlap watch at088B9C48 did not fire; the earlier allocation-overlap hypothesis is not proven. First valid crash pool free-list bucket2 was0x8 and bucket3 linked into injected translation payload stream35 near09E7B064, outside owned pool chunk ranges. Candidate fix hooks FString string-pool Free VA0xB51B4, returns directly for pointers in static campaign stream35 [09E6B020,09EE3020), preserves original first two instructions and original routine for other pointers. New helper runtime08E02FB0, moduleend08E03000 < MDIbase08E03020. Existing section payloads/relocations preserved except8-byte entry jump; all MDI/DSL/DSX resources unchanged.8 Unicorn boundary/original-path tests passed, ISO readback passed. Runtime NOT VERIFIED, root cause remains candidate until reload test succeeds. Evidence outputs/step104_fix. Owned test PPSSPP launched PID24512 port26432 with STEP104 ISO, copied saves in portable/memstick, monitor work/monitor104_fixed.py output outputs/step104_fixed_repro, exec session96806. User should reproduce checkpoint reload on this fresh window; monitor captures crash but does not auto-close process. No user originals/saves modified. STEP104 is test candidate, do not call fully fixed until runtime confirmed.

STEP104 runtime validation COMPLETE: user confirmed 정상작동한다 after reproducing checkpoint restart in monitored STEP104 window. Monitor latest status showed pausedfalse/steppingfalse; no crash capture exists; runtime log ended with normal NativeShutdown. Latest validated ISO PROJECT_ROOT/BIA_STEP104_CHECKPOINT_STRING_LIFETIME_TEST.iso includes prior translations and string lifetime guard. build_report runtime_verifiedtrue with test scope specified. Other chapters' restart paths not individually verified, Vierville ton remains pending. Test process24512 exited; monitor ends on process exit, no need to close emulator or alter user saves.

## STEP105 — Mortar and grenade pickup text (2026-10-13)
Latest ISO PROJECT_ROOT/BIA_STEP105_MORTAR_PICKUP_KO_TEST.iso from validated STEP104; source preserved. Screenshot ULUS10193_00037 showed English mortar interaction and grenade pickup. Updated 64 verified UseMortarMessage localization references in32 maps to %icon_use% 버튼을 눌러 박격포를 사용하십시오. (icon retained; English action token replaced with Korean imperative). Updated30 exact aligned PickupUsableUSHandGrenade.PickupMessage FString references to 수류탄을 획득했습니다.; property-value verification used exact source sentence and n=cap29, excluded identifiers/stream2.94 references ISO readback passed; per-map native glyph coverage confirmed. Payload storage empty stream35+35000; STEP104 static string lifetime protection covers it. BIAOFF PRX and prior fixes unchanged, independent runtime screen verification pending. Evidence outputs/step105, work/audit105_pickup.py, verify105_pickup_refs.py, build105_pickup.py, verify105_values.py. User emulator/saves untouched. Vierville ton pending.

## STEP106 — Font renderer descriptor candidate fix (2026-10-13)
User ULUS10193_00038: completion screen Korean title/medal/button labels rendered stripes/noise. User identifies mission immediately before Purple Heart Lane; read-only live capture PID28760 matches D4_1800_.MDI native big font09AC4DE0, small08FC3CA0, both859glyphs. Clone09E82220 still512x512; glyph tables/remap present. Its cached FTexture descriptor pointer+E0=09B124B8 has owner+10=09ACA680 (different texture), not clone09E82220. Original good Big descriptor09AE6090 owns09AC4E50. Static disassembly FTexture vtable08D70EA0: GetCacheID returns+8/+C, GetRevision+14 with owner+10, GetUSize/+VSize read owner+48/+4C. Candidate allocates a dedicated24-byte FTexture descriptor in previously empty stream35+17400, vtable08D70EA0, ownerclone, revision1; clone+E0 nowpointsown descriptor. CacheID permap high32CRC32(mdi), low32cloneaddressshift8|E0;32 distinct IDs verified to avoid retained crossmapcache collisions. Original atlas pixels/glyph records/all strings/PRX (STEP104 fix) unchanged, only clone+E0 andempty32Bspace. All32 maps patched and reread verified.
ISO SESSION_SESSION_OUTPUTS/step106_fix/BIA_STEP106_FONT_RENDER_OWNER_TEST.iso (D: insufficient space, so C: workspace output). Source STEP105 preserved. Evidence outputs/step106_font/current_ram.bin,live_fonts.json; outputs/step106_fix/build_report.json; work/build106_descriptor.py then verify106_descriptors.py (second script assigns distinct mapcacheIDs). Runtime NOT YET VERIFIED; do not call completed screen fixed until user tests. No user PPSSPP control or save modifications in this turn. Latest runtime-validated checkpoint fix still STEP104; STEP105 text andSTEP106fontcandidate lackvisualvalidation. Vierville ton pending.

## STEP107 — Purple Heart Lane heading/location/date (2026-10-13)
Latest test ISO SESSION_SESSION_OUTPUTS/step107/BIA_STEP107_PURPLE_HEART_LOCATION_KO_TEST.iso, source STEP106 preserved (font candidate still lacks runtime completion-screen confirmation).
User screenshot00039: Purple Heart Lane / Northwest of Carentan, France / D+4 18:00 June10,1944 English. Applied 퍼플 하트 레인 / 프랑스 카랑탕 북서쪽 / D+4 18:00 1944년6월10일.60 localization title/date references across map copies plus3 actual D4_1800 LevelInfo native property FStrings (stream13 offsets5444C title,54464combineddate,54470location). Exact original values/sourceINT verified; property author Sun yu at54458 untouched. Payloads stream35+36000 and37000, nativeglyphcoverage checked for title/localizationvalues, datesuseASCIIplusalreadyavailable년월일. Independent ISO readback60+3 passed. Prior checkpoint fix/font descriptor/translations preserved. Other chapter heading/location strings were inspected and remain partlyEnglish; do not claim allchapters heading translated. Runtime verification pending. Evidence outputs/step107 and work/*107* scripts. User PPSSPP/save untouched. Vierville ton pending.

## STEP108 — Push Into Carentan heading (2026-10-13)
Latest candidate ISO SESSION_SESSION_OUTPUTS/step108/BIA_STEP108_CARENTAN_LOCATION_KO_TEST.iso, sourceSTEP107 preserved. Screenshot00040: translated Push Into Carentan to 카랑탕 진격, Carentan, France to 프랑스 카랑탕, June12,1944 to1944년6월12일; actual D6_0500 LevelInfo stream13 offsets5444C/54464/54470 verified and combined date D+6 05:00 1944년6월12일.110 total relevant localized/property value references changed across30 mapresources. Nativefontglyphcoverage and ISOreadback passed. Payload empty stream35+38000. Previous checkpoint/renderer/translation fixes preserved, runtimevisualverificationpending. Otherchapterheadingstrings remain partiallyEnglish, do not claim allchapters headings completed. Evidence outputs/step108 and work/*108* scripts. Usergame/savesuntouched; Vierville ton andSTEP106completionfontvisualvalidation stillpending.

## STEP109 — All active mission titles and campaign location names (2026-10-13)
User requests all mission and place names. Latest ISO SESSION_SESSION_OUTPUTS/step109/BIA_STEP109_ALL_MISSION_NAMES_KO_TEST.iso, sourceSTEP108 preserved. Covered all20campaign and12regularskirmish map titles, all20campaign start locations, mission selection catalogs embedded in maps, plus fallback localization files.1993 verified aligned localized/native valueFString refs changed,8additional already-Korean header consistency/date-format refs,2LevelSummaryTitle refs,230fallback values in39INT files. Native LevelInfo title/date/location inventory atstream13 offsets5444C/54464/54470 independently verified all32titles haveKorean and20definedcampaignlocations haveKorean; skirmish locations/date originalundefined placeholders preserved (no inventedlocations). Dates reformatted Korean alongside heading names. Internal map identifiers/keys unchanged. SourceoriginalEnglishbytepools may remain intentionally; actual refs patched. Newtextstorage35+39000,42000,43000. Font coverage checked allnative fonts; atlas/nativeglyph/PRX/renderdescriptor unchanged. New title translations use 동이틀때/야간조명/고양이와쥐 with existingglyphs. Outputs step109 build_report,iso_translation_check,all_levelinfo_check,int_updates,levelsummary_checks; work*109 scripts.24alternate client/server networkbundles SKR_O_* were scanned, have Englishnames but differentmodulefontaddresses; notmodified, onlineplay outside current32active-map implementation. Menu ON_MEMU_O has no remaining matchedEnglishcatalogvalues (alreadyKO); preserved. Runtimevisualvalidationpending, STEP106fontcandidatecompletionconfirmationstillpending, Viervilletonpending. No useremulator/savesmodified.

## STEP110 — Pause menu remaining labels (2026-10-13)
Latest ISO SESSION_SESSION_OUTPUTS/step110/BIA_STEP110_PAUSE_MENU_KO_TEST.iso, sourceSTEP109 preserved. User00041 Pause/ResumeChapter/Options/Back untranslated. Updated332 verified localized valueFString refs across30active mapresources to 일시정지/챕터계속하기/설정/뒤로. Supplement ResumeMission/Game targets were searched, no eligibleEnglishrefs. Identifier/key exclusion preserved. Nativefontglyphcoverage checked and independent ISOreadback332passed. Payload empty35+44000,16-bytealigned buffers. Priortranslations/atlas/fonts/PRX/rendererdescriptor unchanged. Runtimevisualverificationpending. Evidence outputs/step110 and work*110scripts. NouserPPSSPP/savesmodified. Remainingglobal: STEP106completionfont runtimeconfirmation,Viervilleton,alternatenetworkresources.

## STEP111 — Missing Mac radio caption; compact ISO at requested PROJECT_ROOT (2026-10-13)
User00043 missing MAC_X fromD7_1400_NOBETTERSPOT/D7_1500_NOBETTERSPOT. Applied 맥: 젠장, 무전기로 연락하지 않으면 우리 다 죽어! to2verified compiled localization refs (bothpart1/2). Nativefontglyphcoverage andISOreadbackpassed; empty35+45000 payload,16alignment, STEP104staticstringguard covers it.
Latest ISO PROJECT_ROOT/BIA_STEP111_RADIO_SUBTITLE_KO_TEST.iso. User explicitly requested ISOs located PROJECT_ROOT; persist this outputdirectory preference. Dfree1.527GB insufficient for3.35GBSTEP110. NTFScompressCSTEP110 completed, bytesunchanged, physical3.109GB stilltoo large. Instead repacked ISO: retained directory/header/path-table prefix151552bytes, copied all1147active files tosequential sectoraligned extents, updated bothendian fileextent/PVDvolumesize fields. No filecontents changed duringrepack, verifiedall1147SHA256, nofilesdeleted fromISO; obsoleteappendedversions excluded. Then only2mapresourcespatched; postpatchall1147filebytesSHAverifiedagain with2expectedmodifiedMDIhashes. Finalsize ~1.42GB fitsDwithoutdeletinguserfiles. No originals/saves/emulator changed; sourceSTEP110preserved (NTFScompressionstorageattributeonly). Evidence outputs/step111:repack_inventory,repack_check,build_report,iso_translation_check; work/audit111_radio,repack111_iso,build111_radio,verify111_radio,verify111_repack. Runtimeboot/visualvalidationpending; do notclaimplayedcompactISO. Existing unresolvedfontSTEP106completionconfirmation/Viervilleton/alternatenetworkresource translation remain.

## STEP112 candidate and verification hang (2026-10-13)
Candidate PROJECT_ROOT/BIA_STEP112_DIALOGUE_AND_INTERACTION_KO_TEST.iso, not released as runtime validated. Added16 missed compiled dialogue FString refs,8840 interaction/pickup/weapon value refs across32maps+menu,941 fallback INT display values in29files,4 Korean nativeTI1 title cards (Bookends3 and first jump). Catalog767unique voiced sentences from839sourceoccurrences: final remaining_dialogue_audit.json has0eligible English dialogue references. SourceSTEP111 preserved. Reports outputs/step112; scripts work/*112*. Independent complete interaction readback and prior font/PRX regression validation still needed. Menu stream35 extended0x1000 with6translated buffers (originallen133104), runtime risk needs checking; payloadcampaign35+47000. Movie playback remains deferred.
User reported test PPSSPP hang. Owned verification process28720 was stopped through runtime112_smoke.py quit command; confirmed no PPSSPPWindows64 processes remain. User saves untouched. Same apparent wait also occurred with baselineSTEP110, so STEP112 regression not established. Cached cpu.status PC0891B6D4 belonged idle0, NOT proof of infinite loop. Thread319 user_main waits semaphore at088D6594; s1=08E2D020 menu base, sp09FEC3A0; regs outputs/step112_runtime/wait_thread_regs.json. ShowProgressThread also semaphore wait. Own log outputs/step112_runtime/ppsspp.log has framebuffer copy warnings but no established root cause. GPU debugger output fails Could not download output; native CUA capture twice timed out (stop repeating). SoftwareRendererFalse restored; D3D11 backend2. Earlier read-only hangRAM outputs/step112_hang/current_ram.bin. Next investigate menu loading wait at088D6594 and verification settings before publishing112. Do not mistake idle cached regs for corruption. Latest user-received ISO remainsSTEP111.
STEP112 hang analysis/fix: captured RAM caller08817798 enters loader error loop08817770, filename stack ON_MEMU_O.MDI. Loader expected original stream35 decoded133104 bytes, builder extended by4096 despite fixed loader length. Original stream35 entirelyzero; relocated6menu translations into its existing zero area atoffset0 instead of extending. work/fix112_menu_length.py independently preserves originaldecodedlength and6refs/fontkeys. Rebuilt currentDSTEP112 menu. Runtime afterStart successfully exitsShowProgress loader: user_main running(waitType0), AudioWorker/AudioDecode/Async threads created, SaveIO loaded privateprofile, menuATRAC music decode. Evidence outputs/step112_runtime/menu_fix_status.json andppsspp.log. Test harness currentownedPID1028/session62567 stillopen atmenu, nav112_command.json quit closesonlyowned. BaselineSTEP110 earlier apparentidlewait notsufficientcausal proof; do notsaybaseline110sameconfirmedloadererror. RootcauseSTEP112menuextension confirmedby successfulsameenvironment boot after lengthfix. Fullallchapters/translationvisualvalidationstillpending; 6deferredmoviesmustnotplay.
STEP113 report user00049 partially corruptedHangul objective Capture88mm guns andmillhouse; Completed! untranslated. Read-only captured userPPSSPPPID28240 (pathoriginal2026-09-18),32MiBRAM outputs/step113_font/current_ram.bin, noinputs/pause/writes. Liveatlas fingerprint uniquely matchesD10_0801.MDI (diff0); D10_0600diff1307 initiallymisidentifiedfromobjectivecatalog. D10_0801 nativefonts854glyphs. Atlas34first0x40000, RFont35first0x17000, dedicatedFTexture35+17400 allbyte-identicaltoSTEP112 ISO. CloneUTexture09E82220 retains512dims, rendererptr09E82420. Thus CPUatlas/table/descriptorcorruption notobserved; GPUcache/renderpath investigation pending, do notclaimrootcauseorfix. UseraskedasyncwhichISO andcontinuousplayvsload, answerpending. Scriptscapture113_font/analyze113_font/compare113_font/match113_map; static_live_comparison.json/map_match.json evidence. UserPPSSPPmustnotcloseorcontrol. RemainingCompletedstatuslabeltranslationneedsaudit.
STEP114 (2026-10-15) screenshot partialEnglishPauseMenu. Read-onlyuserPID34380 snapshot outputs/step114_menu/current_ram.bin, liveatlasmatchesD10_0802; STEP112interactionpayloadpresent, STEP110pausepayloadzero. Source audit110 excludedEnglishstring ifprecedingbytewasnot0/FF; removedthisinvalidboundaryconstraint in audit114_menu.py while retainingalignedFString/keyverification/identifierexclusion. Found247stillEnglishrefs across32MDIs:192Completed! +55menu refs including D10_0802Pause/Resume/Options/Back/Restart/Quit. Built PROJECT_ROOT/BIA_STEP114_MENU_COMPLETION_KO_TEST.iso fromSTEP112, payload35+50000 existingzeroes, originalstreamlengthpreserved,64UIFontglyphcoveragepassed, sourcehashunchanged, allatlas/font/PRX/menuMDI/DSLbytespreserved. Independent verify114_menu.py readback247KoreanFStringpayloadspassed. Runtimevisualverificationpending; no userinput/save/processchanges. Prior STEP113continuouschapterfontcorruption stillunresolved and mustnotclaimfixedby114. SourceSTEP112preserved.
STEP115 fontbleed candidate (2026-10-15): screenshots00050chapterselectionbody/footerand00051mainmenu edgesdouble/blur. Read-onlyPID34952RAM outputs/step115_font/current_ram.bin, nouserinputs/changes. Offline menu ON_MEMU_O.MDI RFontstream23 existing696Hangul records UV ranges from(x+.5,y+.5)to(x+17.5,y+16.5) overcells17x16, endpoints1pixelbeyondlastcellpixelcenters. 580/696have nonzero adjacentneighborpixels; menu_uv_analysis.json evidence. This is plausibleatlasbleedcause, notprovencompleteexplanationforengineshadows/GPUcachecorruption. Built PROJECT_ROOT/BIA_STEP115_FONT_UV_INSET_TEST.iso fromSTEP114: insetonlyu1by1/128andv1by1/256 foraddedHangul/curlyquoteRFontrecords in32mapsstream35plusmenustream23. First8recordbytes/advancefields unchanged, decodedstreamlengthsidentical, allatlaspixels/nativeUFonttables/PRX/DSLunchanged, allMDIISOreadbackpassed. Workbuild115_uv.py reportoutputs/step115_font/build_report.json. Runtimevisualvalidationpending; testcandidateonly. Do notclaimfullfontcorruptionfixed; STEP113continuouschapterGPU/cacheproblemstillunresolved. Sources114and112preserved. Needusertest menu0050/0051visualcomparisonafterfreshISOload; donotautomaticallycontroltheirrunninggame.
STEP116 tutorials and aimed teammate labels (2026-10-15): user00052/53/54 TRAIN_X/Y/Z firstmission strategicflanking/suppressingfire popups plus00055 Plt.Sgt.Hassay English. Catalog62TRAIN values:57alreadytranslatedinmaster,5missing newlytranslated (firstmission3 plusmortardismount2).40TeammateName displayvalues fromGBXGAMEPLAY.INT translated, rankskept andsurnameconsistent with existingdialogueactors (Risner리스너,Obrieski오브리에스키,McCreary맥크리리 etc). Hassay하세이상사, tutorialnicknamed맥상사. Preservedallcontroltokens sortedexact. Audited32regularmaps+menu noinvalidprecedingbytefilter, found1802eligiblecompiledrefs (56namerefs/map +10tutorialrefs), all32mapspatched. SourceDSTEP115UVcandidate preserved; outputPROJECT_ROOT/BIA_STEP116_TUTORIAL_CHARACTER_NAMES_KO_TEST.iso. Existingzero35+52000payload16aligned, no decodedstreamlengthchange,64nativefontHangulcoveragepassed, allfont/atlas/UV/PRX/menuMDI/DSL preserved.6INTfallbackfiles107displayvaluesupdated. Independent finalISOreadback1802UTF8ptr/n/capverified; work/prepare116,targets116,audit116,prep116_build,build116,fallback116,verify116. Evidenceoutputs/step116. No userPPSSPPinputs/saves/processchanges. Actualpopup/namevisualverificationpending; do notclaimallgameEnglisheradicated. STEP115visualbleedcandidate andSTEP113continuouschapterglyphcorruptionremainunconfirmed/unresolved.
STEP117 NewObjective + transient postureicon investigation (2026-10-15): user00056plantTNTposeicon greenopaque rectangle, alsoMGmount, returnsnormalafteractionends (userconfirmed). Do nottreatpersistentfontcorruptionorsavestatecause. Built PROJECT_ROOT/BIA_STEP117_NEW_OBJECTIVE_KO_TEST.iso fromSTEP116,128NewObjective compiledrefs across32MDIs ->새목표, 2GBXHUD.INTfallbackvalues, independentverify117128passed. Payload35+54000empty16aligned, fontcoverage/oldatlas/PRX/UV/decodedlengthpreserved. Source116preserved. Outputnotclaimiconfixed.
Icon evidence outputs/step117_icon: read-onlyuserPID34952RAM32MiB, noinputs/pause/resume; allUTexturecachedrenderownercheck0mismatches incurrentcapture. Compared200validUTextureheaderobjects inD0_0130 againstoriginalISO:199originalheadersidentical,onlyaddedHangulclone35+17200different. StillneedbadstateGPUcapture. LocalPPSSPPGPURecordSubscriber.cpp confirms gpu.record.dump recordsnextframewithoutpause; capturedcurrentframe viauserdebugger26420 tocurrent_gpu.ppdmp,478241bytes, outputs/current_gpu_summary.json. Currentframe notconfirmedbadpose; don'tclaimitshowscause. Asyncaskedusertoreproduceplant/mountandreportwhilebroken, answerpending. Readywork/capture117_gpu.py fornextframeandcapture117_icon.py forRAM; bothassertuserPID34952 (refreshPIDbeforefutureturn). GPURecord.cpp/Format.h andparse_bia_gpu_dump.py alreadylocal. Nothirdpartypluginneeded, no usergamecontrol/savechanges. Remaininglivefailurepossiblytexturealpha/UV/GPUcache specificaction state; notestablished. PriorSTEP113continuouschapterglyphcorruption unresolved,115UVcandidatevisualvalidationpending.
STEP118 font gutter candidate (2026-10-15): user00059 difficulty쉬움etc andbodytextstilloverlap; STEP115UVinsetaloneinsufficient. Do notclaimestablishedshadow/spacingrootcause. SourceSTEP117; builtPROJECT_ROOT/BIA_STEP118_FONT_GUTTER_TEST.iso. Re-rasterizedonlyaddedHangul atlas17x16cells usingMalgun14instead16, centeredinside1pixelclearborder onall4edges. All33resources(32maps+menu) patchatlas34/menu22 only; exactpernibbleallowedcellmaskverified allLatin/icon/outsidepixelsunchanged. UV/metrics/advances/lineheight/nativefonttables/text/PRX/DSL/streamlengthunchanged. Allbordersassertedzero, nativeMDI+ISOreadbackpassed, preservedsource117. Workbuild118_gutter.py, outputs/step118_font/build_report.json andglyph_size_comparison.png (top16/bottom14 inspectedoffline); runtimevisualpending. TradeoffHangulglyphinksapproximately2pixelsmaller, fixedadvanceunchanged. SomecurlyquoteexcludedfromHanonlymaskbydesign. CaptureuserPID34952RAMread-onlyoutputs/step118_font/current_ram.bin; currentRAMisnotmenu23locationso cannotinferloadedmenuUVversionfromthatcapture. Usergameuntouched. Postureicontransientbadstatecapture stillpending, continuouschapterGPUglyphcorruption unresolved. Avoidassertingcompletefixwithoutactualscreenshotcomparison.
STEP119 requestedFreeLook/Press/Checkpoint (2026-10-15): sourceDSTEP118, outputPROJECT_ROOT/BIA_STEP119_ACTION_FREELOOK_CHECKPOINT_KO_TEST.iso. FreeLook->자유시점, Checkpoint->체크포인트. Pressgeneratedbyactiontoken, actualstringslowercasepress; uppercaseUIautomatic, notliteralPress. TranslatedTRAININGBUTTONS ACTION values press누르기, hold누르고있기, pressandhold길게누르기, tap짧게누르기, release누름해제, move이동. Initial놓기glyph놓absent;changedreleasewordbeforeanymapwrite, fontchecksallpassed. Native6FStringpropertysequence [press,tap,release,hold,hold,move] verified192fields across32maps, field4longpress->길게누르기. Also nativeHUDdisplaycontexts FreeLook precededSpectatingView/followedNewObjective andCheckpoint precededLoadCheckpoint/followedCONNECTING or precededOracleCamTargetSelf/followedLoadingProgress,2272refs verified; avoidsblindidentifierreplacement. Total3904valueFStrings patched32resources, payload35+56000originalzeroes,16alignment. Allnativefontglyphcoverage/ISOreadback and independentverify1193904passed. Fallback119 updatesINTexactdisplayvalues includingTRAININGBUTTONS/GBXHUD/GBXSCRIPTED/NEWLOCALIZE; reportoutputs/step119/fallback_translation_check.json. Allmetadatafonts/UV/gutteratlas/PRX/menuMDI/DSLunchanged, decodedstreamlengths preserved, source118hashpreserved. Evidenceaudit119,native119_actions,finalprep119,build119,fallback119,verify119 underwork; reportsoutputs/step119. Runtimevisualvalidationpending, notclaimallremainingEnglishfixed. PostureicontransientbadstatecaptureandSTEP113continuousfontcorruptionstillpending; STEP118guttervisualconfirmationpending. UserPPSSPP/savesuntouched.
STEP120 Mac aimedname consistency: user explicitly prefersaimed하세이상사->맥상사consistentwithsubtitle맥. BuiltPROJECT_ROOT/BIA_STEP120_MAC_NAME_KO_TEST.iso fromSTEP119,32verifiedcompiledTeammateNamevalueFStringrefs across32regularmapresources, exactUTF8bytecounts. FallbackGBXGAMEPLAY.INT1valueupdated. Independentverify12032passed; fontcoverage/fontatlas/gutter/UV/PRX/DSL/menuMDI/streamlengthunchanged, source119preserved. Payload35+58000existingzeroes16aligned. Workprep120,audit120,build120,fallback120,verify120 reportsoutputs/step120. Runtimevisualvalidationpending; allpriorunresolvedicontransient/fontGPUissuesremainpending. Usergame/savesuntouched. FuturecharacterlabelcanonicalMacis맥상사, don'treintroduce하세이상사inTeammateName.
STEP121 diagnostic only (no newISO): user00061 someHangulcellsnoise; FreeLookstillEnglish. Read-only userPID34952 RAM outputs/step121_font/current_ram.bin, CPUstatuspausedTrue (didNOTresume/pause/input). CurrentcapturedmapuniquelymatchesSKR_US_BROK.MDI pre118atlas(D112/116) diff0, screenshotD0_0130dialogueMAC_ZF isearliermoment; doNOTcomparecurrentRAMtofirstmissionasif same map. Crucial definitiveinspection: installedpsutiltoscopedwork/python_deps then psutil.Process(34952).open_files filteredonlyISO/CSO/CHD/PPST returns PROJECT_ROOT/BIA_STEP116_TUTORIAL_CHARACTER_NAMES_KO_TEST.iso. Evidenceoutputs/step121_font/open_game_files.json. Thus currentusergameNOTSTEP118/119/120, latestfontgutter/freeLook/Macnamefixesnotloaded. Explainedcannotjudgeeffectofthelatercandidatesfrom116screenshot, andnotclaim120provennoiseFix. LatestcompleteISOstillPROJECT_ROOT/BIA_STEP120_MAC_NAME_KO_TEST.iso (cumulative118/119). Userownsactiveplay; DO NOTautoclose/restartorswapISOandloseprogress. Suggestnormalgame-saveandnextfullboot120, avoidloadingoldemulatorstatewhenvalidatingnewassetdata. CurrentCPUpaused preventsrecordnextframe; capture121_gpu.pydidNOTrequestrecordsincepaused. Originalnoise/GPUcacheunresolveduntilnewversiontestedatproblemstate. No userprocesswrites/savemodifications. Workversion121.py earlycomparisonwrongD0mapandthereforediffsnotrootcause; map_match.json iscorrectcurrentmapidentification.
STEP122 diagnostic only: user00062quitconfirmation showsnoiseat뉴/니다 and아니오. RecheckeduserPID34952openISOread-onlyviafilteredpsutil: stillSTEP116. CPUstatuspausedTrue,steppingFalse,ticks247958777091; PauseOnLostFocusFalse/PauseWhenMinimizedFalse, so doNOTinferfocuspauseorautomaticallyresume. Originalsource116 SKR_US_BROKfontatlasdecodedwithknown4bitPSPswizzle: source_upper_cells.png shows뉴/니/다/단actualbitmapsclean. These glyphs are clustered atlaspagex128..255,y0..31; e.g뉴179,0;니145,16;다179,16. Normalneighbor돌230,48. This regionpattern mayhelpGPUupload/cache investigation, notestablishedrootcause. NeedbadframeGPUcommand/texturecapture whenuserchoosestorun; don'tpause/resumetheirgame. NoISOproduced. Workinspect122_positions.py/preview122_cells.py,outputs/step122_font/source_upper_cells.png. ExplainedCPU/sourceimageclean/current116old; doesNOTprove120solvesnoise. Stillunresolveduntilactualruntimecapture/newversioncheck. Usercancontinuereporting116defects; avoidclaiminglatestvalidatedorblindnewcandidates.


<!-- STEP125_SPEAKER_BREAKS_SAFE_BEGIN -->
## STEP125 — Restore movie subtitles at speaker transitions
Date: 2026-10-15 20:18:32
Status: BUILT_UNVERIFIED (STATIC_READBACK_PASS, RUNTIME_QA_PENDING).
Source: PROJECT_ROOT\BIA_STEP124_TEXT_REVIEW_KO_TEST.iso
Output: PROJECT_ROOT\BIA_STEP125_SPEAKER_BREAKS_KO_TEST.iso
Source SHA256: 9600e3c08572d20c4b251e6d6413545f33851de4fc09825f9b61b66d9d2beffa
Target SHA256: 6d431b60b0ba23ff01347cfd9ee8393a2bc7d55047ba1d4daafbc1ef82a433fb
Preserved STEP124 as original source; three one-byte 0x20->0x5C speaker boundaries corrected: EM_1230_BOOKENDS2.ST1 field9, EM_VICTORYINCARETAN.ST1 field4, FM_0115EAGLESJUMP.ST1 field15.
No font/texture/PRX/text/ISO bytes changed elsewhere (entire-file SHA256 readback). 133 subtitle fields retain the STEP124 11px font; 130 others byte-for-byte inherited.
PPSSPP and saves untouched; runtime movie playback & menu overlap & ongoing noise/icon issues UNVERIFIED.
Step log: PROJECT_ROOT\log\STEP_125_speaker_breaks_20261015_201815
<!-- STEP125_SPEAKER_BREAKS_SAFE_END -->


<!-- STEP126_LEGGETT_RANK_BEGIN -->
## STEP126 — Leggett addressing Mac by rank
Status: BUILT_UNVERIFIED; real runtime verification pending.
Source: PROJECT_ROOT\BIA_STEP125_SPEAKER_BREAKS_KO_TEST.iso
Output: PROJECT_ROOT\BIA_STEP126_LEGGETT_MAC_RANK_KO_TEST.iso
Corrected one exact text field: 하지만 병장님 -> 하지만 중사님.
Active resource: /PSP_GAME/USRDIR/SYSTEM/D0_0130_EAGLES.INT
Source SHA256: 6d431b60b0ba23ff01347cfd9ee8393a2bc7d55047ba1d4daafbc1ef82a433fb
Target SHA256: 5e34a186cd2eec3e9420068ff9eb15f907177a27901498873067120300c87ace
Other bytes unchanged; STEP125 user runtime check of font and speaker breaks still baseline.
Other Leggett Sergeant contexts and icon bugs unverified; user PPSSPP and saves untouched.
<!-- STEP126_LEGGETT_RANK_END -->


<!-- STEP127_FIX1_LEGGETT_MDI_BEGIN -->
## STEP127 FIX1 — Compiled MDI Leggett rank subtitle
Status: BUILT_UNVERIFIED (static ISO/MDI readback PASS, PPSSPP runtime PENDING).
Source: PROJECT_ROOT\BIA_STEP126_LEGGETT_MAC_RANK_KO_TEST.iso
Output: PROJECT_ROOT\BIA_STEP127_FIX1_LEGGETT_MDI_KO_TEST.iso
Resource: /PSP_GAME/USRDIR/SYSTEM/D0_0130_.MDI, stream35 offset0x1181C; LEGGETT_H value ptr0x09E7C83C, reference stream26 offset0x73978.
Text: 레겟: 하지만 병장님... -> 레겟: 하지만 중사님... (fixed 31-byte UTF-8 value).
All other decoded streams/strings, original PPSSPP/saves, and STEP126 ISO preserved.
Original valid rank references (e.g. Allen 병장님) unchanged.
Source SHA256: 5e34a186cd2eec3e9420068ff9eb15f907177a27901498873067120300c87ace
Target SHA256: c76f757c2bb306640df2cfecf3055adcd68f6fc2ec6df275bbfb849501217958
Unresolved elsewhere: runtime icon issue and earlier glyph noise (user reported no current noise on STEP125).
<!-- STEP127_FIX1_LEGGETT_MDI_END -->


<!-- STEP128_WITHOUTSAVING_BEGIN -->
## STEP128 — MC_WITHOUTSAVING raw default string
Status: BUILT_UNVERIFIED (static readback PASS; in-game confirm popup NOT YET verified).
Source STEP127 FIX1 (user reported its Leggett fix works): PROJECT_ROOT\BIA_STEP127_FIX1_LEGGETT_MDI_KO_TEST.iso
Output: PROJECT_ROOT\BIA_STEP128_WITHOUT_SAVING_KO_TEST.iso
Changed ONLY the exact raw English MC_WITHOUTSAVING default associated with the original key
to 저장하지 않고 계속하시겠습니까? in MDI stream24. Existing compiled Korean values preserved.
Files changed: D0_0130_.MDI
SHA256: 01533a85a663f6fe0e8ecf1833dfcd6778a948914899c2af44195a3261d80f0a
Do not claim screen fixed until screenshot runtime verification. Original PPSSPP/saves not touched.
<!-- STEP128_WITHOUTSAVING_END -->

## STEP129 — ISO compact from verified STEP127 FIX1 (2026-10-15)
- Status: BUILT_UNVERIFIED (static checks PASS; runtime/boot pending)
- Input: PROJECT_ROOT\BIA_STEP127_FIX1_LEGGETT_MDI_KO_TEST.iso, SHA256 c76f757c2bb306640df2cfecf3055adcd68f6fc2ec6df275bbfb849501217958
- Output: PROJECT_ROOT\BIA_STEP129_COMPACT_STEP127_FIX1_KO_TEST.iso, SHA256 99091ae6abd1c3d5462ba1e299116eb77081aa4fb5bb417542f2039fe2254cae; size 1413019648 bytes
- All 1147 active ISO files full-sector SHA256 readback PASS; ISO records and structural prefix verified.
- User PPSSPP/saves and previous ISOs untouched. Do not publish before independent PPSSPP boot + gameplay validation.
- STEP128 unsolved English `ARE YOU SURE YOU WANT TO CONTINUE WITHOUT SAVING?` is excluded from this base.
