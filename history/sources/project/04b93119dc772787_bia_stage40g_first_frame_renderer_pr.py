#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import base64
import csv
import hashlib
import importlib.util
import json
import struct
import subprocess
import sys
import time
import traceback
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(r"PROJECT_ROOT")
BASE_TOOLS = ROOT / "bia_stage39b_tools"

SOURCE_ISO = ROOT / "BIA_STAGE40F_ON_MEMU_RESIDENT_MASS_TEST.iso"
STAGE40F_RETRY = ROOT / "bia_stage40f_retry_tools" / "run_bia_stage40f_retry.ps1"

OUT = ROOT / "analysis" / "stage40g_first_frame_renderer_proof"
LOG_DIR = ROOT / "log"

SUCCESS_ZIP = LOG_DIR / "bia_stage40g_upload.zip"
FAIL_ZIP = LOG_DIR / "fail_bia_stage40g_upload.zip"
REPORT_PATH = OUT / "stage40g_report.json"
PPSSPP_LOG = OUT / "stage40g_ppsspp.log"

SCRIPT_DIR = Path(__file__).resolve().parent
PLAN_PATH = SCRIPT_DIR / "stage40g_on_memu_plan.tsv"

TARGET = [
    "PSP_GAME",
    "USRDIR",
    "SYSTEM",
    "ON_MEMU_O.MDI",
]

EXPECTED_MDI_SHA1 = "297216ed0f00948f64dd644952b90a71a58dd638"

MDI_SEQ_BASE = 0x08E2D020
MDI_STREAM_SIZE = 0x78000

LIVE_STREAM = 23
LIVE_BASE = MDI_SEQ_BASE + LIVE_STREAM * MDI_STREAM_SIZE
ALLOC_START = 0xA870

RENDER_CALL_RUNTIME = 0x08972360
EXPECTED_RENDER_JAL_RUNTIME = bytes.fromhex("e410330e")
UNICODE_LOOKUP = 0x08C7F2FC
WIDE_RENDER_LOOKUP_RA = 0x08972368

FONT_OBJECT = 0x0972385C
EXPECTED_GLYPH_COUNT = 847
EXPECTED_GLYPH_PTR = 0x098F5020

MENU_OPEN_MARKER = (
    "sceIoOpen(disc0:/PSP_GAME/USRDIR/SYSTEM/RAWFILES/MENUINT0.RAW"
)

# These are the actual top-level metadata records from the Stage40F plan.
TOP_LEVEL = [
    {
        "label": "Skirmish",
        "ko": "스커미시",
        "char": "커",
        "metadata_addr": 0x095EC790,
        "expected_ptr": 0x09902998,
        "expected_num": 13,
    },
    {
        "label": "Options",
        "ko": "옵션",
        "char": "옵",
        "metadata_addr": 0x095EC7AC,
        "expected_ptr": 0x099028F0,
        "expected_num": 7,
    },
    {
        "label": "Profile",
        "ko": "프로필",
        "char": "프",
        "metadata_addr": 0x095EC7C8,
        "expected_ptr": 0x099028A0,
        "expected_num": 10,
    },
]

STORY = {
    "label": "Story",
    "char": "토",
}

RAM_START = 0x08800000
RAM_END = 0x0A800000


def log(msg):
    print(msg, flush=True)


def sha1(data):
    return hashlib.sha1(data).hexdigest()


def align_up(v, a=4):
    return (v + a - 1) & ~(a - 1)


def parse_int(v):
    s = str(v).strip()
    return int(s, 0) if s else None


def runtime_addr(stream_index, offset):
    return (
        MDI_SEQ_BASE
        + stream_index * MDI_STREAM_SIZE
        + offset
    )


def load_helpers():
    p = BASE_TOOLS / "bia_stage39b_compiled_mdi_text.py"
    if not p.exists():
        raise RuntimeError(f"Missing Stage39B helper: {p}")

    sys.path.insert(0, str(BASE_TOOLS))
    spec = importlib.util.spec_from_file_location(
        "bia_stage39b_local", p
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)

    b = getattr(mod, "b", None)
    if b is None and hasattr(mod, "s39"):
        b = getattr(mod.s39, "b", None)
    if b is None:
        raise RuntimeError("Could not resolve Stage39B helpers")

    return mod, b


