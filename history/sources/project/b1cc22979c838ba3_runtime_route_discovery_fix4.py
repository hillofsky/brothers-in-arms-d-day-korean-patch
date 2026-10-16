#!/usr/bin/env python3
import argparse, base64, hashlib, json, os, socket, struct, time
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
            x=self.sock.recv(4096)
            if not x: raise RuntimeError("WebSocket handshake closed")
            data+=x
            if len(data)>65536: raise RuntimeError("WebSocket handshake too large")
        head=data.split(b"\r\n\r\n",1)[0].decode("latin1","replace")
        if " 101 " not in head:
            raise RuntimeError("WebSocket handshake failed: "+head[:1200])
        accept=None
        for line in head.split("\r\n")[1:]:
            if ":" in line:
                k,v=line.split(":",1)
                if k.lower()=="sec-websocket-accept":accept=v.strip()
        exp=base64.b64encode(hashlib.sha1((key+"258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()).decode()
        if accept!=exp:raise RuntimeError(f"Bad WebSocket accept: {accept!r}")
        self.ticket=0

    def _readn(self,n):
        data=b""
        while len(data)<n:
            x=self.sock.recv(n-len(data))
            if not x:raise RuntimeError("WebSocket closed")
            data+=x
        return data

    def _send_frame(self,payload,opcode=1):
        if isinstance(payload,str):payload=payload.encode("utf-8")
        n=len(payload);mask=os.urandom(4)
        h=bytes([0x80|opcode])
        if n<126:h+=bytes([0x80|n])
        elif n<65536:h+=bytes([0x80|126])+struct.pack("!H",n)
        else:h+=bytes([0x80|127])+struct.pack("!Q",n)
        masked=bytes(payload[i]^mask[i%4] for i in range(n))
        self.sock.sendall(h+mask+masked)

    def _recv_frame(self):
        h=self._readn(2);b0,b1=h
        op=b0&0x0f;n=b1&0x7f;masked=bool(b1&0x80)
        if n==126:n=struct.unpack("!H",self._readn(2))[0]
        elif n==127:n=struct.unpack("!Q",self._readn(8))[0]
        mask=self._readn(4) if masked else None
        data=self._readn(n) if n else b""
        if mask:data=bytes(data[i]^mask[i%4] for i in range(n))
        return bool(b0&0x80),op,data

    def recv(self,timeout=15):
        old=self.sock.gettimeout();self.sock.settimeout(timeout)
        try:
            chunks=[];msgop=None
            while True:
                fin,op,data=self._recv_frame()
                if op==8:raise RuntimeError("WebSocket server closed")
                if op==9:
                    self._send_frame(data,10);continue
                if op==10:continue
                if op in (1,2):msgop=op;chunks=[data]
                elif op==0:chunks.append(data)
                else:continue
                if fin and msgop is not None:
                    raw=b"".join(chunks)
                    return raw.decode("utf-8","replace") if msgop==1 else raw
        finally:self.sock.settimeout(old)

    def send_json(self,event,**kwargs):
        self.ticket+=1
        o={"event":event,"ticket":self.ticket};o.update(kwargs)
        self._send_frame(json.dumps(o,separators=(",",":"),ensure_ascii=False))
        return self.ticket

    def request(self,event,timeout=20,**kwargs):
        ticket=self.send_json(event,**kwargs)
        end=time.time()+timeout;seen=[]
        while time.time()<end:
            msg=self.recv(max(.2,end-time.time()))
            if isinstance(msg,bytes):continue
            try:o=json.loads(msg)
            except Exception:continue
            seen.append(o)
            if o.get("ticket")==ticket:
                if o.get("event")=="error":raise RuntimeError(f"{event} error: {o}")
                return o
        raise TimeoutError(f"Timeout waiting {event}; last={seen[-8:]}")

    def wait_event(self,event,timeout=8):
        end=time.time()+timeout
        while time.time()<end:
            msg=self.recv(max(.2,end-time.time()))
            if isinstance(msg,bytes):continue
            try:o=json.loads(msg)
            except Exception:continue
            if o.get("event")==event:return o
        raise TimeoutError(event)

    def close(self):
        try:self._send_frame(b"",8)
        except Exception:pass
        try:self.sock.close()
        except Exception:pass

def pause(ws):
    ws.send_json("cpu.stepping")
    try:
        ws.wait_event("cpu.stepping",5)
        return
    except Exception:
        pass
    for _ in range(15):
        try:
            s=ws.request("cpu.status",3)
            if s.get("stepping"):return
        except Exception:pass
        time.sleep(.1)
    raise RuntimeError("Could not pause CPU")

def resume(ws):
    ws.send_json("cpu.resume")
    time.sleep(.1)
    for _ in range(15):
        try:
            s=ws.request("cpu.status",3)
            if not s.get("stepping"):return
        except Exception:pass
        time.sleep(.1)

def screenshot(ws,path):
    # PPSSPP v1.20.x can return "Could not download output" for
    # gpu.buffer.screenshot / GPU_GetOutputFramebuffer. Use the active render
    # target instead; this is the PSP-native rendered scene and is the safer
    # debugger path.
    pause(ws)
    try:
        attempts=[]
        for typ in ("base64","uri"):
            try:
                o=ws.request("gpu.buffer.renderColor",20,type=typ)
                attempts.append({"type":typ,"keys":list(o.keys())})
                raw=None
                if isinstance(o.get("base64"),str) and o["base64"]:
                    raw=base64.b64decode(o["base64"])
                elif isinstance(o.get("uri"),str) and o["uri"].startswith("data:image/"):
                    raw=base64.b64decode(o["uri"].split(",",1)[1])
                elif isinstance(o.get("data"),str) and o["data"]:
                    v=o["data"]
                    if v.startswith("data:image/"):
                        v=v.split(",",1)[1]
                    raw=base64.b64decode(v)
                if raw and raw.startswith(b"\\x89PNG\\r\\n\\x1a\\n"):
                    Path(path).write_bytes(raw)
                    return {
                        "source":"gpu.buffer.renderColor",
                        "type":typ,
                        "width":o.get("width"),
                        "height":o.get("height"),
                        "bytes":len(raw),
                        "response_keys":list(o.keys()),
                    }
                attempts[-1]["decode_error"]="No PNG payload in response"
            except Exception as e:
                attempts.append({"type":typ,"error":str(e)})
        raise RuntimeError(f"renderColor capture failed: {attempts}")
    finally:
        resume(ws)

def mem_search(ws,text):
    p=text.encode("utf-8")
    o=ws.request("memory.search",20,address=0x08000000,size=0x02000000,
                 type="bytes",base64=base64.b64encode(p).decode(),align=1,maxResults=20)
    return o.get("matches",[]),bool(o.get("truncated",False))

def press(ws,button,duration=2):
    return ws.request("input.buttons.press",10,button=button,duration=duration)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--port",type=int,required=True)
    ap.add_argument("--outdir",required=True)
    a=ap.parse_args()
    out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)
    ws=None
    report={"step":"STEP_070_FIX4","status":"IN_PROGRESS","port":a.port,
            "runtime_verified":False,"route_discovery_only":True}
    try:
        last=None
        for _ in range(60):
            try:
                ws=WSClient("127.0.0.1",a.port,timeout=3);break
            except Exception as e:
                last=e;time.sleep(.5)
        if ws is None:raise RuntimeError(f"Could not connect debugger: {last}")

        # Protocol liveness only. OS-level PID/command-line identity is verified
        # by PowerShell before this Python script is allowed to run.
        ver=ws.request("version",10,name="bia-step070-fix4",version="1.0")
        report["debugger_version_response"]=ver

        game=None
        for _ in range(60):
            try:
                g=ws.request("game.status",5)
                game=g.get("game")
                report["last_game_status"]=g
                if game:break
            except Exception:pass
            time.sleep(.5)
        if not game:raise RuntimeError("Game did not report boot-complete state")
        report["game"]=game

        time.sleep(5)
        report["title_screenshot"]=screenshot(ws,out/"00_title.png")

        def sample():
            d={}
            for t in ["스커미시 로비","게임 팁:","늪을 건너"]:
                try:
                    m,tr=mem_search(ws,t);d[t]={"matches":m,"truncated":tr}
                except Exception as e:d[t]={"error":str(e)}
            return d

        report["memory_at_title"]=sample()

        press(ws,"start",3)
        time.sleep(4)
        report["main_screenshot"]=screenshot(ws,out/"01_main_menu.png")
        report["memory_at_main_menu"]=sample()

        sels=[]
        for i in range(1,7):
            press(ws,"down",2);time.sleep(.7)
            fn=f"{i+1:02d}_main_down_{i}.png"
            sels.append({"down_count":i,"screenshot":fn,"capture":screenshot(ws,out/fn)})
        report["main_menu_selection_sweep"]=sels
        report["memory_after_selection_sweep"]=sample()

        hits=[]
        for phase in ("memory_at_title","memory_at_main_menu","memory_after_selection_sweep"):
            for text,rec in report[phase].items():
                if rec.get("matches"):hits.append({"phase":phase,"text":text,"matches":rec["matches"]})
        report["korean_runtime_memory_hits"]=hits
        report["runtime_loaded_korean"]=bool(hits)
        report["runtime_render_verified"]=False
        report["status"]="RUNTIME_ROUTE_DISCOVERY_CAPTURED"
        report["next_action"]="Inspect menu screenshots, then confirm only the exact Skirmish entry."
    finally:
        if ws:ws.close()
        (out/"step070_fix4_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")

if __name__=="__main__":main()
