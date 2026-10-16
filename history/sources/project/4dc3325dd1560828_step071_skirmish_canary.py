#!/usr/bin/env python3
import argparse, base64, hashlib, json, os, socket, struct, time, zlib
from pathlib import Path

VRAMS=(0x04000000,0x04044000)
RAM_BASE=0x08000000
RAM_SIZE=0x02000000
STRIDE=512
W=480
H=272
VRAM_SIZE=STRIDE*H*2

class WS:
    def __init__(self,port):
        self.s=socket.create_connection(("127.0.0.1",port),timeout=5)
        self.s.settimeout(20)
        key=base64.b64encode(os.urandom(16)).decode()
        req=(
            f"GET /debugger HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\n"
            "Upgrade: websocket\r\nConnection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n"
            "Sec-WebSocket-Protocol: debugger.ppsspp.org\r\n\r\n"
        )
        self.s.sendall(req.encode("ascii"))
        d=b""
        while b"\r\n\r\n" not in d:
            d+=self.s.recv(4096)
        head=d.split(b"\r\n\r\n",1)[0].decode("latin1","replace")
        if " 101 " not in head: raise RuntimeError("WS handshake failed: "+head[:1000])
        self.ticket=0

    def rn(self,n):
        d=b""
        while len(d)<n:
            x=self.s.recv(n-len(d))
            if not x: raise RuntimeError("WS closed")
            d+=x
        return d

    def frame(self,payload,opcode=1):
        if isinstance(payload,str):payload=payload.encode()
        n=len(payload);mask=os.urandom(4)
        h=bytes([0x80|opcode])
        if n<126:h+=bytes([0x80|n])
        elif n<65536:h+=bytes([0x80|126])+struct.pack("!H",n)
        else:h+=bytes([0x80|127])+struct.pack("!Q",n)
        self.s.sendall(h+mask+bytes(payload[i]^mask[i%4] for i in range(n)))

    def recv(self,timeout=40):
        old=self.s.gettimeout();self.s.settimeout(timeout)
        try:
            chunks=[];msgop=None
            while True:
                b0,b1=self.rn(2);fin=bool(b0&0x80);op=b0&15;n=b1&127
                if n==126:n=struct.unpack("!H",self.rn(2))[0]
                elif n==127:n=struct.unpack("!Q",self.rn(8))[0]
                mask=self.rn(4) if b1&0x80 else None
                data=self.rn(n) if n else b""
                if mask:data=bytes(data[i]^mask[i%4] for i in range(n))
                if op==8:raise RuntimeError("WS server closed")
                if op==9:self.frame(data,10);continue
                if op==10:continue
                if op in (1,2):msgop=op;chunks=[data]
                elif op==0 and msgop is not None:chunks.append(data)
                else:continue
                if fin and msgop is not None:
                    raw=b"".join(chunks)
                    return raw.decode("utf-8","replace") if msgop==1 else raw
        finally:self.s.settimeout(old)

    def request(self,event,timeout=40,**kw):
        self.ticket+=1;t=self.ticket
        o={"event":event,"ticket":t};o.update(kw)
        self.frame(json.dumps(o,separators=(",",":"),ensure_ascii=False))
        end=time.time()+timeout
        while time.time()<end:
            m=self.recv(max(.2,end-time.time()))
            if isinstance(m,bytes):continue
            try:r=json.loads(m)
            except:continue
            if r.get("ticket")==t:
                if r.get("event")=="error":raise RuntimeError(f"{event} error: {r}")
                return r
        raise TimeoutError(event)

    def send(self,event,**kw):
        self.ticket+=1
        o={"event":event,"ticket":self.ticket};o.update(kw)
        self.frame(json.dumps(o,separators=(",",":"),ensure_ascii=False))

    def close(self):
        try:self.frame(b"",8)
        except:pass
        try:self.s.close()
        except:pass

def pause(ws):
    ws.send("cpu.stepping")
    time.sleep(.15)
    for _ in range(30):
        try:
            if ws.request("cpu.status",3).get("stepping"):return
        except:pass
        time.sleep(.1)
    raise RuntimeError("Could not pause CPU")

def resume(ws):
    ws.send("cpu.resume")
    time.sleep(.15)

