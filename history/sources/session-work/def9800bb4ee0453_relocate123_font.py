from pathlib import Path
p=Path('work/font123.py');s=p.read_text(encoding='utf-8-sig').replace(" layout=[]"," assert not any(st[mi][count*24:(count+len(missing))*24]),(name,'RFont record capacity')\n layout=[]").replace("  for f in inv[name]['fonts']:","  fontnum=0\n  for f in inv[name]['fonts']:")
a=s.index('   for ptr,payload,oldsize in');z=s.index('   assert needed<=',a)
s=s[:a]+'''   lg,lr,lb=[(0x64000,0x69000,0x6b000),(0x6c000,0x71000,0x73000)][fontnum];fontnum+=1
   for off,payload in [(lg,records),(lr,maps),(lb,struct.pack('<1024i',*heads))]:
    assert not any(st[35][off:off+len(payload)]),(name,'new font space',hex(off));mu[35][off:off+len(payload)]=payload
   for off,value in [(0x28,base+35*stride+lg),(0x40,base+35*stride+lr),(0x4c,base+35*stride+lb),(0x2c,len(pairs)),(0x30,len(pairs)),(0x44,len(pairs)),(0x48,len(pairs))]:struct.pack_into('<I',mu[fi],fo+off,value)
'''+s[z:];p.write_text(s,encoding='utf-8')
