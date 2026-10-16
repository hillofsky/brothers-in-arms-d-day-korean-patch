#!/usr/bin/env python3
from __future__ import annotations

import base64
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
import re
import secrets
import socket
import struct
import subprocess
import time
import traceback
import zipfile
from pathlib import Path

ROOT = Path(r"PROJECT_ROOT")
LOG_DIR = ROOT / "log"
ANALYSIS_DIR = ROOT / "analysis" / "stage18_gpu_frame_dump"

STORY_GUEST = 0x08E41620

WM_APP = 0x8000
WM_USER_GET_BASE_POINTER = WM_APP + 0x3118
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
SW_RESTORE = 9

PROCESS_VM_READ = 0x0010
PROCESS_QUERY_INFORMATION = 0x0400

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
user32 = ctypes.WinDLL("user32", use_last_error=True)

user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
user32.FindWindowW.restype = wintypes.HWND
user32.SendMessageW.argtypes = [
    wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
]
user32.SendMessageW.restype = ctypes.c_ssize_t
user32.PostMessageW.argtypes = [
    wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
]
user32.PostMessageW.restype = wintypes.BOOL
user32.GetWindowThreadProcessId.argtypes = [
    wintypes.HWND, ctypes.POINTER(wintypes.DWORD)
]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.SetForegroundWindow.restype = wintypes.BOOL
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.ShowWindow.restype = wintypes.BOOL

kernel32.OpenProcess.argtypes = [
    wintypes.DWORD, wintypes.BOOL, wintypes.DWORD
]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.ReadProcessMemory.argtypes = [
    wintypes.HANDLE, wintypes.LPCVOID, wintypes.LPVOID,
    ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)
]
kernel32.ReadProcessMemory.restype = wintypes.BOOL
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL


def log(s=""):
    print(s, flush=True)


def find_stage09_memstick():
    summary = ROOT / "analysis" / "stage09_texture_dump" / "summary.json"
    if summary.exists():
        try:
            data = json.loads(summary.read_text(encoding="utf-8"))
            for s in data.get("dump_dirs", []):
                q = Path(s)
                while q != q.parent:
                    if q.name.lower() == "memstick":
                        return q
                    q = q.parent
        except Exception:
            pass

    known = Path(
        r"LOCAL_PATH"
        r"\c-users-admin-downloads\work\ppsspp\memstick"
    )
    return known if known.is_dir() else None


def find_ppsspp_exe():
    candidates = []
    memstick = find_stage09_memstick()
    if memstick:
        base = memstick.parent
        candidates += [
            base / "PPSSPPWindows64.exe",
            base / "PPSSPPDebug64.exe",
            base / "PPSSPPWindows.exe",
        ]

    candidates += [
        ROOT / "PPSSPPWindows64.exe",
        ROOT / "ppsspp" / "PPSSPPWindows64.exe",
    ]

    for p in candidates:
        if p.is_file():
            return p

    codex = Path.home() / "Documents" / "Codex"
    if codex.is_dir():
        for name in ("PPSSPPWindows64.exe", "PPSSPPDebug64.exe"):
            try:
                hits = list(codex.rglob(name))
            except OSError:
                hits = []
            if hits:
                return max(hits, key=lambda p: p.stat().st_mtime_ns)

    raise RuntimeError("PPSSPP executable not found")


def find_original_iso():
    isos = []
    for p in ROOT.glob("*.iso"):
        if not p.is_file():
            continue
        u = p.name.upper()
        if "STAGE" in u or "TEST" in u:
            continue
        isos.append(p)

    if not isos:
        raise RuntimeError(r"Original ISO not found under PROJECT_ROOT")

    named = [
        p for p in isos
        if "BROTHERS" in p.name.upper() or "D-DAY" in p.name.upper()
    ]
    return max(named or isos, key=lambda p: p.stat().st_size)


