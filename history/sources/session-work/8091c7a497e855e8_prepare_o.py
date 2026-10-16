from pathlib import Path
p=Path('work/build_width40l.py').read_text(encoding='utf-8-sig')
p=p.replace("outputs/stage40l","outputs/stage40o").replace("'s1':17,'s2':18","'s0':16,'s1':17,'s2':18,'a3':7")
p=p.replace("i(35,'t1','s2',0x38);i(35,'t0','s1',0)","i(35,'t1','s1',0x38);i(35,'t0','s0',0)").replace("i(35,'t2','s1',4)","i(35,'t2','s0',4)").replace("i(43,'t1','s2',0x38)","i(43,'t1','s1',0x38)").replace("r(8,'zero','a2','zero')","r(8,'zero','a3','zero')")
p=p.replace('VA=0x4c0480;CALL=0x4fcc0;BIAS=0x80;REL=0x734bec','VA=0x4c0580;CALL=0x4f244;BIAS=0x80;REL=0x734bf4')
p=p.replace('BIA_STAGE40K_CONTROLS_FONT_TEST','BIA_STAGE40M_CONTROLS_COMPLETE_TEST').replace('BIA_STAGE40L_CONTROLS_UTF8_WIDTH_TEST','BIA_STAGE40O_CONTROLS_UTF8_COMPLETE_TEST')
p=p.replace("bytes.fromhex('09f8c000')","bytes.fromhex('09f8e000')").replace('(0x4c03f0,0)','(0x4c0400,0)')
Path('work/build_width40o.py').write_text(p,encoding='utf-8')
