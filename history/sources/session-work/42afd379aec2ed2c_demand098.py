import csv,json
from pathlib import Path
rows=list(csv.DictReader(Path('PROJECT_ROOT/log/STEP_079/outputs/compiled967_patch_refs.tsv').open(encoding='utf-8-sig'),delimiter='\t'));print('non-Hangul/non-ASCII',[(hex(cp),chr(cp)) for cp in sorted({ord(ch) for r in rows for ch in r['korean'] if ord(ch)>127 and not 0xac00<=ord(ch)<=0xd7a3})]);print('MDIcounts',len({r['mdi'] for r in rows}))
