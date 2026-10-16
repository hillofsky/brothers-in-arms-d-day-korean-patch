#!/usr/bin/env python3
from pathlib import Path
import argparse,json,hashlib,importlib.util,shutil,collections,csv

ap=argparse.ArgumentParser()
ap.add_argument("--root",required=True)
ap.add_argument("--manifest",required=True)
ap.add_argument("--outdir",required=True)
a=ap.parse_args()

root=Path(a.root);out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)
source=root/"BIA_STAGE43T_TITLE_PROMPT_FIX.iso"
dest=root/"BIA_STAGE69_FIX1_NONMDI_INT92_TEST.iso"
helper=root/"bia_stage40i_tools"/"bia_stage40i_actual_resource_trace.py"
manifest=json.loads(Path(a.manifest).read_text(encoding="utf-8"))
entries=manifest["entries"]

if not source.exists():raise RuntimeError(f"Missing source ISO: {source}")
if len({x["resource_id"] for x in entries})!=92:raise RuntimeError("Manifest ID count != 92")
if len(entries)!=99:raise RuntimeError("Manifest occurrence count != 99")
if len({x["file"] for x in entries})!=18:raise RuntimeError("Manifest file count != 18")

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
    # All original target INTs are ASCII. If Hangul is introduced, UTF-8 is
    # required. Preserve BOM only if source had one.
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
    section_at={}
    for i,line in enumerate(lines,1):
        s=line.strip()
        if s.startswith("[") and s.endswith("]"):
            section=s[1:-1]
            section_at[i]=section
            continue
        k=line_key(line)
        if k is not None:
            positions[(section,k)].append(i)
    return positions

byfile=collections.defaultdict(list)
for x in entries:byfile[x["file"]].append(x)

source_sha_before=sha256_file(source)
if dest.exists():dest.unlink()
shutil.copy2(source,dest)

file_reports=[]
occ_reports=[]
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
        choice_reason=""
        current_raw=None

        # 1. Strongest case: unique section/key. Stage38 established that this
        #    key belongs to this resource occurrence, so current value drift is
        #    diagnostic rather than a reason to reject the key.
        if len(candidates)==1:
            chosen=candidates[0]
            choice_reason="UNIQUE_SECTION_KEY"
        else:
            # 2. For duplicate keys, prefer exact original/target value.
            exact=[]
            for ln in candidates:
                _,right,_=split_value(lines[ln-1])
                if right in (item["original_raw_value"],item["target_raw_value"]):
                    exact.append(ln)
            if len(exact)==1:
                chosen=exact[0];choice_reason="DUPLICATE_KEY_EXACT_VALUE"
            elif item["line"] in candidates:
                # 3. Stage38 original line number is acceptable only if it is
                #    still one of the exact same section/key candidates.
                chosen=item["line"];choice_reason="DUPLICATE_KEY_STAGE38_LINE"
            else:
                raise RuntimeError(
                    f"Ambiguous duplicate key for {item['resource_id']}: "
                    f"{fname} [{item['section']}] {item['key']} candidates={candidates}"
                )

        left,right,end=split_value(lines[chosen-1])
        current_raw=right
        if right==item["target_raw_value"]:
            pre_state="ALREADY_TARGET_KO"
            already+=1
        elif right==item["original_raw_value"]:
            pre_state="STAGE38_ORIGINAL_ENGLISH"
            lines[chosen-1]=left+"="+item["target_raw_value"]+end
            changed+=1
        else:
            pre_state="CURRENT_VALUE_DRIFTED_FROM_STAGE38"
            lines[chosen-1]=left+"="+item["target_raw_value"]+end
            changed+=1;drifted+=1

        occ_reports.append({
            "resource_id":item["resource_id"],
            "classification":item["classification"],
            "file":fname,
            "section":item["section"],
            "key":item["key"],
            "stage38_line":item["line"],
            "actual_line":chosen,
            "choice_reason":choice_reason,
            "pre_state":pre_state,
            "current_raw_before":current_raw,
            "stage38_original_raw":item["original_raw_value"],
            "target_raw":item["target_raw_value"],
        })

    newtext="".join(lines)
    newblob=encode_int(newtext,enc)

    # Exact section/key post verification.
    verify_text,_=decode_int(newblob)
    vlines=verify_text.splitlines(keepends=True)
    vpos=build_positions(vlines)
    for item in items:
        vals=[]
        for ln in vpos.get((item["section"],item["key"]),[]):
            _,right,_=split_value(vlines[ln-1])
            vals.append(right)
        if item["target_raw_value"] not in vals:
            raise RuntimeError(
                f"Post-patch target missing: {item['resource_id']} "
                f"{fname} [{item['section']}] {item['key']}"
            )

    b.append_iso_file_and_repoint(dest,parts+[fname],newblob)
    rb=b.iso_read_file(dest,parts+[fname])[1]
    if rb!=newblob:raise RuntimeError(f"ISO readback mismatch: {fname}")

    file_reports.append({
        "file":fname,
        "input_encoding":enc,
        "output_encoding":"utf-8-sig" if enc=="utf-8-sig" else "utf-8",
        "occurrences":len(items),
        "changed":changed,
        "already_target_korean":already,
        "drifted_current_values":drifted,
        "before_size":len(blob),
        "after_size":len(newblob),
        "before_sha256":before_sha,
        "after_sha256":hashlib.sha256(newblob).hexdigest(),
        "readback_verified":True,
    })

