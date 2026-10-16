exec(open('work/audit43r_title.py',encoding='utf-8-sig').read().split('for name,iso')[0])
_,dsl=b.iso_read_file(Path('PROJECT_ROOT/BIA_STAGE43Q_HINT_HEIGHT_TEST.iso'),b.TARGET_DSL);print('entry', [hex(x) for x in struct.unpack_from('<III',dsl,0x169e12)]);print('desc',dsl[0x175137:0x175137+32].hex())
import base64
p=Path('work/nav43r_tmp.json');p.write_text(json.dumps({'debug_request':{'event':'memory.write','address':0x08e693c0,'base64':base64.b64encode(struct.pack('<I',0xa087d020)).decode()},'name':'correct_atlas_live'}));p.replace('work/nav43r_command.json')
