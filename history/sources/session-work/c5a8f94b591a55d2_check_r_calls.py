from pathlib import Path
import json,struct
out=Path('outputs/stage40r_validation');r=json.loads(Path('outputs/stage40r/campaign_renderer_patch_report.json').read_text());d=json.loads((out/'disasm_0x898e354.json').read_text());ops={x['address']:x['encoding'] for x in d['lines'] if x['type']=='opcode'};ram=(out/'controls_ram.bin').read_bytes();results=[]
for c in r['calls']:
 a=int(c['runtime'],0);word=ops.get(a,struct.unpack_from('<I',ram,a-0x8000000)[0]);results.append({'runtime':hex(a),'word':hex(word),'expected':c['expected_word'],'match':word==int(c['expected_word'],0)})
print(results)
