import importlib.util,struct,hashlib
from pathlib import Path
s=importlib.util.spec_from_file_location('m','PROJECT_ROOT/bia_stage40i_tools/bia_stage40i_actual_resource_trace.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);_,b=m.load_helpers()
iso=Path('PROJECT_ROOT/BIA_STAGE40K_CONTROLS_FONT_TEST.iso')
for path in [['PSP_GAME','SYSDIR','BOOT.BIN'],['PSP_GAME','SYSDIR','EBOOT.BIN'],['PSP_GAME','USRDIR','SYSTEM','BIAON.PRX']]:
 _,data=b.iso_read_file(iso,path);print('/'.join(path),len(data),hashlib.sha1(data).hexdigest(),data[:4].hex());Path('work/'+path[-1]+'.40k').write_bytes(data)
data=Path('work/BOOT.BIN.40k').read_bytes();print('call',data[0x4fcc0+0x80:0x4fcc0+0x88].hex())
for p in range(0x5bf54c,0x5bf54c+0x177848,8):
 off,typ=struct.unpack_from('<II',data,p)
 if 0x4c0480<=off<0x4c06c0: print(hex(p),hex(off),typ)
