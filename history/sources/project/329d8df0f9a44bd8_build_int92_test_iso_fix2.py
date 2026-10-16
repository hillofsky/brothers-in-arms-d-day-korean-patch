#!/usr/bin/env python3
from pathlib import Path
import argparse,json,hashlib,importlib.util,shutil,collections,csv

ap=argparse.ArgumentParser()
ap.add_argument("--root",required=True)
ap.add_argument("--manifest",required=True)
ap.add_argument("--movie-lineage",required=True)
ap.add_argument("--outdir",required=True)
a=ap.parse_args()

root=Path(a.root);out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)
source=root/"BIA_STAGE43T_TITLE_PROMPT_FIX.iso"
dest=root/"BIA_STAGE69_FIX2_NONMDI_INT92_TEST.iso"
helper=root/"bia_stage40i_tools"/"bia_stage40i_actual_resource_trace.py"

manifest=json.loads(Path(a.manifest).read_text(encoding="utf-8"))
entries=manifest["entries"]
if len({x["resource_id"] for x in entries})!=92:raise RuntimeError("Manifest ID count != 92")
if len(entries)!=99:raise RuntimeError("Manifest occurrence count != 99")
if len({x["file"] for x in entries})!=18:raise RuntimeError("Manifest file count != 18")

with Path(a.movie_lineage).open("r",encoding="utf-8-sig",newline="") as f:
    movie_rows=list(csv.DictReader(f,delimiter="\t"))
movie_files=[r["file"] for r in movie_rows]
if len(movie_files)!=8:raise RuntimeError(f"Expected 8 verified movie files, got {len(movie_files)}")

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
        return data.decode("ascii"),"ascii"

def encode_int(text,enc):
    if enc=="utf-8-sig":return text.encode("utf-8-sig")
    return text.encode("utf-8")

def split_value(line):
    body=line.rstrip("\r\n")
    if "=" not in body:return None,None,None
    left,right=body.split("=",1)
    ending=line[len(body):]
    return left,right,ending

def line_key(line):
    left,_,_=split_value(line)
    return left.strip() if left is not None else None

def build_positions(lines):
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
    return positions

def write_reports(file_reports,occ_reports):
    with (out/"int_file_patch_report.tsv").open("w",encoding="utf-8-sig",newline="") as f:
        fs=["file","input_encoding","output_encoding","occurrences","changed","already_target_korean",
            "drifted_current_values","before_size","after_size","before_sha256","after_sha256","readback_verified"]
        w=csv.DictWriter(f,fieldnames=fs,delimiter="\t",lineterminator="\n")
        w.writeheader();w.writerows(file_reports)
    with (out/"int_occurrence_patch_report.tsv").open("w",encoding="utf-8-sig",newline="") as f:
        fs=["resource_id","classification","file","section","key","stage38_line","actual_line",
            "choice_reason","pre_state","current_raw_before","stage38_original_raw","target_raw"]
        w=csv.DictWriter(f,fieldnames=fs,delimiter="\t",lineterminator="\n")
        w.writeheader();w.writerows(occ_reports)
    with (out/"drifted_stage43t_values.tsv").open("w",encoding="utf-8-sig",newline="") as f:
        fs=["resource_id","classification","file","section","key","stage38_line","actual_line",
            "choice_reason","pre_state","current_raw_before","stage38_original_raw","target_raw"]
        w=csv.DictWriter(f,fieldnames=fs,delimiter="\t",lineterminator="\n")
        w.writeheader()
        w.writerows([x for x in occ_reports if x["pre_state"]=="CURRENT_VALUE_DRIFTED_FROM_STAGE38"])

if not source.exists():raise RuntimeError(f"Missing source ISO: {source}")
source_sha_before=sha256_file(source)
if dest.exists():dest.unlink()
shutil.copy2(source,dest)

byfile=collections.defaultdict(list)
for x in entries:byfile[x["file"]].append(x)

file_reports=[]
occ_reports=[]

