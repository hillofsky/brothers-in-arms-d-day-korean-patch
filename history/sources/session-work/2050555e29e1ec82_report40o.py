import json,struct,re,hashlib,zipfile,shutil
from pathlib import Path
out=Path('outputs/stage40o_validation');ram=(out/'controls_ram.bin').read_bytes();base=0x08000000
read=lambda a,n:ram[a-base:a-base+n]
f=json.loads(Path('PROJECT_ROOT/analysis/stage40f_on_memu_resident_mass/stage40f_report.json').read_text(encoding='utf8'));add=json.loads(Path('outputs/stage40m/ui_additions_report.json').read_text(encoding='utf8'))
payloads=f['build']['payloads']+add['new_ui_translations'];good=sum(read(int(x['runtime'],0),x['bytes'])==x['korean'].encode()+b'\0' for x in payloads);assert good==len(payloads)==658
keys=json.loads(Path('outputs/stage40j/key_restore_report.json').read_text(encoding='utf8'))['restored_keys'];keychecks=[]
for k in keys:
 metadata=0x08e2d020+16*0x78000+int(k['metadata_offset'],0);ptr,n,cap=struct.unpack('<III',read(metadata,12));keychecks.append(read(ptr,n)==k['key'].encode()+b'\0')
assert all(keychecks)
fonts=[]
for a in [0x0972385c,0x0972524c]:
 n=struct.unpack('<H',read(a+0x50,2))[0];ptr=struct.unpack('<I',read(a+0x54,4))[0];assert n==847 and ptr==0x098f5020;fonts.append({'font':hex(a),'glyph_count':n,'glyph_pointer':hex(ptr)})
d=json.loads((out/'disasm_0x8cc4480.json').read_text());ops={x['address']:x['encoding'] for x in d['lines'] if x['type']=='opcode'};helpers=[]
for stage,a in [('stage40l',0x08cc4480),('stage40o',0x08cc4580)]:
 expected=Path('outputs',stage,'utf8_width_helper.bin').read_bytes();actual=b''.join(struct.pack('<I',ops[a+i]) for i in range(0,len(expected),4));assert actual==expected;helpers.append({'runtime':hex(a),'bytes':len(expected),'original_instructions_match':True,'sha1':hashlib.sha1(actual).hexdigest()})
lines=(out/'ppsspp.log').read_text(errors='replace').splitlines();calls=[int(re.search('a1=([0-9a-f]+)',x)[1],16) for x in lines if 'BIA40O' in x];raw=sum(0x80<=x<=0xff for x in calls);assert raw==0 and calls
r={'test_iso':'PROJECT_ROOT/BIA_STAGE40O_CONTROLS_UTF8_COMPLETE_TEST.iso','payload_exact_count':good,'payload_total':len(payloads),'restored_keys_verified':sum(keychecks),'fonts':fonts,'renderer_jal':read(0x08972360,4).hex(),'width_helpers':helpers,'width_lookup_trace':{'calls':len(calls),'hangul_calls':sum(0xac00<=x<=0xd7a3 for x in calls),'raw_utf8_byte_calls':raw},'ram':json.loads((out/'ram_read_report.json').read_text()),'verified_screens':['main_menu','options','controls','audio','game'],'controls_boxes_resolved':True,'missing_labels_added':['자세/행동','재장전/행동'],'runtime_verified':True,'ready_for_final_release':False,'scope':'Verified menu rendering in PPSSPP software renderer; full campaign and physical PSP not tested.'}
assert r['renderer_jal']=='e410330e';(out/'stage40o_report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf8')
deliver=Path('outputs/bia_stage40o_tools');deliver.mkdir(exist_ok=True)
for name in ['build_font40k.py','build_width40l.py','build_additions40m.py','build_width40o.py','test_width_machine.py','test_width40o_machine.py','stage40o_live.py']:
 shutil.copy2(Path('work',name),deliver/name)
readme='''Stage40O 검증 결과
최신 테스트 ISO: PROJECT_ROOT\\BIA_STAGE40O_CONTROLS_UTF8_COMPLETE_TEST.iso

조작 메뉴 본문 글꼴에 한글 매핑과 글리프/아틀라스를 연결했습니다.
누락된 자세/행동, 재장전/행동을 추가했습니다.
두 문자열 너비 계산 경로 모두 widened UTF-8의 2/3바이트 문자를 해독하고 순회 인덱스를 보정합니다.
복구한 현지화 키 24개와 번역 payload 658개를 RAM에서 검증했습니다.
메인/옵션/조작/오디오/게임 메뉴를 직접 확인했습니다.
실행 중 JIT 패치가 있는 코드 메모리는 디버거 disasm의 원본 opcode로 검증했습니다.
전체 캠페인 및 실제 PSP는 미검증이며 최종 배포본이 아닙니다.

첨부 tools는 기존 PROJECT_ROOT 헬퍼/분석 자료를 필요로 합니다. 빌드 스크립트는 기존 테스트 ISO 덮어쓰기를 거부합니다.
라이브 진단 스크립트는 work/nav_command.json 명령 큐와 PPSSPP 디버거를 사용합니다.
ISO는 큰 파일이므로 이 ZIP에 중복 포함하지 않았습니다.
'''
(deliver/'README.txt').write_text(readme,encoding='utf8')
with zipfile.ZipFile('outputs/bia_stage40o_results.zip','w',zipfile.ZIP_DEFLATED) as z:
 for name in ['stage40o_report.json','ram_read_report.json','main_menu_0x4000000.png','options_0x4000000.png','controls_0x4000000.png','audio_0x4000000.png','game_0x4000000.png','disasm_0x8cc4480.json']:
  z.write(out/name,'verified/'+name)
 for p in deliver.iterdir():z.write(p,'tools/'+p.name)
 for stage,report in [('stage40k','font_patch_report.json'),('stage40l','width_patch_report.json'),('stage40m','ui_additions_report.json'),('stage40o','width_patch_report.json')]:z.write(Path('outputs',stage,report),stage+'/'+report)
 for stage in ['stage40l','stage40o']:z.write(Path('outputs',stage,'utf8_width_helper.bin'),stage+'/utf8_width_helper.bin')
 z.write('outputs/stage40j/03_controls_open.png','before/controls.png')
print(json.dumps(r,ensure_ascii=False))
