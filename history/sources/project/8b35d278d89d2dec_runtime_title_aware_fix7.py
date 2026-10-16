#!/usr/bin/env python3
import argparse, base64, hashlib, json, os, socket, struct, time, zlib
from pathlib import Path

VRAM_BUFS=(0x04000000,0x04044000)
RAM_BASE=0x08000000
RAM_SIZE=0x02000000
STRIDE=512
W=480
H=272
READ_SIZE=STRIDE*H*2

class WSClient:
    def __init__(self,host,port,path="/debugger",timeout=10):
        self.sock=socket.create_connection((host,port),timeout=timeout)
        self.sock.settimeout(timeout)
        key=base64.b64encode(os.urandom(16)).decode()
        req=(f"GET {path} HTTP/1.1\r\nHost: {host}:{port}\r\nUpgrade: websocket\r\n"
             "Connection: Upgrade\r\n"
             f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n"
             "Sec-WebSocket-Protocol: debugger.ppsspp.org\r\n\r\n")
        self.sock.sendall(req.encode("ascii"))
        data=b""
        while b"\r\n\r\n" not in data:
            x=self.sock.recv(4096)
            if not x:raise RuntimeError("WebSocket handshake closed")
            data+=x
            if len(data)>65536:raise RuntimeError("Handshake too large")
        head=data.split(b"\r\n\r\n",1)[0].decode("latin1","replace")
        if " 101 " not in head:raise RuntimeError("Handshake failed: "+head[:1000])
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

    def _recv_message(self,timeout=40):
        old=self.sock.gettimeout();self.sock.settimeout(timeout)
        try:
            chunks=[];msgop=None
            while True:
                h=self._readn(2);b0,b1=h
                fin=bool(b0&0x80);op=b0&0x0f;n=b1&0x7f;masked=bool(b1&0x80)
                if n==126:n=struct.unpack("!H",self._readn(2))[0]
                elif n==127:n=struct.unpack("!Q",self._readn(8))[0]
                mask=self._readn(4) if masked else None
                data=self._readn(n) if n else b""
                if mask:data=bytes(data[i]^mask[i%4] for i in range(n))
                if op==8:raise RuntimeError("WebSocket server closed")
                if op==9:self._send_frame(data,10);continue
                if op==10:continue
                if op in (1,2):msgop=op;chunks=[data]
                elif op==0 and msgop is not None:chunks.append(data)
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

    def request(self,event,timeout=40,**kwargs):
        t=self.send_json(event,**kwargs);end=time.time()+timeout;seen=[]
        while time.time()<end:
            msg=self._recv_message(max(.2,end-time.time()))
            if isinstance(msg,bytes):continue
            try:o=json.loads(msg)
            except Exception:continue
            seen.append(o)
            if o.get("ticket")==t:
                if o.get("event")=="error":raise RuntimeError(f"{event} error: {o}")
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
    try:ws.wait_event("cpu.stepping",5);return
    except Exception:pass
    for _ in range(20):
        try:
            if ws.request("cpu.status",3).get("stepping"):return
        except Exception:pass
        time.sleep(.1)
    raise RuntimeError("Could not pause CPU")

def resume(ws):
    ws.send_json("cpu.resume");time.sleep(.1)
    for _ in range(20):
        try:
            if not ws.request("cpu.status",3).get("stepping"):return
        except Exception:pass
        time.sleep(.1)

def read_mem(ws,address,size):
    o=ws.request("memory.read",timeout=50,address=address,size=size,replacements=False)
    s=o.get("base64")
    if not isinstance(s,str):raise RuntimeError(f"memory.read missing base64 keys={list(o)}")
    raw=base64.b64decode(s)
    if len(raw)!=size:raise RuntimeError(f"memory.read length mismatch {len(raw)} != {size}")
    return raw

def rgb565_to_rgb(raw):
    out=bytearray(W*H*3);j=0
    for y in range(H):
        row=y*STRIDE*2
        for x in range(W):
            i=row+x*2;v=raw[i]|(raw[i+1]<<8)
            out[j]=((v>>11)&31)*255//31
            out[j+1]=((v>>5)&63)*255//63
            out[j+2]=(v&31)*255//31
            j+=3
    return bytes(out)

def png_chunk(tag,data):
    return struct.pack(">I",len(data))+tag+data+struct.pack(">I",zlib.crc32(tag+data)&0xffffffff)

def write_png(path,rgb):
    scan=b"".join(b"\x00"+rgb[y*W*3:(y+1)*W*3] for y in range(H))
    raw=b"\x89PNG\r\n\x1a\n"+png_chunk(b"IHDR",struct.pack(">IIBBBBB",W,H,8,2,0,0,0))
    raw+=png_chunk(b"IDAT",zlib.compress(scan,9))+png_chunk(b"IEND",b"")
    Path(path).write_bytes(raw)

