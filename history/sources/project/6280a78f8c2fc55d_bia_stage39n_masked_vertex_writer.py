#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import base64
import importlib.util
import json
import struct
import subprocess
import sys
import time
import traceback
import zipfile
from pathlib import Path

ROOT = Path(r"PROJECT_ROOT")
BASE_TOOLS = ROOT / "bia_stage39b_tools"
ISO = ROOT / "BIA_STAGE39F_CORRECT_NARROW_METADATA_TEST.iso"

OUT = ROOT / "analysis" / "stage39n_masked_vertex_writer"
LOG_DIR = ROOT / "log"

SUCCESS_ZIP = LOG_DIR / "bia_stage39n_upload.zip"
FAIL_ZIP = LOG_DIR / "fail_bia_stage39n_upload.zip"
REPORT_PATH = OUT / "stage39n_report.json"
PPSSPP_LOG = OUT / "stage39n_ppsspp.log"

REF_PATH = Path(__file__).resolve().parent / "stage39h_mainmenu_vertices.bin"
REF_SIZE = 1984
REF_SHA1 = "e1c87ada5beaee44f68e1f4e5f1f1037eaaa3ad7"

# Correct Stage39F source.
DISPLAY1_ADDR = 0x093B1B40
DISPLAY2_ADDR = 0x093B1BF0
META1_ADDR = 0x095EC774
META2_ADDR = 0x095F1758
UTF8 = "스토리".encode("utf-8")
UTF8_NUL = UTF8 + b"\x00"
EXPECTED_META1 = (DISPLAY1_ADDR, 10, 10)
EXPECTED_META2 = (DISPLAY2_ADDR, 10, 10)

MENU_OPEN_MARKER = (
    "sceIoOpen(disc0:/PSP_GAME/USRDIR/SYSTEM/RAWFILES/MENUINT0.RAW"
)

RAM_START = 0x08800000
RAM_END = 0x0A800000
SCAN_CHUNK = 0x00040000

# Vertex format observed in the Stage39H PPDMP is 16 bytes.
VERTEX_STRIDE = 16
UV_BYTES = 4

# The first 36 vertices are the nine visibly corrupted glyph sprites plus
# their shadow/duplicate pass.  UVs are stable even if color/position animation
# changes between frames.
TOP_VERTICES_TO_SCORE = 36
ALL_VERTICES = REF_SIZE // VERTEX_STRIDE

# Require a strong UV-sequence match, not exact color/XY bytes.
MIN_TOP_UV_RATIO = 0.88
MIN_FULL_UV_RATIO = 0.55

MAX_WRITE_HITS = 96
MEMCHECK_SIZE = 4

GPR_NAMES = [
    "zero","at","v0","v1","a0","a1","a2","a3",
    "t0","t1","t2","t3","t4","t5","t6","t7",
    "s0","s1","s2","s3","s4","s5","s6","s7",
    "t8","t9","k0","k1","gp","sp","fp","ra","pc",
]


def log(msg):
    print(msg, flush=True)


def sha1(data):
    import hashlib
    return hashlib.sha1(data).hexdigest()


def load_helpers():
    p = BASE_TOOLS / "bia_stage39b_compiled_mdi_text.py"
    if not p.exists():
        raise RuntimeError(f"Missing Stage39B helper: {p}")
    sys.path.insert(0, str(BASE_TOOLS))
    spec = importlib.util.spec_from_file_location("bia_stage39b_local", p)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    b = getattr(mod, "b", None)
    if b is None and hasattr(mod, "s39"):
        b = getattr(mod.s39, "b", None)
    if b is None:
        raise RuntimeError("Could not resolve Stage39B helper module")
    return mod, b


def read_ws(ws, addr, size):
    r = ws.request(
        "memory.read", timeout=10, address=addr, size=size
    )
    return base64.b64decode(r["base64"])


def regs_to_dict(resp):
    out = {}
    for cat in resp.get("categories", []):
        for n, v in zip(
            cat.get("registerNames", []),
            cat.get("uintValues", []),
        ):
            out[n.lower()] = int(v) & 0xFFFFFFFF
    return out


def disasm(ws, addr, count=72):
    try:
        return ws.request(
            "memory.disasm",
            timeout=10,
            address=addr & 0xFFFFFFFF,
            count=count,
            displaySymbols=True,
            compact=False,
        )
    except Exception as e:
        return {"error": str(e)}


