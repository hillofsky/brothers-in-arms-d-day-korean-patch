import importlib.util,json,struct,sys
from pathlib import Path
s=importlib.util.spec_from_file_location('m',r'PROJECT_ROOT\bia_stage40i_tools\bia_stage40i_actual_resource_trace.py'); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); _,b=m.load_helpers()
ws,_=b.connect_debugger(int(Path('outputs/stage40j_validation/debugger_port.txt').read_text()))
r={'status':ws.request('cpu.status'),'anchors':[]}
try:
 for a,text in [(0x09790510,'조작'),(0x09790568,'유형'),(0x09790570,'조준 반전'),(0x09790580,'조준 보조')]:
  data=m.read_ws(ws,a,len(text.encode('utf-8'))+1); r['anchors'].append({'address':hex(a),'expected':text,'actual_hex':data.hex(),'matches_utf8':data==text.encode('utf-8')+b'\0'})
 import PIL.Image as Image
 for a in [0x04000000,0x04044000]:
  data=m.read_ws(ws,a,512*272*2)
  rgb=bytearray()
  for y in range(272):
   for x in range(480):
    v=struct.unpack_from('<H',data,(y*512+x)*2)[0]; rgb.extend(((v&31)*255//31,((v>>5)&63)*255//63,((v>>11)&31)*255//31))
  Image.frombytes('RGB',(480,272),bytes(rgb)).save('outputs/stage40j_validation/vram_'+hex(a)+'.png')
except Exception as e:r['error']=str(e)
finally:ws.close()
Path('outputs/stage40j_validation/anchors.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8'); print(json.dumps(r,ensure_ascii=False))