def write_append_config():
    cfg = ANALYSIS_DIR / "stage18_append.ini"
    cfg.write_text(
        "[Debugger]\n"
        "ShowDeveloperMenu = True\n"
        "\n"
        "[Graphics]\n"
        "ReplaceTextures = False\n"
        "SaveNewTextures = False\n",
        encoding="utf-8"
    )
    return cfg


def choose_free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]
    finally:
        s.close()


def find_ppsspp_hwnd(timeout=30):
    end = time.time() + timeout
    while time.time() < end:
        hwnd = user32.FindWindowW("PPSSPPWnd", None)
        if hwnd:
            return hwnd
        time.sleep(0.25)
    return 0


def get_pid_base(hwnd):
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

    lo = int(user32.SendMessageW(
        hwnd, WM_USER_GET_BASE_POINTER, 0, 0
    )) & 0xFFFFFFFF
    hi = int(user32.SendMessageW(
        hwnd, WM_USER_GET_BASE_POINTER, 0, 1
    )) & 0xFFFFFFFF
    base = (hi << 32) | lo

    if not pid.value or not base:
        raise RuntimeError("Could not obtain PPSSPP PID/base pointer")

    return pid.value, base


def open_process(pid):
    h = kernel32.OpenProcess(
        PROCESS_VM_READ | PROCESS_QUERY_INFORMATION,
        False, pid
    )
    if not h:
        raise RuntimeError(
            f"OpenProcess failed ({ctypes.get_last_error()})"
        )
    return h


def rpm(h, addr, size):
    buf = (ctypes.c_ubyte * size)()
    got = ctypes.c_size_t()
    ok = kernel32.ReadProcessMemory(
        h, ctypes.c_void_p(addr), ctypes.byref(buf),
        size, ctypes.byref(got)
    )
    if not ok or got.value != size:
        raise RuntimeError(
            f"ReadProcessMemory failed at host 0x{addr:X}: "
            f"{got.value}/{size}"
        )
    return bytes(buf)


def guest_read(h, base, guest, size):
    return rpm(h, base + guest, size)


def foreground(hwnd):
    user32.ShowWindow(hwnd, SW_RESTORE)
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.25)


def tap_key(hwnd, vk):
    foreground(hwnd)
    user32.PostMessageW(hwnd, WM_KEYDOWN, vk, 0)
    time.sleep(0.05)
    user32.PostMessageW(hwnd, WM_KEYUP, vk, 0)


def wait_for_story(hwnd, timeout=120):
    end = time.time() + timeout
    next_input = time.time() + 8
    n = 0

    while time.time() < end:
        try:
            pid, base = get_pid_base(hwnd)
            h = open_process(pid)
            try:
                cur = guest_read(h, base, STORY_GUEST, 10)
                if cur == "Story".encode("utf-16le"):
                    return pid, base
            finally:
                kernel32.CloseHandle(h)
        except Exception:
            pass

        if time.time() >= next_input:
            tap_key(hwnd, 0x0D if n % 2 == 0 else 0x5A)
            n += 1
            next_input = time.time() + 5

        time.sleep(0.4)

    raise RuntimeError("Main menu Story state not detected")


