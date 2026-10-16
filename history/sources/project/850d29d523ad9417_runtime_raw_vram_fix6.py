#!/usr/bin/env python3
import argparse, base64, hashlib, json, os, socket, struct, time, zlib
from pathlib import Path

VRAM_BUFS=(0x04000000,0x04044000)
STRIDE=512
W=480
H=272
BPP=2
READ_SIZE=STRIDE*H*BPP

class WSClient:
    def __init__(self,host,port,path="/debugger",timeout=10):
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
            if len(data)>65536: raise RuntimeError("Handshake too large")
        head=data.split(b"\r\n\r\n",1)[0].decode("latin1","replace")
        if " 101 " not in head: raise RuntimeError("WebSocket handshake failed: "+head[:1000])
        accept=None
        for line in head.split("\r\n")[1:]:
            if ":" in line:
                k,v=line.split(":",1)
                if k.lower()=="sec-websocket-accept":accept=v.strip()
        exp=base64.b64encode(hashlib.sha1((key+"258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()).decode()
        if accept!=exp:raise RuntimeError("Bad WebSocket accept")
        self.ticket=0

    def _readn(self,n):
        d=b""
        while len(d)<n:
            x=self.sock.recv(n-len(d))
            if not x:raise RuntimeError("WebSocket closed")
            d+=x
        return d

    def _send_frame(self,payload,opcode=1):
        if isinstance(payload,str):payload=payload.encode("utf-8")
        n=len(payload);mask=os.urandom(4)
        h=bytes([0x80|opcode])
        if n<126:h+=bytes([0x80|n])
        elif n<65536:h+=bytes([0x80|126])+struct.pack("!H",n)
        else:h+=bytes([0x80|127])+struct.pack("!Q",n)
        masked=bytes(payload[i]^mask[i%4] for i in range(n))
        self.sock.sendall(h+mask+masked)

    def _recv_message(self,timeout=30):
        old=self.sock.gettimeout();self.sock.settimeout(timeout)
        try:
            chunks=[];msgop=None
            while True:
                h=self._readn(2);b0,b1=h
                fin=bool(b0&0x80);op=b0&0x0f
                n=b1&0x7f;masked=bool(b1&0x80)
                if n==126:n=struct.unpack("!H",self._readn(2))[0]
                elif n==127:n=struct.unpack("!Q",self._readn(8))[0]
                mask=self._readn(4) if masked else None
                data=self._readn(n) if n else b""
                if mask:data=bytes(data[i]^mask[i%4] for i in range(n))

                if op==8:raise RuntimeError("WebSocket server closed")
                if op==9:
                    self._send_frame(data,10);continue
                if op==10:continue
                if op in (1,2):
                    msgop=op;chunks=[data]
                elif op==0:
                    if msgop is None:continue
                    chunks.append(data)
                else:
                    continue

                if fin and msgop is not None:
                    raw=b"".join(chunks)
                    return raw.decode("utf-8","replace") if msgop==1 else raw
        finally:
            self.sock.settimeout(old)

    def send_json(self,event,**kwargs):
        self.ticket+=1
        o={"event":event,"ticket":self.ticket};o.update(kwargs)
        self._send_frame(json.dumps(o,separators=(",",":"),ensure_ascii=False))
        return self.ticket

    def request(self,event,timeout=30,**kwargs):
        t=self.send_json(event,**kwargs)
        end=time.time()+timeout;seen=[]
        while time.time()<end:
            msg=self._recv_message(max(.2,end-time.time()))
            if isinstance(msg,bytes):continue
            try:o=json.loads(msg)
            except Exception:continue
            seen.append(o)
            if o.get("ticket")==t:
                if o.get("event")=="error":
                    raise RuntimeError(f"{event} error: {o}")
                return o
        raise TimeoutError(f"Timeout waiting {event}; last={seen[-6:]}")

    def wait_event(self,event,timeout=8):
        end=time.time()+timeout
        while time.time()<end:
            msg=self._recv_message(max(.2,end-time.time()))
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
        ws.wait_event("cpu.stepping",5);return
    except Exception:pass
    for _ in range(20):
        try:
            s=ws.request("cpu.status",3)
            if s.get("stepping"):return
        except Exception:pass
        time.sleep(.1)
    raise RuntimeError("Could not pause CPU")

def resume(ws):
    ws.send_json("cpu.resume")
    time.sleep(.1)
    for _ in range(20):
        try:
            s=ws.request("cpu.status",3)
            if not s.get("stepping"):return
        except Exception:pass
        time.sleep(.1)

def png_chunk(tag,data):
    return struct.pack(">I",len(data))+tag+data+struct.pack(">I",zlib.crc32(tag+data)&0xffffffff)

def write_png_rgb(path,w,h,rgb):
    if len(rgb)!=w*h*3:raise ValueError("RGB length mismatch")
    scan=b"".join(b"\x00"+rgb[y*w*3:(y+1)*w*3] for y in range(h))
    raw=b"\x89PNG\r\n\x1a\n"
    raw+=png_chunk(b"IHDR",struct.pack(">IIBBBBB",w,h,8,2,0,0,0))
    raw+=png_chunk(b"IDAT",zlib.compress(scan,9))
    raw+=png_chunk(b"IEND",b"")
    Path(path).write_bytes(raw)

def rgb565_to_rgb(raw):
    need=STRIDE*H*2
    if len(raw)!=need:raise RuntimeError(f"VRAM read size {len(raw)} != {need}")
    out=bytearray(W*H*3)
    j=0
    for y in range(H):
        row=y*STRIDE*2
        for x in range(W):
            i=row+x*2
            v=raw[i] | (raw[i+1]<<8)
            r=((v>>11)&31)*255//31
            g=((v>>5)&63)*255//63
            b=(v&31)*255//31
            out[j]=r;out[j+1]=g;out[j+2]=b;j+=3
    return bytes(out)

def image_score(rgb):
    # Simple activity score: number of non-near-black pixels plus sampled variance.
    nonblack=0
    vals=[]
    step=max(1,(W*H)//5000)
    px=W*H
    for p in range(0,px,step):
        i=p*3
        y=(rgb[i]*3+rgb[i+1]*6+rgb[i+2])//10
        vals.append(y)
        if y>12:nonblack+=1
    if not vals:return 0
    mean=sum(vals)/len(vals)
    var=sum((v-mean)**2 for v in vals)/len(vals)
    return int(nonblack*1000+var)

def read_mem(ws,address,size):
    o=ws.request("memory.read",timeout=40,address=address,size=size,replacements=False)
    s=o.get("base64")
    if not isinstance(s,str):raise RuntimeError(f"memory.read missing base64: keys={list(o)}")
    raw=base64.b64decode(s)
    if len(raw)!=size:raise RuntimeError(f"memory.read length mismatch {len(raw)} != {size}")
    return raw

def capture_vram(ws,out,prefix):
    pause(ws)
    try:
        caps=[]
        for idx,addr in enumerate(VRAM_BUFS):
            raw=read_mem(ws,addr,READ_SIZE)
            rgb=rgb565_to_rgb(raw)
            fn=f"{prefix}_vram{idx}_{addr:08X}.png"
            write_png_rgb(out/fn,W,H,rgb)
            caps.append({
                "buffer_index":idx,
                "address":f"0x{addr:08X}",
                "file":fn,
                "raw_sha256":hashlib.sha256(raw).hexdigest(),
                "png_sha256":hashlib.sha256((out/fn).read_bytes()).hexdigest(),
                "score":image_score(rgb),
            })
        caps_sorted=sorted(caps,key=lambda x:x["score"],reverse=True)
        return {"buffers":caps,"preferred":caps_sorted[0]["file"]}
    finally:
        resume(ws)

def set_button(ws,name,state):
    ws.request("input.buttons.send",10,buttons={name:bool(state)})

def tap(ws,name,hold=.20,settle=.65):
    set_button(ws,name,True)
    time.sleep(hold)
    set_button(ws,name,False)
    time.sleep(settle)

def mem_search(ws,text):
    p=text.encode("utf-8")
    o=ws.request("memory.search",25,address=0x08000000,size=0x02000000,
                 type="bytes",base64=base64.b64encode(p).decode(),
                 align=1,maxResults=20)
    return o.get("matches",[]),bool(o.get("truncated",False))

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--port",type=int,required=True)
    ap.add_argument("--outdir",required=True)
    a=ap.parse_args()
    out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)
    ws=None
    report={
        "step":"STEP_070_FIX6",
        "status":"IN_PROGRESS",
        "port":a.port,
        "capture_method":"RAW_VRAM_RGB565",
        "vram_addresses":[f"0x{x:08X}" for x in VRAM_BUFS],
        "stride":STRIDE,"width":W,"height":H,
        "runtime_verified":False,
        "route_discovery_only":True,
    }
    try:
        last=None
        for _ in range(60):
            try:
                ws=WSClient("127.0.0.1",a.port,timeout=3);break
            except Exception as e:
                last=e;time.sleep(.5)
        if ws is None:raise RuntimeError(f"Could not connect debugger: {last}")

        report["version"]=ws.request("version",10,name="bia-step070-fix6",version="1.0")

        game=None
        for _ in range(70):
            try:
                gs=ws.request("game.status",5)
                report["last_game_status"]=gs
                game=gs.get("game")
                if game:break
            except Exception:pass
            time.sleep(.5)
        if not game:raise RuntimeError("Game did not reach boot-complete state")
        report["game"]=game

        # Let software renderer settle, then raw-VRAM capture both buffers.
        time.sleep(4)
        report["boot_capture"]=capture_vram(ws,out,"00_boot")

        # Use the proven send/on-off style. Several START taps safely skip boot/title
        # prompts; no CROSS/CIRCLE confirmation is sent here.
        start_caps=[]
        for i in range(1,5):
            tap(ws,"start",hold=.20,settle=.90)
            start_caps.append({"start_count":i,"capture":capture_vram(ws,out,f"01_start_{i}")})
        report["start_sweep"]=start_caps

        def sample():
            d={}
            for t in ["스커미시 로비","게임 팁:","늪을 건너"]:
                try:
                    m,tr=mem_search(ws,t);d[t]={"matches":m,"truncated":tr}
                except Exception as e:d[t]={"error":str(e)}
            return d

        report["memory_after_start_sweep"]=sample()

        # Main-menu route discovery only: DOWN without confirm. Capture both VRAM
        # buffers each time, just like the prior successful Stage40Y workflow.
        sels=[]
        for i in range(1,7):
            tap(ws,"down",hold=.20,settle=.55)
            sels.append({"down_count":i,"capture":capture_vram(ws,out,f"02_down_{i}")})
        report["down_sweep"]=sels
        report["memory_after_down_sweep"]=sample()

        hits=[]
        for phase in ("memory_after_start_sweep","memory_after_down_sweep"):
            for text,rec in report[phase].items():
                if rec.get("matches"):hits.append({"phase":phase,"text":text,"matches":rec["matches"]})
        report["korean_runtime_memory_hits"]=hits
        report["runtime_loaded_korean"]=bool(hits)
        report["runtime_render_verified"]=False
        report["status"]="RUNTIME_ROUTE_DISCOVERY_CAPTURED"
        report["next_action"]="Inspect raw-VRAM captures to identify the exact Skirmish selection, then confirm only that entry."
    finally:
        if ws:ws.close()
        (out/"step070_fix6_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")

if __name__=="__main__":
    main()
