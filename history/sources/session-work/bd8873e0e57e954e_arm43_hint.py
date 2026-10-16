import importlib.util,time,struct
from pathlib import Path
s=importlib.util.spec_from_file_location('m','PROJECT_ROOT/bia_stage40i_tools/bia_stage40i_actual_resource_trace.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);_,b=m.load_helpers();ws,_=b.connect_debugger(int(Path('outputs/stage43c_hint_trace/debugger_port.txt').read_text()))
addresses=[0x09bfb516,0x09bfbe26,0x09bfc5e0]
for a in addresses:ws.request('memory.breakpoint.remove',address=a,size=1)
ws.request('cpu.breakpoint.remove',address=0x08827b08)
print('WAITING FONT; movie memory checks removed',flush=True)
end=time.time()+140
while time.time()<end:
 d=m.read_ws(ws,0x09c1afd4,8)
 if struct.unpack_from('<H',d)[0]==880:
  for a in addresses:ws.request('memory.breakpoint.add',address=a,size=1,enabled=False,log=True,read=True,write=False,logFormat='HINTREAD pc={pc} ra={ra} a0={a0} a1={a1} a2={a2} s0={s0} s1={s1} s2={s2}')
  print('HINT WATCH ARMED',flush=True);break
 time.sleep(.1)
else:print('FONT WAIT TIMEOUT',flush=True)
ws.close()
