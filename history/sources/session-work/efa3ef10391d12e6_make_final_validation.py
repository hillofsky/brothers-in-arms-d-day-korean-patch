from pathlib import Path
p=Path('work/stage40j_validate.py');s=p.read_text(encoding='utf-8');beg=s.index(" time.sleep(3); snap('boot')");end=s.index('except Exception:',beg)
s=s[:beg]+''' time.sleep(3)
 for i in range(8): print(m.press(ws,'start',wait=1.5),flush=True)
 snap('main_menu')
 m.press(ws,'down',wait=.8); m.press(ws,'down',wait=.8); snap('options_selected')
 m.press(ws,'cross',wait=1.2); snap('options_open')
 m.press(ws,'cross',wait=1.2); snap('controls_open')
 data=bytearray(); reads=[]
 for address in range(m.RAM_START,m.RAM_END,m.RAM_CHUNK):
  block=m.read_ws(ws,address,m.RAM_CHUNK)
  if len(block)!=m.RAM_CHUNK: raise RuntimeError('Incomplete RAM read at '+hex(address))
  data.extend(block); reads.append(address)
 (out/'controls_ram.bin').write_bytes(data)
 (out/'ram_read_report.json').write_text(json.dumps({'bytes':len(data),'chunks':len(reads),'all_reads_complete':True},indent=2))
 print('RAM COMPLETE',len(data),flush=True)
'''+s[end:]
p.write_text(s,encoding='utf-8')
