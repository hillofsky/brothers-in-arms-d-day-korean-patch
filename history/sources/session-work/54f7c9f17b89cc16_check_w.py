import json,struct,hashlib,re
from pathlib import Path
out=Path('outputs/stage40w_validation');ram=(out/'controls_ram.bin').read_bytes();r=json.loads(Path('outputs/stage40w/first_mission_patch_report.json').read_text(encoding='utf8'));read=lambda a,n:ram[a-0x8000000:a-0x8000000+n]
for x in r['font_objects']:print(x['runtime'],struct.unpack('<H',read(int(x['runtime'],0)+0x50,2)),read(int(x['runtime'],0)+0x54,4).hex())
print('atlas hash',hashlib.sha1(read(int(r['atlas_runtime'],0),r['atlas_bytes'])).hexdigest()==r['atlas_sha1']);print('payloads',sum(read(int(x['runtime'],0),x['bytes'])==x['korean'].encode()+b'\0' for x in r['payloads']),len(r['payloads']));print('GE',read(0x09c8be40,12).hex())
