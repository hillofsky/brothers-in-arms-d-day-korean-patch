# STEP 065

## Goal
Scan every Stage43T MDI against the 1165 translated-but-unapplied campaign
resource IDs and determine the exact compiled FString/font patch surface.

Checks:
- English value + original INT key matching
- compiled FString stream/offset
- ambiguous duplicate source strings
- missing compiled strings vs raw payload presence
- mission font-object candidates
- per-MDI extra Hangul demand vs proven Stage43A 60-slot extension budget
- matching DSL/DSX pair presence

## Starting State
- Campaign NEEDS_TRANSLATION: 0
- Unapplied campaign units: 1165
- Exact Stage38 source occurrences: 1435, verified in STEP_064
- ISO modification: none

## Result
IN_PROGRESS

## Completion Update
Time: 2026-10-07T23:33:49+09:00
Result: VERIFIED
Detail: STEP065_AUDIT_VERIFIED_resolved_0_unresolved_1165_font_over_0

## Verification
Audit only. Stage43T ISO remains untouched.

## Next Step
If compiled coverage/font capacity is safe, construct the actual bulk campaign
MDI/DSL/DSX/INT patcher. Any unresolved records must be recovered explicitly
instead of guessed.
