import importlib.util,subprocess,time,json,base64,traceback
from pathlib import Path
root=Path.cwd(); out=root/'outputs/stage43k_trace'; out.mkdir(parents=True,exist_ok=True)
s=importlib.util.spec_from_file_location('m',r'PROJECT_ROOT\bia_stage40i_tools\bia_stage40i_actual_resource_trace.py'); m=importlib.util.module_from_spec(s); s.loader.exec_module(m)
m.SOURCE_ISO=Path('PROJECT_ROOT/BIA_STAGE43I_CAMPAIGN_HINT_FIT_TEST.iso'); _,b=m.load_helpers(); port=b.choose_free_port(); log=out/'ppsspp.log'
if log.exists(): log.unlink()
cfg=out/'capture.ini'; cfg.write_text('[General]\nWindowX = 100\nWindowY = 100\nWindowWidth = 960\nWindowHeight = 544\n[Graphics]\nSoftwareRenderer = True\n',encoding='utf-8')
p=subprocess.Popen([str(b.find_ppsspp_exe()),'--loglevel=4',f'--log={log}','--windowed',f'--appendconfig={cfg}',f'--debugger={port}',str(m.SOURCE_ISO)])
ws=None
try:
 port=b.wait_for_actual_debugger_port(log,30); (out/'debugger_port.txt').write_text(str(port)); ws,host=b.connect_debugger(port); print('CONNECTED',p.pid,flush=True)
 m.wait_cpu_ready(ws)
 ws.request('cpu.breakpoint.add',address=0x08827b0c,enabled=False,log=True,condition='a0 >= 0x80',logFormat='HUDCP cp={a0} font={s7} index={a2} text={t9}')
 ws.request('cpu.breakpoint.add',address=0x08c5ced4,enabled=False,log=True,condition='a1 >= 0x80',logFormat='RFONT cp={a1} font={a0} ra={ra} text={s0}')
 ws.request('cpu.breakpoint.add',address=0x0881f2b4,enabled=False,log=True,condition='a2 >= 0x80',logFormat='UWIDTH cp={a2} font={a1} ra={ra}')
 command=root/'work/nav43k_command.json'; deadline=time.time()+1200
 def snap(name):
  import struct
  from PIL import Image
  for a in [0x04000000,0x04044000]:
   data=m.read_ws(ws,a,512*272*2); rgb=bytearray()
   for y in range(272):
    for x in range(480):
     v=struct.unpack_from('<H',data,(y*512+x)*2)[0]; rgb.extend(((v&31)*255//31,((v>>5)&63)*255//63,((v>>11)&31)*255//31))
   Image.frombytes('RGB',(480,272),bytes(rgb)).save(out/(name+'_'+hex(a)+'.png'))
  print('SNAP',name,flush=True)
 time.sleep(3); snap('boot')
 deadline=time.time()+1200
 while time.time()<deadline:
  if command.exists():
   c=json.loads(command.read_text(encoding='utf-8-sig')); command.unlink()
   if c.get('quit'): break
   if c.get('trace'):
    ws.request('cpu.breakpoint.add',address=int(c.get('trace_address','0x08C7F2FC'),0),enabled=False,log=True,condition=c.get('trace_condition','a1 >= 0x80'),logFormat='BIA40Y a0={a0} a1={a1} ra={ra} s0={s0} s1={s1} s2={s2} s3={s3} s4={s4} s5={s5} sp={sp}')
   if c.get('watch'):
    for a in c['watch']: print(ws.request('memory.breakpoint.add',address=int(a,0),size=1,enabled=False,log=True,read=True,write=False,logFormat='HUDREAD pc={pc} ra={ra} a0={a0} a1={a1} s0={s0} s1={s1} s2={s2}'),flush=True)
   for button in c.get('buttons',[]): print(m.press(ws,button,wait=c.get('wait',1)),flush=True)
   if c.get('hold_button'):
    ws.request('input.buttons.send',buttons={c['hold_button']:True});time.sleep(c.get('hold_seconds',.3));ws.request('input.buttons.send',buttons={c['hold_button']:False});time.sleep(c.get('settle',1))
   if c.get('analog'):
    ws.request('input.analog.send',x=c['analog'][0],y=c['analog'][1])
    time.sleep(c.get('hold_seconds',2))
    ws.request('input.analog.send',x=0,y=0)
   snap(c.get('name','current'))
   if c.get('vram'):
    (out/(c.get('name','current')+'_vram.bin')).write_bytes(m.read_ws(ws,0x04000000,0x200000))
   if c.get('memoryAddress'):
    (out/(c.get('name','current')+'_memory.bin')).write_bytes(m.read_ws(ws,int(c['memoryAddress'],0),c.get('memorySize',512)))
   if c.get('regs'):
    (out/(c.get('name','current')+'_regs.json')).write_text(json.dumps(ws.request('cpu.getAllRegs'),indent=2))
   if c.get('trace') and not c.get('keep_trace'):
    ws.request('cpu.breakpoint.remove',address=int(c.get('trace_address','0x08C7F2FC'),0))
   if c.get('width_probe'):
    ws.request('cpu.breakpoint.add',address=0x08C7F2FC,enabled=True,log=False,condition='ra == 0x08C7F9BC && a1 >= 0xE0 && a1 < 0xF0 && s0 == 0x0972524C')
    until=time.time()+12
    while time.time()<until:
     if ws.request('cpu.status').get('stepping'):break
     time.sleep(.02)
    regs=ws.request('cpu.getAllRegs');(out/'width_probe_regs.json').write_text(json.dumps(regs,indent=2))
    g={}
    for cat in regs.get('categories',[]):
     for n,v in zip(cat.get('registerNames',[]),cat.get('uintValues',[])):g[n.lower()]=v
    for reg in ['s0','s1','s2','s3','s4','s5','s6','s7','a0','a2','a3','sp']:
     a=g.get(reg,0)
     if 0x08000000<=a<0x0a000000:
      (out/('width_'+reg+'.bin')).write_bytes(m.read_ws(ws,a,0x180))
    ws.request('cpu.breakpoint.remove',address=0x08C7F2FC);ws.send_json({'event':'cpu.resume'})
   if c.get('disasmAddress'):
    addr=int(c['disasmAddress'],0); (out/('disasm_'+hex(addr)+'.json')).write_text(json.dumps(ws.request('memory.disasm',address=addr,count=c.get('count',100)),indent=2))
   if c.get('disasm'):
    (out/'lookup_disasm.json').write_text(json.dumps(ws.request('memory.disasm',address=0x08C7F2FC,count=90),indent=2),encoding='utf-8')
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
except Exception: print(traceback.format_exc(),flush=True)
finally:
 if ws: ws.close()
 p.terminate(); p.wait(timeout=10)