def load_plan():
    rows = list(csv.DictReader(
        PLAN_PATH.open(
            encoding="utf-8-sig",
            newline="",
        ),
        delimiter="\t",
    ))

    if len(rows) != 1675:
        raise RuntimeError(f"Expected 1675 actions, got {len(rows)}")

    if len({x["unit_id"] for x in rows}) != 690:
        raise RuntimeError("Expected 690 unique units")

    if len({x["korean"] for x in rows}) != 656:
        raise RuntimeError("Expected 656 unique Korean payloads")

    return rows


def expected_payloads(plan):
    seen = set()
    payloads = []
    cursor = ALLOC_START

    for row in plan:
        ko = row["korean"]
        if ko in seen:
            continue
        seen.add(ko)

        blob = ko.encode("utf-8") + b"\x00"
        cursor = align_up(cursor, 4)
        ptr = runtime_addr(LIVE_STREAM, cursor)

        payloads.append({
            "korean": ko,
            "ptr": ptr,
            "offset": cursor,
            "blob": blob,
        })
        cursor += len(blob)

    return payloads


def ensure_iso(b):
    def mdi_hash():
        if not SOURCE_ISO.exists():
            return None
        try:
            _, data = b.iso_read_file(SOURCE_ISO, TARGET)
            return sha1(data)
        except Exception:
            return None

    before = mdi_hash()

    if before == EXPECTED_MDI_SHA1:
        return {
            "reused": True,
            "mdi_sha1": before,
            "path": str(SOURCE_ISO),
        }

    if not STAGE40F_RETRY.exists():
        raise RuntimeError(
            "Stage40F ISO is missing/wrong and retry runner is unavailable"
        )

    log("[Stage40G] Regenerating Stage40F ISO.")
    p = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(STAGE40F_RETRY),
        ],
        check=False,
    )

    after = mdi_hash()

    # Stage40F's previous runtime verifier is known to return nonzero after it
    # has already built a structurally valid ISO. Hash identity is the gate.
    if after != EXPECTED_MDI_SHA1:
        raise RuntimeError(
            f"Stage40F MDI hash mismatch after regeneration: {after}"
        )

    return {
        "reused": False,
        "regeneration_exit_code": p.returncode,
        "mdi_sha1": after,
        "path": str(SOURCE_ISO),
    }


def read_ws(ws, address, size):
    r = ws.request(
        "memory.read",
        timeout=10,
        address=address,
        size=size,
    )
    return base64.b64decode(r["base64"])


def parse_regs(resp):
    uints = {}

    for cat in resp.get("categories", []):
        names = cat.get("registerNames", [])
        vals = cat.get("uintValues", [])

        for i, name in enumerate(names):
            if i < len(vals):
                uints[name.lower()] = int(vals[i]) & 0xFFFFFFFF

    return uints


def wait_cpu_ready(ws, timeout=20):
    end = time.time() + timeout
    attempts = 0
    last_error = None

    while time.time() < end:
        attempts += 1
        try:
            status = ws.request("cpu.status", timeout=2)
            probe = read_ws(ws, RENDER_CALL_RUNTIME, 4)
            if len(probe) == 4:
                return {
                    "ready": True,
                    "attempts": attempts,
                    "status": status,
                    "probe": probe.hex(),
                }
        except Exception as e:
            last_error = str(e)

        time.sleep(0.05)

    return {
        "ready": False,
        "attempts": attempts,
        "last_error": last_error,
    }


