import json,re,collections,struct
from pathlib import Path
out=Path('outputs/stage40o_validation');d=json.loads((out/'disasm_0x8cc4480.json').read_text());ops={x['address']:x['encoding'] for x in d['lines'] if x['type']=='opcode'}
for stage,addr in [('stage40l',0x8cc4480),('stage40o',0x8cc4580)]:
 expected=Path('outputs',stage,'utf8_width_helper.bin').read_bytes();actual=b''.join(struct.pack('<I',ops[addr+i]) for i in range(0,len(expected),4));print(stage,actual==expected)
lines=(out/'ppsspp.log').read_text(errors='replace').splitlines();a=[int(re.search(r'a1=([0-9a-f]+)',x)[1],16) for x in lines if 'BIA40O' in x];print('trace',len(a),'hangul',sum(0xac00<=v<=0xd7a3 for v in a),'rawbytes',sum(0x80<=v<=0xff for v in a))
