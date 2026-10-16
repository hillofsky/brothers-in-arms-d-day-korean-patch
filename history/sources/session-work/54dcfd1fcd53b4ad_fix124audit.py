from pathlib import Path
p=Path('work/audit124.py');s=p.read_text(encoding='utf-8');s='\n'.join(l for l in s.splitlines() if "d[h.start()-1]" not in l)+'\n';p.write_text(s,encoding='utf-8')
