#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import base64
import bisect
import csv
import importlib.util
import json
import re
import struct
import subprocess
import sys
import time
import traceback
import zipfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(r"PROJECT_ROOT")
BASE_TOOLS = ROOT / "bia_stage39b_tools"

SOURCE_ISO = ROOT / "BIA_STAGE40F_ON_MEMU_RESIDENT_MASS_TEST.iso"

OUT = ROOT / "analysis" / "stage40i_actual_resource_trace"
LOG_DIR = ROOT / "log"

SUCCESS_ZIP = LOG_DIR / "bia_stage40i_upload.zip"
FAIL_ZIP = LOG_DIR / "fail_bia_stage40i_upload.zip"
REPORT_PATH = OUT / "stage40i_report.json"
PPSSPP_LOG = OUT / "stage40i_ppsspp.log"

RENDER_CALL_RUNTIME = 0x08972360
EXPECTED_RENDER_JAL_RUNTIME = bytes.fromhex("e410330e")
FONT_OBJECT = 0x0972385C
EXPECTED_GLYPH_COUNT = 847
EXPECTED_GLYPH_PTR = 0x098F5020

MENU_OPEN_MARKER = (
    "sceIoOpen(disc0:/PSP_GAME/USRDIR/SYSTEM/RAWFILES/MENUINT0.RAW"
)

RAM_START = 0x08000000
RAM_END = 0x0A000000
RAM_CHUNK = 0x20000
ISO_CHUNK = 0x400000

PROBES = [
    {
        "id": "BIA-00514",
        "key": "MENU0PTION_CONTROLLER_CONFIG",
        "english": "Controls Config",
        "korean": "조작 설정",
    },
    {
        "id": "BIA-00625",
        "key": "MENU0PTION_CONTROLLER_HORZ_SEN",
        "english": "Horizontal Sensitivity",
        "korean": "수평 감도",
    },
    {
        "id": "BIA-01052",
        "key": "MENU0PTION_CONTROLLER_VERT_SEN",
        "english": "Vertical Sensitivity",
        "korean": "수직 감도",
    },
    {
        "id": "BIA-01054",
        "key": "MENU0PTION_CONTROLLER_VIBRATION",
        "english": "Vibration",
        "korean": "진동",
    },
]


def log(msg):
    print(msg, flush=True)


