import importlib.util,json,base64
from pathlib import Path
s=importlib.util.spec_from_file_location('m','PROJECT_ROOT/bia_stage40i_tools/bia_stage40i_actual_resource_trace.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);_,b=m.load_helpers();w,_=b.connect_debugger(26442)
try:
 import time
 w.send_json({'event':'cpu.stepping'});time.sleep(.3);print(w.request('cpu.status'))
 d=w.request('gpu.buffer.renderColor',type='uri',timeout=5)
 for k,v in d.items():
  if isinstance(v,str) and v.startswith('data:image'):Path('outputs/step112_runtime/gpu_actual.png').write_bytes(base64.b64decode(v.split(',',1)[1]))
 print([(k,len(v) if isinstance(v,str) else type(v).__name__) for k,v in d.items()])
finally:w.send_json({'event':'cpu.resume'});w.close()

