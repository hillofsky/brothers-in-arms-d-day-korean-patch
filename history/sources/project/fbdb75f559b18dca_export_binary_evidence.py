#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""STEP078: preserve exact representative MDI/DSL/DSX bytes for offline reverse engineering.
Diagnostic/export only. DO NOT PATCH any ISO.
"""
from __future__ import annotations
import argparse, hashlib, importlib.util, json, struct, os, zipfile
from pathlib import Path

ROOT=Path(r"PROJECT_ROOT")
ORIGINAL=ROOT/"Brothers in Arms - D-Day (USA) (v1.01).iso"
STAGE69=ROOT/"BIA_STAGE69_FIX2_NONMDI_INT92_TEST.iso"
PARTS=['PSP_GAME','USRDIR','SYSTEM']

KNOWN_ORIGINAL_SHA="3d138a30a4e468532d551c74c848b4ec1ab7a044a726c5434e8a6a20e6814f66"
KNOWN_STAGE69_SHA="5683ad64d2ca2764fc05bb5a690402ae17c47398298878ca1bfc5e04ecb514b8"

SAMPLES = [
    ("original","D0_0130_.MDI",("MDI","DSL","DSX")),
    ("stage69","D0_0130_.MDI",("MDI","DSL","DSX")),
    ("stage69","D0_0700_.MDI",("MDI","DSL","DSX")),
    ("stage69","D0_1015_.MDI",("DSL","DSX")),
    ("stage69","D1_1830_.MDI",("DSL","DSX")),
    ("stage69","SKR_DE_HOLD.MDI",("DSL","DSX")),
]

def sha_bytes(buf: bytes):
    return hashlib.sha256(buf).hexdigest()

def sha_file(path: Path):
    h=hashlib.sha256()
    with path.open("rb") as fp:
        for part in iter(lambda:fp.read(1024*1024), b""):
            h.update(part)
    return h.hexdigest()

def load_base():
    helper=ROOT/"bia_stage40i_tools"/"bia_stage40i_actual_resource_trace.py"
    if not helper.is_file():
        raise FileNotFoundError(helper)
    spec=importlib.util.spec_from_file_location("bia_stage40i",str(helper))
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _,b=module.load_helpers()
    return b,helper

def little_u32(buf,offset):
    if offset < 0 or offset+4>len(buf):
        return None
    return f"0x{struct.unpack_from('<I',buf,offset)[0]:08X}"

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--outdir",required=True)
    ap.add_argument("--package-root",required=True)
    a=ap.parse_args()
    out=Path(a.outdir)
    out.mkdir(parents=True,exist_ok=True)

    b,helper=load_base()
    iso_paths={"original":ORIGINAL,"stage69":STAGE69}
    sha_before={}
    for key,p in iso_paths.items():
        if not p.is_file():
            raise FileNotFoundError(p)
        sha_before[key]=sha_file(p)
    if sha_before["original"]!=KNOWN_ORIGINAL_SHA or sha_before["stage69"]!=KNOWN_STAGE69_SHA:
        raise RuntimeError(
            "ISO baseline identity mismatch. Refusing to export from an unverified build: "
            +json.dumps(sha_before,ensure_ascii=False)
        )

    capture=out/"STEP078_binary_evidence.zip"
    if capture.exists():
        capture.unlink()
    manifest=[]
    inventories=[]
    info={}
    for key,mdi,extensions in SAMPLES:
        iso=iso_paths[key]
        stem=mdi[:-4]
        entry={}
        for ext in extensions:
            name=f"{stem}.{ext}"
            path=PARTS+[name]
            meta,blob=b.iso_read_file(iso,path)
            payload=bytes(blob)
            outname=f"{key}/{name}"
            entry[ext]=payload

            details={
                "source":key, "name":name, "type":ext,
                "archive_member":outname,
                "bytes":len(payload), "sha256":sha_bytes(payload),
            }
            manifest.append(details)
            print(f"[{len(manifest):02d}] {outname}: {len(payload)} B",flush=True)

        # MDI parsed file is used to compare original vs patched first mission,
        # and to compare its structure to the untouched D0_0700 campaign MDI.
        if "MDI" in entry:
            s={x["index"]:bytes(x["decoded"]) for x in b.parse_mdi(entry["MDI"])}
            entry["mdi_streams"]=s
            for idx,dec in sorted(s.items()):
                inventories.append({
                    "source":key,"mdi":mdi,"stream":idx,
                    "decoded_bytes":len(dec),"sha256":sha_bytes(dec),
                    "nonzero_bytes":sum(1 for v in dec if v),
                    "first_64_hex":dec[:64].hex()
                })

        # Keep physical DSX for direct offline archive-loader analysis, and
        # cross-check its reconstructed logical bytes against DSL.
        if "DSL" in entry and "DSX" in entry:
            logical=b.dsx_logical_bytes(entry["DSX"])
            if logical!=entry["DSL"]:
                raise RuntimeError(f"DSL/DSX mismatch {key}:{stem}")
            info[f"{key}/{stem}"]={
                "dsx_logical_equals_dsl":True,
                "dsl_sha256":sha_bytes(entry["DSL"]),
                "dsx_sha256":sha_bytes(entry["DSX"]),
                "dsl_bytes":len(entry["DSL"]),
                "dsx_bytes":len(entry["DSX"]),
            }

        # Archive the verified samples only. ZIP_DEFLATED compresses MDI/DSL
        # binary evidence; file names preserve original exact basename.
        with zipfile.ZipFile(capture,mode="a",compression=zipfile.ZIP_DEFLATED,
                             compresslevel=7,allowZip64=True) as z:
            for ext in extensions:
                file_name=f"{stem}.{ext}"
                z.writestr(f"{key}/{file_name}",entry[ext])

    # Known positive-control location: first mission original→Stage69 changes.
    _,odsl=b.iso_read_file(ORIGINAL,PARTS+["D0_0130_.DSL"])
    _,pdsl=b.iso_read_file(STAGE69,PARTS+["D0_0130_.DSL"])
    if len(odsl)!=len(pdsl):
        raise RuntimeError("First-mission DSL changed size unexpectedly")
    diff=[i for i,(x,y) in enumerate(zip(odsl,pdsl)) if x!=y]
    runs=[]
    for i in diff:
        if runs and runs[-1]["end"]==i:
            runs[-1]["end"]=i+1
        else:
            runs.append({"start":i,"end":i+1})
    for r in runs:
        off=r["start"];end=r["end"]
        r.update({
            "offset":f"0x{off:08X}",
            "old_hex":odsl[off:end].hex(),
            "stage69_hex":pdsl[off:end].hex(),
            "window_original_hex":odsl[max(0,off-48):min(len(odsl),end+48)].hex(),
            "window_stage69_hex":pdsl[max(0,off-48):min(len(pdsl),end+48)].hex(),
        })
    positive_control={
        "original_relocation_offset":"0x0031E2AE",
        "original_relocation_hex":odsl[0x31E2AE:0x31E2AE+12].hex(),
        "stage69_relocation_hex":pdsl[0x31E2AE:0x31E2AE+12].hex(),
        "known_b8_offset":"0x004ACEE4",
        "original_b8_u32":little_u32(odsl,0x4ACEE4),
        "stage69_b8_u32":little_u32(pdsl,0x4ACEE4),
        "changed_byte_count":len(diff),
        "changed_runs":runs,
    }
    (out/"first_mission_dsl_actual_delta.json").write_text(
        json.dumps(positive_control,ensure_ascii=False,indent=2),encoding="utf-8"
    )

    # Bundle exact historical builder and STEP066 reference subset into the
    # evidence archive as separate names, ensuring it is self-contained.
    pkg=Path(a.package_root)
    with zipfile.ZipFile(capture,mode="a",compression=zipfile.ZIP_DEFLATED,
                         compresslevel=7,allowZip64=True) as z:
        for name in ("historical_build_firstmission40y.py",
                     "selected_compiled_fstring_refs.tsv"):
            p=pkg/"evidence"/name
            if p.exists():
                z.write(p,f"references/{name}")

    sha_after={k:sha_file(p) for k,p in iso_paths.items()}
    if sha_before!=sha_after:
        raise RuntimeError("READ-ONLY INTEGRITY ERROR: an ISO hash changed during export")

    report={
        "step":"STEP_078",
        "status":"VERIFIED_BINARY_EVIDENCE_EXPORTED",
        "iso_modified":False,
        "output_iso_created":False,
        "original_sha_before":sha_before["original"],
        "original_sha_after":sha_after["original"],
        "stage69_sha_before":sha_before["stage69"],
        "stage69_sha_after":sha_after["stage69"],
        "original_preserved":True,
        "stage69_preserved":True,
        "archive_name":capture.name,
        "archive_size":capture.stat().st_size,
        "captured_resources":len(manifest),
        "dsl_dsx_consistency_checks":len(info),
        "first_mission_dsl_changed_bytes":len(diff),
        "payloads_exact_not_rewritten":True,
        "compiled967_iso_built":False,
        "first_mission_korean_runtime_state":"previously VERIFIED (not re-tested)",
        "int92_runtime_state":"BUILT_UNVERIFIED",
        "six_movie_playbacks_deferred":True,
        "next_action":"Analyze captured full original/modified first-mission DSL, other campaign and skirmish DSL, DSX, and MDI binaries OFFLINE in the conversation; derive a semantics-based binding before modifying 31 other missions."
    }
    (out/"step078_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    (out/"sample_manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    (out/"mdi_decoded_stream_inventory.json").write_text(
        json.dumps(inventories,ensure_ascii=False,indent=2),encoding="utf-8")
    (out/"dsl_dsx_validation.json").write_text(
        json.dumps(info,ensure_ascii=False,indent=2),encoding="utf-8")

    with zipfile.ZipFile(capture) as z:
        bad=z.testzip()
        if bad:
            raise RuntimeError("Binary evidence archive CRC failed for "+bad)
        if len(z.infolist()) != len(manifest)+2:
            raise RuntimeError("Unexpected file count in binary evidence")
    print(json.dumps({
        "status":report["status"],
        "captured_resources":len(manifest),
        "archive_size":capture.stat().st_size,
        "first_mission_dsl_changed_bytes":len(diff),
        "source_preserved":True
    },ensure_ascii=False),flush=True)

if __name__=="__main__":
    main()
