from pathlib import Path
r=Path(__file__).resolve().parents[1]
run=(r/'run.ps1').read_text(encoding='utf-8-sig')
launch=(r/'LAUNCH.ps1').read_text(encoding='utf-8-sig')
watch=(r/'scripts/passive_owner_watch.py').read_text()
ws=(r/'scripts/ws_readonly.py').read_text()
assert 'Stop-Process -Id ([int]$LaunchPid)' not in run, 'PPSSPP auto-kill remains!'
assert 'capture_owner_init.py' not in run
assert 'passive_owner_watch.py' in run
assert 'passive_owner_watch.py' in watch or 'passive_owner_watch.py' in run
assert 'cpu.breakpoint.add' not in watch
assert 'memory.breakpoint.add' not in watch
assert 'cpu.stepping' not in watch
assert 'cpu.resume' not in watch
assert 'memory.write' not in watch
assert "allowed={'version','game.status','memory.read'}" in ws
assert "fall_bia_STEP_095_FIX1_passive_owner_probe_" in run
assert "fall_bia_STEP_095_FIX1_passive_owner_probe_" in launch
assert 'Compress-Archive' in launch
assert 'TestArchive' in launch
assert 'Stop-Process' not in launch
assert 'PROJECT_STATE_BEFORE_STEP095_FIX1.md' in run
print('PASS: safe APIs, no PPSSPP termination, independent fallback ZIP, state isolation')
