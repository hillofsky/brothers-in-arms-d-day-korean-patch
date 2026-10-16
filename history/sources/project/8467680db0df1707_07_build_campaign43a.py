import importlib.util,struct,json,shutil,csv,hashlib,re,collections
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
root=Path(r'PROJECT_ROOT');source=root/'BIA_STAGE42H_ALL8_MOVIES_512_TEST.iso';dest=root/'BIA_STAGE43A_FIRST_CAMPAIGN_KO_TEST.iso';out=Path('outputs/stage43a');out.mkdir(parents=True,exist_ok=True)
sp=importlib.util.spec_from_file_location('m',root/'bia_stage40i_tools/bia_stage40i_actual_resource_trace.py');m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);_,b=m.load_helpers()
parts=['PSP_GAME','USRDIR','SYSTEM'];name='D0_0130_';_,blob=b.iso_read_file(source,parts+[name+'.MDI']);st={x['index']:bytes(x['decoded']) for x in b.parse_mdi(blob)};mu={i:bytearray(d) for i,d in st.items()};base=0x08E03020;stride=0x78000;metabase=base+35*stride
rows=json.loads(Path('work/first_campaign_units.json').read_text(encoding='utf-8'));translations=json.loads(Path('work/campaign_first_ko.json').read_text(encoding='utf-8'));audit=json.loads(Path('work/campaign_first_reference_audit.json').read_text(encoding='utf-8'))
assert len(rows)==len(translations)==137
for r in rows:assert collections.Counter(re.findall(r'%[^%\s]+%',r['English']))==collections.Counter(re.findall(r'%[^%\s]+%',translations[r['id']]))
plan=json.loads((root/'bia_stage39a_tools/stage39a_font_plan.json').read_text(encoding='utf-8'));oldchars={x['char'] for x in plan['layout']};added=sorted({c for v in translations.values() for c in v if ord(c)>127}-oldchars);assert len(added)==33
# Decode the proven font atlas; retain every existing glyph cell and all Latin pixels.
atlas=bytes(st[34][:0x20000]);pixels=bytearray(512*512)
for y in range(512):
 for x in range(512):
  bx=x//2;off=(y//8)*2048+(bx//16)*128+(y%8)*16+bx%16;pixels[y*512+x]=((atlas[off]>>(4*(x%2)))&15)*17
