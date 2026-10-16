#!/usr/bin/env python3
import argparse, csv, hashlib, json, re, sys
from pathlib import Path

SECTOR=2048

def sha1(b): return hashlib.sha1(b).hexdigest()

class ISO9660:
    def __init__(self,path):
        self.path=Path(path)
        self.f=self.path.open("rb")
        pvd=self.read_at(16*SECTOR,SECTOR)
        if pvd[0]!=1 or pvd[1:6]!=b"CD001":
            raise ValueError("ISO9660 primary volume descriptor not found")
        self.root=self._parse_record(pvd,156)
    def close(self): self.f.close()
    def read_at(self,off,size):
        self.f.seek(off);b=self.f.read(size)
        if len(b)!=size: raise EOFError((off,size,len(b)))
        return b
    def _parse_record(self,buf,off):
        if off>=len(buf) or not buf[off]: return None
        ln=buf[off];r=buf[off:off+ln]
        nl=r[32];rn=r[33:33+nl]
        if rn==b"\x00": name="."
        elif rn==b"\x01": name=".."
        else: name=rn.decode("ascii","replace").split(";",1)[0]
        return {"name":name,"extent":int.from_bytes(r[2:6],"little"),
                "size":int.from_bytes(r[10:14],"little"),"dir":bool(r[25]&2)}
    def children(self,node):
        data=self.read_at(node["extent"]*SECTOR,node["size"])
        out=[];p=0
        while p<len(data):
            ln=data[p]
            if ln==0:
                p=((p//SECTOR)+1)*SECTOR;continue
            r=self._parse_record(data,p)
            if r and r["name"] not in (".",".."): out.append(r)
            p+=ln
        return out
    def walk(self):
        st=[("",self.root)];seen=set()
        while st:
            base,node=st.pop()
            key=(node["extent"],node["size"])
            if key in seen: continue
            seen.add(key)
            for c in self.children(node):
                path=(base+"/"+c["name"]).replace("//","/")
                yield path,c
                if c["dir"]:st.append((path,c))
    def extract(self,node):
        return self.read_at(node["extent"]*SECTOR,node["size"])

TIME_RE=re.compile(rb'(\d{2}:\d{2}(?::\d{2})?(?:\.\d+)?)\s*-->\s*(\d{2}:\d{2}(?::\d{2})?(?:\.\d+)?)')
COORD_RE=re.compile(rb'(\d{1,4}),(\d{1,4}),')

def decode_latin(b):
    return b.decode("cp1252","replace")

def clean_text_bytes(field):
    # caret is a control terminator; trailing padding spaces before it are not text.
    if not field.endswith(b"^"): return field
    body=field[:-1].rstrip(b" ")
    return body+b"^"

def parse_st1(data):
    """
    Generic ST1 parser:
      - every visible subtitle/title payload is a field terminated by '^'
      - field start is immediately after the last LF before that caret, or byte 0
      - metadata between the previous field and current field carries time/coords
    This matches FM_0115EAGLESJUMP.ST1 and preserves exact fixed field sizes.
    """
    fields=[]
    prev_end=0
    idx=1
    for m in re.finditer(rb'\^',data):
        end=m.end()
        # Start after last LF before caret, but not before the end of the prior field.
        lf=data.rfind(b'\n',prev_end,m.start())
        start=prev_end if lf<0 else lf+1
        # Skip CR if weird line endings leave it at start.
        while start<m.start() and data[start:start+1] in (b'\r',b'\n'):
            start+=1
        raw=data[start:end]
        # Ignore pathological empty carets if any.
        if not raw: 
            prev_end=end
            continue
        clean=clean_text_bytes(raw)
        meta=data[prev_end:start]
        tm=list(TIME_RE.finditer(meta))
        cm=list(COORD_RE.finditer(meta))
        t0=t1=""
        if tm:
            t0=tm[-1].group(1).decode("ascii","replace")
            t1=tm[-1].group(2).decode("ascii","replace")
        x=y=""
        if cm:
            x=cm[-1].group(1).decode("ascii")
            y=cm[-1].group(2).decode("ascii")
        text=decode_latin(clean[:-1]) # omit ^ in TSV text, keep separately as control
        fields.append({
            "index":idx,
            "offset":start,
            "field_bytes":end-start,
            "time_start":t0,
            "time_end":t1,
            "coord_x":x,
            "coord_y":y,
            "text":text,
            "raw_clean_hex":clean.hex(),
        })
        idx+=1
        prev_end=end
    return fields

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--iso",required=True)
    ap.add_argument("--out",required=True)
    a=ap.parse_args()
    iso_path=Path(a.iso);out=Path(a.out)
    out.mkdir(parents=True,exist_ok=True)
    extracted=out/"st1"
    extracted.mkdir(exist_ok=True)

    iso=ISO9660(iso_path)
    rows=[];files=[]
    try:
        for path,node in iso.walk():
            if node["dir"] or not node["name"].upper().endswith(".ST1"):
                continue
            data=iso.extract(node)
            fields=parse_st1(data)
            safe_name=path.strip("/").replace("/","__")
            p=extracted/safe_name
            p.write_bytes(data)
            rec={
                "iso_path":path,
                "name":node["name"],
                "lbn":node["extent"],
                "size":len(data),
                "sha1":sha1(data),
                "field_count":len(fields),
            }
            files.append(rec)
            for f in fields:
                rows.append({
                    "iso_path":path,
                    "file":node["name"],
                    "field_index":f["index"],
                    "offset_hex":f"0x{f['offset']:X}",
                    "field_bytes":f["field_bytes"],
                    "time_start":f["time_start"],
                    "time_end":f["time_end"],
                    "coord_x":f["coord_x"],
                    "coord_y":f["coord_y"],
                    "english":f["text"],
                    "korean":"",
                })
    finally:
        iso.close()

    # Stable order by ISO path then field index.
    rows.sort(key=lambda r:(r["iso_path"].lower(),int(r["field_index"])))
    files.sort(key=lambda r:r["iso_path"].lower())

    tsv=out/"movie_subtitles.tsv"
    cols=["iso_path","file","field_index","offset_hex","field_bytes",
          "time_start","time_end","coord_x","coord_y","english","korean"]
    with tsv.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=cols,delimiter="\t",lineterminator="\n")
        w.writeheader();w.writerows(rows)

    # Also group into a human-readable text file for translation review.
    grouped=[]
    cur=None
    for r in rows:
        if r["iso_path"]!=cur:
            cur=r["iso_path"]
            grouped += ["", "="*90, cur, "="*90]
        timing=(f"{r['time_start']} --> {r['time_end']}" if r["time_start"] else "[TITLE/UNTIMED]")
        grouped.append(f"[{int(r['field_index']):03d}] {timing} bytes={r['field_bytes']} off={r['offset_hex']}")
        grouped.append(r["english"].replace("\\","\\n"))
    (out/"movie_subtitles_readable.txt").write_text("\n".join(grouped).lstrip(),encoding="utf-8")

    report={
        "stage":"42A",
        "source_iso":str(iso_path),
        "source_iso_size":iso_path.stat().st_size,
        "st1_file_count":len(files),
        "subtitle_field_count":len(rows),
        "files":files,
        "completed":True,
    }
    (out/"stage42a_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    (out/"stage42a_summary.txt").write_text(
        "BIA Stage42A - all ST1 movie subtitle sweep\n\n"
        f"Source ISO: {iso_path}\n"
        f"ST1 files: {len(files)}\n"
        f"Fields: {len(rows)}\n\n"
        "Upload this ZIP so the Korean column can be translated and the slot budget analyzed.\n",
        encoding="utf-8"
    )
    print((out/"stage42a_summary.txt").read_text(encoding="utf-8"))
    return 0

if __name__=="__main__":
    try: sys.exit(main())
    except Exception as e:
        print("STAGE42A FAILED:",repr(e),file=sys.stderr)
        raise
