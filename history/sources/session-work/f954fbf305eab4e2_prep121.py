from pathlib import Path
for src,dst in [('work/capture118_font.py','work/capture121_font.py'),('work/capture117_gpu.py','work/capture121_gpu.py')]:
 s=Path(src).read_text(encoding='utf-8-sig').replace('outputs/step118_font','outputs/step121_font').replace('outputs/step117_icon','outputs/step121_font');Path(dst).write_text(s,encoding='utf-8')
