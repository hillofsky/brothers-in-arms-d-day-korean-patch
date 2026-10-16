import importlib.util,ctypes,json,re,struct
from pathlib import Path
s=importlib.util.spec_from_file_location('m','PROJECT_ROOT/bia_stage40i_tools/bia_stage40i_actual_resource_trace.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);_,b=m.load_helpers();hwnd=b.find_ppsspp_hwnd(timeout=2);pid,hostbase=b.get_pid_base(hwnd);assert pid==34380,(pid,'unexpected process');k=ctypes.WinDLL('kernel32',use_last_error=True);k.OpenProcess.argtypes=[ctypes.c_uint32,ctypes.c_int,ctypes.c_uint32];k.OpenProcess.restype=ctypes.c_void_p;k.CloseHandle.argtypes=[ctypes.c_void_p];h=k.OpenProcess(0x0410,False,pid);assert h
try:
 r=b.rpm(h,hostbase+0x08000000,0x02000000)
finally:k.CloseHandle(h)
out=Path('outputs/step114_menu');out.mkdir(exist_ok=True);(out/'current_ram.bin').write_bytes(r);(out/'native_read_report.json').write_text(json.dumps({'pid':pid,'method':'PPSSPP read-only base-pointer query and ReadProcessMemory','guest_start':'0x08000000','guest_end':'0x0A000000','bytes':len(r),'process_write_permissions_requested':False,'game_paused_or_resumed':False},indent=2))
print('READ PSP RAM ONLY',len(r))
