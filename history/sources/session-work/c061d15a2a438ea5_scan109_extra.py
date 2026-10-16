exec(open('work/audit109_titles.py',encoding='utf-8-sig').read().split('allrefs=[]')[0]);rec=b.iso_find_record(src,['PSP_GAME','USRDIR','SYSTEM'])
with src.open('rb') as f:names2=[x['name'] for x in b.iso_list_dir(f,rec['extent'],rec['size']) if x['name'].startswith('SKR_O_') and x['name'].endswith('.MDI')]
results=[]
for name in names2:
 _,blob=b.iso_read_file(src,['PSP_GAME','USRDIR','SYSTEM',name]);st=b.parse_mdi(blob);hits=[]
 for e in st:
  raw=bytes(e['decoded'])
  for en in targets:
   if en.encode()+b'\0' in raw:hits.append(en)
 results.append({'mdi':name,'matching_display_strings':sorted(set(hits))})
Path('outputs/step109/extra_resource_scan.json').write_text(json.dumps(results,indent=2));print([(x['mdi'],len(x['matching_display_strings'])) for x in results])
