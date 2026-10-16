#!/usr/bin/env python3
import argparse, hashlib, json, shutil, sys
from pathlib import Path

SECTOR=2048
TARGETS={
    "FM_0115EAGLESJUMP.ST1": ("FM_0115EAGLESJUMP_41E.ST1",
        "22376d64818e019c78a1e26d371a7111e0f06dc9"),
    "SUBTITLEHASHMAP.INI": ("SUBTITLEHASHMAP_41E.INI",
        "e151e11e3fe4f71200fa031c236c62a55bd72542"),
    "SUBTITLETEXTURE.RAW": ("SUBTITLETEXTURE_41E.RAW",
        "dd5969a9ff241ab56481d2c96e107322e9b598b0"),
}

def sha1(b): return hashlib.sha1(b).hexdigest()

class ISO:
    def __init__(self,p):
        self.p=Path(p); self.f=self.p.open("r+b")
        pvd=self.read(16*SECTOR,SECTOR)
        if pvd[0]!=1 or pvd[1:6]!=b"CD001": raise ValueError("Not ISO9660 PVD")
        self.root=self.parse(pvd,156)
    def read(self,o,n):
        self.f.seek(o); b=self.f.read(n)
        if len(b)!=n: raise EOFError((o,n,len(b)))
        return b
    def write(self,o,b):
        self.f.seek(o); self.f.write(b)
    def parse(self,buf,o):
        ln=buf[o]
        if not ln:return None
        r=buf[o:o+ln]; nl=r[32]; rn=r[33:33+nl]
        name="." if rn==b"\0" else (".." if rn==b"\1" else rn.decode("ascii","replace").split(";",1)[0])
        return {"name":name,"extent":int.from_bytes(r[2:6],"little"),
                "size":int.from_bytes(r[10:14],"little"),"dir":bool(r[25]&2)}
    def children(self,n):
        data=self.read(n["extent"]*SECTOR,n["size"]); o=0; out=[]
        while o<len(data):
            ln=data[o]
            if ln==0:
                o=((o//SECTOR)+1)*SECTOR; continue
            r=self.parse(data,o)
            if r and r["name"] not in (".",".."):out.append(r)
            o+=ln
        return out
    def walk(self):
        st=[("",self.root)]
        while st:
            base,n=st.pop()
            for c in self.children(n):
                p=(base+"/"+c["name"]).replace("//","/")
                yield p,c
                if c["dir"]:st.append((p,c))
    def close(self): self.f.close()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--source",required=True)
    ap.add_argument("--output",required=True)
    ap.add_argument("--assets",required=True)
    ap.add_argument("--report",required=True)
    a=ap.parse_args()

    src=Path(a.source); dst=Path(a.output); assets=Path(a.assets)
    if not src.exists(): raise FileNotFoundError(src)
    if dst.exists(): raise FileExistsError(f"Refusing to overwrite {dst}")
    shutil.copyfile(src,dst)

    rep={"stage":"41E","source":str(src),"output":str(dst),"patches":[]}
    iso=ISO(dst)
    try:
        found={}
        for path,node in iso.walk():
            bn=node["name"].upper()
            if bn in TARGETS: found[bn]=(path,node)
        for name,(asset_name,expected) in TARGETS.items():
            if name not in found: raise RuntimeError(f"Missing ISO file {name}")
            path,node=found[name]
            old=iso.read(node["extent"]*SECTOR,node["size"])
            if sha1(old)!=expected:
                raise RuntimeError(f"{name} source SHA1 mismatch: {sha1(old)}")
            new=(assets/asset_name).read_bytes()
            if len(new)!=len(old):
                raise RuntimeError(f"{name} size changed {len(old)} -> {len(new)}")
            iso.write(node["extent"]*SECTOR,new)
            check=iso.read(node["extent"]*SECTOR,len(new))
            if check!=new: raise RuntimeError(f"{name} readback mismatch")
            rep["patches"].append({
                "name":name,"iso_path":path,"lbn":node["extent"],
                "size":len(new),"old_sha1":expected,"new_sha1":sha1(new)
            })
    finally:
        iso.close()

    rep["output_size"]=dst.stat().st_size
    rep["completed"]=True
    Path(a.report).write_text(json.dumps(rep,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(rep,ensure_ascii=False,indent=2))

if __name__=="__main__":
    sys.exit(main())
