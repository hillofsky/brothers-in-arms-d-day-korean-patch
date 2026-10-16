import json,re
from pathlib import Path
out=Path('outputs/step112');t={}
manual={'DoorUseMessage':'%icon_use% 버튼을 눌러 문을 여십시오.','TalkToCharacterMessage':'%icon_use% 버튼을 눌러 대화하십시오.','GammonBombMessage':'%icon_use% 버튼을 눌러 개먼 폭탄을 설치하십시오.','TNTMessage':'%icon_use% 버튼을 눌러 폭약을 설치하십시오.','ReadSignMessage':'%icon_use% 버튼을 눌러 표지판을 읽으십시오.','UseMG42Message':'%icon_use% 버튼을 눌러 MG42를 사용하십시오.','UseMortarMessage':'%icon_use% 버튼을 눌러 박격포를 사용하십시오.','UseBrowningMessage':'%icon_use% 버튼을 눌러 브라우닝 기관총을 사용하십시오.','UseColt45Message':'%icon_use% 버튼을 눌러 45구경 권총을 사용하십시오.','UsePak36Message':'%icon_use% 버튼을 눌러 Pak 36을 사용하십시오.','PickupItemMessage':'%icon_use% 버튼을 눌러 아이템을 획득하십시오.','UseTankMachineGunMessage':'%icon_use% 버튼을 눌러 전차 기관총을 사용하십시오.','RestockWeapons':'%icon_use% 버튼을 눌러 무기와 탄약을 보급받으십시오.','RestockUsable':'%icon_use% 버튼을 눌러 아이템을 보급받으십시오.','PlantExplosive':'%icon_use% 버튼을 눌러 폭약을 설치하십시오.','DisarmExplosive':'%icon_use% 버튼을 눌러 폭약을 해체하십시오.','RearmExplosive':'%icon_use% 버튼을 눌러 폭약을 다시 설치하십시오.','TankGrenadeMessage':'%icon_use% 버튼을 눌러 전차 안에 폭약을 넣으십시오.','PlungerMessage':'%icon_use% 버튼을 눌러 폭약을 폭파하십시오.','UseFlareCrateMessage':'%icon_use% 버튼을 눌러 조명탄 상자를 사용하십시오.','PawnGiveHealth':'%icon_use% 버튼을 눌러 치료하십시오.','PawnGiveHealthMessage':'%icon_use% 버튼을 눌러 치료하십시오.','PickupMessage':'%icon_use% 버튼으로 사용:|','TrophyMessage':'%icon_use% 버튼을 눌러 전리품을 사용하십시오.','CannotUseGrenadeMessage':'전차에 수류탄을 넣으려면 해치를 열어야 합니다.','TalkToPawnMessage':'%icon_use% 버튼으로 대화하기: ','TalkToPawnMessage1':'%icon_use% 버튼으로 대화하기: ','PawnRestockMessage':'%icon_use% 버튼을 눌러 탄약을 보급받으십시오.','PawnRestockMessage1':'%icon_use% 버튼으로 탄약 받기: ','PawnRestockedMessage1':'탄약을 받았습니다: '}
weapons={'German K98 Rifle':'독일군 K98 소총','German K98 Sniper Rifle':'독일군 K98 저격 소총','German FG42':'독일군 FG42','German FG42 Machine Gun':'독일군 FG42 기관총','German FG42 Sniper Machine Gun':'독일군 FG42 저격 기관총','FG 42':'FG42','German MP 40':'독일군 MP40','German MP40':'독일군 MP40','German Machine Pistol 40':'독일군 MP40 기관단총','German Panzerfaust':'독일군 판처파우스트','German P38 Pistol':'독일군 P38 권총','German STG44 Machine Gun':'독일군 STG44 기관총','STG 44':'STG44','German MG42 Machinegun':'독일군 MG42 기관총','German Mortar':'독일군 박격포','US Bar Machine Gun':'미군 BAR 기관총','US BAR':'미군 BAR','US Bazooka':'미군 바주카','US .45 Pistol':'미군 45구경 권총','US M1 Carbine Rifle':'미군 M1 카빈 소총','US M1 Rifle':'미군 M1 소총','US Springfield Rifle':'미군 스프링필드 소총','US M1A1 Sub-Machine Gun':'미군 M1A1 기관단총','US M3A1 Sub-Machine Gun':'미군 M3A1 기관단총'};t.update(weapons)
for line in Path('PROJECT_ROOT/extracted/PSP_GAME/USRDIR/SYSTEM/GBXBASE.INT').read_bytes().decode('cp1252').splitlines():
 if '=' not in line:continue
 key,val=line.split('=',1);en=val.strip().strip('"')
 if key in manual:t[en]=manual[key]
for line in Path('PROJECT_ROOT/extracted/PSP_GAME/USRDIR/SYSTEM/GBXINVENTORY.INT').read_bytes().decode('cp1252').splitlines():
 if '=' not in line:continue
 key,val=line.split('=',1);en=val.strip().strip('"')
 if key=='PickupMessage':
  if en.startswith('You picked up a '):
   obj=en[len('You picked up a '):].rstrip('.');ko={'Bandage':'붕대','Trophy':'전리품','HandGrenade':'수류탄'}.get(obj)
   if ko:t[en]=ko+'을 획득했습니다.' if ko not in ['붕대'] else '붕대를 획득했습니다.'
  elif en.startswith('You got the '):
   obj=en[len('You got the '):].rstrip('.');ko=weapons.get(obj)
   if ko:t[en]=ko+'을 획득했습니다.'
t['You picked up a HandGrenade.']='수류탄을 획득했습니다.';t['You picked up some ammo.']='탄약을 획득했습니다.';(out/'interaction_translations.json').write_text(json.dumps(t,ensure_ascii=False,indent=2),encoding='utf-8')
p=Path('work/audit112_dialogues.py').read_text(encoding='utf-8-sig').replace("src=Path('PROJECT_ROOT/BIA_STEP111_RADIO_SUBTITLE_KO_TEST.iso')","src=Path('PROJECT_ROOT/BIA_STEP112_DIALOGUE_AND_INTERACTION_KO_TEST.iso')").replace('available_translations.json','interaction_translations.json').replace("valid=True # Exact complete voiced sentence in an aligned FString; not a code identifier","valid=key in keys or (' ' in en and '%s' not in en) # Display phrase or verified localized key")
p=p.replace("(out/'reference_audit.json')","(out/'interaction_reference_audit.json')");Path('work/audit112_interactions.py').write_text(p,encoding='utf-8')
