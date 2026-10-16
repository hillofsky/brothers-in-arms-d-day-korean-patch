"""Portable BIA MDI inspection and conservative fixed-byte translation edits."""
import argparse,hashlib,json,os,re,shutil,sys
from pathlib import Path
from dev import bia_formats as fmt
ROOT=Path(__file__).resolve().parents[1]

def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for chunk in iter(lambda:f.read(8*1024*1024),b''):h.update(chunk)
 return h.hexdigest()

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('command',choices=['inspect','extract','build'])
 p.add_argument('--source',type=Path,required=True)
 p.add_argument('--resource',default='D0_0130_.MDI')
 p.add_argument('--output',type=Path)
 p.add_argument('--edits',type=Path,help='JSON list: stream, offset, old, new')
 a=p.parse_args()
 m=json.loads((ROOT/'patch/manifest.json').read_text())
 if sha(a.source)!=m['patched_iso']['sha256']:raise ValueError('Requires exact STEP129 release ISO; candidate chaining not supported')
 if not re.fullmatch(r'[A-Za-z0-9_]+[.]MDI',a.resource):raise ValueError('Invalid MDI filename')
 parts=['PSP_GAME','USRDIR','SYSTEM',a.resource]
 rec,blob=fmt.iso_read_file(a.source,parts)
 streams=fmt.parse_mdi(blob)
 if a.command=='inspect':
  print(json.dumps({'resource':a.resource,'size':len(blob),'sha256':hashlib.sha256(blob).hexdigest(),'streams':[{'index':s['index'],'decoded_bytes':len(s['decoded'])} for s in streams]},indent=2));return
 if not a.output:raise ValueError('--output is required')
 if a.output.exists() or a.output.resolve()==a.source.resolve():raise ValueError('Output must be new and different from source')
 if a.command=='extract':
  a.output.mkdir(parents=True)
  for s in streams:(a.output/('stream%02d.bin'%s['index'])).write_bytes(s['decoded'])
  print('Extracted locally; do not commit extracted streams.');return
 if not a.edits:raise ValueError('--edits is required')
 edits=json.loads(a.edits.read_text(encoding='utf-8-sig'))
 if not isinstance(edits,list) or not edits:raise ValueError('Expected nonempty edit list')
 replacements={};covered=set()
 for e in edits:
  i=e['stream'];off=e['offset'];old=e['old'];new=e['new']
  if not isinstance(i,int) or i<0 or i>=len(streams) or not isinstance(off,int) or off<0:raise ValueError('Invalid stream or offset')
  # Deliberately support only the known appended text stream.
  if i!=35:raise ValueError('Only verified text stream35 is supported')
  ob=old.encode('utf-8');nb=new.encode('utf-8')
  if not ob or len(ob)!=len(nb) or '\0' in old+new:raise ValueError('Require equal nonzero UTF-8 byte counts and no NUL')
  tokens=lambda text: re.findall(r'%[^%]+%|%(?:\d+\$)?[-+0 #]*\d*(?:\.\d+)?[sdifuxXc]|\\|\r|\n',text)
  if tokens(old)!=tokens(new):raise ValueError('Control token sequence changed')
  if set(new)-set(old)-set(chr(c) for c in range(32,127)):raise ValueError('New glyphs require separate native-font validation; this conservative tool only reuses characters in old text')
  dec=streams[i]['decoded']
  if off+len(ob)>=len(dec) or dec[off:off+len(ob)+1]!=ob+b'\0':raise ValueError('Exact old NUL-terminated text assertion failed')
  span={(i,x) for x in range(off,off+len(ob))}
  if covered & span:raise ValueError('Overlapping edits')
  covered.update(span);replacements.setdefault(i,bytearray(dec))[off:off+len(ob)]=nb
 rebuilt=fmt.rebuild_mdi(blob,{i:bytes(d) for i,d in replacements.items()})
 check=fmt.parse_mdi(rebuilt)
 if len(check)!=len(streams):raise ValueError('MDI stream count changed')
 for s,t in zip(streams,check):
  if t['decoded']!=bytes(replacements.get(s['index'],s['decoded'])):raise ValueError('MDI readback mismatch')
 a.output.parent.mkdir(parents=True,exist_ok=True)
 temp=a.output.with_name(a.output.name+'.partial')
 if shutil.disk_usage(a.output.parent).free<a.source.stat().st_size+len(rebuilt)+128*1024*1024:raise ValueError('Insufficient free disk for separate candidate')
 owned=False
 try:
  with temp.open('xb') as out:
   owned=True
   with a.source.open('rb') as src:shutil.copyfileobj(src,out,8*1024*1024)
  fmt.append_iso_file_and_repoint(temp,parts,rebuilt)
  if fmt.iso_read_file(temp,parts)[1]!=rebuilt:raise ValueError('ISO readback mismatch')
  # Validate every original byte except the intended directory entry/volume fields.
  allowed=set(range(rec['record_offset']+2,rec['record_offset']+18))
  with a.source.open('rb') as src,temp.open('rb') as out:
   sector=16
   while True:
    src.seek(sector*2048);vd=src.read(2048)
    if len(vd)!=2048 or vd[1:6]!=b'CD001':break
    if vd[0] in (1,2):allowed.update(range(sector*2048+80,sector*2048+88))
    if vd[0]==255:break
    sector+=1
   src.seek(0);offset=0
   for oldchunk in iter(lambda:src.read(8*1024*1024),b''):
    out.seek(offset);newchunk=out.read(len(oldchunk))
    if oldchunk!=newchunk:
     if any(offset+i not in allowed for i,(x,y) in enumerate(zip(oldchunk,newchunk)) if x!=y):raise ValueError('Unrelated ISO bytes changed')
    offset+=len(oldchunk)
  # Exclusive publication; preserve a pre-existing target even on POSIX.
  os.link(temp,a.output)
  print(json.dumps({'output_sha256':sha(a.output),'static_readback':'PASS','runtime_qa':'PENDING','baseline_preserved':True}))
 finally:
  if owned:temp.unlink(missing_ok=True)

if __name__=='__main__':
 try:main()
 except Exception as e:print('ERROR:',e,file=sys.stderr);sys.exit(1)