image=Image.frombytes('L',(512,512),bytes(pixels));draw=ImageDraw.Draw(image);font=ImageFont.truetype(r'LOCAL_PATH',16)
occupied={(x['atlas_x'],x['atlas_y']) for x in plan['layout']};slots=[(page*128+col*17,y) for page in range(4) for y in range(0,496,16) for col in range(7) if not(page==0 and y<256)];assert len(slots)==756
free=[pos for pos in slots if pos not in occupied];assert len(free)==60
newlayout=[]
for index,(ch,(x,y)) in enumerate(zip(added,free)):
 bbox=font.getbbox(ch);w=bbox[2]-bbox[0];h=bbox[3]-bbox[1];assert w<=17 and h<=16,(ch,bbox)
 draw.rectangle((x,y,x+16,y+15),fill=0);draw.text((x-bbox[0]+(17-w)//2,y-bbox[1]+(16-h)//2),ch,font=font,fill=255)
 newlayout.append({'char':ch,'codepoint':ord(ch),'glyph_index':847+index,'atlas_x':x,'atlas_y':y})
newpixels=image.tobytes();newatlas=bytearray(atlas);allowed=set()
for item in newlayout:
 for y in range(item['atlas_y'],item['atlas_y']+16):
  for x in range(item['atlas_x'],item['atlas_x']+17):
   bx=x//2;off=(y//8)*2048+(bx//16)*128+(y%8)*16+bx%16;shift=4*(x%2);v=min(15,(newpixels[y*512+x]+8)//17);newatlas[off]=(newatlas[off]&~(15<<shift))|(v<<shift);allowed.add((x,y))
assert all(newpixels[y*512+x]==pixels[y*512+x] for y in range(512) for x in range(512) if (x,y) not in allowed)
mu[34][:0x20000]=newatlas;image.save(out/'campaign_font_extended.png')
# Expand records and rebuild the 44 Unicode lookup pages without disturbing text payloads at B000.
count=880;old=st[35];meta=bytearray(0xAB30);meta[:847*24]=old[:847*24];template=old[151*24:152*24];page_start=0x5300;page_map={hb:page_start+(hb-0xAC)*512 for hb in range(0xAC,0xD8)}
for hb,off in page_map.items():meta[off:off+512]=old[0x5000+(hb-0xAC)*512:0x5200+(hb-0xAC)*512]
for item in newlayout:
 cp=item['codepoint'];gi=item['glyph_index'];x=item['atlas_x'];y=item['atlas_y'];record=bytearray(template);struct.pack_into('<H',record,0,cp)
 for off,v in [(8,(x+.5)/128),(12,(y+.5)/256),(16,(x+17.5)/128),(20,(y+16.5)/256)]:struct.pack_into('<f',record,off,v)
 meta[gi*24:(gi+1)*24]=record;struct.pack_into('<H',meta,page_map[cp>>8]+(cp&255)*2,gi)
meta[0xAB00:0xAB30]=old[0xA800:0xA830];mu[35][:len(meta)]=meta
for off in [0x7F64,0xA0FC]:
 assert struct.unpack_from('<H',mu[30],off+0x50)[0]==847
 struct.pack_into('<H',mu[30],off+0x50,count)
 for hb,pos in page_map.items():struct.pack_into('<I',mu[30],off+0x58+hb*4,metabase+pos)
 for field in [0x474,0x478,0x488]:
  ptr=struct.unpack_from('<I',mu[30],off+field)[0];assert metabase+0xA800<=ptr<metabase+0xA830;struct.pack_into('<I',mu[30],off+field,ptr+0x300)
# Existing Y text is preserved; append campaign payloads in the same proven stream.
cursor=0x10000;cache={};actions=[];key_audit=[]
for ref in audit['refs']:
 if not ref['key_verified']:continue
 assert ref['stream']==26
 off=int(ref['offset'],16);ko=translations[ref['id']];payload=ko.encode('utf-8')+b'\0'
 if ko not in cache:
  assert cursor+len(payload)<stride;mu[35][cursor:cursor+len(payload)]=payload;cache[ko]=(metabase+cursor,len(payload));cursor=(cursor+len(payload)+3)&~3
 ptr,n=cache[ko];key=st[26][off-12:off];struct.pack_into('<III',mu[26],off,ptr,n,n);assert mu[26][off-12:off]==key
 actions.append({**ref,'korean':ko,'pointer':hex(ptr),'bytes':n});key_audit.append({'offset':hex(off-12),'bytes_hex':key.hex()})
assert len(actions)==274 and len({x['id'] for x in actions})==135
for x in key_audit:off=int(x['offset'],16);assert mu[26][off:off+12].hex()==x['bytes_hex']
# The two title values were already translated in Y.
for text in [translations['BIA-01749'],translations['BIA-02383']]:assert text.encode('utf-8')+b'\0' in st[35]
changed={i:bytes(d) for i,d in mu.items() if bytes(d)!=st[i]};patched=b.rebuild_mdi(blob,changed);check={x['index']:bytes(x['decoded']) for x in b.parse_mdi(patched)};assert all(check[i]==bytes(d) for i,d in mu.items())
for item in plan['layout']+newlayout:
 cp=item['codepoint'];gi=item['glyph_index'];assert struct.unpack_from('<H',check[35],page_map[cp>>8]+(cp&255)*2)[0]==gi
assert not dest.exists();shutil.copy2(source,dest);b.append_iso_file_and_repoint(dest,parts+[name+'.MDI'],patched);assert b.iso_read_file(dest,parts+[name+'.MDI'])[1]==patched
report={'stage':'43A','source':str(source),'test_iso':str(dest),'translated_first_mission_units':137,'new_compiled_units':135,'compiled_value_refs':274,'already_translated_title_units':2,'font_count':880,'added_hangul':33,'atlas_sha1':hashlib.sha1(newatlas).hexdigest(),'metadata_base':hex(metabase),'new_payload_start':hex(metabase+0x10000),'payload_end_offset':hex(cursor),'changed_streams':list(changed),'control_tokens_verified':True,'key_metadata_unchanged':True,'all_unicode_pages_verified':True,'iso_readback_verified':True,'runtime_verified':False,'full_campaign_complete':False}
(out/'campaign_patch_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');(out/'campaign_actions.json').write_text(json.dumps(actions,ensure_ascii=False,indent=2),encoding='utf-8');(out/'new_font_glyphs.json').write_text(json.dumps(newlayout,ensure_ascii=False,indent=2),encoding='utf-8')
with (out/'campaign_first_mission_ko.tsv').open('w',encoding='utf-8-sig',newline='') as f:
 fields=list(rows[0]);writer=csv.DictWriter(f,fields,delimiter='\t');writer.writeheader()
 for row in rows:writer.writerow({**row,'한국어':translations[row['id']]})
print(json.dumps(report))
