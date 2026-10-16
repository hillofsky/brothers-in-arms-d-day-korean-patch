#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import base64
import importlib.util
import json
import re
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

OUT = ROOT / "analysis" / "stage39o_frozen_vertex_writer"
LOG_DIR = ROOT / "log"

SUCCESS_ZIP = LOG_DIR / "bia_stage39o_upload.zip"
FAIL_ZIP = LOG_DIR / "fail_bia_stage39o_upload.zip"
REPORT_PATH = OUT / "stage39o_report.json"
PPSSPP_LOG = OUT / "stage39o_ppsspp.log"

REF_PATH = Path(__file__).resolve().parent / "stage39h_mainmenu_vertices.bin"
REF_SIZE = 1984
REF_SHA1 = "e1c87ada5beaee44f68e1f4e5f1f1037eaaa3ad7"

# Correct Stage39F localization state.
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

# Main user RAM.  Stage39N searched this while the CPU was still running.
RAM_START = 0x08800000
RAM_END = 0x0A800000
RAM_CHUNK = 0x00080000

# Also inspect PSP VRAM.  GE vertex buffers are allowed to live here.
VRAM_START = 0x04000000
VRAM_END = 0x04200000
VRAM_CHUNK = 0x00010000

VERTEX_STRIDE = 16
UV_SIZE = 4

# First 36 vertices = nine visible corrupted sprites plus their shadow pass.
TOP_VERTEX_COUNT = 36

# Frozen memory should give a very strong sequence match.
MIN_TOP_UV_RATIO = 0.88
MIN_FULL_UV_RATIO = 0.50

# The first two UV pairs alone are already distinctive:
#   v0 = (107,0)
#   v1 = (114,16)
FIRST_UV = bytes.fromhex("6b000000")
SECOND_UV = bytes.fromhex("72001000")

# Try several frozen instants.  The game's transient/ring vertex buffer may
# only contain this batch during part of a frame.
FREEZE_CYCLES = 8
RUN_BETWEEN_FREEZES = 0.12

MAX_CANDIDATES_TO_WATCH = 8
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
        raise RuntimeError("Could not resolve Stage39B helper module")

    return mod, b


def read_ws(ws, addr, size):
    r = ws.request(
        "memory.read",
        timeout=10,
        address=addr,
        size=size,
    )
    return base64.b64decode(r["base64"])


def regs_to_dict(resp):
    out = {}
    for cat in resp.get("categories", []):
        for name, value in zip(
            cat.get("registerNames", []),
            cat.get("uintValues", []),
        ):
            out[name.lower()] = int(value) & 0xFFFFFFFF
    return out


def disasm(ws, addr, count=80):
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
        ws.request("cpu.resume", timeout=0.5)
    except Exception:
        pass


def pause_cpu(ws, timeout=8.0):
    """
    cpu.stepping has intentionally no immediate response in PPSSPP.
    Send it and poll cpu.status until stepping=true.
    """
    try:
        ws.request("cpu.stepping", timeout=0.3)
    except Exception:
        pass

    end = time.time() + timeout
    last = None
    while time.time() < end:
        try:
            last = ws.request("cpu.status", timeout=2)
            if last.get("stepping", False):
                return last
        except Exception:
            pass
        time.sleep(0.02)

    raise RuntimeError(f"CPU did not enter stepping state: {last}")


def wait_pause(ws, timeout=20.0):
    end = time.time() + timeout
    last = None
    while time.time() < end:
        try:
            last = ws.request("cpu.status", timeout=2)
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
                encoding="utf-8",
                errors="replace",
            )
            if MENU_OPEN_MARKER in txt:
                return {
                    "opened": True,
                    "start_presses": presses,
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
        "start_presses": presses,
    }


