from pathlib import Path
import struct,json
r=Path('outputs/step104_user_repro/paused_088b9c8c_ram.bin').read_bytes();pool=0x8dbc740;rows=[]
for bucket in range(1,16):
 head=struct.unpack_from('<I',r,pool-0x8000000+0x18+bucket*4)[0];nodes=[];seen=set()
 while 0x8000000<=head<0xa000000 and head not in seen and len(nodes)<1000:
  seen.add(head);nodes.append(hex(head));head=struct.unpack_from('<I',r,head-0x8000000)[0]
 rows.append({'bucket':bucket,'nodes':nodes,'terminal':hex(head)})
Path('outputs/step104_user_repro/string_pool_chains.json').write_text(json.dumps(rows,indent=2));print([(x['bucket'],len(x['nodes']),x['terminal']) for x in rows])
