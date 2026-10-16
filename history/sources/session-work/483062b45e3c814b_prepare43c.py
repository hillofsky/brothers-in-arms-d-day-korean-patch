from pathlib import Path
s=Path('work/stage43b_live.py').read_text(encoding='utf-8');s=s.replace('stage43b_trace','stage43c_hint_trace').replace('nav43b_command.json','nav43c_command.json');s=s.replace(" m.wait_cpu_ready(ws)"," m.wait_cpu_ready(ws)\n for a in [0x09bfb516,0x09bfbe26,0x09bfc5e0]:\n  ws.request('memory.breakpoint.add',address=a,size=1,enabled=False,log=True,read=True,write=False,logFormat='HINTREAD pc={pc} ra={ra} a0={a0} a1={a1} a2={a2} s0={s0} s1={s1} s2={s2}')")
Path('work/stage43c_live.py').write_text(s,encoding='utf-8')
