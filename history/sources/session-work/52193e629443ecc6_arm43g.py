from pathlib import Path
s=Path('work/stage43g_live.py').read_text(encoding='utf-8');s=s.replace(' m.wait_cpu_ready(ws)'," m.wait_cpu_ready(ws)\n ws.request('cpu.breakpoint.add',address=0x08827b0c,enabled=False,log=True,condition='a0 >= 0xAC00 && a0 <= 0xD7A3',logFormat='HUDCP cp={a0} font={s7} index={a2} text={t9}')")
Path('work/stage43g_live.py').write_text(s,encoding='utf-8')
