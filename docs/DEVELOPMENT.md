# 다른 환경에서 개발 이어가기

기록일: 2026-10-16. Python 3.9+ 표준 라이브러리만 사용하는 개발 도구를 추가했다. 개인 경로·Windows API·에뮬레이터 연결 없이 파일로 동작한다. NTFS/ext4 등 하드링크를 지원하는 출력 파일시스템이 필요하다. 출력과 임시 자료를 위한 여유 공간을 확보한다.

## 시작점

1. 저장소를 clone하고 AGENTS.md와 PROJECT_STATE.md를 읽는다.
2. 사용자가 보유한 원본 ISO를 README의 해시와 대조한다.
3. README에 연결된 Releases에서 해당 누적 xdelta를 받아 기존 적용 도구로 기준 ISO를 만든다. 저장소 소스만으로 과거 모든 단계를 처음부터 다시 만드는 경로는 아직 제공하지 않는다.
4. 아래 개발 도구로 기준 ISO를 조사하고 별도 후보를 만든다. 기준 해시가 다르면 중단한다. 후보를 다시 입력하는 연속 적용은 아직 지원하지 않는다. 누적 변경은 기준 ISO에 적용할 하나의 편집 명세/리소스로 관리한다.

공개 Git 파일 + Releases 패치 + 소유한 원본 ISO로 아래 범위의 개발을 시작할 수 있다. 개인 작업 폴더 전체는 필요하지 않다. 편집한 게임 리소스와 ISO는 local/ 등 로컬에만 보관한다.

## BIA: 번역 원장과 MDI

- data/recovered/text_master.tsv: 캠페인 1,302행. 과거 status는 당시 기록이며 STEP129 적용 여부를 행별로 다시 증명한 것은 아니다. 원장을 바꾸는 것만으로 ISO에 반영되지 않는다.
- data/recovered/movie_subtitles_ko.tsv: 영상 자막 133행. 별도 영상 수정 경로는 이번 도구 범위에 포함하지 않는다.
- tools/dev/bia_formats.py: 역사적 Stage36에서 ISO/MDI 순수 파일 처리 함수만 복구. 런타임 제어 코드 제외.

저장소 루트에서 다음을 실행한다. 경로는 실제 사용자 파일로 바꾼다.

```powershell
python tools/develop.py inspect --source "STEP129.iso" --resource D0_0130_.MDI
python tools/develop.py extract --source "STEP129.iso" --resource D0_0130_.MDI --output "local/mission-streams"
python tools/develop.py build --source "STEP129.iso" --resource D0_0130_.MDI --edits "local/edits.json" --output "local/candidate.iso"
```

edits.json은 아래 형식의 배열이다. 예시는 **변경 없는 재압축 검사**다. offset은 압축 해제한 stream35 안의 바이트 위치다. 수정할 위치와 현재 문자열은 추출 결과에서 확인한다.

```json
[{"stream":35,"offset":71708,"old":"레겟: 하지만 중사님...","new":"레겟: 하지만 중사님..."}]
```

자동 빌드는 stream35의 NUL 종료 UTF-8 문자열, 동일 바이트 길이, 기존 문구의 한글 문자 재사용 범위로 제한한다. 제어 토큰과 줄바꿈을 보존하며 겹치는 편집을 거부한다. 키·포인터·길이·폰트 구조는 건드리지 않는다. 더 긴 번역, 새 한글 글리프, 새 문자열/폰트 확장, 다른 스트림은 추가 개발이 필요하다. ASCII도 모든 글꼴에서 표시된다고 보장하지 않는다.

MDI를 재압축한 뒤 모든 압축 해제 스트림을 비교하고, ISO에 재삽입한 결과를 다시 읽는다. 원본 ISO 영역에서는 대상 디렉터리 레코드와 볼륨 크기 필드 외 바이트가 보존되는지 검사한다. 후속 후보는 테스트 전용이며 릴리즈 manifest를 변경하지 않는다.

## 이번 검증과 남은 범위

실제 검증 결과는 docs/PORTABILITY_VALIDATION.md를 따른다. 새 후보의 정적 검증은 기존 릴리즈의 런타임 검증을 상속하지 않는다. PPSSPP normal boot, 해당 화면, 일반 저장/불러오기를 별도로 확인하고 기록한다. Linux/macOS 실환경 실행은 아직 확인하지 않았다.
