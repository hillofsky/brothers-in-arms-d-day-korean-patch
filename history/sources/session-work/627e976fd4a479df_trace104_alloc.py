import importlib.util,json
from pathlib import Path
s=importlib.util.spec_from_file_location('m','PROJECT_ROOT/bia_stage40i_tools/bia_stage40i_actual_resource_trace.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);_,b=m.load_helpers();w,_=b.connect_debugger(26431)
for a,label,fmt in [(0x088b9c20,'STRFREE','CPSTRFREE pc={pc} s1={s1} oldptr={a1} count={s2} oldcap={a2} ra={ra}'),(0x088b9c48,'STRALLOC','CPSTRALLOC pc={pc} s1={s1} result={v0} count={s2} ra={ra}')]:
 print(w.request('cpu.breakpoint.add',address=a,enabled=False,log=True,condition='s1 >= 0x09A00000 && s1 < 0x09B00000',logFormat=fmt))
w.close()
Path('outputs/step104_user_repro/analysis_status.json').write_text(json.dumps({'crash_reproduced':True,'pc':'0x088b9c8c','invalid_pointer':'0x305f3244','invalid_pointer_bytes':'D2_0','map_resource':'D2_0630_.MDI','fstring_object':'0x09a857e4','cause_not_yet_proven':True,'patch_built':False,'allocation_traces_installed':True},indent=2))
