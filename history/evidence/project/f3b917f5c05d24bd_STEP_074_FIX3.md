# STEP 074 FIX3

## Root cause
FIX2 correctly changed the ORIGINAL TMR18 renderer-page arrays to one entry,
but then incorrectly reused Stage36's MENU-font logical-height expectation
(256) for the CAMPAIGN original font.

The exact original D0_0130_ font read during FIX2 is:
- width = 128
- height = 512

This does not conflict with the proven Korean expanded runtime form:
- four logical pages
- widths = [128,128,128,128]
- heights = [256,256,256,256]

FIX3 uses D0_0130_'s untouched original 128x512 font as the fingerprint for
discovering equivalent campaign font objects in the other MDIs.

## Result
IN_PROGRESS

Time: 2026-10-08T14:52:24+09:00
Result: FAILED
Detail: STEP074 FIX3 failed safely; source Stage69 preserved. Inspect blocked evidence.
