import importlib.util,time
from pathlib import Path
s=importlib.util.spec_from_file_location('m','PROJECT_ROOT/bia_stage40i_tools/bia_stage40i_actual_resource_trace.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);_,b=m.load_helpers();ws,_=b.connect_debugger(int(Path('outputs/stage43c_hint_trace/debugger_port.txt').read_text()))
for a in [0x09bfb516,0x09bfbe26,0x09bfc5e0]:ws.send_json({'event':'memory.breakpoint.remove','address':a,'size':1})
ws.send_json({'event':'cpu.breakpoint.remove','address':0x08827b08});time.sleep(2);ws.close();print('Sent breakpoint removal')
