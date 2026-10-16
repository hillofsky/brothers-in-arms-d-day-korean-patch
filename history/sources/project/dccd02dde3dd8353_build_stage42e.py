#!/usr/bin/env python3
import argparse,hashlib,json,shutil,sys
from pathlib import Path
SECTOR=2048
EXPECTED_INI="441c1fb76940bc2924333920537ac39ff6e49590"
EXPECTED_ST1="f86716f20e80eb9110c7deb86780fe66a54367ea"
def sha1(b):return hashlib.sha1(b).hexdigest()
class ISO:
 def __init__(self,p):
  self.f=Path(p).open("r+b");pvd=self.read(16*SECTOR,SECTOR)
  if pvd[0]!=1 or pvd[1:6]!=b"CD001":raise ValueError("Not ISO9660")
  self.root=self.parse(pvd,156,16*SECTOR+156)
 def read(self,o,n):
  self.f.seek(o);b=self.f.read(n)
  if len(b)!=n:raise EOFError((o,n,len(b)))
  return b
 def write(self,o,b):self.f.seek(o);self.f.write(b)
 def parse(self,b,o,ao):
  ln=b[o]
  if not ln:return None
  r=b[o:o+ln];nl=r[32];rn=r[33:33+nl]
  name="." if rn==b"\0" else (".." if rn==b"\1" else rn.decode("ascii","replace").split(";",1)[0])
  return {"name":name,"extent":int.from_bytes(r[2:6],"little"),"size":int.from_bytes(r[10:14],"little"),"dir":bool(r[25]&2),"record_abs":ao}
 def children(self,n):
  base=n["extent"]*SECTOR;data=self.read(base,n["size"]);o=0;out=[]
  while o<len(data):
   ln=data[o]
   if ln==0:o=((o//SECTOR)+1)*SECTOR;continue
   r=self.parse(data,o,base+o)
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
 def patch_size(self,n,size):
  self.write(n["record_abs"]+10,int(size).to_bytes(4,"little")+int(size).to_bytes(4,"big"));n["size"]=size
 def close(self):self.f.close()
def main():
 ap=argparse.ArgumentParser()
 ap.add_argument("--source",required=True);ap.add_argument("--output",required=True)
 ap.add_argument("--assets",required=True);ap.add_argument("--report",required=True)
 a=ap.parse_args();src=Path(a.source);dst=Path(a.output);assets=Path(a.assets)
 if dst.exists():raise FileExistsError(dst)
 shutil.copyfile(src,dst);iso=ISO(dst);rep={"stage":"42E_UTF8_HASHMAP_PROBE","patches":[]}
 try:
  found={}
  for p,n in iso.walk():
   if n["name"].upper() in ("SUBTITLEHASHMAP.INI","FM_0115EAGLESJUMP.ST1"):found[n["name"].upper()]=(p,n)
  # INI grows slightly; patch directory size, still far inside the 16-sector gap before texture.
  p,n=found["SUBTITLEHASHMAP.INI"];old=iso.read(n["extent"]*SECTOR,n["size"])
  if sha1(old)!=EXPECTED_INI:raise RuntimeError("INI SHA1 mismatch "+sha1(old))
  new=(assets/"SUBTITLEHASHMAP_42E_UTF8.INI").read_bytes()
  if len(new)>16*SECTOR:raise RuntimeError("INI too large")
  iso.write(n["extent"]*SECTOR,new);iso.patch_size(n,len(new))
  rep["patches"].append({"name":"SUBTITLEHASHMAP.INI","old_size":len(old),"new_size":len(new),"new_sha1":sha1(new)})
  p,n=found["FM_0115EAGLESJUMP.ST1"];old=iso.read(n["extent"]*SECTOR,n["size"])
  if sha1(old)!=EXPECTED_ST1:raise RuntimeError("ST1 SHA1 mismatch "+sha1(old))
  new=(assets/"FM_0115EAGLESJUMP_42E_UTF8.ST1").read_bytes()
  if len(new)!=len(old):raise RuntimeError("ST1 size changed")
  iso.write(n["extent"]*SECTOR,new)
  rep["patches"].append({"name":"FM_0115EAGLESJUMP.ST1","size":len(new),"new_sha1":sha1(new)})
 finally:iso.close()
 rep["completed"]=True;rep["output"]=str(dst)
 Path(a.report).write_text(json.dumps(rep,ensure_ascii=False,indent=2),encoding="utf-8")
 print(json.dumps(rep,ensure_ascii=False,indent=2))
if __name__=="__main__":sys.exit(main())
