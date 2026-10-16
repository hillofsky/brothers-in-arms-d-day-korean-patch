from pathlib import Path
import shutil
out=Path('outputs/step097_validation');out.mkdir(exist_ok=True);mem=out/'memstick';src=Path('PROJECT_ROOT/log/STEP_096/20261013_153259_912_25344/isolated_memstick/PSP')
for folder in ['SAVEDATA','SYSTEM']:shutil.copytree(src/folder,mem/'PSP'/folder,dirs_exist_ok=True)
s=Path('work/stage43t_live.py').read_text(encoding='utf-8-sig').replace('stage43t_validation','step097_validation').replace('nav43t_command','nav097_command').replace('BIA_STAGE43T_TITLE_PROMPT_FIX.iso','BIA_STEP097_MISSION2_UFONT_TEST.iso').replace('port=b.choose_free_port()','port=26420')
s=s.replace("p=subprocess.Popen([str(b.find_ppsspp_exe()),", "p=subprocess.Popen([str(b.find_ppsspp_exe()),'--memstick='+str(out/'memstick'),")
s=s.replace("SoftwareRenderer = True\\n", "SoftwareRenderer = True\\n[General]\\nRemoteISOPort = 26420\\nRemoteDebuggerOnStartup = True\\nRemoteDebuggerLocal = True\\n")
Path('work/stage097_live.py').write_text(s,encoding='utf-8')
