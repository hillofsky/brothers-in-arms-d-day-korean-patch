from pathlib import Path
p=Path('work/font123.py');s=p.read_text(encoding='utf-8-sig').replace('assert not dst.exists();shutil.copy2(src,dst)','assert dst.exists()').replace('assert not any(st[ii][oo+oldsize:oo+len(payload)]);','assert not any(st[ii][oo+oldsize:oo+len(payload)]),(name,hex(ptr),oldsize,len(payload),st[ii][oo+oldsize:oo+len(payload)].hex());');p.write_text(s,encoding='utf-8')
