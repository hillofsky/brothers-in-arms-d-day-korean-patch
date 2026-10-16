from pathlib import Path
import shutil
out=Path('outputs/step098_validation');out.mkdir(exist_ok=True);mem=out/'memstick';src=Path('PROJECT_ROOT/log/STEP_096/20261013_153259_912_25344/isolated_memstick/PSP')
for folder in ['SAVEDATA','SYSTEM']:shutil.copytree(src/folder,mem/'PSP'/folder,dirs_exist_ok=True)
s=Path('work/stage097_live.py').read_text(encoding='utf-8-sig').replace('step097_validation','step098_validation').replace('nav097_command','nav098_command').replace('BIA_STEP097_MISSION2_UFONT_TEST.iso','BIA_STEP098_ALL_CHAPTER_UFONT_TEST.iso').replace('26420','26421');s=s.replace("p=subprocess.Popen([str(b.find_ppsspp_exe()),", "p=subprocess.Popen([str(b.find_ppsspp_exe()),'-i',")
Path('work/stage098_live.py').write_text(s,encoding='utf-8')
