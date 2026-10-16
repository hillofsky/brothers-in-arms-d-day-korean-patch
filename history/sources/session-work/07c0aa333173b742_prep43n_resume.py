from pathlib import Path
s=Path('work/nav43n_auto.py').read_text().replace("'start'+str(i)","'rstart'+str(i)").replace("'cross'+str(i)","'rcross'+str(i)").replace("'load'+str(i)","'rload'+str(i)").replace("'hint_fit_verified'","'mission_ready'");Path('work/nav43n_resume_auto.py').write_text(s)
