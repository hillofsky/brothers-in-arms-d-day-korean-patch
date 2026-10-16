#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import base64
import importlib.util
import json
import os
import subprocess
import sys
import time
import traceback
import zipfile
from pathlib import Path

ROOT = Path(r"PROJECT_ROOT")
BASE_TOOLS = ROOT / "bia_stage39b_tools"

SOURCE_ISO = ROOT / "BIA_STAGE39C_COMPILED_LOCALIZATION_TEST.iso"

OUT = ROOT / "analysis" / "stage39e_widen_writer_trace"
LOG_DIR = ROOT / "log"

SUCCESS_ZIP = LOG_DIR / "bia_stage39e_upload.zip"
FAIL_ZIP = LOG_DIR / "fail_bia_stage39e_upload.zip"

PPSSPP_LOG = OUT / "stage39e_ppsspp.log"
REPORT_PATH = OUT / "stage39e_report.json"
TRACE_PATH = OUT / "stage39e_writer_trace.json"
SCREENSHOT = OUT / "stage39e_menu.png"
GPU_DUMP = OUT / "stage39e_menu.ppdmp"

# Stage39C observed the UTF-8 bytes widened byte-by-byte here.
# Unlike the old 0x08E41620 Story slot, this is NOT assumed to be the final
# display string; it is used only as a known write target to catch the writer.
WIDE_COPY_ADDR = 0x08E4E82C

TEST_TEXT = "\uc2a4\ud1a0\ub9ac"
TEST_UTF8 = TEST_TEXT.encode("utf-8")
BYTEWISE_WIDENED = b"".join(bytes((b, 0)) for b in TEST_UTF8)
TRUE_UTF16 = TEST_TEXT.encode("utf-16le")

# Stage39C narrow source values in MDI stream11.
SOURCE_ADDRS = [0x093B1B40, 0x093B1BB4]
SOURCE_SCAN_LO = min(SOURCE_ADDRS) - 0x40
SOURCE_SCAN_HI = max(SOURCE_ADDRS) + 0x80

MAX_MEMCHECK_HITS = 96
TIMEOUT_SECONDS = 360.0

GPR_NAMES = [
    "zero","at","v0","v1","a0","a1","a2","a3",
    "t0","t1","t2","t3","t4","t5","t6","t7",
    "s0","s1","s2","s3","s4","s5","s6","s7",
    "t8","t9","k0","k1","gp","sp","fp","ra","pc",
]


def log(msg: str):
    print(msg, flush=True)


def load_helpers():
    module_path = BASE_TOOLS / "bia_stage39b_compiled_mdi_text.py"
    if not module_path.exists():
        raise RuntimeError(f"Missing Stage39B helper: {module_path}")

    sys.path.insert(0, str(BASE_TOOLS))
    spec = importlib.util.spec_from_file_location(
        "bia_stage39b_local",
        module_path,
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)

    b = getattr(mod, "b", None)
    if b is None and hasattr(mod, "s39"):
        b = getattr(mod.s39, "b", None)
    if b is None:
        raise RuntimeError("Could not resolve Stage39B base helpers")
    return mod, b


def find_callable(objects, name):
    for obj in objects:
        if obj is not None and hasattr(obj, name):
            fn = getattr(obj, name)
            if callable(fn):
                return fn
    return None


def regs_to_dict(resp):
    out = {}
    for cat in resp.get("categories", []):
        names = cat.get("registerNames", [])
        vals = cat.get("uintValues", [])
        for n, v in zip(names, vals):
            out[n.lower()] = int(v) & 0xFFFFFFFF
    return out


def read_bytes(ws, addr, size):
    r = ws.request(
        "memory.read",
        timeout=10,
        address=addr,
        size=size,
    )
    return base64.b64decode(r["base64"])


def disasm(ws, addr, count=32):
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


def add_mem_breakpoint(ws):
    return ws.request(
        "memory.breakpoint.add",
        timeout=10,
        address=WIDE_COPY_ADDR,
        size=len(BYTEWISE_WIDENED) + 2,
        enabled=True,
        log=True,
        write=True,
        change=True,
        logFormat=(
            "BIA_STAGE39E_WIDE_WRITE "
            "pc={pc} ra={ra} "
            "a0={a0} a1={a1} a2={a2} a3={a3} "
            "s0={s0} s1={s1} s2={s2} s3={s3} "
            "t0={t0} t1={t1} t2={t2} t3={t3}"
        ),
    )


