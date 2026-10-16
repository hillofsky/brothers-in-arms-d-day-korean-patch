#!/usr/bin/env python3
import argparse, hashlib, json, shutil, sys
from pathlib import Path

SECTOR=2048
EXPECTED={
 "SUBTITLEHASHMAP.INI":"441c1fb76940bc2924333920537ac39ff6e49590",
 "SUBTITLETEXTURE.RAW":"d25634c34ecdd27abd16b4706781f6d5e04d3e4d",
 "EM_1230_BOOKENDS2.ST1":"6d30acd73ce6c206b06af938ed86dead891ba4da",
}
ASSETS={
 "SUBTITLEHASHMAP.INI":"SUBTITLEHASHMAP_42D.INI",
 "SUBTITLETEXTURE.RAW":"SUBTITLETEXTURE_42D.RAW",
 "EM_1230_BOOKENDS2.ST1":"EM_1230_BOOKENDS2_42D.ST1",
}

def sha1(b): return hashlib.sha1(b).hexdigest()

class ISO:
    def __init__(self,p):
        self.p=Path(p); self.f=self.p.open("r+b")
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
        st=[("",self.root)]
        while st:
            base,n=st.pop()
            for c in self.children(n):
                p=(base+"/"+c["name"]).replace("//","/")
                yield p,c
                if c["dir"]: st.append((p,c))
    def patch_record_extent_size(self,node,extent,size):
        o=node["record_abs"]
        self.write(o+2,int(extent).to_bytes(4,"little")+int(extent).to_bytes(4,"big"))
        self.write(o+10,int(size).to_bytes(4,"little")+int(size).to_bytes(4,"big"))
        node["extent"]=extent; node["size"]=size
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
    if dst.exists(): raise FileExistsError(f"Refusing overwrite: {dst}")
    shutil.copyfile(src,dst)

    iso=ISO(dst)
    rep={"stage":"42D_BOOKENDS2_KO_PROOF","source":str(src),"output":str(dst),
         "patches":[],"aliases":[]}
    try:
        found={}
        for path,node in iso.walk():
            found[node["name"].upper()] = (path,node)

        # Patch the real BOOKENDS2 ST1 plus global subtitle map/atlas.
        for name,asset in ASSETS.items():
            if name not in found: raise RuntimeError("Missing "+name)
            path,node=found[name]
            old=iso.read(node["extent"]*SECTOR,node["size"])
            exp=EXPECTED[name]
            if sha1(old)!=exp:
                raise RuntimeError(f"{name} SHA1 mismatch {sha1(old)} expected {exp}")
            new=(assets/asset).read_bytes()
            if len(new)!=len(old):
                raise RuntimeError(f"{name} size changed {len(old)}->{len(new)}")
            iso.write(node["extent"]*SECTOR,new)
            if iso.read(node["extent"]*SECTOR,len(new))!=new:
                raise RuntimeError(name+" readback mismatch")
            rep["patches"].append({
                "name":name,"path":path,"lbn":node["extent"],"size":len(new),
                "old_sha1":exp,"new_sha1":sha1(new)
            })

        # Temporarily alias the first movie family to BOOKENDS2 for automatic proof.
        pairs=[("FM_0115EAGLESJUMP.BIK","EM_1230_BOOKENDS2.BIK")]
        for ext in ("ST1","ST2","ST3","ST4","ST5","TI1","TI2","TI3","TI4","TI5"):
            pairs.append((f"FM_0115EAGLESJUMP.{ext}",f"EM_1230_BOOKENDS2.{ext}"))

        for target,source in pairs:
            if target not in found or source not in found:
                raise RuntimeError(f"Alias file missing: {target} <- {source}")
            tpath,tnode=found[target]
            spath,snode=found[source]
            old_extent,old_size=tnode["extent"],tnode["size"]
            iso.patch_record_extent_size(tnode,snode["extent"],snode["size"])
            rep["aliases"].append({
                "target":target,"source":source,
                "target_path":tpath,"source_path":spath,
                "old_extent":old_extent,"old_size":old_size,
                "new_extent":snode["extent"],"new_size":snode["size"],
            })
    finally:
        iso.close()

    rep["completed"]=True
    rep["output_size"]=dst.stat().st_size
    Path(a.report).write_text(json.dumps(rep,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(rep,ensure_ascii=False,indent=2))

if __name__=="__main__":
    sys.exit(main())
