import importlib.util,ctypes,json,re,struct
from pathlib import Path
s=importlib.util.spec_from_file_location('m','PROJECT_ROOT/bia_stage40i_tools/bia_stage40i_actual_resource_trace.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);_,b=m.load_helpers();hwnd=b.find_ppsspp_hwnd(timeout=2);pid,hostbase=b.get_pid_base(hwnd);assert pid==21908,(pid,'unexpected process');k=ctypes.WinDLL('kernel32',use_last_error=True);k.OpenProcess.argtypes=[ctypes.c_uint32,ctypes.c_int,ctypes.c_uint32];k.OpenProcess.restype=ctypes.c_void_p;k.CloseHandle.argtypes=[ctypes.c_void_p];h=k.OpenProcess(0x0410,False,pid);assert h
try:
 r=b.rpm(h,hostbase+0x08000000,0x02000000)
finally:k.CloseHandle(h)
out=Path('outputs/step100_probe');out.mkdir(exist_ok=True);(out/'current_ram.bin').write_bytes(r);(out/'native_read_report.json').write_text(json.dumps({'pid':pid,'method':'PPSSPP read-only base-pointer query and ReadProcessMemory','guest_start':'0x08000000','guest_end':'0x0A000000','bytes':len(r),'process_write_permissions_requested':False,'game_paused_or_resumed':False},indent=2))
print('READ PSP RAM ONLY',len(r))
for needle in [b'ton\0','ton'.encode('utf-16le')+b'\0\0']:
 hits=[]
 for hh in re.finditer(re.escape(needle),r):
  a=hh.start()+0x8000000
  if needle[1]==0 and a%2:continue
  start=hh.start()
  if needle[1]==0:
   while start>=2 and 32<=struct.unpack_from('<H',r,start-2)[0]<=126:start-=2
  else:
   while start>0 and 32<=r[start-1]<=126:start-=1
  if hh.start()-start<10:hits.append({'address':hex(a),'context':r[max(0,start-40):hh.start()+len(needle)+8].hex()})
 print('TON',len(hits),hits[:15])