def wait_source(ws, timeout=60.0):
    end = time.time() + timeout
    last = {}

    while time.time() < end:
        try:
            d1 = read_ws(ws, DISPLAY1_ADDR, 16)
            d2 = read_ws(ws, DISPLAY2_ADDR, 16)
            m1 = struct.unpack(
                "<III", read_ws(ws, META1_ADDR, 12)
            )
            m2 = struct.unpack(
                "<III", read_ws(ws, META2_ADDR, 12)
            )

            last = {
                "display1": d1.hex(),
                "display2": d2.hex(),
                "meta1": [
                    f"0x{m1[0]:08X}", m1[1], m1[2]
                ],
                "meta2": [
                    f"0x{m2[0]:08X}", m2[1], m2[2]
                ],
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

        time.sleep(0.1)

    last["ok"] = False
    return last


def guest_read_host(b, pid, base, addr, size):
    h = b.open_process(pid)
    try:
        return b.guest_read(h, base, addr, size)
    finally:
        b.kernel32.CloseHandle(h)


def scan_main_ram_frozen(b, pid, base):
    """
    The CPU MUST already be stepping.  Search main RAM without allowing the
    transient ring buffer to change underneath the scan.
    """
    hits = []
    h = b.open_process(pid)

    try:
        addr = RAM_START
        carry = b""
        carry_addr = RAM_START

        while addr < RAM_END:
            size = min(RAM_CHUNK, RAM_END - addr)

            try:
                chunk = b.guest_read(
                    h, base, addr, size
                )
            except Exception:
                chunk = b"\x00" * size

            data = carry + chunk if carry else chunk
            data_base = carry_addr if carry else addr

            pos = 0
            while True:
                p = data.find(FIRST_UV, pos)
                if p < 0:
                    break

                g = data_base + p

                # Cheap discriminator before full scoring:
                # second vertex must begin 16 bytes later.
                if (
                    p + VERTEX_STRIDE + UV_SIZE
                    <= len(data)
                    and data[
                        p + VERTEX_STRIDE:
                        p + VERTEX_STRIDE + UV_SIZE
                    ] == SECOND_UV
                ):
                    hits.append(g)

                pos = p + 1

            carry_len = VERTEX_STRIDE + UV_SIZE - 1
            carry = data[-carry_len:]
            carry_addr = addr + size - len(carry)
            addr += size

    finally:
        b.kernel32.CloseHandle(h)

    return sorted(set(hits))


def scan_vram_frozen(ws):
    """
    Use debugger memory.read for VRAM so this does not assume the host helper's
    RAM mapping also covers VRAM.
    """
    hits = []
    addr = VRAM_START
    carry = b""
    carry_addr = VRAM_START

    while addr < VRAM_END:
        size = min(VRAM_CHUNK, VRAM_END - addr)

        try:
            chunk = read_ws(ws, addr, size)
        except Exception:
            chunk = b"\x00" * size

        data = carry + chunk if carry else chunk
        data_base = carry_addr if carry else addr

        pos = 0
        while True:
            p = data.find(FIRST_UV, pos)
            if p < 0:
                break

            g = data_base + p
            if (
                p + VERTEX_STRIDE + UV_SIZE
                <= len(data)
                and data[
                    p + VERTEX_STRIDE:
                    p + VERTEX_STRIDE + UV_SIZE
                ] == SECOND_UV
            ):
                hits.append(g)

            pos = p + 1

        carry_len = VERTEX_STRIDE + UV_SIZE - 1
        carry = data[-carry_len:]
        carry_addr = addr + size - len(carry)
        addr += size

    return sorted(set(hits))


def uv_score(blob, ref):
    n = min(
        len(blob) // VERTEX_STRIDE,
        len(ref) // VERTEX_STRIDE,
    )
    matches = []

    for i in range(n):
        a = blob[
            i*VERTEX_STRIDE:
            i*VERTEX_STRIDE + UV_SIZE
        ]
        r = ref[
            i*VERTEX_STRIDE:
            i*VERTEX_STRIDE + UV_SIZE
        ]
        matches.append(a == r)

    top_n = min(TOP_VERTEX_COUNT, len(matches))
    top_ratio = (
        sum(matches[:top_n]) / top_n
        if top_n else 0.0
    )
    full_ratio = (
        sum(matches) / len(matches)
        if matches else 0.0
    )

    return top_ratio, full_ratio, matches


def read_candidate(
    b,
    ws,
    pid,
    base,
    addr,
    size,
):
    if RAM_START <= addr < RAM_END:
        return guest_read_host(
            b, pid, base, addr, size
        )

    if VRAM_START <= addr < VRAM_END:
        return read_ws(ws, addr, size)

    raise RuntimeError(
        f"Unsupported candidate address 0x{addr:08X}"
    )


def score_hits(
    b,
    ws,
    pid,
    base,
    hits,
    region,
    ref,
):
    scored = []

    for addr in hits:
        try:
            blob = read_candidate(
                b, ws, pid, base, addr, len(ref)
            )
        except Exception:
            continue

        top_ratio, full_ratio, matches = uv_score(
            blob, ref
        )

        scored.append({
            "address": addr,
            "address_hex": f"0x{addr:08X}",
            "region": region,
            "top_uv_ratio": top_ratio,
            "full_uv_ratio": full_ratio,
            "first_40_uv_matches": matches[:40],
            "first_64_hex": blob[:64].hex(),
        })

    scored.sort(
        key=lambda x: (
            x["top_uv_ratio"],
            x["full_uv_ratio"],
        ),
        reverse=True,
    )
    return scored


def frozen_search_cycle(
    b,
    ws,
    pid,
    base,
    ref,
    cycle_no,
):
    status = pause_cpu(ws)

    main_hits = scan_main_ram_frozen(
        b, pid, base
    )
    vram_hits = scan_vram_frozen(ws)

    scored = []
    scored += score_hits(
        b, ws, pid, base,
        main_hits, "main_ram", ref,
    )
    scored += score_hits(
        b, ws, pid, base,
        vram_hits, "vram", ref,
    )

    scored.sort(
        key=lambda x: (
            x["top_uv_ratio"],
            x["full_uv_ratio"],
        ),
        reverse=True,
    )

    qualified = [
        x for x in scored
        if (
            x["top_uv_ratio"]
            >= MIN_TOP_UV_RATIO
            and x["full_uv_ratio"]
            >= MIN_FULL_UV_RATIO
        )
    ]

    return {
        "cycle": cycle_no,
        "paused_pc":
            f"0x{int(status.get('pc',0)):08X}",
        "main_two_uv_hits": len(main_hits),
        "vram_two_uv_hits": len(vram_hits),
        "top_candidates": scored[:20],
        "qualified": qualified[:16],
    }


def add_write_bp(ws, addr, label):
    ws.request(
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
            f"BIA39O_{label} "
            "pc={{pc}} ra={{ra}} "
            "a0={{a0}} a1={{a1}} "
            "a2={{a2}} a3={{a3}} "
            "s0={{s0}} s1={{s1}} "
            "s2={{s2}} s3={{s3}} "
            "t0={{t0}} t1={{t1}} "
            "t2={{t2}} t3={{t3}}"
        ),
    )


