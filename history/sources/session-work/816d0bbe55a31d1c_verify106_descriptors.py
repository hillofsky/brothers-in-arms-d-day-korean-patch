exec(open('work/build106_descriptor.py',encoding='utf-8-sig').read().split('assert not dst.exists()')[0])
import zlib;meta=0x08e03020+35*0x78000;clone=meta+0x17200;descriptor=meta+0x17400
report=json.loads((out/'build_report.json').read_text());ids=set()
for row in report['maps']:
 parts=['PSP_GAME','USRDIR','SYSTEM',row['mdi']];_,blob=b.iso_read_file(dst,parts);st={e['index']:bytes(e['decoded']) for e in b.parse_mdi(blob)};d=bytearray(st[35]);cache_id=(zlib.crc32(row['mdi'].encode())<<32)|((clone<<8|0xe0)&0xffffffff);assert cache_id not in ids;ids.add(cache_id);struct.pack_into('<Q',d,0x17408,cache_id);new=b.rebuild_mdi(blob,{35:bytes(d)});b.append_iso_file_and_repoint(dst,parts,new);row['cache_id']=hex(cache_id)
 _,readback=b.iso_read_file(dst,parts);check={e['index']:bytes(e['decoded']) for e in b.parse_mdi(readback)};assert struct.unpack_from('<I',check[35],0x172e0)[0]==descriptor;assert struct.unpack_from('<QII',check[35],0x17408)==(cache_id,clone,1);assert struct.unpack_from('<4I',check[35],0x17248)==(512,512,512,512)
report['distinct_per_map_cache_ids']=len(ids);report['output_sha256']=hashlib.file_digest(dst.open('rb'),'sha256').hexdigest();(out/'build_report.json').write_text(json.dumps(report,indent=2));print('VERIFIED 32 dedicated renderer owners and unique map cache IDs')

