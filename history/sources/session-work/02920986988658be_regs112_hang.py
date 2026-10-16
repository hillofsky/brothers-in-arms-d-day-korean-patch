import importlib.util,json
from pathlib import Path
s=importlib.util.spec_from_file_location('m','PROJECT_ROOT/bia_stage40i_tools/bia_stage40i_actual_resource_trace.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);_,b=m.load_helpers();w,_=b.connect_debugger(26442);Path('outputs/step112_hang/regs.json').write_text(json.dumps(w.request('cpu.getAllRegs'),indent=2));w.close()
