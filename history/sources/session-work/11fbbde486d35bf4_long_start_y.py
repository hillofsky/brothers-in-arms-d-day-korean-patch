import importlib.util
from pathlib import Path
s=importlib.util.spec_from_file_location('m','PROJECT_ROOT/bia_stage40i_tools/bia_stage40i_actual_resource_trace.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);_,b=m.load_helpers();port=int(Path('outputs/stage40y_validation/debugger_port.txt').read_text());ws,host=b.connect_debugger(port);print(ws.request('input.buttons.press',button='start',duration=12,timeout=8));print('Sent duration12 Start');ws.close()

