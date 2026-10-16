#!/usr/bin/env python3
import argparse, base64, json, socket, struct, time, secrets, sys
from pathlib import Path
from collections import Counter

RAM_START = 0x08000000
RAM_END = 0x0A000000
KNOWN_BASE = 0x08E1F21C

NEEDLES = [
    (0x000, "운명의 랑데부".encode("utf-8"), "title"),
    (0x06E, "베이커:".encode("utf-8"), "baker"),
    (0x28F, "맥:".encode("utf-8"), "mac"),
]
WATCH_OFFSETS = [0x000, 0x06E, 0x28F, 0x39E, 0x4B5, 0x55C, 0x59D]

class MiniWS:
    def __init__(self, port):
        self.ticket = 2000
        self.pending = []
        self.sock = None
        last = None
        for af, host in [(socket.AF_INET6, "::1"), (socket.AF_INET, "127.0.0.1")]:
            try:
                s = socket.socket(af, socket.SOCK_STREAM)
                s.settimeout(0.8)
                s.connect((host, port))
                self.sock = s
                self.host = host
                break
            except Exception as e:
                last = e
        if not self.sock:
            raise RuntimeError(f"debugger connect failed: {last}")

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
            data += self.sock.recv(4096)
        if b" 101 " not in data.split(b"\r\n", 1)[0]:
            raise RuntimeError("websocket handshake failed")
        self.sock.settimeout(0.5)

    def _send(self, opcode, payload=b""):
        if isinstance(payload, str):
            payload = payload.encode("utf-8")
        mask = secrets.token_bytes(4)
        n = len(payload)
        h = bytes([0x80 | opcode])
        if n < 126:
            h += bytes([0x80 | n])
        elif n <= 0xFFFF:
            h += bytes([0x80 | 126]) + struct.pack("!H", n)
        else:
            h += bytes([0x80 | 127]) + struct.pack("!Q", n)
        payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        self.sock.sendall(h + mask + payload)

    def _recvn(self, n):
        b = b""
        while len(b) < n:
            c = self.sock.recv(n - len(b))
            if not c:
                raise EOFError("closed")
            b += c
        return b

    def recv(self, timeout=0.5):
        self.sock.settimeout(timeout)
        parts = []
        started = False
        while True:
            b1, b2 = self._recvn(2)
            op = b1 & 0x0F
            fin = bool(b1 & 0x80)
            n = b2 & 0x7F
            if n == 126:
                n = struct.unpack("!H", self._recvn(2))[0]
            elif n == 127:
                n = struct.unpack("!Q", self._recvn(8))[0]
            mask = self._recvn(4) if (b2 & 0x80) else None
            p = self._recvn(n) if n else b""
            if mask:
                p = bytes(v ^ mask[i % 4] for i, v in enumerate(p))
            if op == 8:
                raise EOFError("close frame")
            if op == 9:
                self._send(10, p)
                continue
            if op == 10:
                continue
            if op == 1:
                parts = [p]
                started = True
            elif op == 0 and started:
                parts.append(p)
            else:
                continue
            if fin:
                return json.loads(b"".join(parts).decode("utf-8", "replace"))

    def request(self, event, timeout=10, **kwargs):
        self.ticket += 1
        t = self.ticket
        obj = {"event": event, "ticket": t}
        obj.update(kwargs)
        self._send(1, json.dumps(obj, separators=(",", ":"), ensure_ascii=False))
        end = time.time() + timeout
        while time.time() < end:
            try:
                r = self.recv(min(0.5, max(0.05, end - time.time())))
            except socket.timeout:
                continue
            if r.get("ticket") == t:
                if r.get("event") == "error":
                    raise RuntimeError(f"{event}: {r.get('message')}")
                return r
            self.pending.append(r)
        raise TimeoutError(event)

    def poll(self, secs):
        out = self.pending
        self.pending = []
        end = time.time() + secs
        while time.time() < end:
            try:
                out.append(self.recv(min(0.4, max(0.05, end-time.time()))))
            except socket.timeout:
                pass
        return out

    def close(self):
        try: self._send(8)
        except: pass
        try: self.sock.close()
        except: pass

def safe(ws, event, **kw):
    try:
        return {"ok": True, "response": ws.request(event, **kw)}
    except Exception as e:
        return {"ok": False, "error": repr(e)}

def read_bytes(ws, addr, size):
    r = ws.request("memory.read", timeout=10, address=addr, size=size, replacements=True)
    return base64.b64decode(r.get("base64", ""))

def verify(ws, base):
    rows, score = [], 0
    for off, needle, label in NEEDLES:
        try:
            got = read_bytes(ws, base+off, len(needle))
        except Exception:
            got = b""
        ok = got == needle
        score += int(ok)
        rows.append({
            "label": label, "address_hex": f"0x{base+off:08X}",
            "ok": ok, "got_hex": got.hex()
        })
    return score, rows

def scan(ws, start, end):
    chunk = 0x20000
    carry = b""
    overlap = max(len(n) for _,n,_ in NEEDLES)-1
    for a in range(start, end, chunk):
        data = read_bytes(ws, a, min(chunk, end-a))
        buf = carry + data
        baddr = a - len(carry)
        for off, needle, label in NEEDLES:
            p = buf.find(needle)
            if p >= 0:
                return baddr+p-off, label, baddr+p
        carry = buf[-overlap:]
    return None

