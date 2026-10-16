exec(open('work/match_off.py',encoding='utf-8-sig').read().split('for name,va')[0])
_,blob=b.iso_read_file(iso,['PSP_GAME','USRDIR','SYSTEM','D0_0130_.MDI']);sts={x['index']:bytes(x['decoded']) for x in b.parse_mdi(blob)}
print([(i,len(d),hex(len(d.rstrip(b'\0')))) for i,d in sts.items() if i>=29]);print('st0',sts[0][0x9bc:0xa20].hex())
