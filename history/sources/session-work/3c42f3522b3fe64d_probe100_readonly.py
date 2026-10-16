import importlib.util,json,re,struct
from pathlib import Path
s=importlib.util.spec_from_file_location('m','PROJECT_ROOT/bia_stage40i_tools/bia_stage40i_actual_resource_trace.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);_,b=m.load_helpers();out=Path('outputs/step100_probe');out.mkdir(exist_ok=True);ws,_=b.connect_debugger(26420)
try:
 status=ws.request('game.status');(out/'game_status.json').write_text(json.dumps(status,indent=2));print(status)
 r=bytearray()
 for a in range(0x08000000,0x0a000000,0x20000):r.extend(m.read_ws(ws,a,0x20000))
 assert len(r)==0x2000000;(out/'live_ram.bin').write_bytes(r)
 for needle in [b'ton\0','ton'.encode('utf-16le')+b'\0\0']:
  for h in list(re.finditer(re.escape(needle),r))[:25]:print('TON',hex(h.start()+0x8000000),r[max(0,h.start()-110):h.start()+20].hex())
finally:ws.close()
