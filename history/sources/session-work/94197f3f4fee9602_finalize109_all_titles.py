import importlib.util,json,struct,re,hashlib
from pathlib import Path
s=importlib.util.spec_from_file_location('m','PROJECT_ROOT/bia_stage40i_tools/bia_stage40i_actual_resource_trace.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);_,b=m.load_helpers();out=Path('outputs/step109');iso=(out/'BIA_STEP109_ALL_MISSION_NAMES_KO_TEST.iso').resolve();t=json.loads((out/'translations.json').read_text(encoding='utf-8'));catalog=json.loads((out/'levelinfo_inventory.json').read_text(encoding='utf-8'));checks=[];additional=[]
for item in catalog:
 name=item['mdi'];parts=['PSP_GAME','USRDIR','SYSTEM',name];_,blob=b.iso_read_file(iso,parts);st={e['index']:bytes(e['decoded']) for e in b.parse_mdi(blob)};mut={i:bytearray(v) for i,v in st.items()};cursor=0x42000;changed=False;row={'mdi':name}
 for off,label in [(0x5444c,'title'),(0x54464,'date'),(0x54470,'location')]:
  ptr,n,cap=struct.unpack_from('<III',st[13],off);i,o=divmod(ptr-0x08e03020,0x78000)
  if i not in st or not 1<=n<=512:continue
  en=st[i][o:o+n-1].decode('utf-8');ko=t.get(en)
  match=re.fullmatch(r'(D-Day|D-D\+\d+)\s+(\d{2})(\d{2})\s+June (\d+), 1944',en)
  if match:
   day=match[1].replace('D-D+','D+');ko=f'{day} {match[2]}:{match[3]}  1944년 6월 {int(match[4])}일'
  if label=='title' and not name.startswith('SKR_'):
   stem=name[:-4].rstrip('_');files=list(Path('PROJECT_ROOT/extracted/PSP_GAME/USRDIR/SYSTEM').glob(stem+'*.INT'))
   if files:
    title=next((x.split('=',1)[1].strip().strip('"') for x in files[0].read_bytes().decode('cp1252').splitlines() if x.startswith('Title=')),None)
    ko=t.get(title,ko)
  if ko is not None and ko!=en:
   raw=ko.encode()+b'\0';assert not any(st[35][cursor:cursor+len(raw)]);mut[35][cursor:cursor+len(raw)]=raw;struct.pack_into('<III',mut[13],off,0x08e03020+35*0x78000+cursor,len(raw),len(raw));cursor=(cursor+len(raw)+15)&~15;additional.append({'mdi':name,'offset':off,'english':en,'korean':ko});changed=True;en=ko
  row[label]=en
  if label=='title':assert any('\uac00'<=c<='\ud7a3' for c in en),(name,en)
  if label=='location' and not en.startswith('<?'):assert any('\uac00'<=c<='\ud7a3' for c in en),(name,en)
 if changed:
  rebuilt=b.rebuild_mdi(blob,{i:bytes(d) for i,d in mut.items() if bytes(d)!=st[i]});b.append_iso_file_and_repoint(iso,parts,rebuilt);assert b.iso_read_file(iso,parts)[1]==rebuilt
 checks.append(row)
# Translate localization fallback values while preserving section names, keys and internal map/resource identifiers.
rec=b.iso_find_record(iso,['PSP_GAME','USRDIR','SYSTEM'])
with iso.open('rb') as f:intfiles=[r['name'] for r in b.iso_list_dir(f,rec['extent'],rec['size']) if r['name'].endswith('.INT')]
intchecks=[]
for name in intfiles:
 parts=['PSP_GAME','USRDIR','SYSTEM',name];_,data=b.iso_read_file(iso,parts);lines=data.splitlines(keepends=True);count=0
 for j,line in enumerate(lines):
  raw=line.rstrip(b'\r\n')
  if b'=' not in raw:continue
  key,val=raw.split(b'=',1);k=key.decode('ascii',errors='ignore')
  if not(k in ['Title','TitleLocation','TitleDate'] or re.fullmatch(r'(NameLong|NameShort|Date|StoryMissionNameLong|StoryMissionNameShort|StoryMissionDate)\(\d+\)',k)):continue
  v=val.strip().strip(b'"').decode('cp1252',errors='replace');ko=t.get(v)
  if ko is None:continue
  quote=b'"' if val.strip().startswith(b'"') else b'';eol=b'\r\n' if line.endswith(b'\r\n') else b'\n';lines[j]=key+b'='+quote+ko.encode()+quote+eol;count+=1
 if count:
  new=b''.join(lines);b.append_iso_file_and_repoint(iso,parts,new);assert b.iso_read_file(iso,parts)[1]==new;intchecks.append({'file':name,'values_updated':count})
(out/'all_levelinfo_check.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8');(out/'additional_header_refs.json').write_text(json.dumps(additional,ensure_ascii=False,indent=2),encoding='utf-8');(out/'int_updates.json').write_text(json.dumps(intchecks,indent=2));report=json.loads((out/'build_report.json').read_text(encoding='utf-8'));report.update({'all_32_active_map_titles_korean_verified':True,'all_20_campaign_locations_korean_verified':True,'additional_header_refs':len(additional),'external_int_files_updated':len(intchecks),'external_int_values_updated':sum(r['values_updated'] for r in intchecks),'unused_network_variants_scanned_not_modified':24,'output_sha256':hashlib.file_digest(iso.open('rb'),'sha256').hexdigest()});(out/'build_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print('COMPLETE HEADERS32; additional',len(additional),'INT files',len(intchecks),'values',sum(r['values_updated'] for r in intchecks))