# Source Stage43T must remain untouched.
source_sha_after=sha256_file(source)
if source_sha_after!=source_sha_before:
    raise RuntimeError("Source Stage43T ISO changed unexpectedly")

# Preserve all 8 Stage42H-derived movie ST1 files byte-for-byte.
movie_files=[
"EM_1130_BOOKENDS.ST1","EM_1230_BOOKENDS2.ST1","EM_1300_BOOKENDS4.ST1","EM_1330_BOOKENDS3.ST1",
"EM_CRACKOFDAWN.ST1","EM_PURPLEHEARTLANE.ST1","EM_THEALLAMERICANS.ST1","EM_VICTORYINCARETAN.ST1"
]
movie_report=[]
for fname in movie_files:
    sb=b.iso_read_file(source,parts+[fname])[1]
    db=b.iso_read_file(dest,parts+[fname])[1]
    if sb!=db:raise RuntimeError(f"Movie ST1 changed unexpectedly: {fname}")
    movie_report.append({"file":fname,"sha256":hashlib.sha256(db).hexdigest(),"preserved":True})

# Preserve existing verified Stage43T resources that this INT-only build must
# never touch.
preserve_files=[
"ON_MEMU.MDI","ON_MEMU.DSL","ON_MEMU.DSX",
"D0_0130_.MDI","D0_0130_.DSL","D0_0130_.DSX",
]
preserve=[]
for fname in preserve_files:
    sb=b.iso_read_file(source,parts+[fname])[1]
    db=b.iso_read_file(dest,parts+[fname])[1]
    if sb!=db:raise RuntimeError(f"Baseline file changed unexpectedly: {fname}")
    preserve.append({"file":fname,"sha256":hashlib.sha256(db).hexdigest(),"preserved":True})

dest_sha=sha256_file(dest)

with (out/"int_file_patch_report.tsv").open("w",encoding="utf-8-sig",newline="") as f:
    fs=["file","input_encoding","output_encoding","occurrences","changed","already_target_korean","drifted_current_values","before_size","after_size","before_sha256","after_sha256","readback_verified"]
    w=csv.DictWriter(f,fieldnames=fs,delimiter="\t",lineterminator="\n");w.writeheader();w.writerows(file_reports)

with (out/"int_occurrence_patch_report.tsv").open("w",encoding="utf-8-sig",newline="") as f:
    fs=["resource_id","classification","file","section","key","stage38_line","actual_line","choice_reason","pre_state","current_raw_before","stage38_original_raw","target_raw"]
    w=csv.DictWriter(f,fieldnames=fs,delimiter="\t",lineterminator="\n");w.writeheader();w.writerows(occ_reports)

with (out/"drifted_stage43t_values.tsv").open("w",encoding="utf-8-sig",newline="") as f:
    fs=["resource_id","classification","file","section","key","stage38_line","actual_line","choice_reason","pre_state","current_raw_before","stage38_original_raw","target_raw"]
    w=csv.DictWriter(f,fieldnames=fs,delimiter="\t",lineterminator="\n");w.writeheader()
    w.writerows([x for x in occ_reports if x["pre_state"]=="CURRENT_VALUE_DRIFTED_FROM_STAGE38"])

with (out/"movie_st1_preservation.tsv").open("w",encoding="utf-8-sig",newline="") as f:
    w=csv.DictWriter(f,fieldnames=["file","sha256","preserved"],delimiter="\t",lineterminator="\n");w.writeheader();w.writerows(movie_report)

report={
    "step":"STEP_069_FIX1",
    "status":"BUILT_UNVERIFIED",
    "failure_fixed":"STEP069 rejected a unique section/key because its current Stage43T raw value had drifted from the Stage38 original.",
    "source_iso":str(source),
    "output_iso":str(dest),
    "source_iso_sha256_before":source_sha_before,
    "source_iso_sha256_after":source_sha_after,
    "output_iso_sha256":dest_sha,
    "target_ids":92,
    "target_occurrences":99,
    "target_int_files":18,
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
(out/"step069_fix1_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(report,ensure_ascii=False))