# ------------------------------------------------------------------
# Patch all 18 INT files. This exact logic already reached completion
# in STEP_069 FIX1 before its later preservation-name failure.
# ------------------------------------------------------------------
for fname,items in sorted(byfile.items()):
    _,blob=b.iso_read_file(dest,parts+[fname])
    before_sha=hashlib.sha256(blob).hexdigest()
    text,enc=decode_int(blob)
    lines=text.splitlines(keepends=True)
    positions=build_positions(lines)

    changed=already=drifted=0
    for item in items:
        candidates=positions.get((item["section"],item["key"]),[])
        if not candidates:
            raise RuntimeError(
                f"Missing section/key for {item['resource_id']}: "
                f"{fname} [{item['section']}] {item['key']}"
            )

        chosen=None
        reason=""
        if len(candidates)==1:
            chosen=candidates[0]
            reason="UNIQUE_SECTION_KEY"
        else:
            exact=[]
            for ln in candidates:
                _,right,_=split_value(lines[ln-1])
                if right in (item["original_raw_value"],item["target_raw_value"]):
                    exact.append(ln)
            if len(exact)==1:
                chosen=exact[0];reason="DUPLICATE_KEY_EXACT_VALUE"
            elif item["line"] in candidates:
                chosen=item["line"];reason="DUPLICATE_KEY_STAGE38_LINE"
            else:
                raise RuntimeError(
                    f"Ambiguous duplicate key for {item['resource_id']}: "
                    f"{fname} [{item['section']}] {item['key']} candidates={candidates}"
                )

        left,right,end=split_value(lines[chosen-1])
        current_raw=right
        if right==item["target_raw_value"]:
            state="ALREADY_TARGET_KO";already+=1
        elif right==item["original_raw_value"]:
            state="STAGE38_ORIGINAL_ENGLISH"
            lines[chosen-1]=left+"="+item["target_raw_value"]+end
            changed+=1
        else:
            state="CURRENT_VALUE_DRIFTED_FROM_STAGE38"
            lines[chosen-1]=left+"="+item["target_raw_value"]+end
            changed+=1;drifted+=1

        occ_reports.append({
            "resource_id":item["resource_id"],"classification":item["classification"],
            "file":fname,"section":item["section"],"key":item["key"],
            "stage38_line":item["line"],"actual_line":chosen,"choice_reason":reason,
            "pre_state":state,"current_raw_before":current_raw,
            "stage38_original_raw":item["original_raw_value"],
            "target_raw":item["target_raw_value"],
        })

    newblob=encode_int("".join(lines),enc)

    # Verify target values before writing ISO.
    vtext,_=decode_int(newblob);vlines=vtext.splitlines(keepends=True);vpos=build_positions(vlines)
    for item in items:
        vals=[]
        for ln in vpos.get((item["section"],item["key"]),[]):
            _,right,_=split_value(vlines[ln-1]);vals.append(right)
        if item["target_raw_value"] not in vals:
            raise RuntimeError(f"Post-patch target missing: {item['resource_id']} {fname} {item['key']}")

    b.append_iso_file_and_repoint(dest,parts+[fname],newblob)
    rb=b.iso_read_file(dest,parts+[fname])[1]
    if rb!=newblob:raise RuntimeError(f"ISO readback mismatch: {fname}")

    file_reports.append({
        "file":fname,"input_encoding":enc,
        "output_encoding":"utf-8-sig" if enc=="utf-8-sig" else "utf-8",
        "occurrences":len(items),"changed":changed,"already_target_korean":already,
        "drifted_current_values":drifted,
        "before_size":len(blob),"after_size":len(newblob),
        "before_sha256":before_sha,"after_sha256":hashlib.sha256(newblob).hexdigest(),
        "readback_verified":True,
    })

# IMPORTANT: persist patch evidence before any later safety checks.
write_reports(file_reports,occ_reports)
(out/"INT_PATCH_LOOP_COMPLETE.txt").write_text(
    f"18 INT files patched/read back successfully.\n"
    f"92 IDs / 99 occurrences processed.\n"
    f"changed={sum(x['changed'] for x in file_reports)}\n"
    f"already_target={sum(x['already_target_korean'] for x in file_reports)}\n"
    f"drifted={sum(x['drifted_current_values'] for x in file_reports)}\n",
    encoding="utf-8"
)

