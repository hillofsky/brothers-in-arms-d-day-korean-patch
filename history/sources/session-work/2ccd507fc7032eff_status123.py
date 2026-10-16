import importlib.util,json
from pathlib import Path
s=importlib.util.spec_from_file_location('m','PROJECT_ROOT/bia_stage40i_tools/bia_stage40i_actual_resource_trace.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);_,b=m.load_helpers();w,_=b.connect_debugger(26442)
try:
 result={'game':w.request('game.status'),'cpu':w.request('cpu.status'),'threads':w.request('hle.thread.list')};Path('outputs/step123_runtime/boot_status.json').write_text(json.dumps(result,indent=2));print(json.dumps({'game':result['game'],'threads':[(x['name'],x['statuses']) for x in result['threads']['threads']]}))
finally:w.close()
