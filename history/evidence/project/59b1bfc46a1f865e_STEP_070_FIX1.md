# STEP 070 FIX1

## Goal
Launch only the Stage69 FIX2 test ISO in a dedicated PPSSPP instance, verify
the debugger PID and ISO path, capture the title/main menu, and sweep main-menu
highlight positions without confirming any option.

Also search PSP RAM for:
- 스커미시 로비
- 게임 팁:
- 늪을 건너

A RAM hit means runtime loading only; it does NOT prove rendering.

## Safety
- ports restricted to 26420..26439
- temporary appendconfig only
- no normal ppsspp.ini modification
- no unrelated PPSSPP process is killed or controlled
- all input goes through the verified WebSocket instance

## Result
IN_PROGRESS
