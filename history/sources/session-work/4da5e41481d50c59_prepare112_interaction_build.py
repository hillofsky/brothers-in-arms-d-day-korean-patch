from pathlib import Path
import json,shutil
out=Path('outputs/step112');a=json.loads((out/'interaction_reference_audit.json').read_text(encoding='utf-8'));t=json.loads((out/'interaction_translations.json').read_text(encoding='utf-8'))
for en,ko in list(t.items()):
 if en.startswith('You got the ') and ko.endswith('을 획득했습니다.'):
  obj=ko[:-len('을 획득했습니다.')];ch=obj[-1];particle='을' if '\uac00'<=ch<='\ud7a3' and (ord(ch)-0xac00)%28 else '를';t[en]=obj+particle+' 획득했습니다.'
for r in a['refs']:r['korean']=t[r['english']]
a['targets']=t;(out/'interaction_reference_audit.json').write_text(json.dumps(a,ensure_ascii=False,indent=2),encoding='utf-8');(out/'interaction_translations.json').write_text(json.dumps(t,ensure_ascii=False,indent=2),encoding='utf-8')
snapshot=(out/'interaction_source.iso').resolve();assert not snapshot.exists();shutil.copy2('PROJECT_ROOT/BIA_STEP112_DIALOGUE_AND_INTERACTION_KO_TEST.iso',snapshot)
p=Path('work/build112_dialogues.py').read_text(encoding='utf-8-sig');start=p.index('src=Path(');end=p.index(';dst=',start);p=p[:start]+"src=Path('"+str(snapshot).replace('\\','/')+"')"+p[end:];p=p.replace("out/'reference_audit.json'","out/'interaction_reference_audit.json'").replace('0x46000','0x47000').replace("out/'build_report.json'","out/'interaction_build_report.json'")
p=p.replace("for name,rr in group.items():", "fontmap['ON_MEMU_O.MDI']=[]\nfor name,rr in group.items():")
p=p.replace("needed={ord(c) for r in rr for c in r['korean']}","needed={ord(c) for r in rr for c in r['korean']}\n if name=='ON_MEMU_O.MDI':\n  cps={struct.unpack_from('<H',st[23],j*24)[0] for j in range(847)};assert needed<=cps,('menu RFont missing glyphs',needed-cps)")
p=p.replace("'BIAON.PRX','ON_MEMU_O.MDI','ON_MEMU.DSL'","'BIAON.PRX','ON_MEMU.DSL'");Path('work/build112_interactions.py').write_text(p,encoding='utf-8')
