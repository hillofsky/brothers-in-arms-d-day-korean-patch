from pathlib import Path
s=Path('work/stage40j_validate.py').read_text(encoding='utf-8');s=s.replace("outputs/stage40j_validation","outputs/stage40k").replace("deadline=time.time()+600","deadline=time.time()+1200")
s=s.replace("log=out/'ppsspp.log'", "log=out/'ppsspp.log'\nif log.exists(): log.unlink()")
s=s.replace("   for button in c.get('buttons',[]):", "   if c.get('trace'):\n    ws.request('cpu.breakpoint.add',address=0x08C7F2FC,enabled=False,log=True,condition='a1 >= 0x80',logFormat='BIA40K a0={a0} a1={a1} ra={ra} s0={s0} s1={s1} s2={s2} s3={s3} s4={s4} s5={s5} sp={sp}')\n   for button in c.get('buttons',[]):")
s=s.replace("   snap(c.get('name','current'))", "   snap(c.get('name','current'))\n   if c.get('trace'):\n    ws.request('cpu.breakpoint.remove',address=0x08C7F2FC)\n   if c.get('disasm'):\n    (out/'lookup_disasm.json').write_text(json.dumps(ws.request('memory.disasm',address=0x08C7F2FC,count=90),indent=2),encoding='utf-8')")
Path('work/stage40k_live.py').write_text(s,encoding='utf-8')