def wait_menu_resource(ws, timeout=180):
    end = time.time() + timeout
    last_press = 0
    presses = 0

    while time.time() < end:
        if PPSSPP_LOG.exists():
            txt = PPSSPP_LOG.read_text(
                encoding="utf-8",
                errors="replace",
            )
            if MENU_OPEN_MARKER in txt:
                return {
                    "opened": True,
                    "startup_start_presses": presses,
                }

        now = time.time()
        if now - last_press >= 1.25:
            try:
                ws.request(
                    "input.buttons.press",
                    timeout=3,
                    button="start",
                    duration=2,
                )
                presses += 1
            except Exception:
                pass
            last_press = now

        time.sleep(0.1)

    return {
        "opened": False,
        "startup_start_presses": presses,
    }


def remove_bp(ws):
    try:
        ws.request(
            "cpu.breakpoint.remove",
            timeout=5,
            address=UNICODE_LOOKUP,
        )
    except Exception:
        pass


def resume(ws):
    try:
        ws.request("cpu.resume", timeout=0.5)
    except Exception:
        pass


def wait_pause(ws, timeout=12):
    end = time.time() + timeout

    while time.time() < end:
        try:
            s = ws.request("cpu.status", timeout=2)
            if s.get("stepping", False):
                return s
        except Exception:
            pass

        time.sleep(0.015)

    return None


def arm_probe(ws, char):
    code = ord(char)
    remove_bp(ws)

    ws.request(
        "cpu.breakpoint.add",
        timeout=10,
        address=UNICODE_LOOKUP,
        enabled=True,
        log=False,
        condition=(
            f"a1 == 0x{code:X} && "
            f"ra == 0x{WIDE_RENDER_LOOKUP_RA:08X}"
        ),
    )


def collect_probe(ws, label, char, timeout=12):
    code = ord(char)
    paused = wait_pause(ws, timeout=timeout)

    if paused is None:
        remove_bp(ws)
        return {
            "label": label,
            "char": char,
            "codepoint": f"U+{code:04X}",
            "hit": False,
        }

    regs = parse_regs(
        ws.request(
            "cpu.getAllRegs",
            timeout=10,
        )
    )

    s0 = regs.get("s0", 0)
    sample = None

    if RAM_START <= s0 < RAM_END:
        try:
            sample = read_ws(ws, s0, 48).hex()
        except Exception:
            pass

    result = {
        "label": label,
        "char": char,
        "codepoint": f"U+{code:04X}",
        "hit": True,
        "pc": f"0x{regs.get('pc',0):08X}",
        "ra": f"0x{regs.get('ra',0):08X}",
        "a1": f"0x{regs.get('a1',0):08X}",
        "s0": f"0x{s0:08X}",
        "s4": regs.get("s4"),
        "s5": regs.get("s5"),
        "source_sample_hex": sample,
    }

    remove_bp(ws)
    return result


def read_top_level_metadata(ws):
    results = []

    for item in TOP_LEVEL:
        expected_blob = item["ko"].encode("utf-8") + b"\x00"

        try:
            raw = read_ws(ws, item["metadata_addr"], 12)
            ptr, num, maxv = struct.unpack("<III", raw)

            value_raw = read_ws(ws, ptr, max(1, num))
            value = value_raw.split(b"\x00", 1)[0].decode(
                "utf-8",
                errors="replace",
            )

            results.append({
                "label": item["label"],
                "metadata_addr": f"0x{item['metadata_addr']:08X}",
                "raw_hex": raw.hex(),
                "ptr": f"0x{ptr:08X}",
                "num": num,
                "max": maxv,
                "value": value,
                "expected_ptr": f"0x{item['expected_ptr']:08X}",
                "expected_num": item["expected_num"],
                "ok": (
                    ptr == item["expected_ptr"]
                    and num == item["expected_num"]
                    and maxv == item["expected_num"]
                    and value == item["ko"]
                ),
            })
        except Exception as e:
            results.append({
                "label": item["label"],
                "metadata_addr": f"0x{item['metadata_addr']:08X}",
                "ok": False,
                "error": str(e),
            })

    return results


