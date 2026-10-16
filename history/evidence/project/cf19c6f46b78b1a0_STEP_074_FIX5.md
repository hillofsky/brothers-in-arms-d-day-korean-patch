# STEP 074 FIX5

## Root cause
The historical first-mission patch modifies TWO original campaign text-font
objects. They are not identical roles.

The failure sequence proves:
- one original role is 128x512;
- the other original role is 128x256.

FIX2 saw the 128x512 object first.
FIX3 then passed that metric check and reached the texture check.
FIX4 removed that texture equality check, continued to the second object, and
correctly observed 128x256.

The previous scripts incorrectly forced one shared metric and/or one shared
original texture onto both roles.

## FIX5
- derives both template metrics independently from the untouched D0_0130_ ISO;
- matches every target candidate to the corresponding template by exact metric
  plus normalized font-object similarity;
- does not require the two original texture objects to be equal;
- refuses ambiguous template-role matches;
- independently retains the Stage40Y expanded-Korean texture-object fingerprint;
- performs all 32 dry-runs before creating an ISO.

## Result
IN_PROGRESS

Time: 2026-10-08T15:29:24+09:00
Result: FAILED
Detail: STEP074 FIX5 failed safely. Source Stage69 preserved; inspect template-role/blocked evidence.
