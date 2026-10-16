from pathlib import Path
p=Path('work/build_firstmission40s.py').read_text(encoding='utf-8-sig').replace('outputs/stage40s','outputs/stage40u').replace('BIA_STAGE40S_FIRST_MISSION_KOREAN_TEST','BIA_STAGE40U_FIRST_MISSION_KOREAN_TEST')
p=p.replace('atlasbase=seq+33*stride;metabase=seq+34*stride;textbase=seq+35*stride','atlasbase=seq+34*stride;metabase=seq+35*stride;textbase=metabase+0xb000')
p=p.replace('mu[34][:len(meta)]=meta','mu[35][:len(meta)]=meta').replace('mu[33][:len(atlas)]=atlas','mu[34][:len(atlas)]=atlas').replace('mu[35][cursor:cursor+len(payload)]=payload','mu[35][0xb000+cursor:0xb000+cursor+len(payload)]=payload')
Path('work/build_firstmission40u.py').write_text(p,encoding='utf8')