def verify_all_payloads(ws, payloads):
    failures = []
    checked = 0

    for p in payloads:
        try:
            got = read_ws(ws, p["ptr"], len(p["blob"]))
            checked += 1

            if got != p["blob"]:
                failures.append({
                    "korean": p["korean"],
                    "ptr": f"0x{p['ptr']:08X}",
                    "expected_hex": p["blob"].hex(),
                    "actual_hex": got.hex(),
                })
        except Exception as e:
            failures.append({
                "korean": p["korean"],
                "ptr": f"0x{p['ptr']:08X}",
                "error": str(e),
            })

    return {
        "checked": checked,
        "total": len(payloads),
        "failure_count": len(failures),
        "failures": failures[:100],
        "ok": (
            checked == len(payloads)
            and not failures
        ),
    }


def metadata_census(ws, plan, payloads):
    ptr_by_ko = {
        p["korean"]: p["ptr"]
        for p in payloads
    }

    exact = 0
    mismatch = []
    by_stream = Counter()

    for row in plan:
        si = parse_int(row["metadata_stream"])
        off = parse_int(row["metadata_offset"])
        addr = runtime_addr(si, off)

        ptr = ptr_by_ko[row["korean"]]
        num = len(row["korean"].encode("utf-8")) + 1
        expected = (ptr, num, num)

        try:
            got = struct.unpack(
                "<III",
                read_ws(ws, addr, 12),
            )

            if got == expected:
                exact += 1
            else:
                by_stream[si] += 1
                mismatch.append({
                    "unit_id": row["unit_id"],
                    "english": row["english"],
                    "korean": row["korean"],
                    "metadata_stream": si,
                    "metadata_offset": f"0x{off:X}",
                    "metadata_runtime": f"0x{addr:08X}",
                    "expected": [
                        f"0x{expected[0]:08X}",
                        expected[1],
                        expected[2],
                    ],
                    "actual": [
                        f"0x{got[0]:08X}",
                        got[1],
                        got[2],
                    ],
                })
        except Exception as e:
            by_stream[si] += 1
            mismatch.append({
                "unit_id": row["unit_id"],
                "english": row["english"],
                "korean": row["korean"],
                "metadata_stream": si,
                "metadata_offset": f"0x{off:X}",
                "metadata_runtime": f"0x{addr:08X}",
                "error": str(e),
            })

    return {
        "total": len(plan),
        "exact": exact,
        "mismatch_count": len(mismatch),
        "mismatch_by_stream": {
            str(k): v
            for k, v in sorted(by_stream.items())
        },
        "mismatches": mismatch,
    }


