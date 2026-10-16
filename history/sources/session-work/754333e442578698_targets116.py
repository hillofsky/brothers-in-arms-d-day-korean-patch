import json,re
from pathlib import Path
o=Path('outputs/step116');t=json.loads((o/'tutorial_targets.json').read_text(encoding='utf-8'));missing=json.loads((o/'missing_tutorials.json').read_text(encoding='utf-8'));values=['적을 제압하려면 맥 상사가 엄폐물을 피해 사격할 수 있는 새 위치로 이동해야 한다. 이런 기동을 측면 공격이라 한다.%newline%계속하려면 %Button_Cross%를 누른다.','맥 상사가 이 위치에 도착하면 적을 직접 조준하여 쉽게 제압할 수 있다.%newline%계속하려면 %Button_Cross%를 누른다.','맥 상사가 이동하는 동안 당신과 레겟은 적에게 제압 사격을 가해야 한다.%newline%계속하려면 %Button_Cross%를 누른다.','%action_use% %icon_use%로 박격포에서 물러난다.','%action_fall_out% %icon_fall_out% 또는 이동 명령으로 대원들을 박격포에서 물러나게 한다.']
for r,ko in zip(missing,values):t[r[2]]=ko
names={'Allen':'앨런','Locke':'로크','Hartsock':'하트삭','Jameson':'제임슨','Garnett':'가넷','Corrion':'코리온','Leggett':'레겟','Baker':'베이커','Muzza':'무자','Cole':'콜','York':'요크','Wheaton':'휘튼','Hooper':'후퍼','Doe':'도','McCreary':'맥크리어리','Rivas':'리바스','Desola':'데솔라','Zanovich':'자노비치','Obrieski':'오브리스키','Courtland':'코틀랜드','Hassay':'하세이','Combs':'콤스','Lewis':'루이스','Scott':'스콧','Boyd':'보이드','Risner':'리즈너','Jackson':'잭슨','Kilroy':'킬로이','Doyle':'도일','Paddock':'패독','Cassidy':'캐시디','Friar':'프라이어','Campbell':'캠벨','McConnel':'맥코넬','Paige':'페이지','Marsh':'마시','Johnson':'존슨','Hersh':'허시','Marshall':'마셜'};ranks={'Pvt.':'이병','Pfc.':'일병','Cpl.':'상병','Sgt.':'하사','Lt. Col.':'중령','Lt.':'중위','Col.':'대령','Plt. Sgt.':'상사'};active=False;nm={}
for line in Path('PROJECT_ROOT/extracted/PSP_GAME/USRDIR/SYSTEM/GBXGAMEPLAY.INT').read_text().splitlines():
 if line.startswith('['):active=line=='[TeammateName]';continue
 if not active or '=' not in line:continue
 en=line.split('=',1)[1].strip()
 if en=='Soldier':ko='병사'
 else:
  rank,surname=en.rsplit(' ',1);ko=names[surname]+' '+ranks[rank]
 nm[en]=ko;t[en]=ko
for en,ko in t.items():assert sorted(re.findall(r'%[^%]+%',en))==sorted(re.findall(r'%[^%]+%',ko)),en
(o/'translations.json').write_text(json.dumps(t,ensure_ascii=False,indent=2),encoding='utf-8');(o/'name_translations.json').write_text(json.dumps(nm,ensure_ascii=False,indent=2),encoding='utf-8');print('targets',len(t),'names',len(nm))
s=Path('work/audit112_interactions.py').read_text(encoding='utf-8-sig').replace('BIA_STEP112_DIALOGUE_AND_INTERACTION_KO_TEST.iso','BIA_STEP115_FONT_UV_INSET_TEST.iso').replace('outputs/step112/interaction_translations.json','outputs/step116/translations.json').replace("out=Path('outputs/step112')","out=Path('outputs/step116')").replace('interaction_reference_audit.json','reference_audit.json').replace('    if h.start() and d[h.start()-1] not in (0,255):continue\n','');Path('work/audit116.py').write_text(s,encoding='utf-8')
