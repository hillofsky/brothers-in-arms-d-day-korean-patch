#!/usr/bin/env python3
import argparse,hashlib,json,math,shutil,sys
from pathlib import Path
SECTOR=2048
EXPECTED_INI="441c1fb76940bc2924333920537ac39ff6e49590"
EXPECTED_ST1="f86716f20e80eb9110c7deb86780fe66a54367ea"
EXPECTED_RAW="d25634c34ecdd27abd16b4706781f6d5e04d3e4d"
def sha1(b):return hashlib.sha1(b).hexdigest()
class ISO:
 def __init__(self,p):
  self.p=Path(p);self.f=self.p.open("r+b")
  self.pvd_off=16*SECTOR
  pvd=self.read(self.pvd_off,SECTOR)
  if pvd[0]!=1 or pvd[1:6]!=b"CD001":raise ValueError("Not ISO9660")
  self.root=self.parse(pvd,156,self.pvd_off+156)
  self.old_volume_sectors=int.from_bytes(pvd[80:84],"little")
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
  return {"name":name,"extent":int.from_bytes(r[2:6],"little"),
          "size":int.from_bytes(r[10:14],"little"),"dir":bool(r[25]&2),"record_abs":ao}
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
 def patch_extent_size(self,n,extent,size):
  o=n["record_abs"]
  self.write(o+2,int(extent).to_bytes(4,"little")+int(extent).to_bytes(4,"big"))
  self.write(o+10,int(size).to_bytes(4,"little")+int(size).to_bytes(4,"big"))
 def patch_volume_sectors(self,sectors):
  self.write(self.pvd_off+80,int(sectors).to_bytes(4,"little")+int(sectors).to_bytes(4,"big"))
 def close(self):self.f.close()

def main():
 ap=argparse.ArgumentParser()
 ap.add_argument("--source",required=True);ap.add_argument("--output",required=True)
 ap.add_argument("--assets",required=True);ap.add_argument("--report",required=True)
 a=ap.parse_args();src=Path(a.source);dst=Path(a.output);assets=Path(a.assets)
 if dst.exists():raise FileExistsError(dst)
 shutil.copyfile(src,dst)
 iso=ISO(dst);rep={"stage":"42G_512_GLOBAL_ATLAS_PROBE","patches":[]}
 try:
  found={}
  for p,n in iso.walk():
   u=n["name"].upper()
   if u in ("SUBTITLEHASHMAP.INI","SUBTITLETEXTURE.RAW","FM_0115EAGLESJUMP.ST1"):
    found[u]=(p,n)
  for req in ("SUBTITLEHASHMAP.INI","SUBTITLETEXTURE.RAW","FM_0115EAGLESJUMP.ST1"):
   if req not in found:raise RuntimeError("Missing "+req)

  # In-place INI.
  p,n=found["SUBTITLEHASHMAP.INI"];old=iso.read(n["extent"]*SECTOR,n["size"])
  if sha1(old)!=EXPECTED_INI:raise RuntimeError("INI SHA1 mismatch "+sha1(old))
  new=(assets/"SUBTITLEHASHMAP_42G.INI").read_bytes()
  if len(new)!=len(old):raise RuntimeError("INI size changed")
  iso.write(n["extent"]*SECTOR,new)
  rep["patches"].append({"name":"SUBTITLEHASHMAP.INI","old_sha1":sha1(old),"new_sha1":sha1(new),"size":len(new)})

  # In-place first ST1.
  p,n=found["FM_0115EAGLESJUMP.ST1"];old=iso.read(n["extent"]*SECTOR,n["size"])
  if sha1(old)!=EXPECTED_ST1:raise RuntimeError("ST1 SHA1 mismatch "+sha1(old))
  new=(assets/"FM_0115EAGLESJUMP_42G.ST1").read_bytes()
  if len(new)!=len(old):raise RuntimeError("ST1 size changed")
  iso.write(n["extent"]*SECTOR,new)
  rep["patches"].append({"name":"FM_0115EAGLESJUMP.ST1","old_sha1":sha1(old),"new_sha1":sha1(new),"size":len(new)})

  # Append expanded 512x512 RAW to a fresh extent.
  p,n=found["SUBTITLETEXTURE.RAW"];old=iso.read(n["extent"]*SECTOR,n["size"])
  if sha1(old)!=EXPECTED_RAW:raise RuntimeError("RAW SHA1 mismatch "+sha1(old))
  new=(assets/"SUBTITLETEXTURE_42G_512.RAW").read_bytes()
  if len(new)!=512*512*4:raise RuntimeError("Unexpected expanded RAW size")
  iso.f.seek(0,2);end=iso.f.tell()
  aligned=((end+SECTOR-1)//SECTOR)*SECTOR
  if aligned>end:iso.f.write(b"\0"*(aligned-end))
  new_extent=aligned//SECTOR
  iso.f.write(new)
  final=iso.f.tell()
  final_aligned=((final+SECTOR-1)//SECTOR)*SECTOR
  if final_aligned>final:iso.f.write(b"\0"*(final_aligned-final))
  new_sectors=final_aligned//SECTOR
  iso.patch_extent_size(n,new_extent,len(new))
  iso.patch_volume_sectors(new_sectors)
  rep["patches"].append({"name":"SUBTITLETEXTURE.RAW","old_lbn":n["extent"],"old_size":len(old),
                         "new_lbn":new_extent,"new_size":len(new),"old_sha1":sha1(old),"new_sha1":sha1(new)})
  rep["old_volume_sectors"]=iso.old_volume_sectors
  rep["new_volume_sectors"]=new_sectors
 finally:iso.close()
 rep["completed"]=True;rep["output"]=str(dst);rep["output_size"]=dst.stat().st_size
 Path(a.report).write_text(json.dumps(rep,ensure_ascii=False,indent=2),encoding="utf-8")
 print(json.dumps(rep,ensure_ascii=False,indent=2))
if __name__=="__main__":sys.exit(main())