def remove_write_bp(ws, addr):
    try:
        ws.request(
            "memory.breakpoint.remove",
            timeout=5,
            address=addr,
            size=MEMCHECK_SIZE,
        )
    except Exception:
        pass


def pointer_samples(ws, regs):
    out = []

    for name in GPR_NAMES:
        if name not in regs:
            continue

        value = regs[name]
        if not (
            RAM_START <= value < RAM_END
        ):
            continue

        base = max(RAM_START, value - 128)

        try:
            raw = read_ws(ws, base, 384)
        except Exception:
            continue

        p = raw.find(UTF8)

        out.append({
            "register": name,
            "value": f"0x{value:08X}",
            "sample_base": f"0x{base:08X}",
            "utf8_story_address":
                None if p < 0
                else f"0x{base+p:08X}",
            "sample_hex": raw.hex(),
        })

    return out


def identify_break_address(candidates):
    """
    PPSSPP's log normally prints the memcheck address.  Read the newest matching
    CHK/BIA39O line and map it back to one of our candidate addresses.
    """
    if not PPSSPP_LOG.exists():
        return None, []

    text = PPSSPP_LOG.read_text(
        encoding="utf-8",
        errors="replace",
    )
    lines = text.splitlines()
    interesting = [
        line for line in lines
        if (
            "BIA39O_" in line
            or "CHK Write" in line
        )
    ][-80:]

    lowered = "\n".join(interesting).lower()

    for addr in candidates:
        token = f"{addr:08x}"
        if token in lowered:
            return addr, interesting

    return None, interesting


