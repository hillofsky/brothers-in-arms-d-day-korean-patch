import importlib.util,json,base64
from pathlib import Path
s=importlib.util.spec_from_file_location('m','PROJECT_ROOT/bia_stage40i_tools/bia_stage40i_actual_resource_trace.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);_,b=m.load_helpers();port=int(Path('outputs/stage43g_validation/debugger_port.txt').read_text());ws,_=b.connect_debugger(port)
try:
 ws.send_json({'event':'cpu.stepping'})
 r=json.loads(Path('outputs/stage43h/font_report.json').read_text())
 for k,a in r['addresses'].items():
  data=Path('outputs/stage43h/'+k+'.bin').read_bytes();print(ws.request('memory.write',address=int(a,0),base64=base64.b64encode(data).decode()))
 data=Path('outputs/stage43h/header.bin').read_bytes();print(ws.request('memory.write',address=0x08fc3cc8,base64=base64.b64encode(data).decode()))
 ws.send_json({'event':'cpu.resume'})
finally:ws.close()

