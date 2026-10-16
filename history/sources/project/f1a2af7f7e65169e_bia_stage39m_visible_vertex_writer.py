#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import base64
import importlib.util
import json
import os
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

OUT = ROOT / "analysis" / "stage39m_visible_vertex_writer"
LOG_DIR = ROOT / "log"

SUCCESS_ZIP = LOG_DIR / "bia_stage39m_upload.zip"
FAIL_ZIP = LOG_DIR / "fail_bia_stage39m_upload.zip"
REPORT_PATH = OUT / "stage39m_report.json"
PPSSPP_LOG = OUT / "stage39m_ppsspp.log"

REF_PATH = Path(__file__).resolve().parent / "stage39h_mainmenu_vertices.bin"
REF_SHA1 = "e1c87ada5beaee44f68e1f4e5f1f1037eaaa3ad7"
REF_SIZE = 1984

# Correct Stage39F source/metadata.
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

# First sprite of the actually visible corrupted label, from Stage39H PPDMP:
# UV 107,0 -> 114,16; screen 169,68 -> 175,85.
FIRST_VERTEX_16 = bytes.fromhex(
    "6b000000000000fe"  # u=107 v=0 color=FE000000
    "a900440000000b00" # x=169 y=68 z=0 + pad
)
# In case exact color/animation differs, the first 8 bytes of the vertex are
# still useful as a fallback signature.
FIRST_VERTEX_8 = FIRST_VERTEX_16[:8]

MAX_HITS = 160
MEMCHECK_SIZE = 16

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


def disasm(ws, addr, count=64):
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


def wait_pause(ws, timeout=12.0):
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


def guest_scan(b, pid, base, needle):
    """
    Exact byte search of guest RAM via the same proven host ReadProcessMemory
    helper used in Stage39G.
    """
    hits = []
    overlap = max(0, len(needle) - 1)
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

            if tail:
                data = tail + chunk
                data_base = tail_addr
            else:
                data = chunk
                data_base = addr

            pos = 0
            while True:
                p = data.find(needle, pos)
                if p < 0:
                    break
                g = data_base + p
                if RAM_START <= g < RAM_END:
                    hits.append(g)
                pos = p + 1

            if overlap:
                tail = data[-overlap:]
                tail_addr = addr + size - len(tail)

            addr += size
    finally:
        b.kernel32.CloseHandle(h)

    return sorted(set(hits))


def guest_read_direct(b, pid, base, addr, size):
    h = b.open_process(pid)
    try:
        return b.guest_read(h, base, addr, size)
    finally:
        b.kernel32.CloseHandle(h)


def score_candidate(b, pid, base, addr, ref):
    try:
        got = guest_read_direct(b, pid, base, addr, len(ref))
    except Exception:
        return None

    eq = sum(1 for x, y in zip(got, ref) if x == y)
    ratio = eq / max(1, len(ref))

    # Also score the first 18 sprites (the corrupted top item + shadow)
    top_len = 18 * 2 * 16
    top_eq = sum(
        1 for x, y in zip(got[:top_len], ref[:top_len]) if x == y
    )
    top_ratio = top_eq / top_len

    return {
        "address": addr,
        "address_hex": f"0x{addr:08X}",
        "full_match_ratio": ratio,
        "top_label_match_ratio": top_ratio,
        "read_sha1": sha1(got),
        "first_64_hex": got[:64].hex(),
    }


def locate_vertex_buffer(b, pid, base, ref):
    # Strongest signature first.
    prefix64 = ref[:64]
    hits = guest_scan(b, pid, base, prefix64)
    method = "prefix64"

    if not hits:
        hits = guest_scan(b, pid, base, ref[:32])
        method = "prefix32"

    if not hits:
        hits = guest_scan(b, pid, base, ref[:16])
        method = "prefix16"

    if not hits:
        hits = guest_scan(b, pid, base, ref[:8])
        method = "prefix8"

    scored = []
    for addr in hits[:128]:
        s = score_candidate(b, pid, base, addr, ref)
        if s:
            scored.append(s)

    scored.sort(
        key=lambda x: (
            x["top_label_match_ratio"],
            x["full_match_ratio"],
        ),
        reverse=True,
    )

    return {
        "method": method,
        "candidate_count": len(hits),
        "candidates": scored[:16],
        "best": scored[0] if scored else None,
    }


