import importlib.util
from pathlib import Path
s=importlib.util.spec_from_file_location('m','PROJECT_ROOT/bia_stage40i_tools/bia_stage40i_actual_resource_trace.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);_,b=m.load_helpers();ws,_=b.connect_debugger(int(Path('outputs/stage43j_trace/debugger_port.txt').read_text()));ws.ticket=9000
print(ws.request('cpu.status',timeout=3),flush=True)
for a in [0x09e6b020,0x09e8b020,0x09e94020]:print(ws.request('memory.breakpoint.remove',address=a,timeout=3),flush=True)
ws.close()
