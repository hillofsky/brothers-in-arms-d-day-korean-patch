# Brothers in Arms: D-Day — 비공식 한국어 패치 (PSP)

**대상:** *Brothers in Arms: D-Day* 북미판 (USA v1.01, `ULUS10193`)  
**공개 버전:** `v0.1.0-beta` — 2026-10-15  
**상태:** 부분 검증 베타. STEP129 최적화본의 PPSSPP 정상 작동은 사용자 확인을 받았으나 전체 캠페인 및 모든 문구의 검증은 완료되지 않았습니다.

> 이 저장소에는 원본·수정 ISO, 게임 파일, 세이브 데이터를 올리지 않습니다. Releases에는 원본 게임을 소유한 사용자가 직접 적용할 **xdelta3 차이 패치**와 검증용 manifest만 제공합니다.

## 다운로드

[Releases에서 v0.1.0-beta 받기](https://github.com/hillofsky/brothers-in-arms-d-day-korean-patch/releases/tag/v0.1.0-beta)

Releases의 `bia-dday-korean-v0.1.0-beta.xdelta`(또는 분할 `.partNN` 파일)와 `manifest.json`을 받습니다. **원본 ISO가 필요한 패치**이며 게임 전체 파일이 아닙니다.

## 적용 방법

1. 본인이 소유한 **미패치 북미판 USA v1.01 / ULUS10193 ISO**를 준비합니다. 다른 판본 또는 이미 수정된 ISO에는 적용하지 마세요.
2. Python 3.9+와 [공식 xdelta3](https://github.com/jmacd/xdelta/releases)를 준비합니다.
3. `manifest.json`과 `.xdelta`(분할판이면 모든 `.partNN`)를 한 폴더에 저장한 뒤, 이 저장소의 적용 도구를 실행합니다.

```powershell
py -3 tools/apply_patch.py --source "D:\Games\Brothers in Arms - D-Day (USA) (v1.01).iso" --manifest "manifest.json" --xdelta "C:\Tools\xdelta3.exe" --output "D:\Games\BIA_DDAY_Korean_v0.1.0-beta.iso"
```

명령은 원본과 결과의 **크기·SHA-256을 검사**합니다. SHA-256이 맞지 않으면 적용을 중단하거나 생성 파일을 삭제합니다. 원본 ISO는 변경하지 않습니다.

GUI [Delta Patcher](https://github.com/marco-calautti/DeltaPatcher)에서도 같은 `.xdelta` 파일을 사용할 수 있습니다. GUI를 사용한 뒤에는 `manifest.json`의 `patched_iso.sha256`과 생성 ISO의 SHA-256을 비교하세요. 분할판의 경우 먼저 모든 파트를 순서대로 결합해야 합니다.

실제 PPSSPP에서 새로운 ISO를 **새로 부팅**해 검증하세요. 예전에 만든 세이브스테이트는 이전 메모리나 텍스처 상태를 복원할 수 있으므로 신규 패치 QA의 기준으로 사용하지 않는 것이 좋습니다. 일반 게임 내 저장 데이터는 사용자 판단에 따라 보존하세요.

## 배포 ISO 기준

- 내부 최종본: `BIA_STEP129_COMPACT_STEP127_FIX1_KO_TEST.iso` (1,413,019,648 bytes)
- 배포본 ISO SHA-256: `99091ae6abd1c3d5462ba1e299116eb77081aa4fb5bb417542f2039fe2254cae`
- STEP127 FIX1의 번역을 유지하면서 비사용 섹터를 정리한 ISO입니다. STEP128의 미해결 실험은 포함되지 않습니다.

## 번역 포함 범위

- 메인/게임 내 메뉴, 도움말 및 조작 설명의 한국어화 진행
- 캠페인 대사와 UI의 컴파일된 문자열 한국어화
- 영상 자막(화자 교체 시 줄바꿈 보존) 및 자막 글꼴 확대 후보 반영
- 스커미시 일부 자원과 이름 표기 번역
- 무기 모델명(`P38`, `M1`, `BAR` 등) 영문 유지, 주변 설명 한국어화
- `Staff Sergeant Mac`을 **맥 중사**로 표기하도록 보완
- 레겟의 `하지만 병장님...`을 `하지만 중사님...`으로 수정한 STEP127 FIX1 포함

## 확인된 상태와 알려진 문제

- **실제 화면 확인:** STEP125 영상 화자 전환 줄바꿈, STEP127 FIX1 레겟 호칭 수정, STEP129 최적화 ISO PPSSPP 정상 작동(사용자 확인).
- **정적 검증:** STEP127 FIX1 MDI 문자열 수정 및 STEP129 ISO9660 재배치 후 활성 파일 1,147개 SHA-256 일치.
- **남은 영어 문구:** `ARE YOU SURE YOU WANT TO CONTINUE WITHOUT SAVING?` (확인창). STEP128 시도에도 화면은 영어로 남아 있어 공개 기준에서 제외했습니다.
- **추가 QA 필요:** 전체 캠페인·스커미시·모든 영상 장면의 시각적 확인, 일부 메뉴 한글 겹침/일부 장면의 글리프 및 자세 아이콘 문제.

자세한 범위와 제한은 [검증 현황](docs/QA_STATUS.md), [릴리즈 변경점](docs/RELEASE_NOTES_v0.1.0-beta.md)을 참고하세요.

## 기술·법적 안내

비공식 팬 번역 프로젝트입니다. 원본 게임·이름·상표에 대한 권리는 각 권리자에게 있으며 제작사의 공식 지원을 받지 않습니다. 게임 ISO 또는 추출 리소스는 배포하지 않습니다. **패치 적용을 위해 적법하게 보유한 해당 판본의 ISO가 필요합니다.**

문제 제보에는 게임 버전, 패치 버전, 재현 위치, 스크린샷만 첨부해 주세요. 원본 ISO나 세이브 데이터는 첨부하지 마세요.

## Codex 세션에서 이어가기

[현재 상태](PROJECT_STATE.md) → [세션 인계](HANDOFF.md) → [운영 절차](docs/OPERATIONS.md)를 확인하세요. 저장소만으로 가능한 점검은 `python tools/check_resume.py`입니다. 전체 개발 재빌드 가능 여부와 게임 QA는 별도입니다.
