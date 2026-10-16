# STEP 074 FIX2

## Root cause
FIX1 incorrectly read FOUR entries from each original 151-glyph TMR18
width/height/texture renderer-page array.

Stage36 already proved the original font has exactly ONE valid entry:
- u16 width = 128
- u16 height = 256
- u32 texture object
Four renderer-page entries are created only by the Korean font expansion.

FIX2 corrects this interpretation and keeps the proven Stage39A/40Y/43A
generalization path.

## Result
IN_PROGRESS

Time: 2026-10-08T14:34:27+09:00
Result: FAILED
Detail: STEP074 FIX2 failed safely; inspect blocked evidence. Source Stage69 preserved.
