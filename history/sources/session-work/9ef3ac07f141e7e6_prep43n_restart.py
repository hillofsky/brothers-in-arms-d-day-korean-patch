from pathlib import Path
s=Path('work/disasm43j_gui.py').read_text().replace('[(0x47b2fc,0x47b43c),(0x47b900,0x47bb00)]','[(0x11f80,0x12130)]');Path('work/disasm43_restart.py').write_text(s)
s=Path('work/stage43m_live.py').read_text().replace('stage43m_validation','stage43n_restart').replace('nav43m_command','nav43n_command');s=s.replace(" command=root/'work/nav43n_command.json'", " ws.request('cpu.breakpoint.add',address=0x088160a8,enabled=True,log=True,condition='t0 < 0x08800000 || t0 >= 0x0A800000',logFormat='RESTARTBAD a0={a0} a1={a1} a2={a2} t0={t0} s0={s0} s1={s1} ra={ra}')\n command=root/'work/nav43n_command.json'")
# Allow reviewable live debugger commands and capture the full PSP user RAM.
s=s.replace("   if c.get('quit'): break", "   if c.get('quit'): break\n   if c.get('debug_request'):print(ws.request(**c['debug_request']),flush=True)\n   if c.get('debug_send'):ws.send_json(c['debug_send'])")
s=s.replace('range(0x08000000,0x0A000000,m.RAM_CHUNK)','range(0x08800000,0x0A800000,m.RAM_CHUNK)');Path('work/stage43n_live.py').write_text(s)
s=Path('work/nav43m_auto.py').read_text().replace('stage43m_validation','stage43n_restart').replace('nav43m','nav43n');Path('work/nav43n_auto.py').write_text(s)