def runtime_test(b, plan, payloads):
    exe = b.find_ppsspp_exe()

    cfg = OUT / "stage40g_append.ini"
    cfg.write_text(
        "[Debugger]\n"
        "ShowDeveloperMenu = True\n"
        "\n"
        "[Graphics]\n"
        "ReplaceTextures = False\n"
        "SaveNewTextures = False\n",
        encoding="utf-8",
    )

    if PPSSPP_LOG.exists():
        PPSSPP_LOG.unlink()

    try:
        b.close_existing_ppsspp(timeout=3.0)
    except Exception:
        pass

    port = b.choose_free_port()

    cmd = [
        str(exe),
        "-d",
        f"--log={PPSSPP_LOG}",
        "--windowed",
        f"--appendconfig={cfg}",
        f"--debugger={port}",
        str(SOURCE_ISO),
    ]

    log("[Stage40G] Launching PPSSPP first-frame proof")
    proc = subprocess.Popen(cmd)
    cleanup = b.register_ppsspp_auto_close(proc)

    result = {
        "pid": proc.pid,
    }

    try:
        hwnd = b.find_ppsspp_hwnd(30)
        if not hwnd:
            raise RuntimeError("PPSSPP window did not appear")

        actual_port = b.wait_for_actual_debugger_port(
            PPSSPP_LOG,
            30,
        )
        ws, host = b.connect_debugger(actual_port)

        try:
            result["debugger_host"] = host
            result["debugger_port"] = actual_port

            ready = wait_cpu_ready(ws)
            result["cpu_ready"] = ready

            if not ready.get("ready"):
                raise RuntimeError("CPU did not become ready")

            result["renderer_jal"] = {
                "actual": read_ws(
                    ws,
                    RENDER_CALL_RUNTIME,
                    4,
                ).hex(),
                "expected": EXPECTED_RENDER_JAL_RUNTIME.hex(),
            }

            menu = wait_menu_resource(ws)
            result["menu_resource"] = menu

            if not menu.get("opened"):
                raise RuntimeError("MENUINT0.RAW did not open")

            # Critical Stage40G change:
            # arm Skirmish BEFORE the title->main-menu Start transition.
            # Stage40F verified 656+1675 RAM records first and therefore missed
            # non-selected labels that are rendered/cached only during initial
            # menu construction.
            time.sleep(2.5)

            first = TOP_LEVEL[0]
            arm_probe(ws, first["char"])

            ws.request(
                "input.buttons.press",
                timeout=5,
                button="start",
                duration=2,
            )

            probes = []

            p = collect_probe(
                ws,
                first["label"],
                first["char"],
                timeout=15,
            )
            probes.append(p)

            if not p["hit"]:
                # No initial Skirmish render means we should not pretend this is
                # a timing-only failure.
                result["first_frame_renderer_probes"] = probes
                raise RuntimeError(
                    "Skirmish Unicode lookup was not hit during initial menu render"
                )

            # We are paused inside the render of Skirmish. Arm Options, resume,
            # then Profile. This catches all three unselected labels in the same
            # first render pass before they can be cached.
            for item in TOP_LEVEL[1:]:
                arm_probe(ws, item["char"])
                resume(ws)

                p = collect_probe(
                    ws,
                    item["label"],
                    item["char"],
                    timeout=10,
                )
                probes.append(p)

                if not p["hit"]:
                    result["first_frame_renderer_probes"] = probes
                    raise RuntimeError(
                        f"{item['label']} Unicode lookup did not hit in first render"
                    )

            # Profile probe leaves CPU paused. The menu objects are now fully
            # initialized, so inspect their exact live metadata before resuming.
            result["top_level_metadata"] = (
                read_top_level_metadata(ws)
            )

            # Story is selected and continuously redrawn, so use it as the
            # Stage39U control after the three first-frame-only probes.
            arm_probe(ws, STORY["char"])
            resume(ws)

            story_probe = collect_probe(
                ws,
                STORY["label"],
                STORY["char"],
                timeout=10,
            )
            probes.append(story_probe)

            result["first_frame_renderer_probes"] = probes

            if not story_probe["hit"]:
                raise RuntimeError("Story control renderer probe failed")

            # Resume before bulk RAM validation.
            resume(ws)
            time.sleep(0.25)

            result["payload_runtime"] = (
                verify_all_payloads(
                    ws,
                    payloads,
                )
            )

            result["metadata_census"] = (
                metadata_census(
                    ws,
                    plan,
                    payloads,
                )
            )

            glyph_count = struct.unpack(
                "<H",
                read_ws(
                    ws,
                    FONT_OBJECT + 0x50,
                    2,
                ),
            )[0]
            glyph_ptr = struct.unpack(
                "<I",
                read_ws(
                    ws,
                    FONT_OBJECT + 0x54,
                    4,
                ),
            )[0]

            result["font_after_menu"] = {
                "glyph_count": glyph_count,
                "glyph_count_ok": (
                    glyph_count == EXPECTED_GLYPH_COUNT
                ),
                "glyph_ptr": f"0x{glyph_ptr:08X}",
                "glyph_ptr_ok": (
                    glyph_ptr == EXPECTED_GLYPH_PTR
                ),
            }

            top_ok = all(
                x.get("ok", False)
                for x in result["top_level_metadata"]
            )
            probes_ok = all(
                x.get("hit", False)
                for x in probes
            )

            result["ok"] = (
                result["renderer_jal"]["actual"]
                == result["renderer_jal"]["expected"]
                and probes_ok
                and top_ok
                and result["payload_runtime"]["ok"]
                and result["font_after_menu"]["glyph_count_ok"]
                and result["font_after_menu"]["glyph_ptr_ok"]
            )

        finally:
            try:
                remove_bp(ws)
                resume(ws)
            except Exception:
                pass
            try:
                ws.close()
            except Exception:
                pass

    finally:
        try:
            cleanup()
            result["ppsspp_closed"] = True
        except Exception as e:
            result["ppsspp_close_error"] = str(e)

    return result