def memread(ws,addr,size):
    r=ws.request("memory.read",60,address=addr,size=size,replacements=False)
    raw=base64.b64decode(r["base64"])
    if len(raw)!=size:raise RuntimeError(f"memory.read {len(raw)} != {size}")
    return raw

def rgb565(raw):
    out=bytearray(W*H*3);j=0
    for y in range(H):
        row=y*STRIDE*2
        for x in range(W):
            i=row+x*2;v=raw[i]|raw[i+1]<<8
            out[j]=((v>>11)&31)*255//31
            out[j+1]=((v>>5)&63)*255//63
            out[j+2]=(v&31)*255//31;j+=3
    return bytes(out)

def chunk(tag,d):
    return struct.pack(">I",len(d))+tag+d+struct.pack(">I",zlib.crc32(tag+d)&0xffffffff)

def savepng(path,rgb):
    scan=b"".join(b"\x00"+rgb[y*W*3:(y+1)*W*3] for y in range(H))
    p=b"\x89PNG\r\n\x1a\n"+chunk(b"IHDR",struct.pack(">IIBBBBB",W,H,8,2,0,0,0))
    p+=chunk(b"IDAT",zlib.compress(scan,9))+chunk(b"IEND",b"")
    Path(path).write_bytes(p)

def similarity(rgb,sig):
    err=0;n=0;close=0
    for s in sig["samples"]:
        i=(s["y"]*W+s["x"])*3;e=s["rgb"]
        d=abs(rgb[i]-e[0])+abs(rgb[i+1]-e[1])+abs(rgb[i+2]-e[2])
        err+=d;n+=1
        if d<=12:close+=1
    return {"mae":err/(3*n) if n else 999,"close_ratio":close/n if n else 0}

def matches(sim):
    return sim["mae"]<=9 or sim["close_ratio"]>=.84

def capture(ws,out,prefix,sigs):
    pause(ws)
    try:
        recs=[]
        for bi,addr in enumerate(VRAMS):
            raw=memread(ws,addr,VRAM_SIZE);rgb=rgb565(raw)
            fn=f"{prefix}_vram{bi}_{addr:08X}.png";savepng(out/fn,rgb)
            sm={k:similarity(rgb,v) for k,v in sigs.items()}
            recs.append({"buffer":bi,"address":f"0x{addr:08X}","file":fn,
                         "raw_sha256":hashlib.sha256(raw).hexdigest(),"similarity":sm})
        return recs
    finally:resume(ws)

def cap_matches(caps,name):
    return any(matches(c["similarity"][name]) for c in caps)

def btn(ws,name,on):
    ws.request("input.buttons.send",10,buttons={name:bool(on)})

def tap(ws,name,hold=.22,settle=.8):
    btn(ws,name,True);time.sleep(hold);btn(ws,name,False);time.sleep(settle)

