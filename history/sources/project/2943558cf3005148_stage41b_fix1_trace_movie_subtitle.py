#!/usr/bin/env python3
import argparse, base64, json, socket, struct, time, secrets, sys
from collections import Counter
from pathlib import Path

RAM_START = 0x08000000
RAM_END   = 0x0A000000
KNOWN_BASE = 0x08E1F21C

NEEDLES = [
    (0x000, "운명의 랑데부".encode("utf-8"), "title"),
    (0x06E, "베이커:".encode("utf-8"), "baker"),
    (0x28F, "맥:".encode("utf-8"), "mac"),
]

# Several records distributed through the ST1.  This avoids missing the trace
# simply because the first subtitle has already been consumed.
WATCH_OFFSETS = [0x000, 0x06E, 0x28F, 0x39E, 0x4B5, 0x55C, 0x59D]

class MiniWS:
    def __init__(self, port, timeout=1.0):
        self.port = port
        self.sock = None
        self.ticket = 1000
        self.pending = []
        last = None
        for af, host in [(socket.AF_INET6, "::1"), (socket.AF_INET, "127.0.0.1")]:
            s = None
            try:
                s = socket.socket(af, socket.SOCK_STREAM)
                s.settimeout(timeout)
                s.connect((host, port))
                self.sock = s
                self.host = host
                break
            except Exception as e:
                last = e
                try:
                    if s:
                        s.close()
                except Exception:
                    pass
        if not self.sock:
            raise RuntimeError(f"Cannot connect debugger port {port}: {last}")

        key = base64.b64encode(secrets.token_bytes(16)).decode()
        req = (
            f"GET /debugger HTTP/1.1\r\nHost: {self.host}:{port}\r\n"
            "Upgrade: websocket\r\nConnection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n"
            "Sec-WebSocket-Protocol: debugger.ppsspp.org\r\n\r\n"
        )
        self.sock.sendall(req.encode("ascii"))
        data = b""
        while b"\r\n\r\n" not in data:
            c = self.sock.recv(4096)
            if not c:
                raise RuntimeError("Debugger handshake closed")
            data += c
        head = data.split(b"\r\n\r\n", 1)[0].decode("latin1", "replace")
        if " 101 " not in head.split("\r\n")[0]:
            raise RuntimeError("WebSocket handshake failed: " + head[:300])
        self.sock.settimeout(0.5)

    def _send_frame(self, opcode, payload=b""):
        if isinstance(payload, str):
            payload = payload.encode("utf-8")
        mask = secrets.token_bytes(4)
        n = len(payload)
        b1 = 0x80 | opcode
        if n < 126:
            hdr = bytes([b1, 0x80 | n])
        elif n <= 0xFFFF:
            hdr = bytes([b1, 0x80 | 126]) + struct.pack("!H", n)
        else:
            hdr = bytes([b1, 0x80 | 127]) + struct.pack("!Q", n)
        enc = bytes(c ^ mask[i % 4] for i, c in enumerate(payload))
        self.sock.sendall(hdr + mask + enc)

    def send_json(self, obj):
        self._send_frame(1, json.dumps(obj, separators=(",", ":"), ensure_ascii=False))

    def _recvn(self, n):
        out = b""
        while len(out) < n:
            c = self.sock.recv(n - len(out))
            if not c:
                raise EOFError("websocket closed")
            out += c
        return out

    def recv_json(self, timeout=0.5):
        self.sock.settimeout(timeout)
        frags = []
        started = False
        while True:
            h = self._recvn(2)
            b1, b2 = h
            op = b1 & 0x0F
            fin = bool(b1 & 0x80)
            n = b2 & 0x7F
            if n == 126:
                n = struct.unpack("!H", self._recvn(2))[0]
            elif n == 127:
                n = struct.unpack("!Q", self._recvn(8))[0]
            mask = self._recvn(4) if b2 & 0x80 else None
            payload = self._recvn(n) if n else b""
            if mask:
                payload = bytes(c ^ mask[i % 4] for i, c in enumerate(payload))
            if op == 8:
                raise EOFError("websocket close frame")
            if op == 9:
                self._send_frame(10, payload)
                continue
            if op == 10:
                continue
            if op == 1:
                frags = [payload]
                started = True
            elif op == 0 and started:
                frags.append(payload)
            else:
                continue
            if fin:
                return json.loads(b"".join(frags).decode("utf-8", "replace"))

    def request(self, event, timeout=10, **params):
        self.ticket += 1
        ticket = self.ticket
        q = {"event": event, "ticket": ticket}
        q.update(params)
        self.send_json(q)
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                r = self.recv_json(min(0.5, max(0.01, deadline - time.time())))
            except socket.timeout:
                continue
            if r.get("ticket") == ticket:
                if r.get("event") == "error":
                    raise RuntimeError(f"{event}: {r.get('message')}")
                return r
            self.pending.append(r)
        raise TimeoutError(f"No response: {event}")

    def poll(self, seconds):
        out = []
        if self.pending:
            out.extend(self.pending)
            self.pending = []
        deadline = time.time() + seconds
        while time.time() < deadline:
            try:
                out.append(self.recv_json(min(0.4, max(0.01, deadline - time.time()))))
            except socket.timeout:
                continue
        return out

    def close(self):
        try:
            self._send_frame(8, b"")
        except Exception:
            pass
        try:
            self.sock.close()
        except Exception:
            pass

