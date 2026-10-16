import importlib.util,time,base64,sys
from pathlib import Path
s=importlib.util.spec_from_file_location('m',r'PROJECT_ROOT\bia_stage40i_tools\bia_stage40i_actual_resource_trace.py'); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); _,b=m.load_helpers()
log=Path('outputs/stage40j/ppsspp.log'); port=b.wait_for_actual_debugger_port(log,5); ws,_=b.connect_debugger(port)
try:
 ws.send_json({'event':'cpu.stepping'}); time.sleep(.3)
 for event in ['gpu.buffer.renderColor','gpu.buffer.screenshot']:
  try:
   r=ws.request(event,timeout=5,type='uri'); Path('outputs/stage40j/'+sys.argv[1]+'.png').write_bytes(base64.b64decode(r['uri'].split(',',1)[1])); print('CAPTURED',event); break
  except Exception as e: print(event,str(e))
finally: ws.send_json({'event':'cpu.resume'}); ws.close()
