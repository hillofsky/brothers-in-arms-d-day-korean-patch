#!/usr/bin/env python3
from pathlib import Path
import argparse,json,hashlib,importlib.util,shutil,re,collections,csv

ap=argparse.ArgumentParser()
ap.add_argument("--root",required=True)
ap.add_argument("--manifest",required=True)
ap.add_argument("--outdir",required=True)
a=ap.parse_args()

root=Path(a.root);out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)
source=root/"BIA_STAGE43T_TITLE_PROMPT_FIX.iso"
dest=root/"BIA_STAGE69_NONMDI_INT92_TEST.iso"
helper=root/"bia_stage40i_tools"/"bia_stage40i_actual_resource_trace.py"
manifest=json.loads(Path(a.manifest).read_text(encoding="utf-8"))
entries=manifest["entries"]

if not source.exists(): raise RuntimeError(f"Missing source ISO: {source}")
if len({x["resource_id"] for x in entries})!=92: raise RuntimeError("Manifest ID count != 92")
if len(entries)!=99: raise RuntimeError("Manifest occurrence count != 99")
if len({x["file"] for x in entries})!=18: raise RuntimeError("Manifest file count != 18")

sp=importlib.util.spec_from_file_location("biahelper",helper)
mod=importlib.util.module_from_spec(sp);sp.loader.exec_module(mod)
_,b=mod.load_helpers()
parts=["PSP_GAME","USRDIR","SYSTEM"]

def sha256_file(p,chunk=8*1024*1024):
    h=hashlib.sha256()
    with p.open("rb") as f:
        while True:
            x=f.read(chunk)
            if not x:break
            h.update(x)
    return h.hexdigest()

def decode_int(data):
    if data.startswith(b"\xef\xbb\xbf"):
        return data.decode("utf-8-sig"),"utf-8-sig"
    try:
        return data.decode("utf-8"),"utf-8"
    except UnicodeDecodeError:
        return data.decode("cp1252"),"cp1252"

def encode_int(text,enc):
    if enc=="utf-8-sig": return text.encode("utf-8-sig")
    return text.encode(enc)

def split_value(line):
    body=line.rstrip("\r\n")
    if "=" not in body:return None,None,None
    left,right=body.split("=",1)
    ending=line[len(body):]
    return left,right,ending

def line_key(line):
    left,_,_=split_value(line)
    return left.strip() if left is not None else None

byfile=collections.defaultdict(list)
for x in entries:byfile[x["file"]].append(x)

if dest.exists():
    dest.unlink()
shutil.copy2(source,dest)
source_sha=sha256_file(source)

file_reports=[]
occ_reports=[]
for fname,items in sorted(byfile.items()):
    _,blob=b.iso_read_file(dest,parts+[fname])
    before_sha=hashlib.sha256(blob).hexdigest()
    text,enc=decode_int(blob)
    lines=text.splitlines(keepends=True)

    # Build section + key positions from the CURRENT Stage43T file.
    section=""
    positions=collections.defaultdict(list)
    for i,line in enumerate(lines,1):
        s=line.strip()
        if s.startswith("[") and s.endswith("]"):
            section=s[1:-1]
            continue
        k=line_key(line)
        if k is not None:
            positions[(section,k)].append(i)

    changed=0;already=0
    for item in items:
        candidates=positions.get((item["section"],item["key"]),[])
        # Prefer the Stage38 line if it still points to the same key/section.
        preferred=item["line"] if item["line"] in candidates else None
        search=[preferred] if preferred else []
        search += [x for x in candidates if x!=preferred]
        chosen=None;state=None;oldraw=None
        for ln in search:
            left,right,end=split_value(lines[ln-1])
            if right==item["original_raw_value"]:
                chosen=ln;state="ENGLISH";oldraw=right;break
            if right==item["target_raw_value"]:
                chosen=ln;state="ALREADY_KO";oldraw=right;break
        if chosen is None:
            # Last safe fallback: exact raw value on the original Stage38 line,
            # but only if its key is still exact.
            ln=item["line"]
            if 1<=ln<=len(lines):
                left,right,end=split_value(lines[ln-1])
                if left is not None and left.strip()==item["key"] and right in (item["original_raw_value"],item["target_raw_value"]):
                    chosen=ln;state="ENGLISH" if right==item["original_raw_value"] else "ALREADY_KO";oldraw=right
        if chosen is None:
            raise RuntimeError(
                f"Cannot safely locate {item['resource_id']} {fname} "
                f"[{item['section']}] {item['key']} line {item['line']}"
            )

        left,right,end=split_value(lines[chosen-1])
        if state=="ENGLISH":
            lines[chosen-1]=left+"="+item["target_raw_value"]+end
            changed+=1
        else:
            already+=1

        occ_reports.append({
            "resource_id":item["resource_id"],"file":fname,
            "section":item["section"],"key":item["key"],
            "stage38_line":item["line"],"actual_line":chosen,
            "pre_state":state,"classification":item["classification"],
        })

    newtext="".join(lines)
    newblob=encode_int(newtext,enc)

    # Re-parse and verify each exact target raw value.
    verify_text,_=decode_int(newblob)
    vlines=verify_text.splitlines(keepends=True)
    section="";vpos=collections.defaultdict(list)
    for i,line in enumerate(vlines,1):
        s=line.strip()
        if s.startswith("[") and s.endswith("]"):
            section=s[1:-1];continue
        k=line_key(line)
        if k is not None:vpos[(section,k)].append(i)
    for item in items:
        good=False
        for ln in vpos.get((item["section"],item["key"]),[]):
            _,right,_=split_value(vlines[ln-1])
            if right==item["target_raw_value"]:
                good=True;break
        if not good:
            raise RuntimeError(f"Post-patch target missing: {item['resource_id']} {fname} {item['key']}")

    b.append_iso_file_and_repoint(dest,parts+[fname],newblob)
    rb=b.iso_read_file(dest,parts+[fname])[1]
    if rb!=newblob:raise RuntimeError(f"ISO readback mismatch: {fname}")
    file_reports.append({
        "file":fname,"encoding":enc,"occurrences":len(items),
        "changed_from_english":changed,"already_korean":already,
        "before_size":len(blob),"after_size":len(newblob),
        "before_sha256":before_sha,"after_sha256":hashlib.sha256(newblob).hexdigest(),
        "readback_verified":True,
    })