def trace_writer(
    b,
    ws,
    pid,
    base,
    ref,
    candidates,
):
    watched = candidates[:MAX_CANDIDATES_TO_WATCH]
    addrs = [int(x["address"]) for x in watched]

    for i, addr in enumerate(addrs):
        add_write_bp(
            ws, addr, f"CAND{i}"
        )

    resume(ws)
    paused = wait_pause(ws, timeout=60.0)

    if paused is None:
        for addr in addrs:
            remove_write_bp(ws, addr)
        return {
            "success": False,
            "reason": "no_candidate_write_break",
            "watched": [
                f"0x{x:08X}" for x in addrs
            ],
        }

    regs = regs_to_dict(
        ws.request("cpu.getAllRegs", timeout=10)
    )
    pc = regs.get(
        "pc", int(paused.get("pc", 0))
    )
    ra = regs.get("ra", 0)

    hit_addr, log_tail = identify_break_address(
        addrs
    )

    # If log parsing cannot identify it, select the candidate nearest a
    # register that points inside the watched range.
    if hit_addr is None:
        for addr in addrs:
            for value in regs.values():
                if (
                    isinstance(value, int)
                    and addr - 0x20 <= value
                    < addr + 0x40
                ):
                    hit_addr = addr
                    break
            if hit_addr is not None:
                break

    hit = {
        "pc": f"0x{pc:08X}",
        "ra": f"0x{ra:08X}",
        "hit_address":
            None if hit_addr is None
            else f"0x{hit_addr:08X}",
        "registers": {
            k: f"0x{v:08X}"
            for k, v in regs.items()
            if isinstance(v, int)
        },
        "pointer_samples": pointer_samples(
            ws, regs
        ),
        "instruction_window":
            disasm(ws, max(0, pc - 0x80), 80),
        "caller_window":
            disasm(ws, max(0, ra - 0x60), 64)
            if ra else None,
        "log_tail": log_tail,
    }

    # Remove all candidate memchecks before controlled stepping.
    for addr in addrs:
        remove_write_bp(ws, addr)

    if hit_addr is not None:
        try:
            before = read_candidate(
                b, ws, pid, base,
                hit_addr, 32,
            )
            hit["before_32"] = before.hex()
        except Exception:
            before = None

        # Execute the exact write once.
        try:
            ws.request(
                "cpu.stepInto",
                timeout=0.5,
            )
        except Exception:
            pass

        # Wait until one instruction has executed.
        end = time.time() + 4
        while time.time() < end:
            try:
                st = ws.request(
                    "cpu.status", timeout=2
                )
                if (
                    st.get("stepping", False)
                    and int(st.get("pc", 0))
                    != pc
                ):
                    break
            except Exception:
                pass
            time.sleep(0.01)

        try:
            after = read_candidate(
                b, ws, pid, base,
                hit_addr, 32,
            )
            hit["after_32"] = after.hex()
            hit["uv_after"] = after[:4].hex()

            ref_uv = None
            for c in watched:
                if int(c["address"]) == hit_addr:
                    ref_uv = ref[:4]
                    break

            if ref_uv is not None:
                hit["first_uv_matches_reference"] = (
                    after[:4] == ref_uv
                )
        except Exception:
            pass

    # Independent confirmation: watch vertex #1 at +16 in the same buffer.
    second = None
    if hit_addr is not None:
        addr2 = hit_addr + VERTEX_STRIDE

        add_write_bp(ws, addr2, "SECOND_VERTEX")
        resume(ws)
        p2 = wait_pause(ws, timeout=20.0)

        if p2 is not None:
            r2 = regs_to_dict(
                ws.request(
                    "cpu.getAllRegs",
                    timeout=10,
                )
            )
            second = {
                "pc":
                    f"0x{r2.get('pc',0):08X}",
                "ra":
                    f"0x{r2.get('ra',0):08X}",
                "same_pc_as_first":
                    r2.get("pc",0) == pc,
                "registers": {
                    k: f"0x{v:08X}"
                    for k, v in r2.items()
                    if isinstance(v, int)
                },
                "instruction_window":
                    disasm(
                        ws,
                        max(0, r2.get("pc",0)-0x40),
                        48,
                    ),
            }

        remove_write_bp(ws, addr2)

    return {
        "success": True,
        "watched": [
            f"0x{x:08X}" for x in addrs
        ],
        "first_write": hit,
        "second_vertex_write": second,
    }


