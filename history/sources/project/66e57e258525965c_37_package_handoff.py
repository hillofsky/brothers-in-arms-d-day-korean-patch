# -*- coding: utf-8 -*-
from pathlib import Path
import json,zipfile
out=Path('outputs');note=r'''# brother in arms d-day2 인계 (2026-10-06)

사용자는 원래 채팅의 한글화 작업을 이어 진행했고, 이제 원래 채팅으로 진행 사항을 전달하라고 요청했습니다. 새 작업이나 추가 패치를 시작하기 전에 이 기록과 검증 보고서를 읽으세요.

## 파일과 작업 환경
- 현재 작업: LOCAL_PATH
- 게임/헬퍼/분석: PROJECT_ROOT
- 안정적인 메뉴 검증본: PROJECT_ROOT\\BIA_STAGE40O_CONTROLS_UTF8_COMPLETE_TEST.iso
- 최신 본편 UI 검증본: PROJECT_ROOT\\BIA_STAGE40Y_FIRST_MISSION_UI_TEST.iso
- 본편 실행 파일 패치만 검증한 비교본: PROJECT_ROOT\\BIA_STAGE40R_CAMPAIGN_RENDERER_TEST.iso
- Stage40O 자료: outputs/bia_stage40o_results.zip
- Stage40Y 자료/이 인계: outputs/bia_stage40y_handoff.zip
- 전체 캠페인, 실제 PSP, 저장/불러오기, 본편에서 메인 메뉴 복귀는 아직 검증 완료되지 않았습니다. 최종 배포본으로 표시하지 마세요.

## Stage40I의 원래 진단 정정
Stage40I import defaultdict 누락 및 RAM 검색 범위를 수정했습니다. 옛 0x08800000..0x0A800000 범위는 끝 8MiB를 조용히 건너뛰었습니다. 올바른 물리 RAM 전체는 0x08000000..0x0A000000, 32MiB이며 읽기 실패/길이 불일치는 오류로 처리합니다. raw LBN 9쌍을 ISO 파일에 매칭했고 INT 6개는 실제 읽혔습니다. 따라서 모든 loose INT가 미사용이라는 주장은 잘못입니다. LOCALIZE.INT 프로브의 실사용은 여전히 관측되지 않았습니다. 메뉴의 실제 표시 자료는 compiled MDI FString 메타데이터입니다.

## Stage40J-O 완료
Stage40F가 lookup key GAME/TYPE 등까지 번역하여 NewLocalize lookup 오류를 만들었습니다. Stage40J는 24개 compiled key 기록을 원본으로 복구하고 번역 value를 유지했습니다.
Stage40K는 메뉴 본문 글꼴 0x0972524C도 제목 글꼴 0x0972385C의 한글/글리프/아틀라스를 공유하게 하여 네모 표시를 해결했습니다. 두 글꼴 count=847, glyph ptr=0x098F5020.
Stage40L/O는 서로 다른 두 문자열 너비 계산 경로를 수정했습니다. widened UTF-8 2/3바이트 시퀀스를 UTF-16 codepoint로 해독하고 문자 순회 인덱스를 보정합니다. ASCII/기존 UTF-16, 잘못된 시퀀스는 유지하며 bounds/overlong/surrogate를 검사합니다. 원래 virtual width call로 tail call합니다. 독립적인 emitted MIPS byte 실행 테스트를 통과했습니다.
Stage40M은 제외 목록에 잘못 빠졌던 Stance/Action -> 자세/행동, Reload/Action -> 재장전/행동 두 value를 추가했습니다.
Stage40O에서 658/658 번역 payload, 복구 key 24개, main/options/controls/audio/game 메뉴를 RAM 및 화면으로 검증했습니다. Width trace 19,235개 모두 한글 codepoint, raw UTF-8 byte 호출 0개. 기존 renderer JAL은 e410330e.
BOOT.BIN와 BIAON.PRX에 width hooks를 적용했고 EBOOT.BIN의 기존 NOPE 진단 override를 유지했습니다. 실제 PSP용 패키징 방법은 아직 아닙니다.

## Stage40P-Y 본편 진행
스토리 -> 새 게임 -> 보통 -> 첫 임무를 진입했습니다. 캠페인은 BIAOFF.PRX를 별도로 로드하여 메뉴 렌더러 패치가 적용되지 않았습니다.
Stage40R은 별도 BIAOFF.PRX의 동일 기능을 byte signature로 찾아 패치했습니다. 아래 3개의 helper와 hook이 runtime disasm 및 call word 검증을 통과했고, 원래 영어 첫 임무 및 pause menu를 정상 실행했습니다.
- Unicode lookup VA 0x458ED4, runtime 0x08C5CED4
- Renderer call VA 0x18A354, runtime 0x0898E354 -> helper 0x08C9F468 (232 bytes); lookup tail delta RA+0x2CEB78
- Width call1 VA 0x4EB3C, runtime 0x08852B3C -> helper 0x08C9F560 (256 bytes)
- Width call2 VA 0x4E0C0, runtime 0x088520C0 -> helper 0x08C9F660 (256 bytes)
- Expected call words: 0x0E327D1A, 0x0E327D58, 0x0E327D98
- .rel.text file 0x59A558 size 0x15CDD8. Disable old C-JIS HI/LO records within helpers; reuse 0x6F51B8 / 0x6F51C0 as J26 call relocations; renderer original relocation 0x629798 stays active.

First mission assets: D0_0130_.MDI / DSL / DSX. Its MDI base is 0x08E03020, NOT menu 0x08E2D020; stride 0x78000.
Original font objects: stream30 offsets 0x7F64/0xA0FC -> runtime 0x09C1AF84 / 0x09C1D11C, each originally 151 glyphs.
Source file zero padding is NOT necessarily runtime free space: streams30-33 are partly used by runtime GE/graphics data. Stage40T font-only isolation reached the game, but its atlas in stream33 was overwritten and text garbled. Runtime comparison identified stream33 nonzero data up to 0x22DC8. Latest layout avoids this:
- Atlas stream34 runtime 0x09DF3020, 131072 bytes (512x512 swizzled T4 production atlas)
- Glyph/page/aux metadata stream35 runtime 0x09E6B020, 0xA860 bytes
- UTF-8 payloads stream35 starting offset 0xB000
- Both font objects now 847 glyphs and pointer 0x09E6B020
- Font texture object 0x09A8D6D0 (Latin16 image was visually identified; another 128x256 texture was a non-font effect and must not be patched)
- Actual GE descriptor runtime 0x09C8BE40. DSL relocation offset 0x31E2AE: old (0x40055140, 0x80, 0x4010E9C0), latest (0x40055140, 0x200, 0xF620CFE0). Negative absolute e2 makes the relocated texture address exactly 0x09DF3020 without assuming base2.
- DSL B8 at 0x4ACEE4 changes 0xB8000807 -> 0xB8000909. DSX logical bytes are rebuilt equal to DSL. Runtime GE words verified: 2030dfa0000209a8090900b8.
- Runtime relocation table appears at 0x08E3803C, but that source MDI region is zero scratch populated from DSX; do not patch the zero MDI region as if it were a stored relocation record.

Stage40S broad exact FString metadata patch stopped with invalid 0x2A2A2A40 write at 0x08CA045C during first mission load. Its exact root cause was not fully isolated. Do NOT promote S (or unverified U/V/X) based on ISO readback alone. The latest approach reduces scope to actual compiled localization value records in streams26/27 plus explicit first mission header fields in stream13. Require preceding FString to be a known INT key and reject records that are keys themselves. Never globally replace source literals or change internal identifiers.
Stage40W first proved pause/options/controls in Korean with all 309 payloads and stable fonts.
Stage40Y preserves all 411 W metadata references and adds 28 references, total 439 actions / 331 units / 325 distinct payloads. All 437 associated key records are unchanged. It adds 뒤로/계속/예/아니요 and the two slash labels; title/location/date strings are inserted, but their actual title-screen display has NOT been separately confirmed (opening movie may contain embedded English titles).
Y runtime report: 325/325 payloads exact, atlas hash exact, both glyph counts/pointers correct, all 3 helpers exact via debugger original disasm, all call words correct. Width trace 6,318 Hangul calls / 0 raw bytes; visible renderer 9,085 Hangul calls. Full 32MiB RAM read succeeds.
Y screens visually checked: pause (일시정지, 챕터 계속, 옵션, 체크포인트 다시 불러오기, 챕터 다시 시작, 챕터 종료, 뒤로/선택), options, controls (all intended labels including 자세/행동 and 재장전/행동). Game resumes, analog horizontal input turns the view; before/after actual 3D frames and compass show the change.

## Current unresolved interaction at interruption
After resuming and turning the view, attempting to return to main menu has NOT been successful. Start reliably reopens pause and cross resumes, but repeated d-pad down input in that later pause menu did not move selection off 챕터 계속 in captures (both buffers checked). Analog vertical and clearing all PSP button states did not visibly fix it. Earlier in the same Y run, down + cross successfully opened Options and controls; therefore do not prematurely classify the later behavior as a translation bug. Diagnose controller state, repeat timing, paused-menu input path and key/value roles before claiming menu-return passed. No observed emulator memory fault in Y.
At user interruption a Python live diagnostic/PPSSPP process may still be active. Last live unified exec session=1552, PPSSPP PID=26628. Check status before using it. Stop only the process owned by this diagnostic, not arbitrary user emulator processes.

## Runtime tools and reproduction
work/stage40y_live.py uses PPSSPP debugger on log-reported actual port (usually 26222; requested port may differ), software renderer, its single main websocket and atomic work/nav_command.json queue.
Write queue via a temporary nav_pending.json then Move-Item to nav_command.json; direct writing has raced into empty JSON before. Commands include name/buttons/wait/scan/trace/trace_address/trace_condition/disasmAddress/count/vram/regs/analog/hold_seconds/quit. Keep waits under 60 seconds.
input.buttons.press duration=2 in original helper may be short for some game navigation. A separate websocket can now successfully send input commands; use b.connect_debugger and ws.request, not an unconnected MiniWebSocket. Official input.buttons.send requires buttons={name: bool}; an up=[...] parameter is invalid. input.analog.send has x,y in [-1,1].
Menu/game frames use RGB565 at VRAM 0x04000000 and 0x04044000, stride512, 480x272 visible. Bink/movie title frames sometimes use RGBA8888; read full VRAM and decode accordingly. GPU screenshot API had failed repeatedly previously; raw VRAM + software renderer is the reliable diagnostic route here.
JIT overwrites original block first words with EMUHACK 0x68xxxxxx, so raw helper SHA alone can falsely fail. Debugger memory.disasm encodings preserve original opcodes; verify those against emitted helpers. Calls were also checked via raw RAM and disasm.
Scripts build_campaign40r.py and build_firstmission40y.py are in the handoff ZIP. They depend on existing PROJECT_ROOT helpers, Stage40O/R source ISOs, original INT/corpus/font plan/atlas. They intentionally refuse to overwrite existing target ISO. Do not install new emulators or reconstruct the entire prior chain unnecessarily.

## Remaining scope
- Resolve later pause navigation/main-menu return before promoting Y beyond UI test status.
- Verify header/title display and B-priority mission dialogue/subtitles/tutorials. Many B strings and other missions remain untranslated.
- Expand other mission fonts/resources using measured per-mission bases/texture relocations and runtime-safe allocations, not fixed menu offsets.
- Keep Stage40O as known menu baseline; Y is first-mission UI test, not full-game Korean completion.
'''
(out/'bia_handoff_2026-10-06.md').write_text(note,encoding='utf8')
with zipfile.ZipFile(out/'bia_stage40y_handoff.zip','w',zipfile.ZIP_DEFLATED) as z:
 z.write(out/'bia_handoff_2026-10-06.md','README_handoff.md')
 for rel in ['stage40y_validation/stage40y_report.json','stage40y/first_mission_patch_report.json','stage40y/translation_actions.json','stage40r/campaign_renderer_patch_report.json','stage40s_validation/stage40s_failure_report.json','stage40y_validation/ram_read_report.json','stage40y_validation/disasm_0x8c9f468.json']:
  z.write(out/rel,rel)
 for name in ['pause_korean','campaign_options','campaign_controls','gameplay_resume','gameplay_after_analog','pause_down_after_clear']:
  z.write(out/'stage40y_validation'/(name+'_0x4000000.png'),'screens/'+name+'.png')
 for path in ['work/build_campaign40r.py','work/build_firstmission40y.py','work/stage40y_live.py','work/report_y_runtime.py','work/audit_y_keys.py','work/test_width_machine.py','work/test_width40o_machine.py']:
  z.write(path,'tools/'+Path(path).name)
 for p in (out/'stage40r').glob('*_helper.bin'):z.write(p,'helpers/'+p.name)
with zipfile.ZipFile(out/'bia_stage40y_handoff.zip') as z:assert z.testzip() is None;print('Handoff ZIP verified:',len(z.infolist()),'entries')