def capture_vram(ws, out, label):
    captures = []
    for addr in [0x04000000, 0x04044000]:
        try:
            raw = read_bytes(ws, addr, 512*272*4)
            p = out / f"{label}_{addr:08X}.bin"
            p.write_bytes(raw)
            captures.append({"address_hex":f"0x{addr:08X}","path":str(p),"bytes":len(raw)})
        except Exception as e:
            captures.append({"address_hex":f"0x{addr:08X}","error":repr(e)})
    return captures

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--iso", required=True)
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    trace = out / "stage41b_fix2_trace.txt"
    evfile = out / "stage41b_fix2_events.jsonl"
    report = {"stage":"41B_FIX2","iso":args.iso,"started":time.strftime("%F %T")}
    ws = None

    def log(msg):
        s=f"[{time.strftime('%H:%M:%S')}] {msg}"
        print(s, flush=True)
        with trace.open("a",encoding="utf-8") as f: f.write(s+"\n")

    try:
        for i in range(100):
            try:
                ws=MiniWS(args.port); break
            except Exception:
                time.sleep(.25)
        if not ws:
            raise RuntimeError("debugger unavailable")

        report["version"]=ws.request("version",name="bia41b-fix2",version="1.0")
        log("Debugger attached. NO automatic button input will be sent.")
        log("PPSSPP에서 직접 START를 누르고 스토리 > 새 게임 > 난이도 선택까지 진행하세요.")
        log("PRESS START 글씨가 안 보여도 START 버튼 자체는 눌러보세요.")
        log("ST1이 메모리에 나타나는 순간 자동으로 추적을 시작합니다.")

        time.sleep(18)
        report["title_vram"]=capture_vram(ws,out,"title_wait")

        base=None
        attempts=[]
        start=time.time()
        fullscan_at=0.0

        while time.time()-start < 240:
            score, rows = verify(ws, KNOWN_BASE)
            attempts.append({"t":round(time.time()-start,2),"known_score":score})
            if score >= 2:
                base=KNOWN_BASE
                log(f"ST1 verified at known base 0x{base:08X}.")
                break

            # Full RAM scan only every ~12 seconds to avoid hammering PPSSPP.
            if time.time()-fullscan_at >= 12:
                fullscan_at=time.time()
                try:
                    hit=scan(ws,RAM_START,RAM_END)
                    if hit:
                        cand,label,hitaddr=hit
                        score2, rows2=verify(ws,cand)
                        attempts.append({
                            "t":round(time.time()-start,2),
                            "scan_base_hex":f"0x{cand:08X}",
                            "label":label,"score":score2
                        })
                        if score2 >= 2:
                            base=cand
                            log(f"ST1 found by RAM scan at 0x{base:08X} ({label}).")
                            break
                except Exception as e:
                    attempts.append({"scan_error":repr(e)})
            time.sleep(.8)

        report["search_attempts"]=attempts

        if base is None:
            report["failure_vram"]=capture_vram(ws,out,"failure")
            report["threads"]=safe(ws,"hle.thread.list")
            raise RuntimeError("ST1 never appeared within 240 seconds.")

        score, rows=verify(ws,base)
        report["st1_base_hex"]=f"0x{base:08X}"
        report["st1_verify"]={"score":score,"rows":rows}
        report["st1_vram"]=capture_vram(ws,out,"st1_loaded")

        armed=[]
        for off in WATCH_OFFSETS:
            a=base+off
            r=safe(ws,"memory.breakpoint.add",address=a,size=8,enabled=False,log=True,
                   read=True,write=False,change=False)
            armed.append({"offset_hex":hex(off),"address_hex":f"0x{a:08X}","result":r})
        report["watchpoints"]=armed
        log("ST1 read watchpoints armed. Continue letting the movie play.")

        hits=[]
        end=time.time()+70
        while time.time()<end:
            for ev in ws.poll(.5):
                if ev.get("event")=="cpu.breakpoint.hit":
                    h=ev.get("hit",{})
                    if h.get("kind")=="memory":
                        hits.append(ev)
                        with evfile.open("a",encoding="utf-8") as f:
                            f.write(json.dumps(ev,ensure_ascii=False)+"\n")
            if len(hits)>=5000:
                break

        pcs=Counter()
        for ev in hits:
            pc=int(ev.get("hit",{}).get("pc",0))
            if pc: pcs[pc]+=1

        report["memory_hit_count"]=len(hits)
        report["reader_pcs"]=[
            {"pc_hex":f"0x{pc:08X}","count":cnt} for pc,cnt in pcs.most_common()
        ]

        report["disasm"]=[]
        for pc,cnt in pcs.most_common(10):
            report["disasm"].append({
                "pc_hex":f"0x{pc:08X}",
                "count":cnt,
                "result":safe(ws,"memory.disasm",
                    address=max(RAM_START,pc-0x100),count=120,
                    displaySymbols=True,compact=False)
            })

        for off in WATCH_OFFSETS:
            safe(ws,"memory.breakpoint.remove",address=base+off,size=8)

        if not pcs:
            raise RuntimeError("ST1 loaded, but no read watchpoint hits were captured.")

        report["completed"]=True
        report["finished"]=time.strftime("%F %T")
        (out/"stage41b_fix2_report.json").write_text(
            json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8"
        )
        log("STAGE41B FIX2 SUCCESS.")
        return 0

    except Exception as e:
        report["completed"]=False
        report["error"]=repr(e)
        report["finished"]=time.strftime("%F %T")
        (out/"stage41b_fix2_report.json").write_text(
            json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8"
        )
        log("STAGE41B FIX2 FAILED: "+repr(e))
        return 1
    finally:
        if ws: ws.close()

if __name__=="__main__":
    sys.exit(main())
