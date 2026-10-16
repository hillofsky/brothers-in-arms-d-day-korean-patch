#!/usr/bin/env python3
import argparse, hashlib, json, shutil, sys
from pathlib import Path
SECTOR=2048
EXPECTED_INI="fad63cc62590b1ad96ef11b941d0a6ed6bf900d4"
EXPECTED_ST1="b449f7b3afb0bfd41286462f136fa0bf49abcfdb"

def sha1(b): return hashlib.sha1(b).hexdigest()

class ISO:
    def __init__(self,p):
        self.f=Path(p).open("r+b")
        pvd=self.read(16*SECTOR,SECTOR)
        if pvd[0]!=1 or pvd[1:6]!=b"CD001": raise ValueError("Not ISO9660")
        self.root=self.parse(pvd,156,16*SECTOR+156)
    def read(self,o,n):
        self.f.seek(o); b=self.f.read(n)
        if len(b)!=n: raise EOFError((o,n,len(b)))
        return b
    def write(self,o,b): self.f.seek(o); self.f.write(b)
    def parse(self,buf,o,abs_off):
        ln=buf[o]
        if not ln:return None
        r=buf[o:o+ln]; nl=r[32]; rn=r[33:33+nl]
        name="." if rn==b"\0" else (".." if rn==b"\1" else rn.decode("ascii","replace").split(";",1)[0])
        return {"name":name,"extent":int.from_bytes(r[2:6],"little"),
                "size":int.from_bytes(r[10:14],"little"),"dir":bool(r[25]&2),
                "record_abs":abs_off}
    def children(self,n):
        base=n["extent"]*SECTOR; data=self.read(base,n["size"]); out=[]; o=0
        while o<len(data):
            ln=data[o]
            if ln==0:
                o=((o//SECTOR)+1)*SECTOR; continue
            r=self.parse(data,o,base+o)
            if r and r["name"] not in (".",".."): out.append(r)
            o+=ln
        return out
    def walk(self):
        stack=[("",self.root)]
        while stack:
            base,n=stack.pop()
            for c in self.children(n):
                p=(base+"/"+c["name"]).replace("//","/")
                yield p,c
                if c["dir"]: stack.append((p,c))
    def close(self): self.f.close()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--source",required=True);ap.add_argument("--output",required=True)
    ap.add_argument("--assets",required=True);ap.add_argument("--report",required=True)
    a=ap.parse_args()
    src=Path(a.source);dst=Path(a.output);assets=Path(a.assets)
    if dst.exists(): raise FileExistsError(dst)
    shutil.copyfile(src,dst)
    iso=ISO(dst); rep={"stage":"42C_HIGHBYTE_PROBE","source":str(src),"output":str(dst),"patches":[]}
    try:
        found={}
        for path,node in iso.walk():
            n=node["name"].upper()
            if n in ("SUBTITLEHASHMAP.INI","FM_0115EAGLESJUMP.ST1"):
                found[n]=(path,node)
        specs={
          "SUBTITLEHASHMAP.INI":("SUBTITLEHASHMAP_42C.INI",EXPECTED_INI),
          "FM_0115EAGLESJUMP.ST1":("FM_0115EAGLESJUMP_42C.ST1",EXPECTED_ST1),
        }
        for name,(asset,expected) in specs.items():
            if name not in found: raise RuntimeError("Missing "+name)
            path,node=found[name]
            old=iso.read(node["extent"]*SECTOR,node["size"])
            if sha1(old)!=expected: raise RuntimeError(f"{name} SHA1 mismatch: {sha1(old)}")
            new=(assets/asset).read_bytes()
            if len(new)!=len(old): raise RuntimeError(f"{name} size changed {len(old)}->{len(new)}")
            iso.write(node["extent"]*SECTOR,new)
            check=iso.read(node["extent"]*SECTOR,len(new))
            if check!=new: raise RuntimeError(name+" readback mismatch")
            rep["patches"].append({"name":name,"path":path,"lbn":node["extent"],
                                   "size":len(new),"old_sha1":expected,"new_sha1":sha1(new)})
    finally:
        iso.close()
    rep["completed"]=True
    Path(a.report).write_text(json.dumps(rep,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(rep,ensure_ascii=False,indent=2))
if __name__=="__main__": sys.exit(main())