def add_memcheck(ws, addr):
    return ws.request(
        "memory.breakpoint.add",
        timeout=10,
        address=addr,
        size=MEMCHECK_SIZE,
        enabled=True,
        log=True,
        read=False,
        write=True,
        change=True,
        logFormat=(
            "BIA39M_VERTEX_WRITE "
            "pc={pc} ra={ra} "
            "a0={a0} a1={a1} a2={a2} a3={a3} "
            "s0={s0} s1={s1} s2={s2} s3={s3} "
            "s4={s4} s5={s5} s6={s6} s7={s7} "
            "t0={t0} t1={t1} t2={t2} t3={t3}"
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


def single_step_write(ws, addr, old_pc):
    """
    Interpreter memchecks pause before the write. Temporarily remove it,
    single-step the exact writer instruction, then leave the CPU paused.
    """
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
        base = max(RAM_START, v - 96)
        try:
            raw = read_ws(ws, base, 256)
        except Exception:
            continue
        p = raw.find(UTF8)
        out.append({
            "register": n,
            "value": f"0x{v:08X}",
            "sample_base": f"0x{base:08X}",
            "utf8_story_address":
                None if p < 0 else f"0x{base+p:08X}",
            "sample_hex": raw.hex(),
        })
    return out


def trace_writer(ws, vertex_addr, ref):
    expected = ref[:16]
    add_memcheck(ws, vertex_addr)

    hits = []
    end = time.time() + 120.0

    while time.time() < end and len(hits) < MAX_HITS:
        resume(ws)
        p = wait_pause(ws, timeout=8.0)
        if p is None:
            continue

        regs = regs_to_dict(
            ws.request("cpu.getAllRegs", timeout=10)
        )
        pc = regs.get("pc", int(p.get("pc", 0)))
        ra = regs.get("ra", 0)

        try:
            before = read_ws(ws, vertex_addr, 32)
        except Exception:
            before = b""

        single_step_write(ws, vertex_addr, pc)

        try:
            after = read_ws(ws, vertex_addr, 32)
        except Exception:
            after = b""

        hit = {
            "pc": f"0x{pc:08X}",
            "ra": f"0x{ra:08X}",
            "before_32": before.hex(),
            "after_32": after.hex(),
            "first_vertex_exact_after":
                after[:16] == expected,
            "first_vertex_prefix8_after":
                after[:8] == expected[:8],
            "registers": {
                k: f"0x{v:08X}"
                for k, v in regs.items()
                if isinstance(v, int)
            },
        }

        # Only include expensive context for promising hits.
        if (
            hit["first_vertex_exact_after"]
            or hit["first_vertex_prefix8_after"]
            or len(hits) < 6
        ):
            hit["pointer_samples"] = pointer_samples(ws, regs)
            hit["instruction_window"] = disasm(
                ws, max(0, pc - 0x80), 80
            )
            hit["caller_window"] = (
                disasm(ws, max(0, ra - 0x60), 64)
                if ra else None
            )

        hits.append(hit)

        if hit["first_vertex_exact_after"]:
            return {
                "success": True,
                "reason": "exact_first_visible_vertex_written",
                "writer": hit,
                "hits": hits,
            }

        # Re-arm for the next write.
        add_memcheck(ws, vertex_addr)

    remove_memcheck(ws, vertex_addr)
    return {
        "success": False,
        "reason": "writer_not_identified_within_limit",
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
        raise RuntimeError("Stage39H vertex reference mismatch")

    _, b = load_helpers()
    exe = b.find_ppsspp_exe()

    cfg = OUT / "stage39m_append.ini"
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

    # Interpreter mode is required for exact pre-write memory breakpoints.
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

    log("[Stage39M] Launching PPSSPP interpreter")
    proc = subprocess.Popen(cmd)
    cleanup = b.register_ppsspp_auto_close(proc)

    report = {
        "stage": "39M",
        "purpose":
            "Locate the actual Stage39H main-menu vertex buffer in PSP RAM "
            "using the recorded GPU vertex bytes, then break on the exact write "
            "that regenerates the first visible corrupted label sprite.",
        "stage39l_result": {
            "wide_renderer":
                "Confirmed. Actual renderer uses font object 0x0972385C, "
                "glyph_ptr 0x098F5020 and production record for U+C2A4.",
            "old_glyph_array_visible_hypothesis":
                "Not supported; old and new glyph135/136 UV watches did not "
                "produce a non-loader renderer hit.",
            "implication":
                "The visible corrupted label must be traced from the generated "
                "GPU vertex stream rather than inferred from font-array reads.",
        },
        "reference_vertices": {
            "bytes": len(ref),
            "sha1": sha1(ref),
            "source":
                "Stage39H PPDMP entry38, texture 0x0987D020, PRIM count 124",
            "first_visible_sprite":
                "UV (107,0)-(114,16), XY (169,68)-(175,85)",
        },
        "iso_patch": False,
        "runtime_patch": False,
    }

    try:
        hwnd = b.find_ppsspp_hwnd(60)
        if not hwnd:
            raise RuntimeError("PPSSPP window did not appear")

        # Resolve direct guest-memory mapping.
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

            # Enter selectable main menu; no more automatic Start after this.
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

            # Match the Stage39H capture timing and allow animation/state to settle.
            time.sleep(8.0)

            loc = locate_vertex_buffer(b, pid, base, ref)
            report["vertex_buffer_search"] = loc

            best = loc.get("best")
            if best is None:
                raise RuntimeError(
                    "Could not locate Stage39H main-menu vertex signature in guest RAM"
                )

            # Require a strong top-label match before placing the memcheck.
            if best["top_label_match_ratio"] < 0.70:
                raise RuntimeError(
                    "Best vertex candidate is too weak: "
                    f"{best['top_label_match_ratio']:.3f}"
                )

            vertex_addr = int(best["address"])
            report["selected_vertex_buffer"] = f"0x{vertex_addr:08X}"

            trace = trace_writer(ws, vertex_addr, ref)
            report["writer_trace"] = trace
            report["completed"] = bool(trace.get("success"))

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
        raise RuntimeError(f"Stage39M failed. See {FAIL_ZIP}")

    log("[Stage39M] COMPLETE")
    log(f"[Stage39M] Upload ZIP: {SUCCESS_ZIP}")


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
        print(f"STAGE 39M FAILED: {FAIL_ZIP}", flush=True)
        raise SystemExit(1)
