import importlib.util,subprocess,time,json,ctypes,traceback
from pathlib import Path
root=Path.cwd();out=root/'outputs/step104_alloc_repro';out.mkdir(parents=True,exist_ok=True)
s=importlib.util.spec_from_file_location('m','PROJECT_ROOT/bia_stage40i_tools/bia_stage40i_actual_resource_trace.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);_,b=m.load_helpers()
portable=root/'outputs/step104_runtime/portable';log=out/'ppsspp.log'
p=subprocess.Popen([str(portable/'PPSSPPWindows64.exe'),'--loglevel=4',f'--log={log}','--windowed','--debugger=26431','PROJECT_ROOT/BIA_STEP103_RELOAD_CONFIRM_KO_TEST.iso'],cwd=portable)
(out/'process.json').write_text(json.dumps({'pid':p.pid,'iso':'PROJECT_ROOT/BIA_STEP103_RELOAD_CONFIRM_KO_TEST.iso','isolated_memstick':str(portable/'memstick')},indent=2))
port=b.wait_for_actual_debugger_port(log,30);ws,_=b.connect_debugger(port);print('MONITOR READY PID',p.pid,'PORT',port,flush=True)
m.wait_cpu_ready(ws)
print(ws.request('cpu.breakpoint.add',address=0x088b9c48,enabled=True,log=False,condition='v0 >= s1 && v0 < s1 + 12'))
print('ALLOCATION OVERLAP WATCH READY',flush=True)
seen=set();deadline=time.time()+3600
while p.poll() is None and time.time()<deadline:
 try:
  state=ws.request('cpu.status',timeout=3);(out/'latest_status.json').write_text(json.dumps(state,indent=2))
  if state.get('paused') or state.get('stepping'):
   pc=state.get('pc',0)
   if pc not in seen:
    seen.add(pc);tag=f'paused_{pc:08x}';regs=ws.request('cpu.getAllRegs',timeout=3);(out/(tag+'_regs.json')).write_text(json.dumps(regs,indent=2));print('PAUSED',hex(pc),flush=True)
    if pc in [0x088b9c8c,0x088b9c48]:
     hwnd=b.find_ppsspp_hwnd(timeout=2);pid,hostbase=b.get_pid_base(hwnd);assert pid==p.pid
     k=ctypes.WinDLL('kernel32',use_last_error=True);k.OpenProcess.argtypes=[ctypes.c_uint32,ctypes.c_int,ctypes.c_uint32];k.OpenProcess.restype=ctypes.c_void_p;k.CloseHandle.argtypes=[ctypes.c_void_p];h=k.OpenProcess(0x0410,False,pid);assert h
     try:r=b.rpm(h,hostbase+0x08000000,0x02000000)
     finally:k.CloseHandle(h)
     (out/(tag+'_ram.bin')).write_bytes(r);print('CRASH RAM CAPTURED',len(r),flush=True)
 except Exception as e:print('MONITOR',type(e).__name__,str(e),flush=True)
 time.sleep(1)
ws.close();print('MONITOR ENDED; emulator not terminated by monitor',flush=True)
