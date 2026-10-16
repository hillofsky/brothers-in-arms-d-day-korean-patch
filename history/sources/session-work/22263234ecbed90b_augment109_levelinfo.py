exec(open('work/audit109_titles.py',encoding='utf-8-sig').read().split('allrefs=[]')[0]);out=Path('outputs/step109');a=json.loads((out/'reference_audit.json').read_text(encoding='utf-8'));catalog=[]
for name in names[:-1]:
 _,blob=b.iso_read_file(src,['PSP_GAME','USRDIR','SYSTEM',name]);st={e['index']:bytes(e['decoded']) for e in b.parse_mdi(blob)};values={}
 for off,label in [(0x5444c,'title'),(0x54464,'date'),(0x54470,'location')]:
  ptr,n,cap=struct.unpack_from('<III',st[13],off);i,o=divmod(ptr-0x8e03020,0x78000)
  if i not in st or not 1<=n<=512 or n!=cap or st[i][o+n-1:o+n]!=b'\0':continue
  raw=st[i][o:o+n-1]
  try:en=raw.decode('utf-8')
  except UnicodeDecodeError:continue
  values[label]=en;ko=targets.get(en)
  hit=re.fullmatch(r'D([+-]\d+)\s+(\d{2})(\d{2})\s+June (\d+), 1944',en)
  if hit:ko=f'D{hit[1]} {hit[2]}:{hit[3]}  1944년 6월 {int(hit[4])}일'
  if ko is None:continue
  rr=[r for r in a['refs'] if r['mdi']==name and r['stream']==13 and r['offset']==off]
  if rr:rr[0]['key_verified']=True;rr[0]['korean']=ko
  else:a['refs'].append({'mdi':name,'stream':13,'offset':off,'english':en,'korean':ko,'key':label,'key_verified':True,'old_ptr':ptr,'old_n':n,'verification':'Native LevelInfo field and exact source date/title/location'})
 catalog.append({'mdi':name,'current_levelinfo':values})
a['targets']=targets;(out/'reference_audit.json').write_text(json.dumps(a,ensure_ascii=False,indent=2),encoding='utf-8');(out/'levelinfo_inventory.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2),encoding='utf-8');print('VALID',sum(x['key_verified'] for x in a['refs']));print('LevelInfo rows',len(catalog))
# Prepare builder, retain 16-byte padded buffers to avoid tightly packed dynamic-string reuse.
p=Path('work/build108_carentan.py').read_text(encoding='utf-8-sig');start=p.index('src=Path(');end=p.index(';dst=',start);p=p[:start]+"src=Path('"+str(src).replace('\\','/')+"')"+p[end:];p=p.replace('outputs/step108','outputs/step109').replace('BIA_STEP108_CARENTAN_LOCATION_KO_TEST.iso','BIA_STEP109_ALL_MISSION_NAMES_KO_TEST.iso').replace('0x38000','0x39000').replace("'STEP108'","'STEP109'").replace('(cursor+len(payload)+3)&~3','(cursor+len(payload)+15)&~15');Path('work/build109_titles.py').write_text(p,encoding='utf-8')
