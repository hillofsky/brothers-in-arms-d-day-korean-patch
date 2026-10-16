from pathlib import Path
import zipfile
p=Path('outputs/bia_handoff_2026-10-06.md');s=p.read_text(encoding='utf8').replace(chr(92)*2,chr(92));s+='\n## 인계 시 마지막 상태\n진단용 Python session 1552와 이 세션이 실행한 PPSSPP PID 26628은 quit 명령으로 정상 종료했습니다. 분석/스크린샷/검증 보고서를 보존했으며 추가 게임 패치는 진행하지 않았습니다.\n';p.write_text(s,encoding='utf8');zpath=Path('outputs/bia_stage40y_handoff.zip')
with zipfile.ZipFile(zpath) as z:items={i.filename:z.read(i) for i in z.infolist()}
items['README_handoff.md']=p.read_bytes()
with zipfile.ZipFile(zpath,'w',zipfile.ZIP_DEFLATED) as z:
 for name,data in items.items():z.writestr(name,data)
with zipfile.ZipFile(zpath) as z:assert z.testzip() is None
print('Handoff finalized')
