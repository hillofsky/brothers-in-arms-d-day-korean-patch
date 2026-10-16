import json,collections
from pathlib import Path
p=json.loads(Path(r'PROJECT_ROOT\bia_stage39b_tools\stage39a_font_plan.json').read_text(encoding='utf-8'));print(collections.Counter(x['renderer_page'] for x in p['layout']));print(p['layout'][-2:])
