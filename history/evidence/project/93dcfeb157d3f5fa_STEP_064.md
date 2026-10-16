# STEP 064

## Why This Step Exists
STEP_063 proved the campaign translation corpus is complete but also showed
that summarized translation-unit references contain `+N more` truncation and
did not recover the historical Stage43 campaign patcher.

## Goal
- Read Stage38 `stage38_entry_map.tsv` to recover every exact source occurrence.
- Verify the 1165 unapplied IDs against exact reference counts.
- Snapshot and validate the corresponding extracted SYSTEM `.INT` files.
- Inventory Stage43T ISO campaign-related files.
- Search PROJECT_ROOT and historical ZIP logs for the actual first/second-mission
  campaign apply/rebuild scripts.

## Starting State
- VERIFIED_APPLIED: 137
- TRANSLATED_PENDING_APPLY: 90
- TRANSLATED_REVIEWED: 1075
- NEEDS_TRANSLATION: 0
- ISO modification: none

## Result
IN_PROGRESS

## Completion Update
Time: 2026-10-07T23:22:41+09:00
Result: VERIFIED
Detail: STEP064_RECOVERY_VERIFIED_occurrences_1435_patchfiles_110

## Verification
Recovery/discovery only. No ISO/resource mutation is claimed.

## Next Step
Analyze the exact occurrence manifest and recovered historical patch scripts,
then build the bulk campaign ISO application stage without guessing.