def remove_mem_breakpoint(ws):
    try:
        ws.request(
            "memory.breakpoint.remove",
            timeout=10,
            address=WIDE_COPY_ADDR,
            size=len(BYTEWISE_WIDENED) + 2,
        )
    except Exception:
        pass


def resume_cpu(ws):
    try:
        ws.request("cpu.resume", timeout=1)
    except Exception:
        # Some PPSSPP builds do not reply to this event immediately.
        pass


def step_one(ws, old_pc):
    """
    Interpreter memchecks trip before the memory instruction executes.
    Temporarily removing the memcheck and stepping once lets us compare the
    target buffer before and after the exact instruction.
    """
    remove_mem_breakpoint(ws)

    try:
        ws.request("cpu.stepInto", timeout=0.5)
    except Exception:
        pass

    end = time.time() + 5.0
    last = None
    while time.time() < end:
        try:
            last = ws.request("cpu.status", timeout=2)
            pc = int(last.get("pc", 0))
            if last.get("stepping", False) and pc != old_pc:
                break
        except Exception:
            pass
        time.sleep(0.01)

    add_mem_breakpoint(ws)
    return last


def wait_pause(ws, deadline, press_start=True):
    last_press = 0.0
    presses = 0
    last = None

    while time.time() < deadline:
        try:
            last = ws.request("cpu.status", timeout=3)
        except Exception:
            time.sleep(0.05)
            continue

        if last.get("stepping", False):
            return last, presses

        now = time.time()
        if press_start and now - last_press >= 0.75:
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

        time.sleep(0.05)

    raise RuntimeError(
        f"Timed out waiting for memory writer; last={last}"
    )


def relevant_registers(ws, regs):
    """
    Find GPRs that point into the known narrow source area or the widened
    destination area.  This often identifies the source/destination registers
    without assuming them in advance.
    """
    out = []
    for name in GPR_NAMES:
        if name not in regs:
            continue
        v = int(regs[name]) & 0xFFFFFFFF

        role = None
        if SOURCE_SCAN_LO <= v < SOURCE_SCAN_HI:
            role = "near_narrow_source"
        elif WIDE_COPY_ADDR - 0x40 <= v < WIDE_COPY_ADDR + 0x80:
            role = "near_wide_destination"

        if role:
            sample = None
            try:
                sample = read_bytes(ws, v, 24).hex()
            except Exception:
                pass
            out.append({
                "register": name,
                "value": f"0x{v:08X}",
                "role": role,
                "memory_24": sample,
            })
    return out


def prefix_match(a: bytes, b: bytes) -> int:
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n


