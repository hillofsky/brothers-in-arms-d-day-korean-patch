import json,struct,zipfile
from pathlib import Path
out=Path('outputs/stage40o_validation');ram=(out/'controls_ram.bin').read_bytes();r=json.loads((out/'stage40o_report.json').read_text(encoding='utf8'));second=json.loads((out/'disasm_0x8853244.json').read_text())['lines'][0]['encoding'];first=struct.unpack_from('<I',ram,0x08853cc0-0x08000000)[0];assert first==0x0e331120 and second==0x0e331160;r['width_call_words']=[hex(first),hex(second)];(out/'stage40o_report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf8')
with zipfile.ZipFile('outputs/bia_stage40o_results.zip','r') as z: files={i.filename:z.read(i) for i in z.infolist()}
files['verified/stage40o_report.json']=(out/'stage40o_report.json').read_bytes();files['verified/disasm_0x8853244.json']=(out/'disasm_0x8853244.json').read_bytes()
with zipfile.ZipFile('outputs/bia_stage40o_results.zip','w',zipfile.ZIP_DEFLATED) as z:
 for name,data in files.items():z.writestr(name,data)
with zipfile.ZipFile('outputs/bia_stage40o_results.zip') as z:assert z.testzip() is None;print('ZIP verified',len(z.infolist()),'entries')