def write_mismatch_tsv(census):
    path = OUT / "stage40g_metadata_mismatches.tsv"

    cols = [
        "unit_id",
        "english",
        "korean",
        "metadata_stream",
        "metadata_offset",
        "metadata_runtime",
        "expected",
        "actual",
        "error",
    ]

    with path.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as f:
        w = csv.DictWriter(
            f,
            fieldnames=cols,
            delimiter="\t",
            extrasaction="ignore",
        )
        w.writeheader()

        for row in census.get("mismatches", []):
            out = dict(row)

            for key in ("expected", "actual"):
                if key in out:
                    out[key] = json.dumps(
                        out[key],
                        ensure_ascii=False,
                    )

            w.writerow(out)

    return path


def make_zip(path):
    if path.exists():
        path.unlink()

    with zipfile.ZipFile(
        path,
        "w",
        zipfile.ZIP_DEFLATED,
    ) as z:
        for p in sorted(OUT.rglob("*")):
            if p.is_file():
                z.write(
                    p,
                    p.relative_to(OUT).as_posix(),
                )

        z.write(
            PLAN_PATH,
            "stage40g_on_memu_plan.tsv",
        )


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    for p in OUT.iterdir():
        if p.is_file():
            p.unlink()

    plan = load_plan()
    payloads = expected_payloads(plan)
    _, b = load_helpers()

    report = {
        "stage": "40G",
        "purpose":
            "Resolve Stage40F's false-negative possibility by arming renderer "
            "breakpoints BEFORE the initial main-menu render, then validate the "
            "three exact top-level metadata records and all 656 resident "
            "payloads.",
        "stage40f_result": {
            "build_iso_readback": True,
            "metadata_actions": 1675,
            "unique_units": 690,
            "unique_payloads": 656,
            "payload_runtime": "656/656 exact",
            "metadata_runtime": "1589/1675 exact at the sampled menu state",
            "font": "847 / 0x098F5020",
            "old_probe_result":
                "Story hit; Skirmish/Options/Profile missed because Stage40F "
                "performed 2331 RAM reads before arming those breakpoints.",
        },
    }

    try:
        report["source"] = ensure_iso(b)

        runtime = runtime_test(
            b,
            plan,
            payloads,
        )
        report["runtime"] = runtime
        report["completed"] = bool(
            runtime.get("ok", False)
        )

        census = runtime.get("metadata_census")
        if census is not None:
            mismatch_path = write_mismatch_tsv(census)
            report["metadata_mismatch_tsv"] = str(mismatch_path)

    except Exception as e:
        report["runtime_exception"] = str(e)
        report["runtime_traceback"] = traceback.format_exc()
        report["completed"] = False

    REPORT_PATH.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    target = (
        SUCCESS_ZIP
        if report["completed"]
        else FAIL_ZIP
    )
    make_zip(target)

    if not report["completed"]:
        raise RuntimeError(
            f"Stage40G failed. See {FAIL_ZIP}"
        )

    log("[Stage40G] COMPLETE")
    log("[Stage40G] Stage40F mass patch accepted.")
    log(f"[Stage40G] Upload ZIP: {SUCCESS_ZIP}")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        OUT.mkdir(parents=True, exist_ok=True)
        LOG_DIR.mkdir(parents=True, exist_ok=True)

        (OUT / "FAILURE.txt").write_text(
            traceback.format_exc(),
            encoding="utf-8",
        )

        try:
            make_zip(FAIL_ZIP)
        except Exception:
            pass

        print(traceback.format_exc(), flush=True)
        print(
            f"STAGE 40G FAILED: {FAIL_ZIP}",
            flush=True,
        )
        raise SystemExit(1)
