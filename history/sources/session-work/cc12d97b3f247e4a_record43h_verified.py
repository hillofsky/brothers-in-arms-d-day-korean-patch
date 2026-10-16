from pathlib import Path
import json
p=Path('outputs/stage43h/font_report.json');r=json.loads(p.read_text());r.update(runtime_verified=True,runtime_evidence='outputs/stage43h_validation/first_hint_0x4000000.png',remaining_issues=['long hint left edge clipped','mission restart stability unverified','second mission translations not applied']);p.write_text(json.dumps(r,indent=2),encoding='utf-8')
p=Path('outputs/bia_campaign_progress.md');s=p.read_text(encoding='utf-8').replace('실제 화면의 한글 표시 및 재시작 안정성은 아직 검증 중입니다.','첫 미션의 목표 방향 힌트가 실제 화면에 한글로 표시되는 것을 확인했습니다. 긴 문장의 왼쪽 일부가 잘리는 문제와 재시작 안정성 검증이 남아 있습니다.');s+='\n실행 검증 화면: stage43h_validation/first_hint_0x4000000.png. 목표·힌트 글자 깨짐 해결을 확인했으나 모든 문구의 배치 검증은 완료하지 않았습니다.\n';p.write_text(s,encoding='utf-8')