def trace_writer(ws):
    deadline = time.time() + TIMEOUT_SECONDS
    hits = []
    start_presses_total = 0

    for hit_no in range(1, MAX_MEMCHECK_HITS + 1):
        status, presses = wait_pause(
            ws, deadline, press_start=True
        )
        start_presses_total += presses

        regs_resp = ws.request("cpu.getAllRegs", timeout=10)
        regs = regs_to_dict(regs_resp)
        pc = int(regs.get("pc", status.get("pc", 0)))
        ra = int(regs.get("ra", 0))

        before = read_bytes(
            ws,
            WIDE_COPY_ADDR,
            len(BYTEWISE_WIDENED) + 4,
        )

        hit = {
            "hit": hit_no,
            "pc": f"0x{pc:08X}",
            "ra": f"0x{ra:08X}",
            "buffer_before_hex": before.hex(),
            "bytewise_prefix_before":
                prefix_match(before, BYTEWISE_WIDENED),
            "true_utf16_prefix_before":
                prefix_match(before, TRUE_UTF16),
            "registers": {
                name: f"0x{int(regs[name]) & 0xFFFFFFFF:08X}"
                for name in GPR_NAMES
                if name in regs
            },
            "pointer_candidates": relevant_registers(ws, regs),
            "instruction_window": disasm(
                ws,
                max(0, pc - 0x30),
                28,
            ),
            "caller_window": disasm(
                ws,
                max(0, ra - 0x20),
                20,
            ) if ra else None,
        }

        # Memchecks in the interpreter trip BEFORE the access.  Execute the
        # exact instruction once without the memcheck, then inspect what changed.
        step_status = step_one(ws, pc)

        after = read_bytes(
            ws,
            WIDE_COPY_ADDR,
            len(BYTEWISE_WIDENED) + 4,
        )

        hit["buffer_after_hex"] = after.hex()
        hit["bytewise_prefix_after"] = prefix_match(
            after, BYTEWISE_WIDENED
        )
        hit["true_utf16_prefix_after"] = prefix_match(
            after, TRUE_UTF16
        )
        hit["changed_offsets"] = [
            i for i, (x, y) in enumerate(zip(before, after))
            if x != y
        ]
        hit["step_status"] = step_status

        hits.append(hit)

        if after.startswith(BYTEWISE_WIDENED):
            return {
                "success": True,
                "reason": "complete_bytewise_widened_target_observed",
                "hits": hits,
                "start_presses_total": start_presses_total,
                "writer_pc": hit["pc"],
                "writer_ra": hit["ra"],
            }

        # If the corrected UTF-16 text somehow already appears, record that
        # separately.  Stage39E is a diagnostic and does not assume which form.
        if after.startswith(TRUE_UTF16):
            return {
                "success": True,
                "reason": "true_utf16_target_observed",
                "hits": hits,
                "start_presses_total": start_presses_total,
                "writer_pc": hit["pc"],
                "writer_ra": hit["ra"],
            }

        resume_cpu(ws)

    return {
        "success": False,
        "reason": "hit_limit_without_target",
        "hits": hits,
        "start_presses_total": start_presses_total,
    }


