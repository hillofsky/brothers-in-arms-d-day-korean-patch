#!/usr/bin/env python3
import argparse, base64, hashlib, json, os, socket, struct, time, urllib.parse
from pathlib import Path

class WSClient:
    def __init__(self, host, port, path="/debugger", timeout=10):
        self.sock=socket.create_connection((host,port),timeout=timeout)
        self.sock.settimeout(timeout)
        key=base64.b64encode(os.urandom(16)).decode()
        req=(
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {host}:{port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            "Sec-WebSocket-Protocol: debugger.ppsspp.org\r\n\r\n"
        )
        self.sock.sendall(req.encode("ascii"))
        data=b""
        while b"\r\n\r\n" not in data:
            chunk=self.sock.recv(4096)
            if not chunk: raise RuntimeError("WebSocket handshake closed")
            data+=chunk
            if len(data)>65536: raise RuntimeError("WebSocket handshake too large")
        head=data.split(b"\r\n\r\n",1)[0].decode("latin1","replace")
        if " 101 " not in head:
            raise RuntimeError("WebSocket handshake failed: "+head[:1000])
        accept=None
        for line in head.split("\r\n")[1:]:
            if ":" in line:
                k,v=line.split(":",1)
                if k.lower()=="sec-websocket-accept":
                    accept=v.strip()
        expected=base64.b64encode(hashlib.sha1((key+"258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()).decode()
        if accept!=expected:
            raise RuntimeError(f"Bad WebSocket accept: {accept!r} != {expected!r}")
        self.ticket=0

    def _recv_exact(self,n):
        b=b""
        while len(b)<n:
            x=self.sock.recv(n-len(b))
            if not x: raise RuntimeError("WebSocket closed")
            b+=x
        return b

    def _send_frame(self, payload, opcode=1):
        if isinstance(payload,str): payload=payload.encode("utf-8")
        fin_opcode=0x80|opcode
        n=len(payload)
        mask=os.urandom(4)
        if n<126:
            hdr=bytes([fin_opcode,0x80|n])
        elif n<65536:
            hdr=bytes([fin_opcode,0x80|126])+struct.pack("!H",n)
        else:
            hdr=bytes([fin_opcode,0x80|127])+struct.pack("!Q",n)
        masked=bytes(payload[i]^mask[i%4] for i in range(n))
        self.sock.sendall(hdr+mask+masked)

    def _recv_frame(self):
        h=self._recv_exact(2)
        b0,b1=h
        fin=bool(b0&0x80);opcode=b0&0x0F
        masked=bool(b1&0x80);n=b1&0x7F
        if n==126:n=struct.unpack("!H",self._recv_exact(2))[0]
        elif n==127:n=struct.unpack("!Q",self._recv_exact(8))[0]
        mask=self._recv_exact(4) if masked else None
        data=self._recv_exact(n) if n else b""
        if masked:data=bytes(data[i]^mask[i%4] for i in range(n))
        return fin,opcode,data

    def recv_message(self, timeout=15):
        old=self.sock.gettimeout();self.sock.settimeout(timeout)
        try:
            chunks=[];msg_opcode=None
            while True:
                fin,op,data=self._recv_frame()
                if op==8: raise RuntimeError("WebSocket server closed")
                if op==9:
                    self._send_frame(data,opcode=10);continue
                if op==10:continue
                if op in (1,2):
                    msg_opcode=op;chunks=[data]
                elif op==0:
                    chunks.append(data)
                else:
                    continue
                if fin and msg_opcode is not None:
                    raw=b"".join(chunks)
                    if msg_opcode==1:
                        return raw.decode("utf-8","replace")
                    return raw
        finally:
            self.sock.settimeout(old)

    def send_json(self,event,**kwargs):
        self.ticket+=1
        obj={"event":event,"ticket":self.ticket}
        obj.update(kwargs)
        self._send_frame(json.dumps(obj,separators=(",",":"),ensure_ascii=False))
        return self.ticket

    def request(self,event,timeout=20,**kwargs):
        ticket=self.send_json(event,**kwargs)
        deadline=time.time()+timeout
        seen=[]
        while time.time()<deadline:
            msg=self.recv_message(timeout=max(0.2,deadline-time.time()))
            if isinstance(msg,bytes): continue
            try:o=json.loads(msg)
            except Exception:continue
            seen.append(o)
            if o.get("ticket")==ticket:
                if o.get("event")=="error":
                    raise RuntimeError(f"{event} error: {o}")
                return o
        raise TimeoutError(f"Timeout waiting for {event}, seen={seen[-10:]}")

    def event_wait(self,event,timeout=15):
        deadline=time.time()+timeout
        seen=[]
        while time.time()<deadline:
            msg=self.recv_message(timeout=max(0.2,deadline-time.time()))
            if isinstance(msg,bytes):continue
            try:o=json.loads(msg)
            except Exception:continue
            seen.append(o)
            if o.get("event")==event:
                return o
        raise TimeoutError(f"Timeout waiting event {event}, seen={seen[-10:]}")

    def close(self):
        try:self._send_frame(b"",opcode=8)
        except Exception:pass
        try:self.sock.close()
        except Exception:pass

def pause(ws):
    # cpu.stepping has no normal immediate response on success.
    ws.send_json("cpu.stepping")
    try:
        ws.event_wait("cpu.stepping",timeout=8)
    except Exception:
        # Fall back to cpu.status to verify actual stepping state.
        for _ in range(20):
            st=ws.request("cpu.status",timeout=3)
            if st.get("stepping"):
                return
            time.sleep(0.1)
        raise

def resume(ws):
    ws.send_json("cpu.resume")
    # Don't require the spontaneous event; verify status instead.
    time.sleep(0.15)
    for _ in range(20):
        try:
            st=ws.request("cpu.status",timeout=3)
            if not st.get("stepping"):
                return
        except Exception:
            pass
        time.sleep(0.1)

def screenshot(ws,path):
    pause(ws)
    try:
        o=ws.request("gpu.buffer.screenshot",timeout=20,type="uri")
        uri=o.get("uri","")
        if not uri.startswith("data:image/png;base64,"):
            raise RuntimeError("Unexpected screenshot response")
        raw=base64.b64decode(uri.split(",",1)[1])
        Path(path).write_bytes(raw)
        return {"width":o.get("width"),"height":o.get("height"),"bytes":len(raw)}
    finally:
        resume(ws)

def mem_search(ws,text):
    payload=text.encode("utf-8")
    o=ws.request(
        "memory.search",timeout=20,
        address=0x08000000,size=0x02000000,
        type="bytes",
        base64=base64.b64encode(payload).decode(),
        align=1,maxResults=20,
    )
    return o.get("matches",[]),bool(o.get("truncated",False))

def press(ws,button,duration=2):
    # input.buttons.press completes after the emulated vblank release.
    return ws.request("input.buttons.press",timeout=10,button=button,duration=duration)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--port",type=int,required=True)
    ap.add_argument("--expected-pid",type=int,required=True)
    ap.add_argument("--expected-iso",required=True)
    ap.add_argument("--outdir",required=True)
    a=ap.parse_args()
    out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)
    log=[]
    ws=None
    report={
        "step":"STEP_070",
        "status":"IN_PROGRESS",
        "port":a.port,
        "expected_pid":a.expected_pid,
        "expected_iso":a.expected_iso,
        "runtime_verified":False,
        "route_discovery_only":True,
    }
    try:
        # Retry WS connect while PPSSPP initializes.
        last=None
        for _ in range(60):
            try:
                ws=WSClient("127.0.0.1",a.port,timeout=3)
                break
            except Exception as e:
                last=e;time.sleep(0.5)
        if ws is None:raise RuntimeError(f"Could not connect debugger: {last}")

        ver=ws.request("version",timeout=10,name="bia-step070",version="1.0")
        report["debugger_version"]=ver
        actual_pid=int(ver.get("pid",-1))
        actual_path=os.path.normcase(os.path.abspath(ver.get("path") or ""))
        expected_path=os.path.normcase(os.path.abspath(a.expected_iso))
        if actual_pid!=a.expected_pid:
            raise RuntimeError(f"Debugger PID mismatch {actual_pid} != {a.expected_pid}")
        if actual_path!=expected_path:
            raise RuntimeError(f"Debugger ISO path mismatch {actual_path!r} != {expected_path!r}")

        # Wait game boot.
        game=None
        for _ in range(80):
            try:
                gs=ws.request("game.status",timeout=5)
                game=gs.get("game")
                if game:break
            except Exception:pass
            time.sleep(0.5)
        if not game:raise RuntimeError("Game did not reach boot-complete state")
        report["game"]=game

        # Let title settle, capture.
        time.sleep(6)
        report["title_screenshot"]=screenshot(ws,out/"00_title.png")

        # Static runtime memory canaries at title.
        title_mem={}
        for t in ["스커미시 로비","게임 팁:","늪을 건너"]:
            try:
                m,tr=mem_search(ws,t);title_mem[t]={"matches":m,"truncated":tr}
            except Exception as e:
                title_mem[t]={"error":str(e)}
        report["memory_at_title"]=title_mem

        # Enter main menu using debugger input only.
        press(ws,"start",3)
        time.sleep(4)
        report["main_screenshot"]=screenshot(ws,out/"01_main_menu.png")

        main_mem={}
        for t in ["스커미시 로비","게임 팁:","늪을 건너"]:
            try:
                m,tr=mem_search(ws,t);main_mem[t]={"matches":m,"truncated":tr}
            except Exception as e:
                main_mem[t]={"error":str(e)}
        report["memory_at_main_menu"]=main_mem

        # Safe route discovery: do NOT confirm an option. Only move highlight
        # down and capture each selection. This avoids entering campaign/network
        # menus until the exact Skirmish index is visually identified.
        selections=[]
        for i in range(1,7):
            press(ws,"down",2)
            time.sleep(0.7)
            info=screenshot(ws,out/f"{i+1:02d}_main_down_{i}.png")
            selections.append({"down_count":i,"screenshot":f"{i+1:02d}_main_down_{i}.png","capture":info})
        report["main_menu_selection_sweep"]=selections

        # One more memory sample after sweep (selection-only should not change
        # loaded resources, but this gives evidence if it does).
        sweep_mem={}
        for t in ["스커미시 로비","게임 팁:","늪을 건너"]:
            try:
                m,tr=mem_search(ws,t);sweep_mem[t]={"matches":m,"truncated":tr}
            except Exception as e:
                sweep_mem[t]={"error":str(e)}
        report["memory_after_selection_sweep"]=sweep_mem

        report["status"]="RUNTIME_ROUTE_DISCOVERY_CAPTURED"
        # A memory hit proves the UTF-8 target is loaded, not rendered.
        ko_hits=[]
        for phase in ("memory_at_title","memory_at_main_menu","memory_after_selection_sweep"):
            for text,rec in report.get(phase,{}).items():
                if rec.get("matches"):
                    ko_hits.append({"phase":phase,"text":text,"matches":rec["matches"]})
        report["korean_runtime_memory_hits"]=ko_hits
        report["runtime_loaded_korean"]=bool(ko_hits)
        report["runtime_render_verified"]=False
        report["next_action"]="Inspect screenshots to identify the exact Skirmish menu selection index, then run a confirm-entry canary."
    finally:
        if ws:
            ws.close()
        (out/"step070_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
        (out/"websocket_log.json").write_text(json.dumps(log,ensure_ascii=False,indent=2),encoding="utf-8")

if __name__=="__main__":
    main()