def scan_targets(ws,targets):
    # One full 32MiB dump, then search all 92 targets locally.
    pause(ws)
    try:
        pieces=[]
        chunk_size=0x100000
        for off in range(0,RAM_SIZE,chunk_size):
            pieces.append(memread(ws,RAM_BASE+off,min(chunk_size,RAM_SIZE-off)))
        ram=b"".join(pieces)
    finally:resume(ws)

    result={}
    for t in targets:
        p=t["korean"].encode("utf-8")
        addrs=[];start=0
        while True:
            i=ram.find(p,start)
            if i<0:break
            addrs.append(f"0x{RAM_BASE+i:08X}")
            if len(addrs)>=20:break
            start=i+1
        result[t["resource_id"]]={
            "korean":t["korean"],
            "classification":t["classification"],
            "addresses":addrs,
            "loaded":bool(addrs),
            "sources":t["sources"],
        }
    return result

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--port",type=int,required=True)
    ap.add_argument("--outdir",required=True)
    ap.add_argument("--signatures",required=True)
    ap.add_argument("--targets",required=True)
    a=ap.parse_args()
    out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)
    sigs=json.loads(Path(a.signatures).read_text(encoding="utf-8"))
    targets=json.loads(Path(a.targets).read_text(encoding="utf-8"))["targets"]
    ws=None
    rep={"step":"STEP_071","status":"IN_PROGRESS","runtime_verified":False,
         "scope":"INT92_SKIRMISH_CANARY","capture_method":"RAW_VRAM_RGB565"}
    try:
        last=None
        for _ in range(60):
            try:ws=WS(a.port);break
            except Exception as e:last=e;time.sleep(.5)
        if ws is None:raise RuntimeError(f"WS connect failed: {last}")
        rep["version"]=ws.request("version",10,name="bia-step071",version="1.0")
        for _ in range(70):
            g=ws.request("game.status",5)
            if g.get("game"):
                rep["game"]=g["game"];break
            time.sleep(.5)
        if "game" not in rep:raise RuntimeError("Game did not boot")

        # Seek exact title using the stable FIX7 signature.
        title_steps=[]
        time.sleep(3)
        for i in range(14):
            c=capture(ws,out,f"00_title_seek_{i:02d}",sigs)
            title_steps.append({"attempt":i,"capture":c})
            if cap_matches(c,"title"):break
            tap(ws,"start",.20,1.0)
        else:raise RuntimeError("Title signature not reached")
        rep["title_seek"]=title_steps

        # Enter menu, but do NOT send any direction until Story-selected main menu
        # is actually visible.
        tap(ws,"start",.22,.5)
        menu_wait=[]
        for i in range(30):
            c=capture(ws,out,f"01_menu_wait_{i:02d}",sigs)
            menu_wait.append({"poll":i,"capture":c})
            if cap_matches(c,"menu_story"):break
            time.sleep(.35)
        else:raise RuntimeError("Story-selected main menu signature not reached")
        rep["main_menu_wait"]=menu_wait

        # Baseline scan before entering Skirmish.
        rep["int92_before_skirmish"]=scan_targets(ws,targets)

        # Story -> Skirmish is exactly one DOWN from the verified FIX7 menu.
        tap(ws,"down",.22,.75)
        c=capture(ws,out,"02_skirmish_selected",sigs)
        if not cap_matches(c,"menu_skirmish"):
            raise RuntimeError("One DOWN did not match verified Skirmish selection")
        rep["skirmish_selection_verified"]=True
        rep["skirmish_selected_capture"]=c

        # Confirm only the verified Skirmish item.
        tap(ws,"cross",.24,.7)

        # Capture the first ~10 seconds after entry without any more user input.
        post=[]
        for i in range(10):
            time.sleep(.75)
            post.append({"sample":i,"capture":capture(ws,out,f"03_skirmish_post_{i:02d}",sigs)})
        rep["post_skirmish_captures"]=post

        # One post-entry full RAM scan over all 92 translated targets.
        after=scan_targets(ws,targets)
        rep["int92_after_skirmish"]=after

        before=rep["int92_before_skirmish"]
        newly=[]
        loaded_after=[]
        for rid,v in after.items():
            if v["loaded"]:loaded_after.append(rid)
            if v["loaded"] and not before[rid]["loaded"]:
                newly.append(rid)
        rep["loaded_after_count"]=len(loaded_after)
        rep["newly_loaded_after_skirmish_count"]=len(newly)
        rep["newly_loaded_after_skirmish_ids"]=newly
        rep["newly_loaded_details"]=[after[rid] | {"resource_id":rid} for rid in newly]

        # Explicit canaries.
        canary_strings=["스커미시 로비","게임 팁:%newline%","늪을 건너"]
        explicit=[]
        for rid,v in after.items():
            if v["korean"] in canary_strings:
                explicit.append({"resource_id":rid,"korean":v["korean"],
                                 "before_loaded":before[rid]["loaded"],
                                 "after_loaded":v["loaded"],
                                 "addresses":v["addresses"],
                                 "sources":v["sources"]})
        rep["explicit_canaries"]=explicit

        rep["status"]="SKIRMISH_ENTERED_INT92_RUNTIME_SCAN_COMPLETE"
        rep["runtime_loaded_int92"]=bool(loaded_after)
        rep["runtime_render_verified"]=False
        rep["next_action"]="Inspect post-entry VRAM captures and explicit/newly-loaded INT92 strings; promote only what is actually evidenced."
    finally:
        if ws:ws.close()
        (out/"step071_report.json").write_text(json.dumps(rep,ensure_ascii=False,indent=2),encoding="utf-8")

if __name__=="__main__":main()
