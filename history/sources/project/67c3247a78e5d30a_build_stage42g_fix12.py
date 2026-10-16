#!/usr/bin/env python3
import argparse,hashlib,json,shutil,sys
from pathlib import Path
SECTOR=2048
EXPECTED_INI="c9d5ccad298d814f6f52093a0671e7c355e3e310"
EXPECTED_RAW="9ab68dee919c47de559ede488f2c3835e43ca4a8"
def sha1(b):return hashlib.sha1(b).hexdigest()
class ISO:
 def __init__(self,p):
  self.f=Path(p).open("r+b");pvd=self.read(16*SECTOR,SECTOR)
  if pvd[0]!=1 or pvd[1:6]!=b"CD001":raise ValueError("Not ISO9660")
  self.root=self.parse(pvd,156)
 def read(self,o,n):
  self.f.seek(o);b=self.f.read(n)
  if len(b)!=n:raise EOFError((o,n,len(b)))
  return b
 def write(self,o,b):self.f.seek(o);self.f.write(b)
 def parse(self,b,o):
  ln=b[o]
  if not ln:return None
  r=b[o:o+ln];nl=r[32];rn=r[33:33+nl]
  name="." if rn==b"\0" else (".." if rn==b"\1" else rn.decode("ascii","replace").split(";",1)[0])
  return {"name":name,"extent":int.from_bytes(r[2:6],"little"),"size":int.from_bytes(r[10:14],"little"),"dir":bool(r[25]&2)}
 def children(self,n):
  data=self.read(n["extent"]*SECTOR,n["size"]);o=0;out=[]
  while o<len(data):
   ln=data[o]
   if ln==0:o=((o//SECTOR)+1)*SECTOR;continue
   r=self.parse(data,o)
   if r and r["name"] not in (".",".."):out.append(r)
   o+=ln
  return out
 def walk(self):
  st=[("",self.root)]
  while st:
   base,n=st.pop()
   for c in self.children(n):
    p=(base+"/"+c["name"]).replace("//","/");yield p,c
    if c["dir"]:st.append((p,c))
 def close(self):self.f.close()
def main():
 ap=argparse.ArgumentParser()
 ap.add_argument("--source",required=True);ap.add_argument("--output",required=True)
 ap.add_argument("--assets",required=True);ap.add_argument("--report",required=True)
 a=ap.parse_args();src=Path(a.source);dst=Path(a.output);assets=Path(a.assets)
 if dst.exists():raise FileExistsError(dst)
 shutil.copyfile(src,dst);iso=ISO(dst);rep={"stage":"42G_FIX12_BUILD","patches":[]}
 try:
  found={}
  for p,n in iso.walk():
   if n["name"].upper() in ("SUBTITLEHASHMAP.INI","SUBTITLETEXTURE.RAW"):
    found[n["name"].upper()]=(p,n)
  for name,asset,expected in (
      ("SUBTITLEHASHMAP.INI","SUBTITLEHASHMAP_42G_FIX12.INI",EXPECTED_INI),
      ("SUBTITLETEXTURE.RAW","SUBTITLETEXTURE_42G_FIX12_512.RAW",EXPECTED_RAW)):
   p,n=found[name];old=iso.read(n["extent"]*SECTOR,n["size"])
   if sha1(old)!=expected:raise RuntimeError(f"{name} SHA1 mismatch: {sha1(old)}")
   new=(assets/asset).read_bytes()
   if len(new)!=len(old):raise RuntimeError(f"{name} size changed")
   iso.write(n["extent"]*SECTOR,new)
   if iso.read(n["extent"]*SECTOR,len(new))!=new:raise RuntimeError(name+" readback mismatch")
   rep["patches"].append({"name":name,"path":p,"lbn":n["extent"],"size":len(new),"new_sha1":sha1(new)})
 finally:iso.close()
 rep["completed"]=True;rep["output"]=str(dst)
 Path(a.report).write_text(json.dumps(rep,ensure_ascii=False,indent=2),encoding="utf-8")
 print(json.dumps(rep,ensure_ascii=False,indent=2))
if __name__=="__main__":sys.exit(main())
