import json,ast,re
from pathlib import Path
o=Path('outputs/step123');t=json.loads((o/'translations.json').read_text(encoding='utf-8'));tree=ast.parse(Path('work/prepare109_titles.py').read_text(encoding='utf-8-sig'))
for node in tree.body:
 if isinstance(node,ast.Assign) and any(isinstance(x,ast.Name) and x.id=='t' for x in node.targets):t.update(ast.literal_eval(node.value));break
manual={
'Defend the town from the descending American paratroopers.':'강하하는 미군 공수부대로부터 마을을 방어하라.',
'Eliminate all enemy forces in a limited amount of time. Time will be awarded for killing enemies; using your squads to do so will award more bonus time. There are no checkpoints.':'제한 시간 안에 모든 적을 제거하라. 적을 처치하면 시간이 추가되며, 분대를 이용하면 더 많은 추가 시간을 얻는다. 체크포인트는 없다.',
'Make your way through an American occupied city to rendezvous with a German tank unit.':'미군이 점령한 도시를 통과해 독일군 전차부대와 합류하라.',
'Defend three Flak 38 gun positions from American paratroopers.':'미군 공수부대로부터 Flak 38 대공포 진지 세 곳을 방어하라.',
'Recapture the Hamlet to ensure a safe route for German supplies.':'독일군의 안전한 보급로를 확보하도록 마을을 탈환하라.',
'Hold your position as the American paratroopers work to break the line and reach the 88 ammo dump.':'미군 공수부대가 방어선을 돌파해 88mm 포 탄약고로 접근하고 있다. 진지를 지켜라.',
'Clear the warehouse district of US forces.':'창고 지구의 미군을 제거하라.',
'German tanks were bombed by American aircraft before they reached your position, leaving a number of Germans on foot.  Eliminate any survivors.':'독일군 전차들이 이곳에 도착하기 전에 미군 항공기의 폭격을 받았다. 살아남아 도보로 이동하는 독일군을 모두 제거하라.',
'Take the bunker and destroy the Flak 36 guns.  Once there hold the position.':'벙커를 점령하고 Flak 36 대공포를 파괴하라. 이후 진지를 사수하라.',
'Allied forces bombed an area where large amounts of German weapons and equipment were being stored and loaded to be moved by rail. Scout the bombed locations along the train tracks and also eliminate any survivors.':'연합군이 독일군 무기와 장비의 철도 수송 거점을 폭격했다. 철로를 따라 폭격 지점을 정찰하고 살아남은 적을 제거하라.',
'Crossroads':'교차로',
'Blow up the bridge to break the German supply route then destroy a train car carrying German supplies.':'다리를 폭파해 독일군의 보급로를 차단한 뒤 보급품을 실은 화물차를 파괴하라.',
'Clear the valley of German soldiers.':'계곡의 독일군 병사를 모두 제거하라.',
'Capture a heavily defended observation post set on a hill.':'방어가 삼엄한 언덕 위 관측소를 점령하라.',
'Eliminate any remaining soldiers.':'남은 적 병사를 모두 제거하라.',
'Objective':'목표','Defense':'방어','Time Challenge':'시간 도전','Wave Completed':'공격 차단 완료','Tour Completed':'작전 완료','Skirmish: Objective':'스커미시: 목표','Skirmish: Time Challenge':'스커미시: 시간 도전','Skirmish: Defense':'스커미시: 방어','Skirmish: Tour of duty':'스커미시: 연속 작전','Skirmish:Mission Completed':'스커미시: 임무 완료','Skirmish:Mission Failed':'스커미시: 임무 실패','Mission Completed.':'임무를 완료했습니다.','Mission Failed.':'임무에 실패했습니다.'}
t.update(manual);missing=json.loads((o/'missing.json').read_text(encoding='utf-8'));assert all(en in t or en=='null' for en in missing),[en for en in missing if en not in t]
entries=json.loads((o/'source_skirmish.json').read_text(encoding='utf-8'))
for r in entries:
 if r['english'] in t:r['korean']=t[r['english']]
for en in list(t):
 if en.strip() in manual:t[en]=manual[en.strip()]
for en,ko in t.items():assert sorted(re.findall(r'%[^%]+%',en))==sorted(re.findall(r'%[^%]+%',ko)),en
(o/'translations.json').write_text(json.dumps(t,ensure_ascii=False,indent=2),encoding='utf-8');(o/'source_skirmish.json').write_text(json.dumps(entries,ensure_ascii=False,indent=2),encoding='utf-8')
s=Path('work/audit112_interactions.py').read_text(encoding='utf-8-sig').replace('BIA_STEP112_DIALOGUE_AND_INTERACTION_KO_TEST.iso','BIA_STEP120_MAC_NAME_KO_TEST.iso').replace('outputs/step112/interaction_translations.json','outputs/step123/translations.json').replace("out=Path('outputs/step112')","out=Path('outputs/step123')").replace('interaction_reference_audit.json','reference_audit.json').replace('    if h.start() and d[h.start()-1] not in (0,255):continue\n','');Path('work/audit123.py').write_text(s,encoding='utf-8')
