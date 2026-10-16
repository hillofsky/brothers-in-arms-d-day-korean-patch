import json,struct
from pathlib import Path
out=Path('outputs/stage40r_validation');ram=(out/'controls_ram.bin').read_bytes();r=json.loads(Path('outputs/stage40r/campaign_renderer_patch_report.json').read_text());ops={x['address']:x['encoding'] for x in json.loads((out/'disasm_0x8c9f468.json').read_text())['lines'] if x['type']=='opcode'}
for h in r['helpers']:
 a=int(h['runtime'],0);actual=b''.join(struct.pack('<I',ops[a+i]) for i in range(0,h['size'],4));expected=Path('outputs/stage40r',h['va']+'_helper.bin').read_bytes();print(h['runtime'],actual==expected)
for a in [0x9c1af84,0x9c1d11c]:print(hex(a),int.from_bytes(ram[a+0x50-0x8000000:a+0x52-0x8000000],'little'))
