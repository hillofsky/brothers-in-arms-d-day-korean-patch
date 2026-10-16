import importlib.util,time
from pathlib import Path
s=importlib.util.spec_from_file_location('m','PROJECT_ROOT/bia_stage40i_tools/bia_stage40i_actual_resource_trace.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);_,b=m.load_helpers();ws,_=b.connect_debugger(int(Path('outputs/stage43j_trace/debugger_port.txt').read_text()))
for addr,n in [(0x09e6b020,880*24),(0x09e8b020,879*20),(0x09e94020,879*20)]:
 ws.send_json({'event':'memory.breakpoint.add','address':addr,'size':n,'enabled':False,'log':True,'read':True,'write':False,'logFormat':'GLYPHREAD pc={pc} ra={ra} a0={a0} a1={a1} a2={a2} s0={s0} s1={s1} s2={s2} s7={s7}'})
time.sleep(.3);ws.close()
