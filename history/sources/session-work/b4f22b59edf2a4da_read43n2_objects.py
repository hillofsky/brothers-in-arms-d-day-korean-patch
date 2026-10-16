from pathlib import Path
import struct,json
r=Path('outputs/stage43n2_restart/before_restart_ram.bin').read_bytes()
def u(a):return struct.unpack_from('<I',r,a-0x08000000)[0]
p=u(0x08ce5b10);o=u(p+0x34);v=u(o);method=u(v+0xbc);print('engine',hex(p),'interface',hex(o),'vtable',hex(v),'post_movie_fn',hex(method));Path('outputs/stage43n2_restart/interface_before.json').write_text(json.dumps({'engine':hex(p),'interface':hex(o),'vtable':hex(v),'post_movie_fn':hex(method)},indent=2))
for a in [p,o,v]:print(hex(a),r[a-0x08000000:a-0x08000000+64].hex())
