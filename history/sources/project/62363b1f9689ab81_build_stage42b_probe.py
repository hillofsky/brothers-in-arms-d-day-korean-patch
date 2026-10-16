#!/usr/bin/env python3
import argparse, hashlib, json, shutil, sys
from pathlib import Path
SECTOR=2048
EXPECTED="373904d416b40b19190a86b7fc28194a28de9c10"
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
                "size":int.from_bytes(r[10:14],"little"),
                "dir":bool(r[25]&2),"record_abs":abs_off}
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
    def patch_size(self,node,size):
        self.write(node["record_abs"]+10,int(size).to_bytes(4,"little")+int(size).to_bytes(4,"big"))
    def close(self): self.f.close()
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--source",required=True); ap.add_argument("--output",required=True)
    ap.add_argument("--ini",required=True); ap.add_argument("--report",required=True)
    a=ap.parse_args()
    src=Path(a.source); dst=Path(a.output); new=Path(a.ini).read_bytes()
    if dst.exists(): raise FileExistsError(dst)
    shutil.copyfile(src,dst)
    iso=ISO(dst); rep={"stage":"42B_HASHMAP_223_PROBE","source":str(src),"output":str(dst)}
    try:
        hit=None
        for path,node in iso.walk():
            if node["name"].upper()=="SUBTITLEHASHMAP.INI":
                hit=(path,node); break
        if not hit: raise RuntimeError("SUBTITLEHASHMAP.INI not found")
        path,node=hit
        old=iso.read(node["extent"]*SECTOR,node["size"])
        if sha1(old)!=EXPECTED: raise RuntimeError("Stage41F hashmap SHA1 mismatch: "+sha1(old))
        if len(new)>16*SECTOR: raise RuntimeError("expanded INI exceeds gap before texture")
        iso.write(node["extent"]*SECTOR,new)
        iso.patch_size(node,len(new))
        if iso.read(node["extent"]*SECTOR,len(new))!=new: raise RuntimeError("readback mismatch")
        rep.update({"iso_path":path,"lbn":node["extent"],"old_size":len(old),"new_size":len(new),
                    "old_sha1":sha1(old),"new_sha1":sha1(new),"unique_map_entries":223,"usable_content_keys":222,
                    "completed":True})
    finally:
        iso.close()
    Path(a.report).write_text(json.dumps(rep,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(rep,ensure_ascii=False,indent=2))
if __name__=="__main__": sys.exit(main())
