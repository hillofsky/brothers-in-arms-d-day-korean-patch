import importlib.util
s=importlib.util.spec_from_file_location('m','PROJECT_ROOT/bia_stage40i_tools/bia_stage40i_actual_resource_trace.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);_,b=m.load_helpers();w,_=b.connect_debugger(26431)
for event in ['cpu.status','game.status']:
 try:print(event,w.request(event))
 except Exception as e:print(e)
w.close()