def resume(ws):
    try:
        ws.request("cpu.resume", timeout=1)
    except Exception:
        pass


def wait_pause(ws, timeout=10.0):
    end = time.time() + timeout
    last = None
    while time.time() < end:
        try:
            last = ws.request("cpu.status", timeout=3)
            if last.get("stepping", False):
                return last
        except Exception:
            pass
        time.sleep(0.02)
    return None


def wait_menu_open(ws, timeout=180.0):
    end = time.time() + timeout
    last_press = 0.0
    presses = 0
    while time.time() < end:
        if PPSSPP_LOG.exists():
            txt = PPSSPP_LOG.read_text(
                encoding="utf-8", errors="replace"
            )
            if MENU_OPEN_MARKER in txt:
                return {"opened": True, "start_presses": presses}

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
    return {"opened": False, "start_presses": presses}


def wait_source(ws, timeout=60.0):
    end = time.time() + timeout
    last = {}
    while time.time() < end:
        try:
            d1 = read_ws(ws, DISPLAY1_ADDR, 16)
            d2 = read_ws(ws, DISPLAY2_ADDR, 16)
            m1 = struct.unpack("<III", read_ws(ws, META1_ADDR, 12))
            m2 = struct.unpack("<III", read_ws(ws, META2_ADDR, 12))
            last = {
                "display1": d1.hex(),
                "display2": d2.hex(),
                "meta1": [f"0x{m1[0]:08X}", m1[1], m1[2]],
                "meta2": [f"0x{m2[0]:08X}", m2[1], m2[2]],
            }
            if (
                d1.startswith(UTF8_NUL)
                and d2.startswith(UTF8_NUL)
                and m1 == EXPECTED_META1
                and m2 == EXPECTED_META2
            ):
                last["ok"] = True
                return last
        except Exception:
            pass
        time.sleep(0.12)
    last["ok"] = False
    return last


def guest_read(b, pid, base, addr, size):
    h = b.open_process(pid)
    try:
        return b.guest_read(h, base, addr, size)
    finally:
        b.kernel32.CloseHandle(h)


def scan_first_uv_candidates(b, pid, base, first_uv):
    """
    Search guest RAM for only the first 4-byte UV pair.  Stage39M incorrectly
    included the animated 4-byte color in its minimum prefix, causing zero hits.
    """
    hits = []
    overlap = len(first_uv) - 1
    tail = b""
    tail_addr = RAM_START

    h = b.open_process(pid)
    try:
        addr = RAM_START
        while addr < RAM_END:
            size = min(SCAN_CHUNK, RAM_END - addr)
            try:
                chunk = b.guest_read(h, base, addr, size)
            except Exception:
                chunk = b"\x00" * size

            data = tail + chunk if tail else chunk
            data_base = tail_addr if tail else addr

            pos = 0
            while True:
                p = data.find(first_uv, pos)
                if p < 0:
                    break
                g = data_base + p
                if RAM_START <= g < RAM_END:
                    hits.append(g)
                pos = p + 1

            tail = data[-overlap:] if overlap else b""
            tail_addr = addr + size - len(tail)
            addr += size
    finally:
        b.kernel32.CloseHandle(h)

    return sorted(set(hits))


def uv_sequence_score(candidate, ref):
    """
    Ignore bytes 4..15 of every 16-byte vertex and compare only u16/u16 UV.
    This survives alpha/color animation and screen-position tweening.
    """
    max_vertices = min(
        len(candidate) // VERTEX_STRIDE,
        len(ref) // VERTEX_STRIDE,
    )

    matches = []
    for i in range(max_vertices):
        a = candidate[i*VERTEX_STRIDE:i*VERTEX_STRIDE+UV_BYTES]
        r = ref[i*VERTEX_STRIDE:i*VERTEX_STRIDE+UV_BYTES]
        matches.append(a == r)

    top_n = min(TOP_VERTICES_TO_SCORE, len(matches))
    top_ratio = (
        sum(matches[:top_n]) / top_n if top_n else 0.0
    )
    full_ratio = (
        sum(matches) / len(matches) if matches else 0.0
    )

    return top_ratio, full_ratio, matches


