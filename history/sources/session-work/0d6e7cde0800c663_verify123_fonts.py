exec(open('work/analyze112_hang.py',encoding='utf-8-sig').read().split('md=Cs')[0])
import json,struct
iso=Path('PROJECT_ROOT/BIA_STEP123_SKIRMISH_KO_TEST.iso');rows=[];checks=0
for item in json.loads(Path('outputs/step098/inventory.json').read_text()):
 name=item['mdi'];_,blob=b.iso_read_file(iso,['PSP_GAME','USRDIR','SYSTEM',name]);st={x['index']:bytes(x['decoded']) for x in b.parse_mdi(blob)};base=0x8e03020;stride=0x78000
 def rd(a,n):
  i,o=divmod(a-base,stride);assert i in st and o+n<=len(st[i]);return st[i][o:o+n]
 for f in item['fonts']:
  if f['glyph_count']==11:continue
  h=rd(int(f['runtime'],16),100);gp,n,cap,tp,tn,tc,rp,rn,rc,bp,bn=struct.unpack_from('<11I',h,0x28);assert n==cap==rn==rc and bn==1024;maps=rd(rp,rn*8);heads=struct.unpack('<1024i',rd(bp,4096));glyphs=rd(gp,n*20)
  for j in range(rn):
   _,cp,gi=struct.unpack_from('<iHH',maps,j*8);k=heads[cp&1023];seen=set()
   while k>=0:
    assert k<rn and k not in seen;seen.add(k);nxt,key,idx=struct.unpack_from('<iHH',maps,k*8)
    if key==cp:assert idx==gi and idx<n;break
    k=nxt
   else:raise AssertionError((name,cp))
   if gi>=150:
    x,y,w,hh,ti=struct.unpack_from('<4IB3x',glyphs,gi*20);assert ti==1 and x+w<=512 and y+hh<=512
   checks+=1
  rows.append({'mdi':name,'font':f['runtime'],'glyphs':rn})
Path('outputs/step123/font_hash_verification.json').write_text(json.dumps({'fonts':len(rows),'lookup_cases':checks,'passed':True,'resources':rows},indent=2));print('FONTS VERIFIED',len(rows),'LOOKUPS',checks)
