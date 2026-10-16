# STEP 074 FIX1

## Root cause fixed
STEP074 incorrectly assumed every untouched campaign/skirmish MDI already had
the Stage39A/43A Korean font mapping. The STEP066 `font_objects_found` table is
a structural candidate inventory, not proof that the Stage39A glyph map was
installed.

Only D0_0130_ currently has the proven Stage43A font.

FIX1:
- derives the original 151-glyph production-font fingerprint from the original
  D0_0130_ MDI's two known runtime-proven font objects;
- discovers the matching two font objects per untouched target MDI;
- derives that MDI's existing Latin16 texture object from its font texture array;
- installs Stage39A 847-glyph donor atlas/metadata plus that MDI's <=31 extra
  glyphs into streams34/35;
- patches the unique DSL relocation + B8 descriptor using the proven Stage40Y
  pattern;
- places translated payloads in stream35 from 0x10000;
- patches only the exact STEP066 FString metadata refs;
- dry-runs all 32 MDIs before creating an output ISO.

D0_0130_ preserves its existing Stage43A font/DSL and only appends the remaining
target payloads after existing stream35 data.

## Result
IN_PROGRESS

Time: 2026-10-08T14:11:49+09:00
Result: FAILED
Detail: STEP074 FIX1 failed safely. Source Stage69 ISO preserved; inspect blocked_mdis/report.
