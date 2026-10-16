exec(open('work/build_width40o.py',encoding='utf8').read().split('_,boot=b.iso_read_file')[0])
_,boot=b.iso_read_file(source,['PSP_GAME','SYSDIR','BOOT.BIN']);print(boot[CALL+BIAS:CALL+BIAS+4].hex());print(struct.unpack_from('<II',boot,REL));print([(hex(o),tuple(hex(x) for x in struct.unpack_from('<II',boot,o))) for o in range(0x734bc4,0x734c74,8)])