def locate_masked_vertex_buffer(b, pid, base, ref):
    first_uv = ref[:4]
    raw_hits = scan_first_uv_candidates(
        b, pid, base, first_uv
    )

    scored = []
    for addr in raw_hits[:4096]:
        try:
            got = guest_read(
                b, pid, base, addr, len(ref)
            )
        except Exception:
            continue

        top_ratio, full_ratio, matches = uv_sequence_score(
            got, ref
        )

        # Also compare XY positions, but only as a secondary diagnostic.
        xy_exact = 0
        xy_near = 0
        n = min(TOP_VERTICES_TO_SCORE, len(got)//16)
        for i in range(n):
            goff = i*16 + 8
            roff = i*16 + 8
            gx, gy = struct.unpack_from("<HH", got, goff)
            rx, ry = struct.unpack_from("<HH", ref, roff)
            if gx == rx and gy == ry:
                xy_exact += 1
            if abs(gx-rx) <= 8 and abs(gy-ry) <= 8:
                xy_near += 1

        scored.append({
            "address": addr,
            "address_hex": f"0x{addr:08X}",
            "top_uv_ratio": top_ratio,
            "full_uv_ratio": full_ratio,
            "top_xy_exact_ratio":
                (xy_exact / n) if n else 0.0,
            "top_xy_near_ratio":
                (xy_near / n) if n else 0.0,
            "first_64_hex": got[:64].hex(),
            "uv_matches_first_40":
                matches[:40],
        })

    scored.sort(
        key=lambda x: (
            x["top_uv_ratio"],
            x["full_uv_ratio"],
            x["top_xy_near_ratio"],
        ),
        reverse=True,
    )

    qualified = [
        x for x in scored
        if (
            x["top_uv_ratio"] >= MIN_TOP_UV_RATIO
            and x["full_uv_ratio"] >= MIN_FULL_UV_RATIO
        )
    ]

    return {
        "first_uv_hex": first_uv.hex(),
        "raw_first_uv_hits": len(raw_hits),
        "scored_count": len(scored),
        "top_candidates": scored[:24],
        "qualified": qualified[:12],
        "best": qualified[0] if qualified else None,
    }


def add_write_memcheck(ws, addr, label):
    return ws.request(
        "memory.breakpoint.add",
        timeout=10,
        address=addr,
        size=MEMCHECK_SIZE,
        enabled=True,
        log=True,
        read=False,
        write=True,
        change=False,
        logFormat=(
            f"BIA39N_{label} "
            "pc={{pc}} ra={{ra}} "
            "a0={{a0}} a1={{a1}} a2={{a2}} a3={{a3}} "
            "s0={{s0}} s1={{s1}} s2={{s2}} s3={{s3}} "
            "s4={{s4}} s5={{s5}} s6={{s6}} s7={{s7}} "
            "t0={{t0}} t1={{t1}} t2={{t2}} t3={{t3}}"
        ),
    )


def remove_memcheck(ws, addr):
    try:
        ws.request(
            "memory.breakpoint.remove",
            timeout=5,
            address=addr,
            size=MEMCHECK_SIZE,
        )
    except Exception:
        pass


def step_one(ws, addr, old_pc):
    remove_memcheck(ws, addr)
    try:
        ws.request("cpu.stepInto", timeout=0.5)
    except Exception:
        pass
    end = time.time() + 4.0
    last = None
    while time.time() < end:
        try:
            last = ws.request("cpu.status", timeout=2)
            if (
                last.get("stepping", False)
                and int(last.get("pc", 0)) != old_pc
            ):
                return last
        except Exception:
            pass
        time.sleep(0.01)
    return last


def pointer_samples(ws, regs):
    out = []
    for n in GPR_NAMES:
        if n not in regs:
            continue
        v = regs[n]
        if not (RAM_START <= v < RAM_END):
            continue
        sample_base = max(RAM_START, v - 96)
        try:
            raw = read_ws(ws, sample_base, 320)
        except Exception:
            continue

        p = raw.find(UTF8)
        out.append({
            "register": n,
            "value": f"0x{v:08X}",
            "sample_base": f"0x{sample_base:08X}",
            "utf8_story_address":
                None if p < 0
                else f"0x{sample_base+p:08X}",
            "sample_hex": raw.hex(),
        })
    return out


def trace_one_vertex_writer(ws, addr, expected_uv, label, timeout=120.0):
    add_write_memcheck(ws, addr, label)
    hits = []
    end = time.time() + timeout

    while time.time() < end and len(hits) < MAX_WRITE_HITS:
        resume(ws)
        p = wait_pause(ws, timeout=min(8.0, max(0.2, end-time.time())))
        if p is None:
            continue

        regs = regs_to_dict(
            ws.request("cpu.getAllRegs", timeout=10)
        )
        pc = regs.get("pc", int(p.get("pc", 0)))
        ra = regs.get("ra", 0)

        before = read_ws(ws, addr, 16)
        step_one(ws, addr, pc)
        after = read_ws(ws, addr, 16)

        hit = {
            "pc": f"0x{pc:08X}",
            "ra": f"0x{ra:08X}",
            "before_16": before.hex(),
            "after_16": after.hex(),
            "expected_uv": expected_uv.hex(),
            "after_uv": after[:4].hex(),
            "expected_uv_after": after[:4] == expected_uv,
            "registers": {
                k: f"0x{v:08X}"
                for k, v in regs.items()
                if isinstance(v, int)
            },
        }

        promising = hit["expected_uv_after"]
        if promising or len(hits) < 5:
            hit["pointer_samples"] = pointer_samples(ws, regs)
            hit["instruction_window"] = disasm(
                ws, max(0, pc - 0x80), 80
            )
            hit["caller_window"] = (
                disasm(ws, max(0, ra - 0x60), 64)
                if ra else None
            )

        hits.append(hit)

        if promising:
            return {
                "success": True,
                "writer": hit,
                "hits": hits,
            }

        add_write_memcheck(ws, addr, label)

    remove_memcheck(ws, addr)
    return {
        "success": False,
        "hits": hits,
    }


def make_zip(path):
    if path.exists():
        path.unlink()
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(OUT.rglob("*")):
            if p.is_file():
                z.write(p, p.relative_to(OUT).as_posix())
        z.write(REF_PATH, REF_PATH.name)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    for p in OUT.iterdir():
        if p.is_file():
            p.unlink()

    if not ISO.exists():
        raise RuntimeError(f"Missing ISO: {ISO}")

    ref = REF_PATH.read_bytes()
    if len(ref) != REF_SIZE or sha1(ref) != REF_SHA1:
        raise RuntimeError("Reference vertex batch mismatch")

    _, b = load_helpers()
    exe = b.find_ppsspp_exe()

    cfg = OUT / "stage39n_append.ini"
    cfg.write_text(
        "[Debugger]\nShowDeveloperMenu = True\n\n"
        "[Graphics]\nReplaceTextures = False\nSaveNewTextures = False\n",
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
        "-i",
        "-d",
        f"--log={PPSSPP_LOG}",
        "--windowed",
        f"--appendconfig={cfg}",
        f"--debugger={port}",
        str(ISO),
    ]

    log("[Stage39N] Launching PPSSPP interpreter")
    proc = subprocess.Popen(cmd)
    cleanup = b.register_ppsspp_auto_close(proc)

    report = {
        "stage": "39N",
        "purpose":
            "Locate the Stage39H visible menu vertex buffer while ignoring "
            "animated color/XY bytes, then catch the exact CPU write that "
            "generates its first UV pair.",
        "stage39m_failure":
            "Stage39M searched exact 8-byte+ prefixes. Its minimum prefix "
            "included the 4-byte vertex color (FE000000), which can vary with "
            "menu alpha/animation. Therefore zero exact candidates did not "
            "mean the vertex buffer was absent.",
        "masked_locator": {
            "compared_bytes_per_vertex":
                "UV only: bytes 0..3 of each 16-byte vertex",
            "top_vertices_scored": TOP_VERTICES_TO_SCORE,
            "min_top_uv_ratio": MIN_TOP_UV_RATIO,
            "min_full_uv_ratio": MIN_FULL_UV_RATIO,
        },
        "reference": {
            "size": len(ref),
            "sha1": sha1(ref),
            "first_uv": ref[:4].hex(),
        },
        "iso_patch": False,
        "runtime_patch": False,
    }

    try:
        hwnd = b.find_ppsspp_hwnd(60)
        if not hwnd:
            raise RuntimeError("PPSSPP window did not appear")

        end = time.time() + 60
        pid = base = None
        while time.time() < end:
            try:
                pid, base = b.get_pid_base(hwnd)
                if pid and base:
                    break
            except Exception:
                pass
            time.sleep(0.2)
        if not pid or not base:
            raise RuntimeError("PPSSPP process memory base unavailable")

        report["process"] = {
            "pid": pid,
            "base": f"0x{int(base):X}",
        }

        actual_port = b.wait_for_actual_debugger_port(
            PPSSPP_LOG, 60
        )
        ws, host = b.connect_debugger(actual_port)

        try:
            report["debugger_host"] = host
            report["debugger_port"] = actual_port

            menu = wait_menu_open(ws)
            report["menu_resource_open"] = menu
            if not menu["opened"]:
                raise RuntimeError("MENUINT0.RAW did not open")

            source = wait_source(ws)
            report["source_resident"] = source
            if not source.get("ok"):
                raise RuntimeError("Correct Stage39F source did not become resident")

            try:
                ws.request(
                    "input.buttons.press",
                    timeout=5,
                    button="start",
                    duration=2,
                )
                report["main_menu_start_sent"] = True
            except Exception as e:
                report["main_menu_start_error"] = str(e)

            # Interpreter timing varies. Scan repeatedly while the menu settles.
            searches = []
            loc = None
            for wait_s in (2.0, 4.0, 6.0, 8.0, 12.0):
                time.sleep(2.0 if not searches else max(0.0, wait_s - searches[-1]["elapsed"]))
                current = locate_masked_vertex_buffer(
                    b, pid, base, ref
                )
                searches.append({
                    "elapsed": wait_s,
                    "result": current,
                })
                if current.get("best"):
                    loc = current
                    break

            report["vertex_search_attempts"] = searches

            if loc is None or loc.get("best") is None:
                raise RuntimeError(
                    "Masked UV search could not locate a live main-menu vertex buffer"
                )

            best = loc["best"]
            vertex_addr = int(best["address"])
            report["selected_vertex_buffer"] = {
                **best,
                "address": f"0x{vertex_addr:08X}",
            }

            # Trace the first vertex UV writer.
            trace0 = trace_one_vertex_writer(
                ws,
                vertex_addr,
                ref[:4],
                "VERTEX0_UV",
                timeout=120.0,
            )
            report["first_vertex_writer"] = trace0

            # Independent confirmation: second vertex of the same first sprite.
            trace1 = {"success": False}
            if trace0.get("success"):
                trace1 = trace_one_vertex_writer(
                    ws,
                    vertex_addr + VERTEX_STRIDE,
                    ref[VERTEX_STRIDE:VERTEX_STRIDE+4],
                    "VERTEX1_UV",
                    timeout=30.0,
                )
            report["second_vertex_writer"] = trace1

            w0 = trace0.get("writer", {})
            w1 = trace1.get("writer", {})
            report["writer_analysis"] = {
                "first_writer_pc": w0.get("pc"),
                "second_writer_pc": w1.get("pc"),
                "same_pc":
                    bool(
                        w0.get("pc")
                        and w1.get("pc")
                        and w0.get("pc") == w1.get("pc")
                    ),
                "first_writer_has_nearby_utf8_story":
                    any(
                        x.get("utf8_story_address")
                        for x in w0.get("pointer_samples", [])
                    ),
            }

            report["completed"] = bool(trace0.get("success"))

        finally:
            try:
                ws.close()
            except Exception:
                pass

    except Exception as e:
        report["runtime_exception"] = str(e)
        report["runtime_traceback"] = traceback.format_exc()
        report["completed"] = False

    finally:
        try:
            cleanup()
            report["ppsspp_closed"] = True
        except Exception as e:
            report["ppsspp_close_error"] = str(e)

    REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    target = SUCCESS_ZIP if report["completed"] else FAIL_ZIP
    make_zip(target)

    if not report["completed"]:
        raise RuntimeError(f"Stage39N failed. See {FAIL_ZIP}")

    log("[Stage39N] COMPLETE")
    log(f"[Stage39N] Upload ZIP: {SUCCESS_ZIP}")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        OUT.mkdir(parents=True, exist_ok=True)
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        (OUT / "FAILURE.txt").write_text(
            traceback.format_exc(), encoding="utf-8"
        )
        try:
            make_zip(FAIL_ZIP)
        except Exception:
            pass
        print(traceback.format_exc(), flush=True)
        print(f"STAGE 39N FAILED: {FAIL_ZIP}", flush=True)
        raise SystemExit(1)
