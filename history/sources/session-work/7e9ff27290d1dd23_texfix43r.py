import json,base64,struct
from pathlib import Path
r=Path('outputs/stage43r_title_probe/title_post_hit_ram.bin').read_bytes();a=0x095e21c0+0x44;v=bytearray(r[a-0x8000000:a-0x8000000+20]);w=struct.unpack_from('<I',v)[0];struct.pack_into('<5I',v,0,(w&65535)|0x09090000,512,512,512,512)
p=Path('work/nav43r_tmp.json');p.write_text(json.dumps({'debug_request':{'event':'memory.write','address':a,'base64':base64.b64encode(v).decode()},'debug_send':{'event':'cpu.resume'},'name':'title_texture_size_live'}));p.replace('work/nav43r_command.json')
