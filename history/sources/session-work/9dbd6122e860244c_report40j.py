import importlib.util,json,struct,zipfile,shutil
from pathlib import Path
out=Path('outputs/stage40j_validation');ram=(out/'controls_ram.bin').read_bytes();base=0x08000000
r=json.loads(Path('outputs/stage40j/key_restore_report.json').read_text(encoding='utf-8')); f=json.loads(Path(r'PROJECT_ROOT\analysis\stage40f_on_memu_resident_mass\stage40f_report.json').read_text(encoding='utf-8'))
def read(a,n):return ram[a-base:a-base+n]
r['payload_exact_count']=sum(read(int(x['runtime'],0),x['bytes'])==x['korean'].encode('utf-8')+b'\0' for x in f['build']['payloads']);r['payload_total']=len(f['build']['payloads'])
r['font']={'glyph_count':int.from_bytes(read(0x0972385C+0x50,2),'little'),'glyph_ptr':hex(int.from_bytes(read(0x0972385C+0x54,4),'little')),'renderer_jal':read(0x08972360,4).hex()}
r['verified_screens']={'main_menu':True,'options':True,'controls':True,'GAME_error_removed':True,'TYPE_error_removed':True,'controls_korean_boxes_remain':True,'capture_method':'Direct RGB565 VRAM read with SoftwareRenderer=True; both buffers captured'}
r['ram']=json.loads((out/'ram_read_report.json').read_text());r['runtime_verified']=True;r['ready_for_final_release']=False
s=importlib.util.spec_from_file_location('m',r'PROJECT_ROOT\bia_stage40i_tools\bia_stage40i_actual_resource_trace.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
r['old_probe_hits']={name:[hex(base+i) for i in [ram.find(pattern)] if i>=0] for name,pattern in m.make_runtime_patterns().items()}
r['controls_text_hits']={t:[hex(base+i) for i in [ram.find(t.encode('utf-8')+b'\0')] if i>=0] for t in ['조작','유형','조준 반전','조준 보조','표준','고급']}
(out/'stage40j_report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
deliver=Path('outputs/bia_stage40j_tools');deliver.mkdir(exist_ok=True)
shutil.copy2('work/restore_keys.py',deliver/'restore_keys.py');shutil.copy2('work/stage40j_validate.py',deliver/'validate_live.py')
(deliver/'README.txt').write_text('Stage40J: selective restoration of 24 compiled localization keys. Already built at PROJECT_ROOT\\BIA_STAGE40J_LOCALIZATION_KEYS_RESTORED_TEST.iso. Requires existing PROJECT_ROOT Stage39U, Stage40F, Stage39B helpers, Stage40G plan and extracted INT files. restore_keys.py intentionally refuses to overwrite the test ISO. validate_live.py uses the current working directory for outputs and a work/nav_command.json queue; diagnostic only. Source ISO is preserved. Validation found GAME and TYPE lookup errors fixed; controls glyph boxes remain. Not a final release. Full RAM is 0x08000000..0x0A000000.\n',encoding='utf-8')
with zipfile.ZipFile('outputs/bia_stage40j_results.zip','w',zipfile.ZIP_DEFLATED) as z:
 for p in [out/'stage40j_report.json',out/'ram_read_report.json',out/'startup_ready_0x4000000.png',out/'options_open_verified_0x4000000.png',out/'controls_open_verified_0x4000000.png',Path('outputs/stage40j/02_options_open.png'),Path('outputs/stage40j/03_controls_open.png')]:z.write(p,('after/' if p.parent==out else 'before/')+p.name)
 for p in deliver.iterdir():z.write(p,'tools/'+p.name)
print(json.dumps({k:r[k] for k in ['payload_exact_count','payload_total','font','controls_text_hits','verified_screens']},ensure_ascii=False))