# Movie ST1 lineage must remain byte-identical to Stage43T source.
movie_files=[
"EM_1130_BOOKENDS.ST1","EM_1230_BOOKENDS2.ST1","EM_1300_BOOKENDS4.ST1","EM_1330_BOOKENDS3.ST1",
"EM_CRACKOFDAWN.ST1","EM_PURPLEHEARTLANE.ST1","EM_THEALLAMERICANS.ST1","EM_VICTORYINCARETAN.ST1"
]
movie_report=[]
for fname in movie_files:
    sb=b.iso_read_file(source,parts+[fname])[1]
    db=b.iso_read_file(dest,parts+[fname])[1]
    same=sb==db
    if not same:raise RuntimeError(f"Movie ST1 changed unexpectedly: {fname}")
    movie_report.append({"file":fname,"sha256":hashlib.sha256(db).hexdigest(),"preserved":True})

# Important already-verified Stage43T files: ensure contents survive.
preserve_files=["ON_MEMU.MDI","ON_MEMU.DSL","ON_MEMU.DSX","D0_0130_.MDI"]
preserve=[]
for fname in preserve_files:
    sb=b.iso_read_file(source,parts+[fname])[1]
    db=b.iso_read_file(dest,parts+[fname])[1]
    same=sb==db
    if not same:raise RuntimeError(f"Baseline file changed unexpectedly: {fname}")
    preserve.append({"file":fname,"sha256":hashlib.sha256(db).hexdigest(),"preserved":True})

dest_sha=sha256_file(dest)
report={
    "step":"STEP_069",
    "status":"BUILT_UNVERIFIED",
    "source_iso":str(source),"output_iso":str(dest),
    "source_iso_sha256":source_sha,"output_iso_sha256":dest_sha,
    "target_ids":92,"target_occurrences":99,"target_int_files":18,
    "files_changed":sum(1 for x in file_reports if x["before_sha256"]!=x["after_sha256"]),
    "occurrences_changed_from_english":sum(x["changed_from_english"] for x in file_reports),
    "occurrences_already_korean":sum(x["already_korean"] for x in file_reports),
    "iso_readback_verified_files":len(file_reports),
    "movie_st1_files_preserved":len(movie_report),
    "stage43t_baseline_files_preserved":len(preserve),
    "compiled_mdi_967_applied":False,
    "movie_106_repatched":False,
    "runtime_verified":False,
    "movie_playback_validation_resumed":False,
}
(out/"step069_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")

with (out/"int_file_patch_report.tsv").open("w",encoding="utf-8-sig",newline="") as f:
    fs=["file","encoding","occurrences","changed_from_english","already_korean","before_size","after_size","before_sha256","after_sha256","readback_verified"]
    w=csv.DictWriter(f,fieldnames=fs,delimiter="\t",lineterminator="\n");w.writeheader();w.writerows(file_reports)
with (out/"int_occurrence_patch_report.tsv").open("w",encoding="utf-8-sig",newline="") as f:
    fs=["resource_id","file","section","key","stage38_line","actual_line","pre_state","classification"]
    w=csv.DictWriter(f,fieldnames=fs,delimiter="\t",lineterminator="\n");w.writeheader();w.writerows(occ_reports)
with (out/"movie_st1_preservation.tsv").open("w",encoding="utf-8-sig",newline="") as f:
    w=csv.DictWriter(f,fieldnames=["file","sha256","preserved"],delimiter="\t",lineterminator="\n");w.writeheader();w.writerows(movie_report)

print(json.dumps(report,ensure_ascii=False))
