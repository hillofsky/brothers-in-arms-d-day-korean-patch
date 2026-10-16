import struct,importlib.util,json,shutil,hashlib
from pathlib import Path
REG={'zero':0,'a0':4,'a1':5,'a2':6,'t0':8,'t1':9,'t2':10,'t3':11,'t6':14,'sp':29,'ra':31}
def I(op,rs,rt,imm):return op<<26|REG[rs]<<21|REG[rt]<<16|(imm&65535)
def R(fn,rs,rt,rd,sh=0):return REG[rs]<<21|REG[rt]<<16|REG[rd]<<11|sh<<6|fn
def decoder(output,advance):
 code=[];labels={};fix=[]
 def e(w):code.append(w)
 def label(n):labels[n]=len(code)
 def branch(op,rs,rt,n):fix.append((len(code),n));e(I(op,rs,rt,0));e(0)
 e(I(9,'sp','sp',-24))
 for j,r in enumerate(['t0','t1','t2','t3']):e(I(43,'sp',r,j*4))
 e(R(33,'a0','zero','t0'));e(I(36,'t0',output,0));e(I(11,output,'t1',0xc2));branch(5,'t1','zero','done')
 e(I(11,output,'t1',0xf0));branch(4,'t1','zero','done')
 e(I(36,'t0','t1',1));e(I(12,'t1','t2',0xc0));e(I(13,'zero','t3',0x80));branch(5,'t2','t3','done')
 e(I(11,output,'t2',0xe0));branch(5,'t2','zero','two')
 e(I(36,'t0','t2',2));e(I(12,'t2','t3',0xc0));e(I(13,'zero','t0',0x80));branch(5,'t3','t0','done')
 e(I(12,output,output,15));e(R(0,'zero',output,output,12));e(I(12,'t1','t1',63));e(R(0,'zero','t1','t1',6));e(I(12,'t2','t2',63));e(R(37,output,'t1',output));e(R(37,output,'t2',output));e(I(9,advance,advance,2));branch(4,'zero','zero','done')
 label('two');e(I(12,output,output,31));e(R(0,'zero',output,output,6));e(I(12,'t1','t1',63));e(R(37,output,'t1',output));e(I(9,advance,advance,1))
 label('done')
 for j,r in enumerate(['t0','t1','t2','t3']):e(I(35,'sp',r,j*4))
 e(R(8,'ra','zero','zero'));e(I(9,'sp','sp',24))
 for pos,n in fix:code[pos]=(code[pos]&0xffff0000)|((labels[n]-pos-1)&65535)
 return struct.pack('<%dI'%len(code),*code)
s=importlib.util.spec_from_file_location('m','PROJECT_ROOT/bia_stage40i_tools/bia_stage40i_actual_resource_trace.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);_,b=m.load_helpers()
src=Path('PROJECT_ROOT/BIA_STAGE43D_CAMPAIGN_UFONT_EXPANSION_TEST.iso');dst=Path('PROJECT_ROOT/BIA_STAGE43E_CAMPAIGN_UTF8_RENDER_TEST.iso');path=['PSP_GAME','USRDIR','SYSTEM','BIAOFF.PRX'];_,old=b.iso_read_file(src,path);new=bytearray(old);edits=[]
def put(va,w,expected=None):
 off=va+0x80;before=struct.unpack_from('<I',old,off)[0]
 if expected is not None:assert before==expected,(hex(va),hex(before),hex(expected))
 struct.pack_into('<I',new,off,w);edits.append({'va':hex(va),'before':hex(before),'after':hex(w)})
helpers=[(0x49b780,decoder('a0','a2')),(0x49b900,decoder('a2','t6'))]
assert all(len(c)<=0x180 for a,c in helpers)
# Main drawing: original addu computes the source pointer; hook the following signed-byte load.
put(0x23b04,0x0c000000|(helpers[0][0]>>2),I(32,'a0','a0',0))
# Original following lw a1,0x54(s7) executes in the new JAL delay slot.
put(0x208dc,0x0c000000|(helpers[1][0]>>2),I(32,'a0','a2',0))
# Original following addiu t0,sp,4 executes in the new JAL delay slot.
for va in [0x23b0c,0x23b18,0x23b24,0x23b28]:put(va,0)
put(0x23b30,I(12,'a0','a0',65535));put(0x23bb4,I(13,'zero','t1',1));put(0x23bc0,R(33,'a0','zero','a1'))
for va in [0x23bc4,0x23bcc,0x23bd0,0x23bd4]:put(va,0)
put(0x23bc8,R(33,'a1','zero','a0'));put(0x23be0,I(12,'a0','a0',65535))
# The shared UFont width lookup must retain the full codepoint and 16-bit glyph index.
put(0x1b2b4,I(12,'a2','t2',65535))
for va in [0x1b2b8,0x1b2c8,0x1b2d4]:put(va,0)
put(0x1b2e0,R(33,'t2','zero','a2'));put(0x1b2e4,R(33,'a2','zero','t2'));put(0x1b2ec,I(12,'t2','t2',65535));put(0x1b354,I(13,'zero','t2',1));put(0x1b360,R(33,'a2','zero','t1'));put(0x1b364,0);put(0x1b368,R(33,'t1','zero','a2'))
for va in [0x1b36c,0x1b370,0x1b374]:put(va,0)
put(0x1b378,I(12,'a2','t2',65535))
relstart=0x59a558;relend=relstart+0x15cdd8;disabled=[];free=[]
for p in range(relstart,relend,8):
 a,t=struct.unpack_from('<II',new,p)
 if any(start<=a<start+len(code) for start,code in helpers) and t:
  assert t in [1,2,4,5,6];struct.pack_into('<II',new,p,a,0);disabled.append(hex(p));t=0
 if t==0 and 0x49b400<=a<0x49ba80:free.append(p)
assert len(free)>=2
for p,a in zip(free,[0x23b04,0x208dc]):struct.pack_into('<II',new,p,a,4)
for a,c in helpers:new[a+0x80:a+0x80+len(c)]=c
assert not dst.exists();shutil.copy2(src,dst);b.overwrite_iso_same_size(dst,path,bytes(new));assert b.iso_read_file(dst,path)[1]==bytes(new)
out=Path('outputs/stage43e');out.mkdir(exist_ok=True)
for a,c in helpers:(out/(hex(a)+'_decoder.bin')).write_bytes(c)
rep={'test_iso':str(dst),'code_sha1':hashlib.sha1(new).hexdigest(),'hooks':['0x08827b04','0x088248dc'],'helpers':[{'va':hex(a),'bytes':len(c)} for a,c in helpers],'disabled_old_relocations':disabled,'new_jal_relocation_offsets':[hex(x) for x in free[:2]],'patches':edits,'iso_readback_verified':True,'runtime_verified':False,'full_campaign_complete':False}
(out/'utf8_render_patch_report.json').write_text(json.dumps(rep,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in rep.items() if k!='patches'}))

