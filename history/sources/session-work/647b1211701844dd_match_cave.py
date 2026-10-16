exec(open('work/match_off.py',encoding='utf-8-sig').read().split('for name,va')[0])
_,orig=b.iso_read_file(Path('PROJECT_ROOT/Brothers in Arms - D-Day (USA) (v1.01).iso'),['PSP_GAME','SYSDIR','BOOT.BIN'])
for va in [0x4c0390,0x4c0350,0x4c0250]:
 needle=orig[va+0x80:va+0x80+16];positions=[];i=off.find(needle)
 while i>=0:positions.append(hex(i-0x80));i=off.find(needle,i+1)
 print(hex(va),positions[:20])
shoff=struct.unpack_from('<I',off,32)[0];shnum=struct.unpack_from('<H',off,48)[0];print('sections')
for j in range(shnum):
 sh=struct.unpack_from('<10I',off,shoff+j*40)
 if sh[1] in [0x700000a0,1]:print(j,[hex(x) for x in sh])

