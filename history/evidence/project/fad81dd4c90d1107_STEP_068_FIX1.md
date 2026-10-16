# STEP 068 FIX1

## Failure Diagnosis
STEP_068 failed safely at its final assertion:
`Expected refined exact movie set of 71, got 106`.

The value 71 was inferred incorrectly from STEP067's broad historical-evidence
count. The authoritative source is Stage42A's actual 133 ST1 subtitle fields.

The failed STEP_068 made no ISO modifications.

## Goal
- derive exact/segment/normalized ST1 overlap from the actual Stage42A fields
- verify all 8 Stage42H ST1 files are preserved byte-for-byte in Stage43T
- refine the true non-movie remainder
- produce the complete 1165-ID apply split

## Result
IN_PROGRESS

## Completion Update
Time: 2026-10-08T00:07:49+09:00
Result: VERIFIED
Detail: STEP068_FIX1_VERIFIED_compiled_967_movie_106_nonmdi_92

## Verification
Static reconciliation only. No ISO mutation and no deferred movie playback validation.

## Next Step
Build the actual patcher for 967 compiled-MDI IDs and the 92 non-MDI/INT IDs,
while preserving the 106 movie-ST1 IDs already carried by Stage43T.
