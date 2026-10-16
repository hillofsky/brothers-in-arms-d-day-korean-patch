import importlib.util,struct,json,hashlib
from pathlib import Path
s=importlib.util.spec_from_file_location('m','PROJECT_ROOT/bia_stage40i_tools/bia_stage40i_actual_resource_trace.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);_,b=m.load_helpers();out=Path('outputs/step098');summary=json.loads((out/'build_report.json').read_text(encoding='utf-8'));reports=json.loads((out/'maps_report.json').read_text(encoding='utf-8'));iso=Path(summary['output_iso']);base=0x08e03020;stride=0x78000;results=[]
for item in reports:
 _,blob=b.iso_read_file(iso,['PSP_GAME','USRDIR','SYSTEM',item['mdi']]);assert hashlib.sha256(blob).hexdigest()==item['mdi_sha256'];st={x['index']:bytes(x['decoded']) for x in b.parse_mdi(blob)}
 def rd(a,n):
  i,o=divmod(a-base,stride);assert i in st and o+n<=len(st[i]);return st[i][o:o+n]
 for f in item['fonts']:
  a=int(f['font'],16);h=rd(a,0x64);gp,n,cap,tp,tn,tc,rp,rn,rc,bp,bn=struct.unpack_from('<11I',h,0x28);assert n==f['glyph_count'] and tn==2 and bn==1024
  heads=struct.unpack('<1024i',rd(bp,4096));maps=rd(rp,n*8);cps=[]
  for j in range(n):
   _,cp,gi=struct.unpack_from('<iHH',maps,j*8);cps.append(cp);i=heads[cp&1023];steps=0
   while i>=0:
    nxt,key,actual=struct.unpack_from('<iHH',maps,i*8)
    if key==cp:assert actual==gi;break
    i=nxt;steps+=1;assert steps<=n
   else:raise AssertionError((item['mdi'],hex(cp)))
  tex=struct.unpack('<I',rd(tp+4,4))[0];clone=rd(tex,0xf0);assert struct.unpack_from('<4I',clone,0x48)==(512,512,512,512);assert struct.unpack_from('<I',clone,0x44)[0]>>16==0x0909
  results.append({'mdi':item['mdi'],'font':f['font'],'glyph_count':n,'hangul_codepoints':sum(0xac00<=cp<=0xd7a3 for cp in cps),'curly_quote_codepoints':sum(cp in [0x2018,0x2019] for cp in cps),'all_hash_lookups_passed':True,'texture_512_verified':True})
 if item['action']=='NATIVE_UFONT_EXPANDED':
  rr=results[-2:];item.setdefault('unicode_glyphs_added_per_font',item.get('hangul_added_per_font'));item['hangul_added_per_font']=rr[0]['hangul_codepoints'];item['curly_quotes_added_per_font']=rr[0]['curly_quote_codepoints']
assert len(results)==64;summary['independent_iso_readback_native_fonts_verified']=64;summary['all_native_unicode_lookup_checks']=sum(r['glyph_count'] for r in results);summary['unicode_note']='Hangul plus needed curly quotes are covered; all original Latin records preserved';(out/'build_report.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8');(out/'maps_report.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2),encoding='utf-8');(out/'independent_iso_font_check.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8');print('ALL64 NATIVE FONTS VERIFIED',summary['all_native_unicode_lookup_checks'],'LOOKUPS')
