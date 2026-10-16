#!/usr/bin/env python3
import argparse,base64,hashlib,json,os,socket,struct,time,zlib
from pathlib import Path
VRAMS=(0x04000000,0x04044000); RAM=0x08000000; RAMSZ=0x02000000
W=480;H=272;STRIDE=512;VSZ=STRIDE*H*2

class WS:
    def __init__(self,port):
        self.s=socket.create_connection(("127.0.0.1",port),timeout=5);self.s.settimeout(30)
        key=base64.b64encode(os.urandom(16)).decode()
        req=(f"GET /debugger HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
             f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\nSec-WebSocket-Protocol: debugger.ppsspp.org\r\n\r\n")
        self.s.sendall(req.encode());d=b""
        while b"\r\n\r\n" not in d:d+=self.s.recv(4096)
        if b" 101 " not in d.split(b"\r\n\r\n",1)[0]:raise RuntimeError("WS handshake failed")
        self.t=0
    def rn(self,n):
        d=b""
        while len(d)<n:
            x=self.s.recv(n-len(d))
            if not x:raise RuntimeError("WS closed")
            d+=x
        return d
    def frame(self,p,op=1):
        if isinstance(p,str):p=p.encode()
        n=len(p);m=os.urandom(4);h=bytes([0x80|op])
        if n<126:h+=bytes([0x80|n])
        elif n<65536:h+=bytes([0x80|126])+struct.pack("!H",n)
        else:h+=bytes([0x80|127])+struct.pack("!Q",n)
        self.s.sendall(h+m+bytes(p[i]^m[i%4] for i in range(n)))
    def recv(self,timeout=50):
        old=self.s.gettimeout();self.s.settimeout(timeout)
        try:
            chunks=[];msgop=None
            while 1:
                b0,b1=self.rn(2);fin=bool(b0&128);op=b0&15;n=b1&127
                if n==126:n=struct.unpack("!H",self.rn(2))[0]
                elif n==127:n=struct.unpack("!Q",self.rn(8))[0]
                mask=self.rn(4) if b1&128 else None;d=self.rn(n) if n else b""
                if mask:d=bytes(d[i]^mask[i%4] for i in range(n))
                if op==8:raise RuntimeError("WS server closed")
                if op==9:self.frame(d,10);continue
                if op==10:continue
                if op in (1,2):msgop=op;chunks=[d]
                elif op==0 and msgop is not None:chunks.append(d)
                else:continue
                if fin and msgop is not None:
                    raw=b"".join(chunks);return raw.decode("utf-8","replace") if msgop==1 else raw
        finally:self.s.settimeout(old)
    def request(self,event,timeout=50,**kw):
        self.t+=1;t=self.t;o={"event":event,"ticket":t};o.update(kw);self.frame(json.dumps(o,separators=(",",":")))
        end=time.time()+timeout
        while time.time()<end:
            m=self.recv(max(.2,end-time.time()))
            if isinstance(m,bytes):continue
            try:r=json.loads(m)
            except:continue
            if r.get("ticket")==t:
                if r.get("event")=="error":raise RuntimeError(f"{event}: {r}")
                return r
        raise TimeoutError(event)
    def send(self,event,**kw):
        self.t+=1;o={"event":event,"ticket":self.t};o.update(kw);self.frame(json.dumps(o,separators=(",",":")))
    def close(self):
        try:self.frame(b"",8)
        except:pass
        try:self.s.close()
        except:pass

def pause(w):
    w.send("cpu.stepping");time.sleep(.15)
    for _ in range(30):
        try:
            if w.request("cpu.status",3).get("stepping"):return
        except:pass
        time.sleep(.1)
    raise RuntimeError("pause failed")
def resume(w):w.send("cpu.resume");time.sleep(.15)
def read(w,a,n):
    r=w.request("memory.read",60,address=a,size=n,replacements=False)
    d=base64.b64decode(r["base64"])
    if len(d)!=n:raise RuntimeError("memory.read size mismatch")
    return d
def rgb565(d):
    out=bytearray(W*H*3);j=0
    for y in range(H):
        row=y*STRIDE*2
        for x in range(W):
            i=row+x*2;v=d[i]|d[i+1]<<8
            out[j]=((v>>11)&31)*255//31;out[j+1]=((v>>5)&63)*255//63;out[j+2]=(v&31)*255//31;j+=3
    return bytes(out)
def ch(t,d):return struct.pack(">I",len(d))+t+d+struct.pack(">I",zlib.crc32(t+d)&0xffffffff)
def png(p,rgb):
    scan=b"".join(b"\0"+rgb[y*W*3:(y+1)*W*3] for y in range(H))
    d=b"\x89PNG\r\n\x1a\n"+ch(b"IHDR",struct.pack(">IIBBBBB",W,H,8,2,0,0,0))+ch(b"IDAT",zlib.compress(scan,9))+ch(b"IEND",b"")
    Path(p).write_bytes(d)
def sim(rgb,s):
    e=0;n=0;close=0
    for q in s["samples"]:
        i=(q["y"]*W+q["x"])*3;v=q["rgb"];d=abs(rgb[i]-v[0])+abs(rgb[i+1]-v[1])+abs(rgb[i+2]-v[2]);e+=d;n+=1
        if d<=12:close+=1
    return {"mae":e/(3*n) if n else 999,"close_ratio":close/n if n else 0}
def good(x):return x["mae"]<=9 or x["close_ratio"]>=.84
def capture(w,out,prefix,sigs):
    pause(w)
    try:
        a=[]
        for bi,addr in enumerate(VRAMS):
            raw=read(w,addr,VSZ);rgb=rgb565(raw);fn=f"{prefix}_vram{bi}_{addr:08X}.png";png(out/fn,rgb)
            a.append({"file":fn,"address":f"0x{addr:08X}","sha256":hashlib.sha256(raw).hexdigest(),
                      "similarity":{k:sim(rgb,v) for k,v in sigs.items()}})
        return a
    finally:resume(w)
def matched(caps,name):return any(good(c["similarity"][name]) for c in caps)
def tap(w,name,wait=.8):
    w.request("input.buttons.send",10,buttons={name:True});time.sleep(.22)
    w.request("input.buttons.send",10,buttons={name:False});time.sleep(wait)
def scan(w,targets):
    pause(w)
    try:
        parts=[read(w,RAM+o,min(0x100000,RAMSZ-o)) for o in range(0,RAMSZ,0x100000)]
    finally:resume(w)
    blob=b"".join(parts);res={}
    for t in targets:
        p=t["korean"].encode("utf-8");arr=[];st=0
        while 1:
            i=blob.find(p,st)
            if i<0:break
            arr.append(f"0x{RAM+i:08X}")
            if len(arr)>=20:break
            st=i+1
        res[t["resource_id"]]={"korean":t["korean"],"classification":t["classification"],"addresses":arr,"loaded":bool(arr),"sources":t["sources"]}
    return res

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--port",type=int,required=True);ap.add_argument("--outdir",required=True);ap.add_argument("--sigs",required=True);ap.add_argument("--targets",required=True)
    a=ap.parse_args();out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)
    sigs=json.loads(Path(a.sigs).read_text(encoding="utf-8"));targets=json.loads(Path(a.targets).read_text(encoding="utf-8"))["targets"]
    rep={"step":"STEP_071_FIX1","status":"IN_PROGRESS","runtime_verified":False}
    w=None
    try:
        last=None
        for _ in range(60):
            try:w=WS(a.port);break
            except Exception as e:last=e;time.sleep(.5)
        if not w:raise RuntimeError(f"WS connect failed {last}")
        rep["version"]=w.request("version",10,name="bia-step071-fix1",version="1.0")
        for _ in range(70):
            g=w.request("game.status",5)
            if g.get("game"):rep["game"]=g["game"];break
            time.sleep(.5)
        if "game" not in rep:raise RuntimeError("game boot timeout")

        # Deterministic known route.
        time.sleep(3)
        for i in range(14):
            c=capture(w,out,f"00_title_{i:02d}",sigs)
            if matched(c,"title"):break
            tap(w,"start",1.0)
        else:raise RuntimeError("title not reached")
        tap(w,"start",.5)
        for i in range(30):
            c=capture(w,out,f"01_story_{i:02d}",sigs)
            if matched(c,"menu_story"):break
            time.sleep(.35)
        else:raise RuntimeError("story menu not reached")
        tap(w,"down",.75)
        c=capture(w,out,"02_skirmish_selected",sigs)
        if not matched(c,"menu_skirmish"):raise RuntimeError("skirmish selection mismatch")
        tap(w,"cross",.7)
        for i in range(20):
            c=capture(w,out,f"03_solo_wait_{i:02d}",sigs)
            if matched(c,"skirmish_solo"):break
            time.sleep(.35)
        else:raise RuntimeError("solo menu not reached")

        rep["before_solo_confirm"]=scan(w,targets)

        # Only new action in FIX1: confirm default Solo Mode once.
        tap(w,"cross",.7)
        post=[]
        for i in range(14):
            time.sleep(.6)
            post.append({"sample":i,"capture":capture(w,out,f"04_solo_post_{i:02d}",sigs)})
        rep["post_solo_confirm_captures"]=post
        aft=scan(w,targets);rep["after_solo_confirm"]=aft
        bef=rep["before_solo_confirm"]
        newly=[rid for rid,v in aft.items() if v["loaded"] and not bef[rid]["loaded"]]
        rep["loaded_after_count"]=sum(1 for v in aft.values() if v["loaded"])
        rep["newly_loaded_count"]=len(newly);rep["newly_loaded_ids"]=newly
        rep["newly_loaded_details"]=[dict(aft[r],resource_id=r) for r in newly]
        explicit=[]
        wanted={"스커미시 로비","게임 팁:%newline%","늪을 건너"}
        for rid,v in aft.items():
            if v["korean"] in wanted:
                explicit.append({"resource_id":rid,"korean":v["korean"],"before_loaded":bef[rid]["loaded"],"after_loaded":v["loaded"],"addresses":v["addresses"],"sources":v["sources"]})
        rep["explicit_canaries"]=explicit
        rep["status"]="SOLO_CONFIRMED_INT92_FINAL_CANARY_COMPLETE"
        rep["next_action"]="Stop INT92 canary work and proceed to compiled-MDI 967 application."
    finally:
        if w:w.close()
        (out/"step071_fix1_report.json").write_text(json.dumps(rep,ensure_ascii=False,indent=2),encoding="utf-8")
if __name__=="__main__":main()
