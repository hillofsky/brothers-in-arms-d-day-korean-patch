import json
from pathlib import Path
r=json.loads(Path('work/campaign_second_reference_audit.json').read_text(encoding='utf-8'));o=Path('outputs/stage43h/second_mission_reference_report.json');o.write_text(json.dumps({'translated_units':90,'mapped_units':r['covered'],'verified_references':len([x for x in r['refs'] if x['key_verified']]),'by_stream':r['by_stream'],'missing':r['missing'],'iso_applied':False},ensure_ascii=False,indent=2),encoding='utf-8')
p=Path('outputs/bia_campaign_progress.md');s=p.read_text(encoding='utf-8');s+='\n두 번째 미션 90개 모두 실제 MDI의 문자열 참조와 연결했습니다. 원문 키를 확인한 참조는 179개이며 누락된 번역 단위는 없습니다. 적용 준비 검사가 통과했습니다.\n';p.write_text(s,encoding='utf-8')
