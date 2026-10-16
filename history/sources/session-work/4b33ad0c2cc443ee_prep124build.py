import json,collections
from pathlib import Path
j=json.loads(Path('outputs/step124/reference_audit.json').read_text(encoding='utf-8'));c=collections.Counter(r['english'] for r in j['refs'] if r['key_verified']);Path('outputs/step124/counts.json').write_text(json.dumps(c,ensure_ascii=False,indent=2),encoding='utf-8');print(len(c),sum(c.values()))
s=Path('work/build123.py').read_text(encoding='utf-8-sig').replace("src=Path('PROJECT_ROOT/working/step123_font_source.iso')","src=Path('PROJECT_ROOT/BIA_STEP123_SKIRMISH_KO_TEST.iso')").replace('BIA_STEP123_SKIRMISH_KO_TEST.iso\').resolve()',"BIA_STEP124_TEXT_REVIEW_KO_TEST.iso').resolve()").replace("out=Path('outputs/step123')","out=Path('outputs/step124')").replace('assert dst.exists();','assert not dst.exists();').replace('0x6000','0x7000').replace('0x5a000','0x5c000').replace('STEP123','STEP124').replace("assert read(r['old_ptr'],r['old_n'])==en.encode()+b'\\0'","assert read(r['old_ptr'],r['old_n'])==en.encode()+b'\\0'")
# RFont count is dynamic after skirmish font additions; use actual first metadata glyph set.
s=s.replace("for j in range(847)","for j in range(847)")
Path('work/build124.py').write_text(s,encoding='utf-8')
