import importlib.util
from pathlib import Path
s=importlib.util.spec_from_file_location('m','PROJECT_ROOT/bia_stage40i_tools/bia_stage40i_actual_resource_trace.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);_,b=m.load_helpers();ws,_=b.connect_debugger(int(Path('outputs/stage43j_trace/debugger_port.txt').read_text()))
for addr,cond,fmt in [(0x08c7f2fc,'a1 >= 0x80','RFont cp={a1} font={a0} ra={ra} s0={s0} s1={s1}'),(0x088248e4,'a2 >= 0x80','LAYOUT cp={a2} font={s1} text={s2} ra={ra}')]:print(ws.request('cpu.breakpoint.add',address=addr,enabled=False,log=True,condition=cond,logFormat=fmt))
ws.close()
