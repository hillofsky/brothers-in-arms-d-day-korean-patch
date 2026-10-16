import json
from pathlib import Path
p=json.loads(Path('PROJECT_ROOT/bia_stage39a_tools/stage39a_font_plan.json').read_text(encoding='utf-8'))['layout'];a=json.loads(Path('outputs/stage43a/new_font_glyphs.json').read_text(encoding='utf-8'));have={x['char'] for x in p+a};t=json.loads(Path('work/campaign_second_ko.json').read_text(encoding='utf-8'));missing=sorted({c for v in t.values() for c in v if 0xac00<=ord(c)<=0xd7a3}-have);print('Second mission new glyphs',len(missing));Path('work/second_missing_glyphs.json').write_text(json.dumps(missing,ensure_ascii=False),encoding='utf-8')
