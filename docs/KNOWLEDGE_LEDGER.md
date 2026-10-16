# 확인된 지식과 실패·미검증 기록

정리일: 2026-10-16. 이번 작업은 로컬 코드/보고서 대조이며 과거 실험을 재실행하지 않았다. 아래는 다시 조사하기 전에 확인할 근거다. **과거 handoff/PROJECT_STATE는 역사 자료이며 현재 AGENTS.md나 사용자 지시보다 우선하지 않는다.**

| 이어 쓸 지식 | 반복하지 않을 판단/시도 | 근거 |
|---|---|---|
| 화면에 보이는 문자열은 compiled MDI의 FString 참조를 확인한다. INT/default 영어 문자열만 바뀌어도 화면은 그대로일 수 있다. | STEP128은 BUILT_UNVERIFIED이고 일부 후보 UNSUPPORTED_CODEC/SKIPPED였다. 현재 QA 문서에서 런타임 실패로 배포 제외됐다. 같은 시도를 성공 빌드로 재사용하지 않는다. | [근거](../history/evidence/project/d4eb79235f5703f9_build_report.json) · [현재 QA](QA_STATUS.md) |
| 화자 교체 줄바꿈은 문장 내 자동 줄바꿈과 다르다. 시간 표기의 콜론을 화자로 오인하지 않는다. | STEP124의 일괄 역슬래시→공백 처리 문제가 있었다. STEP125는 혼합 화자 3필드를 복구했다. 옛 STEP124 인계의 pending과 최신 STEP125 사용자 확인을 구분한다. | [근거](../history/evidence/project/0827e9ae6cca5101_HANDOFF_BIA_TRANSLATION_3.md) · [근거](../history/evidence/project/922ee850ab418cb4_build_report.json) |
| MDI 슬롯·폰트 구조를 유지한다. | 과거 기록에는 menu stream35 decoded 133104 bytes 유지, UIFont 폭과 RFont advance 구분, glyph byte7은 kerning이 아니라 padding으로 기록돼 있다. 이는 역사적 분석 근거이며 수정 전 현재 기준 바이트/객체와 대조해야 한다. | [근거](../history/evidence/project/0827e9ae6cca5101_HANDOFF_BIA_TRANSLATION_3.md) |
| 화면 노이즈·겹침·아이콘 문제는 원인 미확정이다. | STEP118/124의 gutter/advance 개선 후보를 전체 해결로 간주하지 않는다. GPU cache 가설도 확인되지 않았다. 최신 화면 재현부터 한다. | [근거](../history/evidence/project/0827e9ae6cca5101_HANDOFF_BIA_TRANSLATION_3.md) · [현재 QA](QA_STATUS.md) |
| STEP127 FIX1의 레겟 호칭은 INT가 아니라 D0_0130_.MDI stream35에서 수정했다. | decoded offset 0x1181c, reference stream26 offset0x73978, 기존 pointer 유지. 현재 portable 도구도 이 기준 문자열을 실제 읽어 검사했다. 다른 위치로 일반화하지 않는다. | [근거](../history/evidence/project/fbf0b2f59206678c_build_report.json) · [이번 도구 검증](PORTABILITY_VALIDATION.md) |
| 과거 빌드 스크립트에는 후속 ISO를 덮어쓰는 동작·정확한 old-byte assertion이 있다. | build123/build124 및 후속 grammar/movie 스크립트를 순서 확인 없이 다시 실행하지 않는다. 보관본은 PROJECT_ROOT/SESSION_* 경로 치환본이며 실행 가능한 재빌드 체인이 아니다. | [근거](../history/sources/session-work/4e79c2fefe8ff4f1_build124.py) · [근거](../history/evidence/project/0827e9ae6cca5101_HANDOFF_BIA_TRANSLATION_3.md) |
| 과거 복구 작업도 누락 근거 때문에 중단된 기록이 있다. | STEP072 BLOCKED_MISSING_EVIDENCE는 당시 상태다. 현재 복구 여부와 혼동하지 않고 HISTORY_INVENTORY/SOURCE_MAP에서 소스 존재 여부를 다시 검색한다. | [근거](../history/evidence/project/bea7b0e97fb4b1c3_step072_report.json) |

다음 작업자는 [작업 이력 탐색](HISTORY_INDEX.md)에서 단계/근거를 찾고, [함수 목록](SOURCE_MAP.json)에서 구현 위치를 찾는다. 현재 배포 manifest와 최신 PROJECT_STATE에 맞는 소스인지 확인한 뒤 필요한 부분만 사용한다. 미검증 범위를 새 분석 없이 완료 처리하지 않는다.
