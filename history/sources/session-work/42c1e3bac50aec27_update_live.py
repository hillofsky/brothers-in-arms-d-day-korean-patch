from pathlib import Path
p=Path('work/stage40j_live.py'); s=p.read_text(encoding='utf-8-sig')
s=s.replace("p=subprocess.Popen(","cfg=out/'capture.ini'; cfg.write_text('[General]\\nWindowX = 100\\nWindowY = 100\\nWindowWidth = 960\\nWindowHeight = 544\\n[Graphics]\\nGraphicsBackend = 0 (OPENGL)\\n',encoding='utf-8')\np=subprocess.Popen(")
s=s.replace("'--windowed',f'--debugger={port}'","'--windowed',f'--appendconfig={cfg}',f'--debugger={port}'")
s=s.replace("  print('STATE',name,flush=True)","  ws.send_json({'event':'cpu.stepping'}); time.sleep(.3)\n  trLOCAL_PATH   r=ws.request('gpu.buffer.screenshot',timeout=10,type='uri'); (out/(name+'.png')).write_bytes(base64.b64decode(r['uri'].split(',',1)[1])); print('SNAP',name,flush=True)\n  except Exception as e: print('SNAP_ERROR',name,str(e),flush=True)\n  finally: ws.send_json({'event':'cpu.resume'}); time.sleep(.2)")
p.write_text(s,encoding='utf-8')
