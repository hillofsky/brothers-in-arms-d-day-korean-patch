import importlib.util,json,time
from pathlib import Path
s=importlib.util.spec_from_file_location('m','PROJECT_ROOT/bia_stage40i_tools/bia_stage40i_actual_resource_trace.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);_,b=m.load_helpers();out=Path('outputs/stage40y_validation');ws,host=b.connect_debugger(int((out/'debugger_port.txt').read_text()));results=[]
try:
 for button in ['down','down','down','down','cross']:
  r=ws.request('input.buttons.press',button=button,duration=8,timeout=8);results.append({'button':button,'response':r});time.sleep(.45)
finally:ws.close()
(out/'quit_input_results.json').write_text(json.dumps(results,indent=2));print('Buttons applied',len(results))