def make_zip(path):
    if path.exists():
        path.unlink()

    with zipfile.ZipFile(
        path, "w", zipfile.ZIP_DEFLATED
    ) as z:
        for p in sorted(OUT.rglob("*")):
            if p.is_file():
                z.write(
                    p,
                    p.relative_to(OUT).as_posix(),
                )
        z.write(REF_PATH, REF_PATH.name)


def main():
    OUT.mkdir(
        parents=True, exist_ok=True
    )
    LOG_DIR.mkdir(
        parents=True, exist_ok=True
    )

    for p in OUT.iterdir():
        if p.is_file():
            p.unlink()

    if not ISO.exists():
        raise RuntimeError(
            f"Missing Stage39F ISO: {ISO}"
        )

    ref = REF_PATH.read_bytes()
    if (
        len(ref) != REF_SIZE
        or sha1(ref) != REF_SHA1
    ):
        raise RuntimeError(
            "Reference vertex batch mismatch"
        )

    _, b = load_helpers()
    exe = b.find_ppsspp_exe()

    cfg = OUT / "stage39o_append.ini"
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
        b.close_existing_ppsspp(
            timeout=3.0
        )
    except Exception:
        pass

    port = b.choose_free_port()

    # Interpreter is required for reliable write memchecks.
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

    log(
        "[Stage39O] Launching PPSSPP interpreter"
    )

    proc = subprocess.Popen(cmd)
    cleanup = b.register_ppsspp_auto_close(
        proc
    )

    report = {
        "stage": "39O",
        "purpose":
            "Freeze the emulated CPU before scanning for the transient "
            "main-menu vertex ring buffer, then break on its next write.",
        "stage39n_failure":
            "Stage39N found the first UV pair hundreds of times but no "
            "multi-vertex sequence. Its full-RAM scan and candidate scoring "
            "were performed while the CPU continued running, so a transient "
            "ring buffer could be overwritten between discovery and scoring.",
        "critical_change":
            "Use cpu.stepping to freeze emulation for every scan. Also search "
            "PSP VRAM and require the first two vertex UV pairs before scoring.",
        "reference": {
            "size": len(ref),
            "sha1": sha1(ref),
            "first_uv": FIRST_UV.hex(),
            "second_uv": SECOND_UV.hex(),
        },
        "iso_patch": False,
        "runtime_patch": False,
    }

    try:
        hwnd = b.find_ppsspp_hwnd(60)
        if not hwnd:
            raise RuntimeError(
                "PPSSPP window did not appear"
            )

        end = time.time() + 60
        pid = base = None

        while time.time() < end:
            try:
                pid, base = b.get_pid_base(
                    hwnd
                )
                if pid and base:
                    break
            except Exception:
                pass
            time.sleep(0.2)

        if not pid or not base:
            raise RuntimeError(
                "PPSSPP process memory base unavailable"
            )

        report["process"] = {
            "pid": pid,
            "base": f"0x{int(base):X}",
        }

        actual_port = (
            b.wait_for_actual_debugger_port(
                PPSSPP_LOG, 60
            )
        )
        ws, host = b.connect_debugger(
            actual_port
        )

        try:
            report["debugger_host"] = host
            report["debugger_port"] = (
                actual_port
            )

            menu = wait_menu_open(ws)
            report["menu_resource_open"] = menu

            if not menu["opened"]:
                raise RuntimeError(
                    "MENUINT0.RAW did not open"
                )

            source = wait_source(ws)
            report["source_resident"] = source

            if not source.get("ok"):
                raise RuntimeError(
                    "Correct Stage39F source "
                    "did not become resident"
                )

            # Enter selectable main menu once.
            try:
                ws.request(
                    "input.buttons.press",
                    timeout=5,
                    button="start",
                    duration=2,
                )
                report[
                    "main_menu_start_sent"
                ] = True
            except Exception as e:
                report[
                    "main_menu_start_error"
                ] = str(e)

            # Allow title->menu transition and animation to settle.
            time.sleep(6.0)

            cycles = []
            qualified = []

            for cycle_no in range(
                1, FREEZE_CYCLES + 1
            ):
                if cycle_no > 1:
                    resume(ws)
                    time.sleep(
                        RUN_BETWEEN_FREEZES
                    )

                cycle = frozen_search_cycle(
                    b,
                    ws,
                    pid,
                    base,
                    ref,
                    cycle_no,
                )
                cycles.append(cycle)

                if cycle["qualified"]:
                    qualified = (
                        cycle["qualified"]
                    )
                    break

            report[
                "frozen_search_cycles"
            ] = cycles

            if not qualified:
                raise RuntimeError(
                    "No frozen main-RAM/VRAM "
                    "vertex buffer matched the "
                    "Stage39H UV sequence"
                )

            # CPU is still paused from the successful frozen scan.
            report[
                "selected_candidates"
            ] = qualified[
                :MAX_CANDIDATES_TO_WATCH
            ]

            trace = trace_writer(
                b,
                ws,
                pid,
                base,
                ref,
                qualified,
            )
            report["writer_trace"] = trace

            report["completed"] = bool(
                trace.get("success")
            )

        finally:
            try:
                ws.close()
            except Exception:
                pass

    except Exception as e:
        report["runtime_exception"] = str(e)
        report["runtime_traceback"] = (
            traceback.format_exc()
        )
        report["completed"] = False

    finally:
        try:
            cleanup()
            report["ppsspp_closed"] = True
        except Exception as e:
            report[
                "ppsspp_close_error"
            ] = str(e)

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
            f"Stage39O failed. See {FAIL_ZIP}"
        )

    log("[Stage39O] COMPLETE")
    log(
        f"[Stage39O] Upload ZIP: {SUCCESS_ZIP}"
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        OUT.mkdir(
            parents=True, exist_ok=True
        )
        LOG_DIR.mkdir(
            parents=True, exist_ok=True
        )

        (OUT / "FAILURE.txt").write_text(
            traceback.format_exc(),
            encoding="utf-8",
        )

        try:
            make_zip(FAIL_ZIP)
        except Exception:
            pass

        print(
            traceback.format_exc(),
            flush=True,
        )
        print(
            f"STAGE 39O FAILED: {FAIL_ZIP}",
            flush=True,
        )
        raise SystemExit(1)
