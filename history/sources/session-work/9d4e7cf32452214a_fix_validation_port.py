from pathlib import Path
p=Path('work/stage40j_validate.py');s=p.read_text(encoding='utf-8');s=s.replace("port=b.wait_for_actual_debugger_port(log,30); ws,host=b.connect_debugger(port);", "time.sleep(2); (out/'debugger_port.txt').write_text(str(port)); ws,host=b.connect_debugger(port);")
p.write_text(s,encoding='utf-8')
p=Path('work/read_validation.py');s=p.read_text(encoding='utf-8');s=s.replace("b.wait_for_actual_debugger_port(Path('outputs/stage40j_validation/ppsspp.log'),5)","int(Path('outputs/stage40j_validation/debugger_port.txt').read_text())");p.write_text(s,encoding='utf-8')