def runtime(local_mod, b):
    exe = b.find_ppsspp_exe()

    cfg = OUT / "stage39e_append.ini"
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
        previous = b.close_existing_ppsspp(timeout=3.0)
    except Exception:
        previous = None

    requested_port = b.choose_free_port()

    # Interpreter is intentional. PPSSPP checks memory breakpoints before the
    # memory instruction in the interpreter; this gives an exact writer PC.
    cmd = [
        str(exe),
        "-i",
        "-d",
        f"--log={PPSSPP_LOG}",
        "--windowed",
        f"--appendconfig={cfg}",
        f"--debugger={requested_port}",
        str(SOURCE_ISO),
    ]

    log("[Stage39E] Launching PPSSPP interpreter for exact write trace")
    proc = subprocess.Popen(cmd)
    cleanup = b.register_ppsspp_auto_close(proc)

    result = {
        "ppsspp_exe": str(exe),
        "pid": proc.pid,
        "interpreter_mode": True,
        "previous_ppsspp_cleanup": previous,
        "runtime_patch": False,
        "source_iso": str(SOURCE_ISO),
    }

    try:
        hwnd = b.find_ppsspp_hwnd(60)
        if not hwnd:
            raise RuntimeError("PPSSPP window did not appear")

        port = b.wait_for_actual_debugger_port(
            PPSSPP_LOG, 60
        )
        ws, host = b.connect_debugger(port)

        try:
            result["debugger_host"] = host
            result["debugger_port"] = port

            try:
                result["version"] = ws.request(
                    "version",
                    timeout=5,
                    name="bia-stage39e",
                    version="1",
                )
            except Exception as e:
                result["version_error"] = str(e)

            # Add once before reset and again after reset defensively.
            add_mem_breakpoint(ws)
            try:
                result["mem_breakpoints_before_reset"] = ws.request(
                    "memory.breakpoint.list",
                    timeout=5,
                )
            except Exception as e:
                result["mem_breakpoint_list_error"] = str(e)

            try:
                ws.request("game.reset", timeout=10)
            except Exception as e:
                result["game_reset_response"] = str(e)

            time.sleep(1.0)
            try:
                add_mem_breakpoint(ws)
            except Exception:
                pass

            trace = trace_writer(ws)
            result["writer_trace_summary"] = {
                k: v for k, v in trace.items()
                if k != "hits"
            }

            TRACE_PATH.write_text(
                json.dumps(
                    trace,
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            result["target_after_trace_hex"] = read_bytes(
                ws,
                WIDE_COPY_ADDR,
                len(BYTEWISE_WIDENED) + 4,
            ).hex()

            # Stop input permanently after the writer is captured.
            remove_mem_breakpoint(ws)
            resume_cpu(ws)
            time.sleep(1.0)

            # Production font verifier is useful but not required for the
            # pure writer-trace diagnostic.
            inspect = find_callable(
                [
                    local_mod,
                    getattr(local_mod, "s39", None),
                    b,
                ],
                "inspect_production_runtime",
            )
            plan_path = BASE_TOOLS / "stage39a_font_plan.json"
            if inspect and plan_path.exists():
                try:
                    plan = json.loads(
                        plan_path.read_text(encoding="utf-8")
                    )
                    # Resolve pid/base only after the trace so interpreter boot
                    # has had time to finish loading all modules.
                    pid, base = b.get_pid_base(hwnd)
                    result["production_font_runtime"] = inspect(
                        pid,
                        base,
                        plan,
                        plan["atlas_sha1"],
                    )
                except Exception as e:
                    result["production_font_runtime_error"] = str(e)

            capture_fn = find_callable(
                [b, getattr(local_mod, "s39", None), local_mod],
                "capture",
            )
            helper = BASE_TOOLS / "capture_ppsspp.ps1"
            if capture_fn and helper.exists():
                try:
                    capture_fn(hwnd, SCREENSHOT, helper)
                    result["screenshot"] = str(SCREENSHOT)
                except Exception as e:
                    result["screenshot_error"] = str(e)

            record_fn = find_callable(
                [b, getattr(local_mod, "s39", None), local_mod],
                "record_gpu_frame",
            )
            if record_fn:
                try:
                    result["gpu_frame"] = record_fn(
                        ws, GPU_DUMP
                    )
                except Exception as e:
                    result["gpu_frame_error"] = str(e)

            result["writer_confirmed"] = bool(trace.get("success"))

        finally:
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


def make_zip(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(OUT.rglob("*")):
            if p.is_file():
                z.write(p, p.relative_to(OUT).as_posix())


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    for p in OUT.iterdir():
        if p.is_file():
            p.unlink()

    if not SOURCE_ISO.exists():
        raise RuntimeError(f"Missing Stage39C ISO: {SOURCE_ISO}")

    local_mod, b = load_helpers()

    report = {
        "stage": "39E",
        "purpose":
            "Catch the actual instruction that writes the Stage39C observed "
            "byte-wise widened UTF-8 copy, without assuming any decoder function.",
        "stage39d_conclusion":
            "The injected decoder at 0x08CC4390/0x08CC4460 was never executed "
            "for the menu localization path, so 0x08CC4108 is not yet proven "
            "to be this path's converter.",
        "uses_stage39d_decoder_assumption": False,
        "uses_old_story_fixed_slot": False,
        "uses_stage39c_wide_copy_only_as_write_target": True,
        "wide_copy_address": f"0x{WIDE_COPY_ADDR:08X}",
        "narrow_source_addresses": [
            f"0x{x:08X}" for x in SOURCE_ADDRS
        ],
        "test_utf8_hex": TEST_UTF8.hex(),
        "expected_bytewise_widened_hex": BYTEWISE_WIDENED.hex(),
        "true_utf16_hex": TRUE_UTF16.hex(),
        "runtime_patch": False,
    }

    try:
        rt = runtime(local_mod, b)
        report["runtime"] = rt
        report["completed"] = bool(
            rt.get("writer_confirmed", False)
        )
    except Exception as e:
        report["runtime_exception"] = str(e)
        report["runtime_traceback"] = traceback.format_exc()
        report["completed"] = False

    REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    if report["completed"]:
        make_zip(SUCCESS_ZIP)
        log("[Stage39E] COMPLETE")
        log(f"[Stage39E] Upload ZIP: {SUCCESS_ZIP}")
        return

    make_zip(FAIL_ZIP)
    raise RuntimeError(
        f"Stage39E writer trace did not complete. See {FAIL_ZIP}"
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        OUT.mkdir(parents=True, exist_ok=True)
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        failure = OUT / "FAILURE.txt"
        failure.write_text(
            traceback.format_exc(),
            encoding="utf-8",
        )
        try:
            make_zip(FAIL_ZIP)
        except Exception:
            pass
        print(traceback.format_exc(), flush=True)
        print(f"STAGE 39E FAILED: {FAIL_ZIP}", flush=True)
        raise SystemExit(1)