def dump_json(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")

def safe(ws, event, **params):
    try:
        return {"ok": True, "response": ws.request(event, **params)}
    except Exception as e:
        return {"ok": False, "error": repr(e)}

def read_bytes(ws, addr, size, timeout=10):
    r = ws.request("memory.read", timeout=timeout, address=addr, size=size, replacements=True)
    return base64.b64decode(r.get("base64", ""))

def tap(ws, name, hold=0.22):
    out = []
    try:
        out.append(ws.request("input.buttons.send", timeout=5, buttons={name: True}))
        time.sleep(hold)
        out.append(ws.request("input.buttons.send", timeout=5, buttons={name: False}))
        return {"ok": True, "response": out}
    except Exception as e:
        return {"ok": False, "error": repr(e)}

def thread_snapshot(ws):
    try:
        r = ws.request("hle.thread.list", timeout=5)
        blob = json.dumps(r, ensure_ascii=False)
        return r, ("bink thread" in blob.lower())
    except Exception as e:
        return {"error": repr(e)}, False

def wait_initial_bink_end(ws, log, timeout=120):
    start = time.time()
    seen = False
    samples = []
    while time.time() - start < timeout:
        _, active = thread_snapshot(ws)
        samples.append({"t": round(time.time() - start, 2), "active": active})
        if active and not seen:
            seen = True
            log("Initial Bink/logo thread detected.")
        if seen and not active:
            log("Initial Bink/logo thread ended; title/menu navigation may begin.")
            return True, samples
        time.sleep(0.8)
    log("Initial Bink lifecycle not fully observed; continuing with delayed navigation.")
    return False, samples

def scan_region(ws, start, end, needles, chunk=0x10000):
    overlap = max(len(n) for _, n, _ in needles) - 1
    carry = b""
    for addr in range(start, end, chunk):
        size = min(chunk, end - addr)
        data = read_bytes(ws, addr, size, timeout=10)
        buf = carry + data
        buf_base = addr - len(carry)
        for off, needle, label in needles:
            pos = buf.find(needle)
            if pos >= 0:
                return {
                    "hit_addr": buf_base + pos,
                    "needle_offset": off,
                    "label": label,
                    "needle": needle,
                }
        carry = buf[-overlap:] if overlap else b""
    return None

def verify_base(ws, base):
    verdict = []
    score = 0
    for off, needle, label in NEEDLES:
        try:
            got = read_bytes(ws, base + off, len(needle), timeout=5)
            ok = got == needle
        except Exception:
            ok = False
            got = b""
        verdict.append({
            "label": label,
            "address": base + off,
            "address_hex": f"0x{base + off:08X}",
            "ok": ok,
            "got_hex": got.hex(),
        })
        score += int(ok)
    return score, verdict

def find_st1(ws, log, timeout=150):
    t0 = time.time()
    full_scan_done = False
    attempts = []
    while time.time() - t0 < timeout:
        score, ver = verify_base(ws, KNOWN_BASE)
        attempts.append({"kind": "known", "score": score, "verify": ver, "t": round(time.time()-t0, 2)})
        if score >= 2:
            log(f"ST1 verified at Stage41A base 0x{KNOWN_BASE:08X} (score {score}/3).")
            return KNOWN_BASE, attempts

        try:
            hit = scan_region(ws, 0x08D00000, 0x09000000, NEEDLES, chunk=0x10000)
            if hit:
                base = hit["hit_addr"] - hit["needle_offset"]
                score, ver = verify_base(ws, base)
                attempts.append({
                    "kind": "nearby",
                    "hit_addr": hit["hit_addr"],
                    "hit_addr_hex": f"0x{hit['hit_addr']:08X}",
                    "label": hit["label"],
                    "base": base,
                    "base_hex": f"0x{base:08X}",
                    "score": score,
                    "verify": ver,
                    "t": round(time.time()-t0, 2),
                })
                if score >= 2:
                    log(f"ST1 found by local RAM scan: base 0x{base:08X} ({hit['label']}, score {score}/3).")
                    return base, attempts
        except Exception as e:
            attempts.append({"kind": "nearby_error", "error": repr(e), "t": round(time.time()-t0, 2)})
            log("Local RAM scan warning: " + repr(e))

        if not full_scan_done and time.time() - t0 > 25:
            full_scan_done = True
            log("No local hit yet; doing one 32 MiB RAM scan with memory.read chunks.")
            try:
                hit = scan_region(ws, RAM_START, RAM_END, NEEDLES, chunk=0x20000)
                if hit:
                    base = hit["hit_addr"] - hit["needle_offset"]
                    score, ver = verify_base(ws, base)
                    attempts.append({
                        "kind": "full",
                        "hit_addr": hit["hit_addr"],
                        "hit_addr_hex": f"0x{hit['hit_addr']:08X}",
                        "label": hit["label"],
                        "base": base,
                        "base_hex": f"0x{base:08X}",
                        "score": score,
                        "verify": ver,
                        "t": round(time.time()-t0, 2),
                    })
                    if score >= 2:
                        log(f"ST1 found by full RAM scan: base 0x{base:08X} ({hit['label']}, score {score}/3).")
                        return base, attempts
            except Exception as e:
                attempts.append({"kind": "full_error", "error": repr(e), "t": round(time.time()-t0, 2)})
                log("Full RAM scan warning: " + repr(e))
        time.sleep(1.2)
    return None, attempts

def arm_watchpoints(ws, base, log):
    armed = []
    for off in WATCH_OFFSETS:
        addr = base + off
        # PPSSPP: enabled=False => do not pause; log=True => still log/count hits.
        r = safe(
            ws, "memory.breakpoint.add",
            address=addr, size=8, enabled=False, log=True,
            read=True, write=False, change=False
        )
        armed.append({"offset": off, "address": addr, "address_hex": f"0x{addr:08X}", "result": r})
        if r["ok"]:
            log(f"Read watchpoint armed at ST1+0x{off:X} = 0x{addr:08X}.")
    return armed

def collect_mem_hits(ws, base, seconds, log, event_path):
    hits = []
    deadline = time.time() + seconds
    starts = {base + o for o in WATCH_OFFSETS}
    while time.time() < deadline:
        for ev in ws.poll(min(0.5, max(0.05, deadline-time.time()))):
            if ev.get("event") != "cpu.breakpoint.hit":
                continue
            h = ev.get("hit", {})
            if h.get("kind") != "memory":
                continue
            bp = h.get("breakpoint", {})
            st = int(bp.get("start", 0))
            if st in starts:
                hits.append(ev)
                with Path(event_path).open("a", encoding="utf-8") as f:
                    f.write(json.dumps(ev, ensure_ascii=False) + "\n")
        if len(hits) >= 4000:
            log("Hit cap reached (4000); stopping watchpoint collection.")
            break
    return hits

def remove_watchpoints(ws, base):
    return [
        safe(ws, "memory.breakpoint.remove", address=base+off, size=8)
        for off in WATCH_OFFSETS
    ]

def disasm_candidate(ws, pc):
    return {
        "pc": pc,
        "pc_hex": f"0x{pc:08X}",
        "disasm": safe(
            ws, "memory.disasm",
            address=max(RAM_START, pc-0x80), count=72,
            displaySymbols=True, compact=False
        ),
        "compact": safe(
            ws, "memory.disasm",
            address=max(RAM_START, pc-0x80), count=72,
            displaySymbols=True, compact=True
        ),
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--pid", type=int, required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--iso", required=True)
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    trace = out / "stage41b_fix1_trace.txt"
    events = out / "stage41b_fix1_breakpoint_events.jsonl"

    report = {
        "stage": "41B_FIX1",
        "purpose": (
            "Retry dedicated Bink/ST1 subtitle reader trace. "
            "Fixes 41B early navigation and removes unsupported memory.search dependency."
        ),
        "source_iso": args.iso,
        "expected_pid": args.pid,
        "debugger_port": args.port,
        "started": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    ws = None

    def log(s):
        line = f"[{time.strftime('%H:%M:%S')}] {s}"
        print(line, flush=True)
        with trace.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

    try:
        last = None
        for _ in range(100):
            try:
                ws = MiniWS(args.port, 0.5)
                break
            except Exception as e:
                last = e
                time.sleep(0.25)
        if not ws:
            raise RuntimeError(f"Debugger did not open: {last}")

        report["version"] = ws.request("version", name="bia-stage41b-fix1", version="1.0")
        report["cpu_status"] = safe(ws, "cpu.status")
        log("Debugger attached. Waiting for initial logo Bink to END before menu input.")

        lifecycle_ok, samples = wait_initial_bink_end(ws, log, timeout=120)
        report["initial_bink_lifecycle"] = {"completed": lifecycle_ok, "samples": samples}
        time.sleep(2.0)

        # Title -> Story -> New Game -> default difficulty.
        nav = []
        for name, wait in [("start", 3.0), ("cross", 3.0), ("cross", 3.0), ("cross", 1.5)]:
            r = tap(ws, name, 0.22)
            nav.append({"button": name, "result": r})
            log(f"Navigation tap: {name} ({'ok' if r['ok'] else 'failed'})")
            time.sleep(wait)
        report["navigation"] = nav

        second_seen = False
        bink_samples = []
        t = time.time()
        while time.time() - t < 35:
            _, active = thread_snapshot(ws)
            bink_samples.append({"t": round(time.time()-t, 2), "active": active})
            if active:
                second_seen = True
                log("Story Bink thread detected. Searching RAM for patched ST1.")
                break
            time.sleep(0.75)
        report["story_bink_detected"] = second_seen
        report["story_bink_samples"] = bink_samples

        if not second_seen:
            log(
                "Story Bink not detected automatically. "
                "You may manually enter 스토리 > 새 게임 > 난이도 now; tracer keeps waiting."
            )

        base, attempts = find_st1(ws, log, timeout=150)
        report["st1_search_attempts"] = attempts
        report["st1_base"] = base
        report["st1_base_hex"] = f"0x{base:08X}" if base is not None else None

        if base is None:
            report["threads_at_failure"] = safe(ws, "hle.thread.list")
            raise RuntimeError(
                "Korean ST1 buffer was not found. "
                "Automatic route may have missed; no memory.search call was used."
            )

        score, verify = verify_base(ws, base)
        report["st1_verify"] = {"score": score, "records": verify}
        report["st1_sample_hex"] = read_bytes(ws, base, 0x180).hex()

        report["watchpoints"] = arm_watchpoints(ws, base, log)
        log("Collecting ST1 read PCs for up to 55 seconds...")
        hits = collect_mem_hits(ws, base, 55, log, events)
        report["watchpoint_remove"] = remove_watchpoints(ws, base)
        report["memory_hit_count"] = len(hits)

        pcs = Counter()
        examples = {}
        for ev in hits:
            h = ev.get("hit", {})
            pc = int(h.get("pc", 0))
            if pc:
                pcs[pc] += 1
                examples.setdefault(pc, h)

        report["memory_reader_pcs"] = [
            {"pc": pc, "pc_hex": f"0x{pc:08X}", "count": cnt, "example": examples[pc]}
            for pc, cnt in pcs.most_common()
        ]
        report["memory_breakpoint_list_after"] = safe(ws, "memory.breakpoint.list")

        if not pcs:
            raise RuntimeError(
                "ST1 was loaded, but no read watchpoint hit was observed. "
                "Keep Stage41A; next step should trace the ST1 load/copy path."
            )

        log("Reader PCs: " + ", ".join(
            f"0x{pc:08X} x{cnt}" for pc, cnt in pcs.most_common(10)
        ))

        report["candidate_disassembly"] = [
            disasm_candidate(ws, pc) for pc, _ in pcs.most_common(8)
        ]

        # Try to re-hit a reader as an execution breakpoint for registers/backtrace.
        detailed = None
        for pc, cnt in pcs.most_common(6):
            log(f"Trying execution breakpoint at 0x{pc:08X} (memory-read hits {cnt}).")
            add = safe(ws, "cpu.breakpoint.add", address=pc, enabled=True, log=True)
            if not add["ok"]:
                continue

            deadline = time.time() + 22
            while time.time() < deadline:
                for ev in ws.poll(min(0.5, max(0.05, deadline-time.time()))):
                    if ev.get("event") == "cpu.breakpoint.hit":
                        h = ev.get("hit", {})
                        if h.get("kind") == "exec" and int(h.get("pc", 0)) == pc:
                            detailed = {
                                "candidate": pc,
                                "candidate_hex": f"0x{pc:08X}",
                                "hit": ev,
                                "regs": safe(ws, "cpu.getAllRegs"),
                                "backtrace": safe(ws, "hle.backtrace"),
                                "threads": safe(ws, "hle.thread.list"),
                                "modules": safe(ws, "hle.module.list"),
                                "disasm": safe(
                                    ws, "memory.disasm",
                                    address=max(RAM_START, pc-0x100), count=120,
                                    displaySymbols=True, compact=False
                                ),
                            }
                            log(f"Execution breakpoint HIT at 0x{pc:08X}.")
                            break
                if detailed:
                    break

            safe(ws, "cpu.breakpoint.remove", address=pc)
            if detailed:
                break

        report["detailed_hit"] = detailed
        report["completed"] = True
        report["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
        dump_json(out / "stage41b_fix1_report.json", report)

        lines = [
            "Stage41B Fix1 candidate ST1 reader PCs",
            f"ST1 base: 0x{base:08X}",
            f"Memory hits: {len(hits)}",
            "",
        ]
        for pc, cnt in pcs.most_common(20):
            lines.append(f"0x{pc:08X}  hits={cnt}")
        (out / "stage41b_fix1_candidates.txt").write_text(
            "\n".join(lines), encoding="utf-8"
        )

        log("STAGE41B FIX1 SUCCESS: ST1 read path evidence captured.")
        return 0

    except Exception as e:
        report["completed"] = False
        report["error"] = repr(e)
        report["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
        dump_json(out / "stage41b_fix1_report.json", report)
        log("STAGE41B FIX1 FAILED: " + repr(e))
        return 1
    finally:
        if ws:
            ws.close()

if __name__ == "__main__":
    sys.exit(main())
