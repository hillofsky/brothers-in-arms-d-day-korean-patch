import struct,json
from pathlib import Path
p=Path('outputs/stage40n');r=json.loads((p/'width_probe_regs.json').read_text())['categories'][0];print({n:hex(v) for n,v in zip(r['registerNames'],r['uintValues']) if n in ['s1','s2','s3','s4','sp','ra']});print('stack',[(hex(i),hex(v)) for i,v in enumerate(struct.unpack('<96I',(p/'width_sp.bin').read_bytes())) if i<16]);print('s1',struct.unpack('<8I',(p/'width_s1.bin').read_bytes()[:32]));print('s2',struct.unpack('<20I',(p/'width_s2.bin').read_bytes()[:80]))