def capture(hwnd, path: Path, helper: Path):
    foreground(hwnd)
    p = subprocess.run(
        [
            "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
            "-File", str(helper),
            "-Hwnd", str(int(hwnd)),
            "-OutFile", str(path),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if p.returncode != 0 or not path.exists():
        raise RuntimeError("Screenshot capture faileLOCAL_PATH" + (p.stdout or ""))


class MiniWebSocket:
    def __init__(self, host, port, path="/debugger",
                 protocol="debugger.ppsspp.org", timeout=20.0):
        self.host = host
        self.port = port
        self.path = path
        self.protocol = protocol
        self.timeout = timeout
        self.sock = None
        self.ticket = 1000
        self.unsolicited = []

    def connect(self):
        end = time.time() + 30.0
        last = None
        while time.time() < end:
            try:
                s = socket.create_connection(
                    (self.host, self.port), timeout=2.0
                )
                s.settimeout(self.timeout)
                self.sock = s
                break
            except OSError as e:
                last = e
                time.sleep(0.25)
        if self.sock is None:
            raise RuntimeError(
                f"Could not connect debugger port {self.port}: {last}"
            )

        key = base64.b64encode(secrets.token_bytes(16)).decode("ascii")
        req = (
            f"GET {self.path} HTTP/1.1\r\n"
            f"Host: {self.host}:{self.port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            f"Sec-WebSocket-Protocol: {self.protocol}\r\n"
            "\r\n"
        ).encode("ascii")
        self.sock.sendall(req)

        data = bytearray()
        while b"\r\n\r\n" not in data:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise RuntimeError("Debugger WebSocket handshake closed")
            data.extend(chunk)
            if len(data) > 65536:
                raise RuntimeError("Oversized WebSocket handshake")

        header = bytes(data).split(b"\r\n\r\n", 1)[0]
        line = header.split(b"\r\n", 1)[0]
        if b" 101 " not in line:
            raise RuntimeError(
                "WebSocket upgrade failed: "
                + header.decode("latin1", "replace")
            )

    def close(self):
        if self.sock:
            try:
                self._send_frame(b"", opcode=8)
            except Exception:
                pass
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None

    def _read_exact(self, n):
        out = bytearray()
        while len(out) < n:
            b = self.sock.recv(n - len(out))
            if not b:
                raise EOFError("WebSocket closed")
            out.extend(b)
        return bytes(out)

    def _send_frame(self, payload: bytes, opcode=1):
        # RFC6455: client -> server frames MUST be masked.
        mask = secrets.token_bytes(4)
        n = len(payload)
        first = 0x80 | (opcode & 0x0F)
        if n < 126:
            hdr = bytes([first, 0x80 | n])
        elif n <= 0xFFFF:
            hdr = bytes([first, 0x80 | 126]) + struct.pack(">H", n)
        else:
            hdr = bytes([first, 0x80 | 127]) + struct.pack(">Q", n)
        enc = bytes(
            payload[i] ^ mask[i & 3] for i in range(n)
        )
        self.sock.sendall(hdr + mask + enc)

    def send_json(self, obj):
        raw = json.dumps(
            obj, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")
        self._send_frame(raw, opcode=1)

    def recv_message(self, timeout=None):
        if timeout is not None:
            self.sock.settimeout(timeout)

        msg = bytearray()
        started = False

        while True:
            b1, b2 = self._read_exact(2)
            fin = (b1 & 0x80) != 0
            opcode = b1 & 0x0F
            masked = (b2 & 0x80) != 0
            n = b2 & 0x7F

            if n == 126:
                n = struct.unpack(">H", self._read_exact(2))[0]
            elif n == 127:
                n = struct.unpack(">Q", self._read_exact(8))[0]

            mask = self._read_exact(4) if masked else None
            payload = self._read_exact(n)

            if mask:
                payload = bytes(
                    payload[i] ^ mask[i & 3] for i in range(n)
                )

            if opcode == 9:  # ping
                self._send_frame(payload, opcode=10)
                continue
            if opcode == 10:  # pong
                continue
            if opcode == 8:
                raise EOFError("WebSocket server closed connection")

            if opcode == 1:
                msg = bytearray(payload)
                started = True
            elif opcode == 0 and started:
                msg.extend(payload)
            else:
                # Ignore binary/unknown messages.
                if fin:
                    continue

            if fin and started:
                return msg.decode("utf-8", "replace")

    def request(self, event, timeout=20.0, **params):
        self.ticket += 1
        ticket = self.ticket
        obj = {"event": event, "ticket": ticket}
        obj.update(params)
        self.send_json(obj)

        end = time.time() + timeout
        while time.time() < end:
            remaining = max(0.1, end - time.time())
            raw = self.recv_message(timeout=remaining)
            try:
                msg = json.loads(raw)
            except Exception:
                self.unsolicited.append({
                    "raw_prefix": raw[:1000],
                })
                continue

            if (
                msg.get("ticket") == ticket
                and msg.get("event") == event
            ):
                if msg.get("event") == "error":
                    raise RuntimeError(msg.get("message", "Debugger error"))
                return msg

            if msg.get("event") == "error" and msg.get("ticket") == ticket:
                raise RuntimeError(
                    f"{event}: {msg.get('message', 'debugger error')}"
                )

            self.unsolicited.append(msg)

        raise TimeoutError(f"Timed out waiting for {event}")


def recent_dl_addresses(log_path: Path):
    if not log_path.exists():
        return []
    text = log_path.read_text(encoding="utf-8", errors="replace")
    vals = re.findall(
        r"(?:Starting|Resuming) DL execution at ([0-9A-Fa-f]{8})",
        text
    )
    addrs = []
    for s in vals[-200:]:
        a = int(s, 16)
        if a not in addrs:
            addrs.append(a)
    return addrs[-24:]


def make_zip(path: Path, entries):
    with zipfile.ZipFile(
        path, "w", zipfile.ZIP_DEFLATED, compresslevel=6
    ) as z:
        for src, arc in entries:
            p = Path(src)
            if p.exists():
                z.write(p, arc)


def main():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)

    helper = Path(__file__).resolve().parent / "capture_ppsspp.ps1"
    iso = find_original_iso()
    exe = find_ppsspp_exe()
    cfg = write_append_config()
    debugger_port = choose_free_port()

    report = {
        "stage": 18,
        "purpose": "record PPSSPP GE frame dump and GPU-disassemble live menu display lists",
        "iso": str(iso),
        "ppsspp_exe": str(exe),
        "debugger_port": debugger_port,
    }

    screen = ANALYSIS_DIR / "stage18_menu.png"
    ppsspp_log = ANALYSIS_DIR / "stage18_ppsspp_debug.log"
    ppdmp = ANALYSIS_DIR / "stage18_menu.ppdmp"
    disasm_json = ANALYSIS_DIR / "stage18_gpu_disasm.json"
    ws_events = ANALYSIS_DIR / "stage18_ws_events.json"
    report_path = ANALYSIS_DIR / "stage18_report.json"

    # Fresh emulator so the requested debugger port definitely belongs to us.
    old = user32.FindWindowW("PPSSPPWnd", None)
    if old:
        user32.PostMessageW(old, 0x0010, 0, 0)
        for _ in range(30):
            if not user32.FindWindowW("PPSSPPWnd", None):
                break
            time.sleep(0.2)

    cmd = [
        str(exe),
        "-d",
        f"--log={ppsspp_log}",
        "--windowed",
        f"--appendconfig={cfg}",
        f"--debugger={debugger_port}",
        str(iso),
    ]

    log("=" * 80)
    log("BIA Stage 18 - PPSSPP GE frame dump")
    log("=" * 80)
    log(f"Debugger: wLOCAL_PATH")
    log("[auto] PPSSPP original ISO boot")
    proc = subprocess.Popen(cmd)

    hwnd = find_ppsspp_hwnd(30)
    if not hwnd:
        raise RuntimeError("PPSSPP window did not appear")

    pid, base = wait_for_story(hwnd, 120)
    report["pid"] = pid
    report["psp_base"] = f"0x{base:016X}"
    report["menu_detected"] = True

    capture(hwnd, screen, helper)

    ws = MiniWebSocket("127.0.0.1", debugger_port)
    ws.connect()
    try:
        ver = ws.request(
            "version",
            timeout=10,
            name="bia-stage18",
            version="1",
        )
        report["debugger_version"] = ver

        if int(ver.get("pid", -1)) != pid:
            raise RuntimeError(
                f"Debugger PID mismatch: websocket={ver.get('pid')} "
                f"window={pid}"
            )

        # General known menu command area from Stage17 log.
        disasm = {}
        try:
            disasm["menu_cluster"] = ws.request(
                "gpu.displaylist.disasm",
                timeout=10,
                address=0x08DC9700,
                end=0x08DC9C00,
                compact=False,
            )
        except Exception as e:
            disasm["menu_cluster_error"] = str(e)

        # Ask PPSSPP itself for any currently recent display-list addresses,
        # then decode a small window around each.
        time.sleep(0.5)
        for addr in recent_dl_addresses(ppsspp_log):
            start = max(0x08000000, (addr - 0x40) & ~3)
            key = f"0x{addr:08X}"
            try:
                disasm[key] = ws.request(
                    "gpu.displaylist.disasm",
                    timeout=10,
                    address=start,
                    count=64,
                    compact=False,
                )
            except Exception as e:
                disasm[key] = {"error": str(e)}

        disasm_json.write_text(
            json.dumps(disasm, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        # Record a complete next-frame GPU dump. The response is asynchronous
        # and arrives as one JSON message containing a base64 data URI.
        log("[auto] Recording one complete GPU frame...")
        rec = ws.request(
            "gpu.record.dump",
            timeout=90,
        )
        uri = rec.get("uri", "")
        prefix = "data:application/octet-stream;base64,"
        if not uri.startswith(prefix):
            raise RuntimeError(
                "gpu.record.dump returned no ppdmp data URI"
            )

        raw = base64.b64decode(uri[len(prefix):], validate=False)
        if not raw.startswith(b"PPSSPPGE"):
            raise RuntimeError(
                f"Unexpected frame dump magic: {raw[:16]!r}"
            )
        ppdmp.write_bytes(raw)

        report["ppdmp_bytes"] = len(raw)
        report["ppdmp_sha256"] = hashlib.sha256(raw).hexdigest()
        report["ppdmp_magic"] = raw[:8].decode("ascii", "replace")
        if len(raw) >= 12:
            report["ppdmp_version"] = struct.unpack_from("<I", raw, 8)[0]

        ws_events.write_text(
            json.dumps(ws.unsolicited, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    finally:
        ws.close()

    report["recent_display_list_addresses"] = [
        f"0x{x:08X}" for x in recent_dl_addresses(ppsspp_log)
    ]
    report["completed"] = True
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    upload = LOG_DIR / "bia_stage18_upload.zip"
    make_zip(upload, [
        (report_path, "stage18_report.json"),
        (screen, "stage18_menu.png"),
        (ppdmp, "stage18_menu.ppdmp"),
        (disasm_json, "stage18_gpu_disasm.json"),
        (ws_events, "stage18_ws_events.json"),
        (ppsspp_log, "stage18_ppsspp_debug.log"),
        (cfg, "stage18_append.ini"),
    ])

    log()
    log("=" * 80)
    log("Stage 18 complete")
    log(f"PPDMP : {ppdmp}")
    log(f"Upload: {upload}")
    log("=" * 80)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)

        failure = ANALYSIS_DIR / "FAILURE.txt"
        failure.write_text(traceback.format_exc(), encoding="utf-8")

        fail_zip = LOG_DIR / "fail_bia_stage18_upload.zip"
        try:
            make_zip(fail_zip, [
                (failure, "FAILURE.txt"),
                (
                    ANALYSIS_DIR / "stage18_report.json",
                    "stage18_report.json"
                ),
                (
                    ANALYSIS_DIR / "stage18_menu.png",
                    "stage18_menu.png"
                ),
                (
                    ANALYSIS_DIR / "stage18_menu.ppdmp",
                    "stage18_menu.ppdmp"
                ),
                (
                    ANALYSIS_DIR / "stage18_gpu_disasm.json",
                    "stage18_gpu_disasm.json"
                ),
                (
                    ANALYSIS_DIR / "stage18_ws_events.json",
                    "stage18_ws_events.json"
                ),
                (
                    ANALYSIS_DIR / "stage18_ppsspp_debug.log",
                    "stage18_ppsspp_debug.log"
                ),
                (
                    ANALYSIS_DIR / "stage18_append.ini",
                    "stage18_append.ini"
                ),
            ])
        except Exception:
            pass

        print()
        print("=" * 80)
        print("STAGE 18 FAILED")
        print(f"Failure ZIP: {fail_zip}")
        print("=" * 80)
        traceback.print_exc()
        raise
