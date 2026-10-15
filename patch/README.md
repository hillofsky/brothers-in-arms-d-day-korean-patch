# Release assets only

원본·수정 ISO 및 xdelta 파일을 Git 커밋에 포함하지 않습니다.

`manifest.json`은 로컬 배포 생성 도구가 실제 원본·패치 ISO SHA-256을 확인한 뒤 생성합니다.

`.xdelta`와 동일한 `manifest.json`은 GitHub **Releases 첨부 파일**로 업로드합니다.