# Source ISO must remain untouched.
source_sha_after=sha256_file(source)
if source_sha_after!=source_sha_before:
    raise RuntimeError("Source Stage43T ISO changed unexpectedly")

# ------------------------------------------------------------------
# Correct movie preservation check: names are loaded from the VERIFIED
# STEP_068 FIX1 lineage rather than hard-coded guesses.
# ------------------------------------------------------------------
movie_report=[]
lineage_by={r["file"]:r for r in movie_rows}
for fname in movie_files:
    sb=b.iso_read_file(source,parts+[fname])[1]
    db=b.iso_read_file(dest,parts+[fname])[1]
    if sb!=db:raise RuntimeError(f"Movie ST1 changed unexpectedly: {fname}")
    got=hashlib.sha256(db).hexdigest()
    expected=lineage_by[fname].get("stage43t_sha256","")
    if expected and got!=expected:
        raise RuntimeError(f"Movie ST1 hash differs from STEP068 lineage: {fname}")
    movie_report.append({"file":fname,"sha256":got,"expected_stage43t_sha256":expected,"preserved":True})

with (out/"movie_st1_preservation.tsv").open("w",encoding="utf-8-sig",newline="") as f:
    fs=["file","sha256","expected_stage43t_sha256","preserved"]
    w=csv.DictWriter(f,fieldnames=fs,delimiter="\t",lineterminator="\n")
    w.writeheader();w.writerows(movie_report)

# ------------------------------------------------------------------
# Correct baseline filename: ON_MEMU_O.MDI (not ON_MEMU.MDI).
# ------------------------------------------------------------------
preserve_files=[
    "ON_MEMU_O.MDI","ON_MEMU.DSL","ON_MEMU.DSX",
    "D0_0130_.MDI","D0_0130_.DSL","D0_0130_.DSX",
]
preserve=[]
for fname in preserve_files:
    sb=b.iso_read_file(source,parts+[fname])[1]
    db=b.iso_read_file(dest,parts+[fname])[1]
    if sb!=db:raise RuntimeError(f"Baseline file changed unexpectedly: {fname}")
    preserve.append({"file":fname,"sha256":hashlib.sha256(db).hexdigest(),"preserved":True})

with (out/"baseline_preservation.tsv").open("w",encoding="utf-8-sig",newline="") as f:
    w=csv.DictWriter(f,fieldnames=["file","sha256","preserved"],delimiter="\t",lineterminator="\n")
    w.writeheader();w.writerows(preserve)

dest_sha=sha256_file(dest)
report={
    "step":"STEP_069_FIX2",
    "status":"BUILT_UNVERIFIED",
    "failure_fixed":[
        "STEP069_FIX1 used guessed movie ST1 filenames; actual verified STEP068 lineage filenames are now used.",
        "STEP069_FIX1 preservation list used ON_MEMU.MDI; actual Stage43T file is ON_MEMU_O.MDI."
    ],
    "source_iso":str(source),"output_iso":str(dest),
    "source_iso_sha256_before":source_sha_before,
    "source_iso_sha256_after":source_sha_after,
    "output_iso_sha256":dest_sha,
    "target_ids":92,"target_occurrences":99,"target_int_files":18,
    "occurrences_changed":sum(x["changed"] for x in file_reports),
    "occurrences_already_target_korean":sum(x["already_target_korean"] for x in file_reports),
    "occurrences_drifted_from_stage38":sum(x["drifted_current_values"] for x in file_reports),
    "files_changed":sum(1 for x in file_reports if x["before_sha256"]!=x["after_sha256"]),
    "iso_readback_verified_files":len(file_reports),
    "movie_st1_files_preserved":len(movie_report),
    "stage43t_baseline_files_preserved":len(preserve),
    "source_iso_preserved":True,
    "compiled_mdi_967_applied":False,
    "movie_106_repatched":False,
    "runtime_verified":False,
    "movie_playback_validation_resumed":False,
}
(out/"step069_fix2_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(report,ensure_ascii=False))
