exec(open('work/analyze112_hang.py',encoding='utf-8-sig').read().split('md=Cs')[0])
import json,struct
src=Path('PROJECT_ROOT/BIA_STEP120_MAC_NAME_KO_TEST.iso');j=json.loads(Path('outputs/step120/reference_audit.json').read_text(encoding='utf-8'));refs=[x for x in j['refs'] if x['key_verified']];count=0
for name in sorted({x['mdi'] for x in refs}):
 _,d=b.iso_read_file(src,['PSP_GAME','USRDIR','SYSTEM',name]);st={x['index']:bytes(x['decoded']) for x in b.parse_mdi(d)}
 for x in refs:
  if x['mdi']!=name:continue
  a,n,c=struct.unpack_from('<III',st[x['stream']],x['offset']);i,o=divmod(a-0x8e03020,0x78000);assert st[i][o:o+n]==x['korean'].encode()+b'\0';assert n==c;count+=1
Path('outputs/step120/independent_readback.json').write_text(json.dumps({'verified':count,'passed':True},indent=2));print('VERIFIED',count)
