import importlib.util,struct,json,re,shutil
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
s=importlib.util.spec_from_file_location('m','PROJECT_ROOT/bia_stage40i_tools/bia_stage40i_actual_resource_trace.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);_,b=m.load_helpers()
src=Path('PROJECT_ROOT/BIA_STEP120_MAC_NAME_KO_TEST.iso');dst=Path('PROJECT_ROOT/working/step123_font_source.iso');dst.parent.mkdir(exist_ok=True);assert dst.exists()
audit=json.loads(Path('outputs/step123/reference_audit.json').read_text(encoding='utf-8'));refs=[r for r in audit['refs'] if r['key_verified']];groups={name:[r for r in refs if r['mdi']==name] for name in {r['mdi'] for r in refs}};inv={x['mdi']:x for x in json.loads(Path('outputs/step098/inventory.json').read_text())};font=ImageFont.truetype('LOCAL_PATH',14);reports=[]
for name,rr in sorted(groups.items()):
 menu=name=='ON_MEMU_O.MDI';base=0x8e2d020 if menu else 0x8e03020;stride=0x78000;mi,ai=(23,22) if menu else (35,34);meta=base+mi*stride
 _,blob=b.iso_read_file(src,['PSP_GAME','USRDIR','SYSTEM',name]);st={x['index']:bytes(x['decoded']) for x in b.parse_mdi(blob)};mu={i:bytearray(d) for i,d in st.items()}
 def read(a,n):
  i,o=divmod(a-base,stride);assert i in st and o+n<=len(st[i]);return st[i][o:o+n]
 fonts=[]
 for i,d in st.items():
  for h in re.finditer(re.escape(struct.pack('<I',meta)),d):
   off=h.start()
   if off%4 or off<4:continue
   count=struct.unpack_from('<H',d,off-4)[0]
   if 847<=count<=907:fonts.append((i,off-0x54,count))
 assert len(fonts)==2 and len({x[2] for x in fonts})==1,(name,fonts);count=fonts[0][2]
 cps={struct.unpack_from('<H',st[mi],j*24)[0] for j in range(count)};needed={ord(c) for r in rr for c in r['korean']};missing=sorted(needed-cps);assert all(0xac00<=c<=0xd7a3 for c in missing),(name,missing)
 if not missing:continue
 used=set()
 for j in range(151,count):
  u,v=struct.unpack_from('<2f',st[mi],j*24+8);used.add((round(u*128-.5),round(v*256-.5)))
 slots=[(page*128+col*17,y) for page in range(4) for y in range(0,496,16) for col in range(7) if not(page==0 and y<256) and (page*128+col*17,y) not in used];assert len(missing)<=len(slots)
 assert not any(st[mi][count*24:(count+len(missing))*24]),(name,'RFont record capacity')
 layout=[]
 for k,(cp,(x,y)) in enumerate(zip(missing,slots)):
  rec=bytearray(st[mi][151*24:152*24]);struct.pack_into('<H',rec,0,cp);struct.pack_into('<4f',rec,8,(x+.5)/128,(y+.5)/256,(x+16.5)/128,(y+15.5)/256);mu[mi][(count+k)*24:(count+k+1)*24]=rec
  for fi,fo,n in fonts:
   ptr=struct.unpack_from('<I',st[fi],fo+0x58+(cp>>8)*4)[0];si,so=divmod(ptr-base,stride);loc=so+(cp&255)*2;assert struct.unpack_from('<H',mu[si],loc)[0] in (0,count+k);struct.pack_into('<H',mu[si],loc,count+k)
  im=Image.new('L',(17,16),0);dr=ImageDraw.Draw(im);bb=font.getbbox(chr(cp));w,h=bb[2]-bb[0],bb[3]-bb[1];assert w<=15 and h<=14;dr.text(((17-w)//2-bb[0],(16-h)//2-bb[1]),chr(cp),font=font,fill=255);pix=im.load()
  for yy in range(16):
   for xx in range(17):
    gx,gy=x+xx,y+yy;bx=gx//2;o=(gy//8)*2048+(bx//16)*128+(gy%8)*16+bx%16;sh=4*(gx%2);mu[ai][o]=(mu[ai][o]&~(15<<sh))|(((pix[xx,yy]+8)//17)<<sh)
  layout.append((cp,x,y))
 for fi,fo,n in fonts:struct.pack_into('<H',mu[fi],fo+0x50,count+len(missing))
 native=[]
 if not menu:
  fontnum=0
  for f in inv[name]['fonts']:
   if f['glyph_count']==11:continue
   addr=int(f['runtime'],16);fi,fo=divmod(addr-base,stride);head=read(addr,100);gp,n,cap,tp,tn,tc,rp,rn,rc,bp,bn=struct.unpack_from('<11I',head,0x28);assert n==rn and bn==1024
   records=bytearray(read(gp,n*20));pairs=[struct.unpack_from('<iHH',read(rp,rn*8),j*8)[1:] for j in range(rn)]
   for cp,x,y in layout:pairs.append((cp,len(records)//20));records.extend(struct.pack('<4IB3x',x,y,17,16,1))
   heads=[-1]*1024;maps=bytearray()
   for j,(cp,gi) in enumerate(pairs):buck=cp&1023;maps.extend(struct.pack('<iHH',heads[buck],cp,gi));heads[buck]=j
   lg,lr,lb=[(0x64000,0x69000,0x6b000),(0x6c000,0x71000,0x73000)][fontnum];fontnum+=1
   for off,payload in [(lg,records),(lr,maps),(lb,struct.pack('<1024i',*heads))]:
    assert not any(st[35][off:off+len(payload)]),(name,'new font space',hex(off));mu[35][off:off+len(payload)]=payload
   for off,value in [(0x28,base+35*stride+lg),(0x40,base+35*stride+lr),(0x4c,base+35*stride+lb),(0x2c,len(pairs)),(0x30,len(pairs)),(0x44,len(pairs)),(0x48,len(pairs))]:struct.pack_into('<I',mu[fi],fo+off,value)
   assert needed<={cp for cp,gi in pairs};native.append(addr)
 for fi,fo,n in fonts:
  for cp,x,y in layout:
   pp=struct.unpack_from('<I',mu[fi],fo+0x58+(cp>>8)*4)[0];ii,oo=divmod(pp-base,stride);gi=struct.unpack_from('<H',mu[ii],oo+(cp&255)*2)[0];assert struct.unpack_from('<H',mu[mi],gi*24)[0]==cp
 changed={i:bytes(v) for i,v in mu.items() if bytes(v)!=st[i]};new=b.rebuild_mdi(blob,changed);ck={x['index']:bytes(x['decoded']) for x in b.parse_mdi(new)};assert all(ck[i]==bytes(mu[i]) and len(ck[i])==len(st[i]) for i in st);b.append_iso_file_and_repoint(dst,['PSP_GAME','USRDIR','SYSTEM',name],new);assert b.iso_read_file(dst,['PSP_GAME','USRDIR','SYSTEM',name])[1]==new
 reports.append({'mdi':name,'added_codepoints':missing,'rfont_before':count,'rfont_after':count+len(missing),'native_fonts_updated':len(native),'changed_streams':sorted(changed)});print(name,missing,flush=True)
Path('outputs/step123/font_additions.json').write_text(json.dumps(reports,indent=2));print('FONT SOURCE READY',dst)
