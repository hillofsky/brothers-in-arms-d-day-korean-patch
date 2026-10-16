import json,struct,hashlib
from pathlib import Path
r=json.loads(Path('outputs/stage40m_validation/disasm_0x8cc4480.json').read_text());want=Path('outputs/stage40l/utf8_width_helper.bin').read_bytes();have=bytearray()
for line in r['lines']:
 if line.get('addressSize')==4 and line['address']<0x08cc4480+len(want):have.extend(struct.pack('<I',line['encoding']))
print(len(have),len(want),'CPU disassembly helper equals disk',bytes(have)==want)
