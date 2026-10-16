import importlib.util,base64,json
from pathlib import Path
s=importlib.util.spec_from_file_location('m','PROJECT_ROOT/bia_stage40i_tools/bia_stage40i_actual_resource_trace.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);_,b=m.load_helpers();w,_=b.connect_debugger(26420)
try:
 status=w.request('cpu.status');print(status,flush=True)
 if not status.get('stepping') and not status.get('paused'):
  result=w.request('gpu.record.dump');uri=result['uri'];data=base64.b64decode(uri.split(',',1)[1]);p=Path('outputs/step117_icon/current_gpu.ppdmp');p.write_bytes(data);print('RECORDED',len(data),flush=True)
finally:w.close()
