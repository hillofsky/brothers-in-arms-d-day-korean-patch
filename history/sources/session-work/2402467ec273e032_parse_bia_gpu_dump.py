from pathlib import Path
import sys,json,struct,hashlib,argparse
sys.path.insert(0,str(Path(__file__).resolve().parent/'python_deps'))
import zstandard
ap=argparse.ArgumentParser();ap.add_argument('dump');ap.add_argument('out');a=ap.parse_args()
b=Path(a.dump).read_bytes();assert b[:8]==b'PPSSPPGE';assert struct.unpack_from('<I',b,8)[0]>=5
n,size=struct.unpack_from('<II',b,24);o=32;blocks=[]
for i in range(2):
 c=struct.unpack_from('<I',b,o)[0];o+=4;blocks.append(zstandard.ZstdDecompressor().decompress(b[o:o+c]));o+=c
commands,push=blocks;assert len(commands)==n*9 and len(push)==size
st={};summary=[]
for i in range(n):
 t,sz,ptr=struct.unpack_from('<BII',commands,i*9);data=push[ptr:ptr+sz];assert len(data)==sz
 if t==1:
  for w in struct.unpack('<'+str(sz//4)+'I',data):st[w>>24]=w
 if t==16 and all(k in st for k in [0xA0,0xA8,0xB8]):
  entry={'index':i,'size':sz,'sha1':hashlib.sha1(data).hexdigest(),'state':{f'{k:02X}':f'{st.get(k,0):08X}' for k in [0xA0,0xA8,0xB8,0xC2,0xC3,0xC6,0xC7,0x1E,0x12]}}
  summary.append(entry)
result={'commands':n,'texture_draws':len(summary),'unique_states':list({json.dumps(x['state'],sort_keys=True) for x in summary}),'unique_texture_sizes':sorted({x['size'] for x in summary}),'unique_texture_sha1':sorted({x['sha1'] for x in summary}),'draws':summary}
Path(a.out).write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in result.items() if k!='draws'}))
