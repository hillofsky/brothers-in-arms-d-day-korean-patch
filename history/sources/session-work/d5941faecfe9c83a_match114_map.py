exec(open('work/compare113_font.py',encoding='utf-8-sig').read().split('_,d=b.iso_read_file')[0])
r=Path('outputs/step114_menu/current_ram.bin').read_bytes()
rows=[]
for item in json.loads(Path('outputs/step098/inventory.json').read_text()):
 _,d=b.iso_read_file(Path('PROJECT_ROOT/BIA_STEP112_DIALOGUE_AND_INTERACTION_KO_TEST.iso'),['PSP_GAME','USRDIR','SYSTEM',item['mdi']]);ss={x['index']:bytes(x['decoded']) for x in b.parse_mdi(d)}
 live=r[0x9df3020-0x8000000:0x9df3020-0x8000000+0x40000];diff=sum(a!=z for a,z in zip(live,ss[34][:0x40000]));rows.append((diff,item['mdi']))
print(sorted(rows)[:8]);Path('outputs/step114_menu/map_match.json').write_text(json.dumps(sorted(rows),indent=2))
