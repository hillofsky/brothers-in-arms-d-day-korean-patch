from pathlib import Path
p=Path('work/stage40j_validate.py');s=p.read_text(encoding='utf-8');beg=s.index(' def snap(name):');end=s.index(" time.sleep(3); snap('boot')",beg)
s=s[:beg]+''' def snap(name):
  import struct
  from PIL import Image
  for a in [0x04000000,0x04044000]:
   data=m.read_ws(ws,a,512*272*2); rgb=bytearray()
   for y in range(272):
    for x in range(480):
     v=struct.unpack_from('<H',data,(y*512+x)*2)[0]; rgb.extend(((v&31)*255//31,((v>>5)&63)*255//63,((v>>11)&31)*255//31))
   Image.frombytes('RGB',(480,272),bytes(rgb)).save(out/(name+'_'+hex(a)+'.png'))
  print('SNAP',name,flush=True)
'''+s[end:]
s=s.replace("port=b.wait_for_actual_debugger_port(log,30)","port=b.wait_for_actual_debugger_port(log,30)")
p.write_text(s,encoding='utf-8')
