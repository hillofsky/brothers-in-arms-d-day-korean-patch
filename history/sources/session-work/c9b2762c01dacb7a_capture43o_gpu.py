import importlib.util,json,base64
from pathlib import Path
s=importlib.util.spec_from_file_location('m','PROJECT_ROOT/bia_stage40i_tools/bia_stage40i_actual_resource_trace.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);_,b=m.load_helpers();out=Path('outputs/stage43o_validation');ws,_=b.connect_debugger(int((out/'debugger_port.txt').read_text()))
try:
 d=ws.request('gpu.buffer.screenshot',type='uri');print([(k,len(v) if isinstance(v,str) else type(v).__name__) for k,v in d.items()]);
 for k,v in d.items():
  if isinstance(v,str) and v.startswith('data:image'):(out/'gpu_current.png').write_bytes(base64.b64decode(v.split(',',1)[1]))
finally:ws.close()
