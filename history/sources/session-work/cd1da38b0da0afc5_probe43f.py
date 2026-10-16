import importlib.util,time,json
from pathlib import Path
s=importlib.util.spec_from_file_location('m','PROJECT_ROOT/bia_stage40i_tools/bia_stage40i_actual_resource_trace.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);_,b=m.load_helpers();port=int(Path('outputs/stage43f_validation/debugger_port.txt').read_text());ws,_=b.connect_debugger(port)
print(ws.request('cpu.breakpoint.add',address=0x08827b08,enabled=True,log=False,condition='a0 >= 0xAC00 && a0 <= 0xD7A3'),flush=True)
end=time.time()+12
while time.time()<end:
 r=ws.request('cpu.status')
 if r.get('stepping'):
  regs=ws.request('cpu.getAllRegs');Path('outputs/stage43f/hangul_remap_regs.json').write_text(json.dumps(regs,indent=2));g={n.lower():v for c in regs['categories'] for n,v in zip(c['registerNames'],c['uintValues'])};print({n:hex(g.get(n,0)) for n in ['a0','a1','a2','s7','t9','ra']},flush=True)
  for key in ['s7','t9']:
   a=g[key];Path('outputs/stage43f/probe_'+key+'.bin').write_bytes(m.read_ws(ws,a,256))
  break
 time.sleep(.1)
else:print('NO HANGUL HIT',flush=True)
ws.request('cpu.breakpoint.remove',address=0x08827b08);ws.send_json({'event':'cpu.resume'});time.sleep(.1);ws.close()
