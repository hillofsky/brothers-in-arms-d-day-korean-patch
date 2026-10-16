import json,re
from pathlib import Path
j=json.loads(Path('PROJECT_ROOT/stage42g/stage42g_token_dictionary.json').read_text(encoding='utf-8'))
for f in j['all_fields']:
 if re.search(r'\\\s*[^\\:]{1,16}:',f['korean']):print(f['file'],f['field_index'],f['korean'])
