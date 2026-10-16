# STEP 074 FIX6

## Cause and correction
FIX5 matched the two original TMR18 font roles successfully in 31 target MDIs,
but incorrectly required the Stage40Y first-mission texture-object address
0x09A8D6D0 to hold the exact same object at that same address in every MDI.
Those MDIs have different texture layouts and data at that fixed address.

FIX6 uses the exact matched second original font-role texture pointer from
that MDI's +0x488 table. In the verified first mission that pointer equals
Stage40Y's 0x09A8D6D0, but elsewhere it is MDI-specific.
The selected object must be readable, nonzero, and unchanged from the original
ISO to Stage69. First-mission byte similarity is logged but not misused as a
cross-mission invariant.

All 32 MDIs are dry-run before any output ISO exists.
Each MDI's outcome is persisted immediately to per_mdi_dryrun_progress.jsonl.

## Result
IN_PROGRESS

Time: 2026-10-08T15:35:00+09:00
Result: FAILED
Detail: STEP074 FIX5 failed safely. Source Stage69 preserved; inspect template-role/blocked evidence.
