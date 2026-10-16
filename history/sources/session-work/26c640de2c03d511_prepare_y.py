from pathlib import Path
p=Path('work/build_firstmission40x.py').read_text(encoding='utf-8-sig').replace('outputs/stage40x','outputs/stage40y').replace('BIA_STAGE40X_FIRST_MISSION_UI_TEST','BIA_STAGE40Y_FIRST_MISSION_UI_TEST')
p=p.replace("if keytext in keys and keytext == keytext.upper():filtered.append((ri,ro))", "if keytext in keys:filtered.append((ri,ro))")
p=p.replace('  refs=list(set(filtered))', "  refs=list(set(filtered))\n  if english in keyLOCAL_PATH   safe=[]\n   for ri,ro in refLOCAL_PATH    np,nn,nc=struct.unpack_from('<III',st[ri],ro+12)\n    ni=(np-seq)//stride;no=(np-seq)%stride\n    next_is_fstring=ni in st and 1<=nn<=4096 and nn<=nc<=0x100000 and st[ni][no:no+nn].endswith(b'\\0')\n    if not next_is_fstring:safe.append((ri,ro))\n   refs=safe")
Path('work/build_firstmission40y.py').write_text(p,encoding='utf8')