def activity(rgb):
    vals=[];nonblack=0
    step=max(1,(W*H)//5000)
    for p in range(0,W*H,step):
        i=p*3;y=(rgb[i]*3+rgb[i+1]*6+rgb[i+2])//10
        vals.append(y)
        if y>12:nonblack+=1
    if not vals:return 0
    mean=sum(vals)/len(vals);var=sum((v-mean)**2 for v in vals)/len(vals)
    return int(nonblack*1000+var)

def title_similarity(rgb,sig):
    err=0;n=0;exactish=0
    for s in sig["samples"]:
        i=(s["y"]*W+s["x"])*3
        got=(rgb[i],rgb[i+1],rgb[i+2]);exp=s["rgb"]
        d=abs(got[0]-exp[0])+abs(got[1]-exp[1])+abs(got[2]-exp[2])
        err+=d;n+=1
        if d<=12:exactish+=1
    mae=err/(n*3) if n else 999
    ratio=exactish/n if n else 0
    return {"mae":mae,"exactish_ratio":ratio,"is_title":mae<=8.0 or ratio>=0.86}

def capture(ws,out,prefix,sig=None):
    pause(ws)
    try:
        caps=[]
        for idx,addr in enumerate(VRAM_BUFS):
            raw=read_mem(ws,addr,READ_SIZE)
            rgb=rgb565_to_rgb(raw)
            fn=f"{prefix}_vram{idx}_{addr:08X}.png";write_png(out/fn,rgb)
            rec={"buffer_index":idx,"address":f"0x{addr:08X}","file":fn,
                 "raw_sha256":hashlib.sha256(raw).hexdigest(),"score":activity(rgb)}
            if sig:rec["title_similarity"]=title_similarity(rgb,sig)
            caps.append(rec)
        pref=max(caps,key=lambda x:x["score"])
        return {"buffers":caps,"preferred":pref["file"]}
    finally:resume(ws)

def any_title(cap):
    return any(x.get("title_similarity",{}).get("is_title") for x in cap["buffers"])

def set_button(ws,name,state):
    ws.request("input.buttons.send",10,buttons={name:bool(state)})

def tap(ws,name,hold=.22,settle=.8):
    set_button(ws,name,True);time.sleep(hold);set_button(ws,name,False);time.sleep(settle)

def local_ram_search(ws,texts,chunk=0x100000):
    pats={t:t.encode("utf-8") for t in texts}
    hits={t:[] for t in texts}
    overlap=max(len(p) for p in pats.values())-1
    prev=b""
    for off in range(0,RAM_SIZE,chunk):
        size=min(chunk,RAM_SIZE-off)
        raw=read_mem(ws,RAM_BASE+off,size)
        buf=prev+raw
        base=RAM_BASE+off-len(prev)
        for t,p in pats.items():
            start=0
            while True:
                i=buf.find(p,start)
                if i<0:break
                a=base+i
                if RAM_BASE<=a<RAM_BASE+RAM_SIZE and a not in hits[t]:
                    hits[t].append(a)
                    if len(hits[t])>=20:break
                start=i+1
        prev=buf[-overlap:] if overlap else b""
    return {t:[f"0x{x:08X}" for x in xs] for t,xs in hits.items()}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--port",type=int,required=True)
    ap.add_argument("--outdir",required=True)
    ap.add_argument("--title-signature",required=True)
    a=ap.parse_args()
    out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)
    sig=json.loads(Path(a.title_signature).read_text(encoding="utf-8"))
    ws=None
    report={"step":"STEP_070_FIX7","status":"IN_PROGRESS","route_discovery_only":True,
            "capture_method":"RAW_VRAM_RGB565","title_detection":"FIX6_PIXEL_SIGNATURE",
            "runtime_verified":False}
    try:
        last=None
        for _ in range(60):
            try:ws=WSClient("127.0.0.1",a.port,timeout=3);break
            except Exception as e:last=e;time.sleep(.5)
        if ws is None:raise RuntimeError(f"Could not connect debugger: {last}")
        report["version"]=ws.request("version",10,name="bia-step070-fix7",version="1.0")
        for _ in range(70):
            gs=ws.request("game.status",5)
            if gs.get("game"):
                report["game"]=gs["game"];break
            time.sleep(.5)
        if "game" not in report:raise RuntimeError("Game did not boot")

        # Reach the exact title screen instead of blindly assuming a fixed START count.
        title_attempts=[]
        time.sleep(3)
        title_cap=None
        for i in range(12):
            cap=capture(ws,out,f"00_seek_title_{i:02d}",sig)
            title_attempts.append({"attempt":i,"capture":cap})
            if any_title(cap):
                title_cap=cap;break
            tap(ws,"start",hold=.20,settle=1.0)
        report["title_seek"]=title_attempts
        if title_cap is None:
            raise RuntimeError("Known FIX6 title screen not reached within 12 attempts")
        report["title_detected"]=True

        # Only now press START to enter the menu.
        tap(ws,"start",hold=.22,settle=2.0)
        menu_cap=capture(ws,out,"01_main_menu_candidate",sig)
        # If title still present, retry START up to two times.
        retry=0
        while any_title(menu_cap) and retry<2:
            retry+=1
            tap(ws,"start",hold=.22,settle=2.0)
            menu_cap=capture(ws,out,f"01_main_menu_candidate_retry{retry}",sig)
        if any_title(menu_cap):
            raise RuntimeError("START did not leave the title screen")
        report["main_menu_capture"]=menu_cap
        report["main_menu_start_retries"]=retry

        # Full 32MiB local search, matching the older BIA diagnostic method.
        search_terms=["START 버튼을 누르십시오","스토리","스커미시","옵션","스커미시 로비","게임 팁:","늪을 건너"]
        report["ram_search_at_main_menu"]=local_ram_search(ws,search_terms)

        # Capture initial selection and six DOWN positions, no confirmation.
        sweep=[{"down_count":0,"capture":menu_cap}]
        for i in range(1,7):
            tap(ws,"down",hold=.20,settle=.55)
            sweep.append({"down_count":i,"capture":capture(ws,out,f"02_main_down_{i}",sig)})
        report["main_menu_down_sweep"]=sweep

        report["status"]="MAIN_MENU_ROUTE_CAPTURED"
        report["runtime_render_verified"]=False
        report["next_action"]="Inspect down_count 0..6 captures, identify exact Skirmish selection, then confirm only that item."
    finally:
        if ws:ws.close()
        (out/"step070_fix7_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")

if __name__=="__main__":main()
