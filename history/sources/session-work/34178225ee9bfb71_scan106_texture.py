exec(open('work/static104.py',encoding='utf-8-sig').read().split('for a,z')[0])
# Scan direct UTexture cached-render-interface accesses.
hits=[]
for i in md.disasm(prx[0x80:0x80+5760768],0x08804000):
 if i.mnemonic in ['lw','sw'] and '0xe0(' in i.op_str and 0x08b00000<i.address<0x08c00000:hits.append((i.address,i.mnemonic,i.op_str))
print(hits[:70])
