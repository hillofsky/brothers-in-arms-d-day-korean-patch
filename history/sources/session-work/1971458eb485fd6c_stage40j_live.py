import importlib.util,subprocess,time,json,base64,traceback
from pathlib import Path
root=Path.cwd(); out=root/'outputs/stage40j'; out.mkdir(parents=True,exist_ok=True)
s=importlib.util.spec_from_file_location('m',r'PROJECT_ROOT\bia_stage40i_tools\bia_stage40i_actual_resource_trace.py'); m=importlib.util.module_from_spec(s); s.loader.exec_module(m)
_,b=m.load_helpers(); port=b.choose_free_port(); log=out/'ppsspp.log'
cfg=out/'capture.ini'; cfg.write_text('[General]\nWindowX = 100\nWindowY = 100\nWindowWidth = 960\nWindowHeight = 544\n[Graphics]\nSoftwareRenderer = True\n',encoding='utf-8')
p=subprocess.Popen([str(b.find_ppsspp_exe()),'--loglevel=3',f'--log={log}','--windowed',f'--appendconfig={cfg}',f'--debugger={port}',str(m.SOURCE_ISO)])
ws=None
try:
 port=b.wait_for_actual_debugger_port(log,30); ws,host=b.connect_debugger(port); print('CONNECTED',p.pid,flush=True)
 m.wait_cpu_ready(ws)
 command=root/'work/nav_command.json'; deadline=time.time()+600
 def snap(name):
  ws.send_json({'event':'cpu.stepping'}); time.sleep(.3)
  try:
   r=ws.request('gpu.buffer.screenshot',timeout=10,type='uri'); (out/(name+'.png')).write_bytes(base64.b64decode(r['uri'].split(',',1)[1])); print('SNAP',name,flush=True)
  except Exception as e: print('SNAP_ERROR',name,str(e),flush=True)
  finally: ws.send_json({'event':'cpu.resume'}); time.sleep(.2)
 time.sleep(3); snap('boot')
 while time.time()<deadline:
  if command.exists():
   c=json.loads(command.read_text(encoding='utf-8-sig')); command.unlink()
   if c.get('quit'): break
   for button in c.get('buttons',[]): m.press(ws,button,wait=c.get('wait',1))
   if c.get('scan'):
    hits=m.scan_ram(ws); (out/(c['name']+'_hits.json')).write_text(json.dumps(hits,indent=2),encoding='utf-8')
   snap(c['name'])
  time.sleep(.15)
except Exception: print(traceback.format_exc(),flush=True)
finally:
 if ws: ws.close()
 p.terminate(); p.wait(timeout=10)