def load_helpers():
    p = BASE_TOOLS / "bia_stage39b_compiled_mdi_text.py"
    if not p.exists():
        raise RuntimeError(f"Missing Stage39B helper: {p}")

    sys.path.insert(0, str(BASE_TOOLS))
    spec = importlib.util.spec_from_file_location(
        "bia_stage39b_local",
        p,
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


# ---------------------------------------------------------------------------
# ISO9660 inventory
# ---------------------------------------------------------------------------

def read_dir_record(buf, off):
    length = buf[off]
    if length == 0:
        return None, off + 1

    rec = buf[off:off+length]
    if len(rec) < 34:
        return None, off + length

    extent = int.from_bytes(rec[2:6], "little")
    size = int.from_bytes(rec[10:14], "little")
    flags = rec[25]
    nlen = rec[32]
    name = rec[33:33+nlen]

    return {
        "extent_lba": extent,
        "size": size,
        "flags": flags,
        "name_raw": name,
    }, off + length


def normalize_iso_name(raw):
    if raw == b"\x00":
        return "."
    if raw == b"\x01":
        return ".."

    name = raw.decode("ascii", errors="replace")
    name = name.split(";", 1)[0]

    if name.endswith("."):
        name = name[:-1]

    return name


def iso_inventory(iso_path):
    sector = 2048
    records = []
    visited_dirs = set()

    with iso_path.open("rb") as f:
        f.seek(16 * sector)
        pvd = f.read(sector)

        if len(pvd) != sector or pvd[1:6] != b"CD001":
            raise RuntimeError("Not a valid ISO9660 PVD")

        root_len = pvd[156]
        root = pvd[156:156+root_len]
        root_extent = int.from_bytes(root[2:6], "little")
        root_size = int.from_bytes(root[10:14], "little")

        def walk_dir(extent, size, prefix):
            key = (extent, size)
            if key in visited_dirs:
                return
            visited_dirs.add(key)

            f.seek(extent * sector)
            data = f.read(size)

            pos = 0
            while pos < len(data):
                # Zero means advance to next sector boundary.
                if data[pos] == 0:
                    pos = ((pos // sector) + 1) * sector
                    continue

                rec, nxt = read_dir_record(data, pos)
                pos = nxt

                if not rec:
                    continue

                name = normalize_iso_name(rec["name_raw"])
                if name in (".", ".."):
                    continue

                path = f"{prefix}/{name}" if prefix else name
                is_dir = bool(rec["flags"] & 0x02)

                item = {
                    "path": path,
                    "extent_lba": rec["extent_lba"],
                    "byte_offset": rec["extent_lba"] * sector,
                    "size": rec["size"],
                    "is_dir": is_dir,
                }
                records.append(item)

                if is_dir:
                    walk_dir(
                        rec["extent_lba"],
                        rec["size"],
                        path,
                    )

        walk_dir(root_extent, root_size, "")

    return records


def map_offset_to_file(file_records, starts, absolute_offset):
    i = bisect.bisect_right(starts, absolute_offset) - 1
    if i < 0:
        return None

    r = file_records[i]
    if absolute_offset < r["byte_offset"] + r["size"]:
        return r

    return None


# ---------------------------------------------------------------------------
# Static source search
# ---------------------------------------------------------------------------

def make_static_patterns():
    patterns = {}

    for p in PROBES:
        patterns[f"{p['id']}:key_ascii"] = p["key"].encode("ascii")
        patterns[f"{p['id']}:english_ascii"] = p["english"].encode("ascii")
        patterns[f"{p['id']}:english_utf16le"] = p["english"].encode("utf-16le")

    return patterns


def raw_iso_search(iso_path, files):
    patterns = make_static_patterns()
    max_len = max(len(x) for x in patterns.values())
    overlap = max_len - 1

    file_records = sorted(
        [r for r in files if not r["is_dir"]],
        key=lambda r: r["byte_offset"],
    )
    starts = [r["byte_offset"] for r in file_records]

    hits = []

    with iso_path.open("rb") as f:
        prev = b""
        absolute = 0

        while True:
            block = f.read(ISO_CHUNK)
            if not block:
                break

            data = prev + block
            base = absolute - len(prev)

            for pname, needle in patterns.items():
                start = 0
                while True:
                    pos = data.find(needle, start)
                    if pos < 0:
                        break

                    abs_off = base + pos
                    rec = map_offset_to_file(
                        file_records,
                        starts,
                        abs_off,
                    )

                    hits.append({
                        "pattern": pname,
                        "absolute_offset": abs_off,
                        "absolute_hex": f"0x{abs_off:X}",
                        "file": rec["path"] if rec else "",
                        "file_offset": (
                            abs_off - rec["byte_offset"]
                            if rec else None
                        ),
                        "file_offset_hex": (
                            f"0x{abs_off-rec['byte_offset']:X}"
                            if rec else ""
                        ),
                        "file_extent_lba": (
                            rec["extent_lba"] if rec else None
                        ),
                        "file_size": (
                            rec["size"] if rec else None
                        ),
                    })

                    start = pos + 1

            prev = data[-overlap:] if overlap else b""
            absolute += len(block)

    # Deduplicate overlap duplicates.
    unique = {}
    for h in hits:
        unique[(h["pattern"], h["absolute_offset"])] = h

    return list(unique.values())


def mdi_decoded_search(iso_path, files, b):
    patterns = make_static_patterns()
    hits = []

    with iso_path.open("rb") as f:
        for rec in files:
            if rec["is_dir"]:
                continue
            if not rec["path"].upper().endswith(".MDI"):
                continue

            f.seek(rec["byte_offset"])
            raw = f.read(rec["size"])

            try:
                streams = b.parse_mdi(raw)
            except Exception:
                continue

            for st in streams:
                data = bytes(st["decoded"])

                for pname, needle in patterns.items():
                    start = 0

                    while True:
                        pos = data.find(needle, start)
                        if pos < 0:
                            break

                        hits.append({
                            "mdi": rec["path"],
                            "stream": st["index"],
                            "decoded_offset": pos,
                            "decoded_offset_hex": f"0x{pos:X}",
                            "pattern": pname,
                        })

                        start = pos + 1

    return hits


def write_tsv(path, rows, fields):
    with path.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as f:
        w = csv.DictWriter(
            f,
            delimiter="\t",
            fieldnames=fields,
            extrasaction="ignore",
        )
        w.writeheader()
        for r in rows:
            w.writerow(r)


# ---------------------------------------------------------------------------
# Runtime trace
# ---------------------------------------------------------------------------

def read_ws(ws, address, size):
    r = ws.request(
        "memory.read",
        timeout=10,
        address=address,
        size=size,
    )
    return base64.b64decode(r["base64"])


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


def press(ws, button, wait=0.45):
    result = {
        "button": button,
    }

    try:
        ws.request(
            "input.buttons.press",
            timeout=4,
            button=button,
            duration=2,
        )
        result["ok"] = True
    except Exception as e:
        result["ok"] = False
        result["error"] = str(e)

    time.sleep(wait)
    return result


def make_runtime_patterns():
    patterns = {}

    for p in PROBES:
        forms = {
            "key_ascii": p["key"].encode("ascii"),
            "key_utf16le": p["key"].encode("utf-16le"),
            "english_ascii": p["english"].encode("ascii"),
            "english_utf16le": p["english"].encode("utf-16le"),
            "korean_utf8": p["korean"].encode("utf-8"),
            "korean_utf16le": p["korean"].encode("utf-16le"),
            "korean_cp949": p["korean"].encode("cp949"),
            "korean_widened_utf8_u16": b"".join(
                bytes((x, 0))
                for x in p["korean"].encode("utf-8")
            ),
            "korean_widened_cp949_u16": b"".join(
                bytes((x, 0))
                for x in p["korean"].encode("cp949")
            ),
        }

        for form, needle in forms.items():
            patterns[f"{p['id']}:{form}"] = needle

    return patterns


def scan_ram(ws):
    patterns = make_runtime_patterns()
    max_len = max(len(x) for x in patterns.values())
    overlap = max_len - 1

    hits = {
        name: []
        for name in patterns
    }

    prev = b""
    addr = RAM_START

    while addr < RAM_END:
        size = min(RAM_CHUNK, RAM_END - addr)

        try:
            block = read_ws(ws, addr, size)
        except Exception as exc:
            raise RuntimeError(f"RAM read failed at 0x{addr:08X}, size 0x{size:X}") from exc
        if len(block) != size:
            raise RuntimeError(f"Incomplete RAM read at 0x{addr:08X}: {len(block)}/{size}")

        data = prev + block
        base = addr - len(prev)

        for name, needle in patterns.items():
            start = 0

            while len(hits[name]) < 32:
                pos = data.find(needle, start)
                if pos < 0:
                    break

                absolute = base + pos
                s = f"0x{absolute:08X}"

                if s not in hits[name]:
                    hits[name].append(s)

                start = pos + 1

        prev = data[-overlap:] if overlap else b""
        addr += size

    return hits


def summarize_runtime_hits(stage, hits):
    rows = []

    for name, addresses in hits.items():
        pid, form = name.split(":", 1)

        for addr in addresses:
            rows.append({
                "stage": stage,
                "probe_id": pid,
                "form": form,
                "address": addr,
            })

    return rows


def runtime_trace(b):
    exe = b.find_ppsspp_exe()

    cfg = OUT / "stage40i_append.ini"
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

    log("[Stage40I] Launching PPSSPP resource trace")
    proc = subprocess.Popen(cmd)
    cleanup = b.register_ppsspp_auto_close(proc)

    result = {
        "pid": proc.pid,
        "stages": [],
    }

    all_rows = []

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

            # Enter selectable top-level menu.
            time.sleep(2.5)
            nav = [press(ws, "start", wait=1.0)]

            hits = scan_ram(ws)
            result["stages"].append({
                "stage": "main_menu",
                "navigation": list(nav),
                "hits": hits,
            })
            all_rows.extend(
                summarize_runtime_hits("main_menu", hits)
            )

            # Story -> Skirmish -> Options, then enter Options.
            nav.extend([
                press(ws, "down"),
                press(ws, "down"),
                press(ws, "cross", wait=1.0),
            ])

            hits = scan_ram(ws)
            result["stages"].append({
                "stage": "options_menu",
                "navigation": list(nav),
                "hits": hits,
            })
            all_rows.extend(
                summarize_runtime_hits("options_menu", hits)
            )

            # Best-effort enter first item of Options, expected controller config
            # on this build. Even if it is not, the trace remains diagnostic.
            nav.append(
                press(ws, "cross", wait=1.0)
            )

            hits = scan_ram(ws)
            result["stages"].append({
                "stage": "options_first_submenu",
                "navigation": list(nav),
                "hits": hits,
            })
            all_rows.extend(
                summarize_runtime_hits(
                    "options_first_submenu",
                    hits,
                )
            )

            glyph_count = int.from_bytes(
                read_ws(ws, FONT_OBJECT + 0x50, 2),
                "little",
            )
            glyph_ptr = int.from_bytes(
                read_ws(ws, FONT_OBJECT + 0x54, 4),
                "little",
            )

            result["font"] = {
                "glyph_count": glyph_count,
                "glyph_count_ok": glyph_count == EXPECTED_GLYPH_COUNT,
                "glyph_ptr": f"0x{glyph_ptr:08X}",
                "glyph_ptr_ok": glyph_ptr == EXPECTED_GLYPH_PTR,
            }

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

    return result, all_rows


def parse_lbn_log(log_path, files):
    if not log_path.exists():
        return []

    text = log_path.read_text(
        encoding="utf-8",
        errors="replace",
    )

    file_by_lba = defaultdict(list)

    for r in files:
        if not r["is_dir"]:
            file_by_lba[r["extent_lba"]].append(r)

    pairs = sorted(set(
        (
            int(a, 16),
            int(b, 16),
        )
        for a, b in re.findall(
            r"sce_lbn0x([0-9A-Fa-f]+)_size0x([0-9A-Fa-f]+)",
            text,
        )
    ))

    rows = []

    for lba, size in pairs:
        matches = file_by_lba.get(lba, [])

        if matches:
            for r in matches:
                rows.append({
                    "lbn": f"0x{lba:X}",
                    "logged_size": f"0x{size:X}",
                    "logged_size_dec": size,
                    "iso_file": r["path"],
                    "iso_file_size": r["size"],
                    "size_matches": r["size"] == size,
                })
        else:
            rows.append({
                "lbn": f"0x{lba:X}",
                "logged_size": f"0x{size:X}",
                "logged_size_dec": size,
                "iso_file": "",
                "iso_file_size": "",
                "size_matches": False,
            })

    return rows


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


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    for p in OUT.iterdir():
        if p.is_file():
            p.unlink()

    report = {
        "stage": "40I",
        "purpose":
            "Trace the actual runtime/source location for the four controller "
            "strings after Stage40H proved that repointing loose LOCALIZE.INT "
            "does not affect RAM.",
        "stage40h_conclusion":
            "All four encoding variants rebuilt and read back correctly, but "
            "none of the four Korean probes appeared anywhere in 32 MiB RAM. "
            "The PPSSPP log only showed LOCALIZE.INT in directory enumeration; "
            "there were zero sceIoOpen() calls naming any .INT file.",
        "source_iso": str(SOURCE_ISO),
    }

    try:
        if not SOURCE_ISO.exists():
            raise RuntimeError(
                f"Missing Stage40F ISO: {SOURCE_ISO}"
            )

        _, b = load_helpers()

        log("[Stage40I] Building ISO9660 inventory")
        files = iso_inventory(SOURCE_ISO)
        report["iso_file_count"] = len(
            [x for x in files if not x["is_dir"]]
        )

        inventory_rows = [
            x for x in files
            if not x["is_dir"]
        ]
        write_tsv(
            OUT / "stage40i_iso_inventory.tsv",
            inventory_rows,
            [
                "path",
                "extent_lba",
                "byte_offset",
                "size",
                "is_dir",
            ],
        )

        log("[Stage40I] Raw ISO probe search")
        raw_hits = raw_iso_search(
            SOURCE_ISO,
            files,
        )
        report["raw_iso_hit_count"] = len(raw_hits)

        write_tsv(
            OUT / "stage40i_iso_raw_hits.tsv",
            raw_hits,
            [
                "pattern",
                "absolute_offset",
                "absolute_hex",
                "file",
                "file_offset",
                "file_offset_hex",
                "file_extent_lba",
                "file_size",
            ],
        )

        log("[Stage40I] Decoded MDI probe search")
        mdi_hits = mdi_decoded_search(
            SOURCE_ISO,
            files,
            b,
        )
        report["mdi_decoded_hit_count"] = len(mdi_hits)

        write_tsv(
            OUT / "stage40i_mdi_decoded_hits.tsv",
            mdi_hits,
            [
                "mdi",
                "stream",
                "decoded_offset",
                "decoded_offset_hex",
                "pattern",
            ],
        )

        log("[Stage40I] Runtime menu/options trace")
        runtime, runtime_rows = runtime_trace(b)
        report["runtime"] = runtime

        write_tsv(
            OUT / "stage40i_runtime_hits.tsv",
            runtime_rows,
            [
                "stage",
                "probe_id",
                "form",
                "address",
            ],
        )

        lbn_rows = parse_lbn_log(
            PPSSPP_LOG,
            files,
        )
        report["raw_lbn_open_count"] = len(lbn_rows)

        write_tsv(
            OUT / "stage40i_lbn_map.tsv",
            lbn_rows,
            [
                "lbn",
                "logged_size",
                "logged_size_dec",
                "iso_file",
                "iso_file_size",
                "size_matches",
            ],
        )

        # Compact summary for quick inspection.
        english_runtime = [
            r for r in runtime_rows
            if r["form"] in (
                "english_ascii",
                "english_utf16le",
            )
        ]
        korean_runtime = [
            r for r in runtime_rows
            if r["form"].startswith("korean_")
        ]
        key_runtime = [
            r for r in runtime_rows
            if r["form"] in (
                "key_ascii",
                "key_utf16le",
            )
        ]

        report["summary"] = {
            "raw_iso_hits": len(raw_hits),
            "decoded_mdi_hits": len(mdi_hits),
            "runtime_english_hits": len(english_runtime),
            "runtime_korean_hits": len(korean_runtime),
            "runtime_key_hits": len(key_runtime),
            "lbn_records": len(lbn_rows),
        }

        report["completed"] = True

    except Exception as e:
        report["exception"] = str(e)
        report["traceback"] = traceback.format_exc()
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
            f"Stage40I failed. See {FAIL_ZIP}"
        )

    log("[Stage40I] COMPLETE")
    log(f"[Stage40I] Upload ZIP: {SUCCESS_ZIP}")


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
            f"STAGE 40I FAILED: {FAIL_ZIP}",
            flush=True,
        )
        raise SystemExit(1)
