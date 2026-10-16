from pathlib import Path
p=Path('work/stage40j_validate.py');s=p.read_text(encoding='utf-8');beg=s.index(' time.sleep(3)\n for i in range(8)');end=s.index('except Exception:',beg)
s=s[:beg]+''' time.sleep(3); snap('boot')
 deadline=time.time()+600
 while time.time()<deadline:
  if command.exists():
   c=json.loads(command.read_text(encoding='utf-8-sig')); command.unlink()
   if c.get('quit'): break
   for button in c.get('buttons',[]): print(m.press(ws,button,wait=c.get('wait',1)),flush=True)
   snap(c.get('name','current'))
   if c.get('scan'):
    data=bytearray()
    for address in range(0x08000000,0x0A000000,m.RAM_CHUNK):
     block=m.read_ws(ws,address,m.RAM_CHUNK)
     if len(block)!=m.RAM_CHUNK: raise RuntimeError('Incomplete read '+hex(address))
     data.extend(block)
    (out/'controls_ram.bin').write_bytes(data)
    (out/'ram_read_report.json').write_text(json.dumps({'start':'0x08000000','end':'0x0A000000','bytes':len(data),'chunks':len(data)//m.RAM_CHUNK,'all_reads_complete':True},indent=2))
    print('RAM COMPLETE',len(data),flush=True)
  time.sleep(.15)
'''+s[end:]
p.write_text(s,encoding='utf-8')
cmd=Path('work/nav_command.json')
if cmd.exists():cmd.unlink()
