#!/usr/bin/env python3
import argparse, base64, json, socket, struct, time, secrets, sys
from pathlib import Path
from collections import Counter

RAM_START=0x08000000
RAM_END=0x0A000000
KNOWN_ST1_BASE=0x08E1F21C
CAMPAIGN_RENDER_CALL=0x0898E354
CAMPAIGN_EXPECTED_WORD=0x0E327D1A

NEEDLES=[
    (0x000,'운명의 랑데부'.encode('utf-8'),'title'),
    (0x06E,'베이커:'.encode('utf-8'),'baker'),
    (0x28F,'맥:'.encode('utf-8'),'mac'),
]
WATCH_OFFSETS=[0x000,0x06E,0x28F,0x39E,0x4B5,0x55C,0x59D]

class WS:
    def __init__(self,port):
        self.ticket=3000; self.pending=[]; self.sock=None
        err=None
        for af,host in [(socket.AF_INET6,'::1'),(socket.AF_INET,'127.0.0.1')]:
            try:
                s=socket.socket(af,socket.SOCK_STREAM); s.settimeout(.8); s.connect((host,port))
                self.sock=s; self.host=host; break
            except Exception as e: err=e
        if not self.sock: raise RuntimeError(f'debugger connect failed: {err}')
        key=base64.b64encode(secrets.token_bytes(16)).decode()
        req=(f'GET /debugger HTTP/1.1\r\nHost: {self.host}:{port}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n'
             f'Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\nSec-WebSocket-Protocol: debugger.ppsspp.org\r\n\r\n')
        self.sock.sendall(req.encode('ascii'))
        b=b''
        while b'\r\n\r\n' not in b: b+=self.sock.recv(4096)
        if b' 101 ' not in b.split(b'\r\n',1)[0]: raise RuntimeError('websocket handshake failed')
        self.sock.settimeout(.5)
    def _send(self,op,p=b''):
        if isinstance(p,str): p=p.encode('utf-8')
        m=secrets.token_bytes(4); n=len(p); h=bytes([0x80|op])
        if n<126: h+=bytes([0x80|n])
        elif n<=0xffff: h+=bytes([0x80|126])+struct.pack('!H',n)
        else: h+=bytes([0x80|127])+struct.pack('!Q',n)
        e=bytes(v^m[i%4] for i,v in enumerate(p)); self.sock.sendall(h+m+e)
    def _n(self,n):
        b=b''
        while len(b)<n:
            c=self.sock.recv(n-len(b))
            if not c: raise EOFError('closed')
            b+=c
        return b
    def recv(self,timeout=.5):
        self.sock.settimeout(timeout); parts=[]; started=False
        while True:
            b1,b2=self._n(2); op=b1&15; fin=bool(b1&0x80); n=b2&127
            if n==126: n=struct.unpack('!H',self._n(2))[0]
            elif n==127: n=struct.unpack('!Q',self._n(8))[0]
            mask=self._n(4) if b2&0x80 else None; p=self._n(n) if n else b''
            if mask: p=bytes(v^mask[i%4] for i,v in enumerate(p))
            if op==8: raise EOFError('close')
            if op==9: self._send(10,p); continue
            if op==10: continue
            if op==1: parts=[p]; started=True
            elif op==0 and started: parts.append(p)
            else: continue
            if fin: return json.loads(b''.join(parts).decode('utf-8','replace'))
    def request(self,event,timeout=10,**kw):
        self.ticket+=1; t=self.ticket; q={'event':event,'ticket':t}; q.update(kw)
        self._send(1,json.dumps(q,separators=(',',':'),ensure_ascii=False))
        end=time.time()+timeout
        while time.time()<end:
            try: r=self.recv(min(.5,max(.05,end-time.time())))
            except socket.timeout: continue
            if r.get('ticket')==t:
                if r.get('event')=='error': raise RuntimeError(f"{event}: {r.get('message')}")
                return r
            self.pending.append(r)
        raise TimeoutError(event)
    def poll(self,secs):
        o=self.pending; self.pending=[]; end=time.time()+secs
        while time.time()<end:
            try:o.append(self.recv(min(.4,max(.05,end-time.time()))))
            except socket.timeout:pass
        return o
    def close(self):
        try:self._send(8)
        except:pass
        try:self.sock.close()
        except:pass

def safe(ws,event,**kw):
    try:return {'ok':True,'response':ws.request(event,**kw)}
    except Exception as e:return {'ok':False,'error':repr(e)}

def readmem(ws,a,n):
    r=ws.request('memory.read',timeout=10,address=a,size=n,replacements=True)
    return base64.b64decode(r.get('base64',''))

def read32(ws,a):
    b=readmem(ws,a,4)
    return struct.unpack('<I',b)[0] if len(b)==4 else None

def tap(ws,name,hold=.28):
    a=ws.request('input.buttons.send',timeout=5,buttons={name:True})
    time.sleep(hold)
    b=ws.request('input.buttons.send',timeout=5,buttons={name:False})
    time.sleep(.18)
    return {'down':a,'up':b}

def threads(ws):
    try:return ws.request('hle.thread.list',timeout=5)
    except Exception as e:return {'error':repr(e)}

def has_bink(t): return 'bink thread' in json.dumps(t,ensure_ascii=False).lower()

def wait_initial_logo(ws,log,limit=90):
    seen=False; samples=[]; t0=time.time()
    while time.time()-t0<limit:
        t=threads(ws); active=has_bink(t); samples.append({'t':round(time.time()-t0,2),'active':active})
        if active: seen=True
        if seen and not active:
            log('Initial logo Bink ended.')
            return True,samples
        time.sleep(.7)
    return False,samples

def verify_st1(ws,base):
    rows=[]; score=0
    for off,needle,label in NEEDLES:
        try:g=readmem(ws,base+off,len(needle))
        except:g=b''
        ok=g==needle; score+=int(ok)
        rows.append({'label':label,'address_hex':f'0x{base+off:08X}','ok':ok,'got_hex':g.hex()})
    return score,rows

def scan_st1(ws):
    chunk=0x20000; carry=b''; ov=max(len(x[1]) for x in NEEDLES)-1
    for a in range(RAM_START,RAM_END,chunk):
        data=readmem(ws,a,min(chunk,RAM_END-a)); buf=carry+data; ba=a-len(carry)
        for off,needle,label in NEEDLES:
            p=buf.find(needle)
            if p>=0:
                base=ba+p-off; score,rows=verify_st1(ws,base)
                if score>=2:return base,label,rows
        carry=buf[-ov:]
    return None

def wait_campaign(ws,log,limit=40):
    t0=time.time(); samples=[]
    while time.time()-t0<limit:
        try:w=read32(ws,CAMPAIGN_RENDER_CALL)
        except:w=None
        samples.append({'t':round(time.time()-t0,2),'word_hex':None if w is None else f'0x{w:08X}'})
        if w==CAMPAIGN_EXPECTED_WORD:
            log(f'BIAOFF campaign module confirmed at 0x{CAMPAIGN_RENDER_CALL:08X}.')
            return True,samples
        time.sleep(.4)
    return False,samples



def event_type_counts(events):
    c = Counter()
    for ev in events:
        c[str(ev.get('event', '<none>'))] += 1
    return dict(c.most_common())

def memory_hits_from(events):
    out = []
    for ev in events:
        if ev.get('event') == 'cpu.breakpoint.hit' and ev.get('hit', {}).get('kind') == 'memory':
            out.append(ev)
    return out

def flush_existing_events(ws, log, seconds=.25):
    evs = ws.poll(seconds)
    log(f'Flushed {len(evs)} pre-watchpoint queued events BEFORE arming.')
    return {
        'count': len(evs),
        'types': event_type_counts(evs),
        'memory_hits': len(memory_hits_from(evs)),
    }

def bp_list(ws):
    r = safe(ws, 'memory.breakpoint.list')
    if not r.get('ok'):
        return r
    bps = r['response'].get('breakpoints', [])
    return {
        'ok': True,
        'breakpoints': bps,
        'total_hits': sum(int(x.get('hits', 0)) for x in bps),
    }

def arm_log_watchpoints(ws, log):
    rows = []
    for off in WATCH_OFFSETS:
        a = KNOWN_ST1_BASE + off
        r = safe(
            ws, 'memory.breakpoint.add',
            address=a, size=8, enabled=False, log=True,
            read=True, write=True, change=False
        )
        rows.append({'offset_hex':hex(off),'address_hex':f'0x{a:08X}','result':r})
        if r.get('ok'):
            log(f'Log R/W watchpoint: ST1+0x{off:X} = 0x{a:08X}')
    return rows

def make_pause_read_breakpoint(ws, address, log):
    # Replaces the log-only breakpoint at this exact range.
    r = safe(
        ws, 'memory.breakpoint.add',
        address=address, size=8, enabled=True, log=True,
        read=True, write=False, change=False
    )
    if r.get('ok'):
        log(f'Pause-on-read breakpoint armed at 0x{address:08X}.')
    else:
        log(f'Pause-on-read breakpoint failed: {r}')
    return r

def remove_all_watchpoints(ws):
    rows=[]
    for off in WATCH_OFFSETS:
        rows.append(safe(ws,'memory.breakpoint.remove',address=KNOWN_ST1_BASE+off,size=8))
    return rows

def fire_resume(ws):
    # cpu.resume can be deferred; send without a ticket so our request loop does not wait.
    try:
        ws._send(1, json.dumps({'event':'cpu.resume'}, separators=(',',':')))
        return {'ok':True}
    except Exception as e:
        return {'ok':False,'error':repr(e)}

def capture_hit_detail(ws, ev):
    h=ev.get('hit',{})
    pc=int(h.get('pc',0))
    d={
        'event':ev,
        'pc_hex':f'0x{pc:08X}' if pc else None,
        'status':safe(ws,'cpu.status'),
        'regs':safe(ws,'cpu.getAllRegs'),
        'backtrace':safe(ws,'hle.backtrace'),
        'threads':safe(ws,'hle.thread.list'),
    }
    if pc:
        d['disasm']=safe(
            ws,'memory.disasm',
            address=max(RAM_START,pc-0x140),count=160,
            displaySymbols=True,compact=False
        )
    return d

def collect_window(ws, seconds, evfile, log, pause_addr=None, hit_cap=12000):
    all_type_counts=Counter()
    memhits=[]
    detailed=[]
    start=time.time()
    while time.time()-start<seconds:
        evs=ws.poll(min(.35,max(.05,seconds-(time.time()-start))))
        for ev in evs:
            all_type_counts[str(ev.get('event','<none>'))]+=1
            if ev.get('event')!='cpu.breakpoint.hit':
                continue
            h=ev.get('hit',{})
            if h.get('kind')!='memory':
                continue
            memhits.append(ev)
            with evfile.open('a',encoding='utf-8') as f:
                f.write(json.dumps(ev,ensure_ascii=False)+'\n')

            bp=h.get('breakpoint',{})
            st=int(bp.get('start',0))
            if pause_addr is not None and st==pause_addr:
                log(f'PAUSING memory breakpoint HIT at PC 0x{int(h.get("pc",0)):08X}.')
                detailed.append(capture_hit_detail(ws,ev))
                # Remove this pausing BP, restore it as log-only read/write, and resume.
                safe(ws,'memory.breakpoint.remove',address=pause_addr,size=8)
                safe(ws,'memory.breakpoint.add',
                     address=pause_addr,size=8,enabled=False,log=True,
                     read=True,write=True,change=False)
                rr=fire_resume(ws)
                detailed[-1]['resume']=rr
                pause_addr=None
            if len(memhits)>=hit_cap:
                log(f'Memory hit event cap reached ({hit_cap}).')
                return memhits, dict(all_type_counts), detailed, pause_addr
    return memhits, dict(all_type_counts), detailed, pause_addr

def scan_all_occurrences(ws, needles):
    found={label:[] for _,_,label in needles}
    chunk=0x20000
    overlap=max(len(n) for _,n,_ in needles)-1
    carry=b''
    for a in range(RAM_START,RAM_END,chunk):
        data=readmem(ws,a,min(chunk,RAM_END-a))
        buf=carry+data
        ba=a-len(carry)
        for off,needle,label in needles:
            p=0
            while True:
                p=buf.find(needle,p)
                if p<0: break
                addr=ba+p
                if RAM_START<=addr<RAM_END and addr not in found[label]:
                    found[label].append(addr)
                p+=1
        carry=buf[-overlap:] if overlap else b''
    return {k:[f'0x{x:08X}' for x in sorted(v)] for k,v in found.items()}

def pc_summary(hits):
    pcs=Counter()
    examples={}
    seq=[]
    for ev in hits:
        h=ev.get('hit',{})
        pc=int(h.get('pc',0))
        if pc:
            pcs[pc]+=1
            examples.setdefault(pc,h)
        if 'sequence' in ev:
            seq.append(ev['sequence'])
    return pcs,examples,seq

def wait_st1(ws,log,limit=90):
    t0=time.time(); attempts=[]; lastscan=-999
    while time.time()-t0<limit:
        s,rows=verify_st1(ws,KNOWN_ST1_BASE)
        attempts.append({'t':round(time.time()-t0,2),'known_score':s})
        if s>=2:
            log(f'ST1 verified at 0x{KNOWN_ST1_BASE:08X}.')
            return KNOWN_ST1_BASE,attempts,rows
        if time.time()-t0-lastscan>12:
            lastscan=time.time()-t0
            try:
                x=scan_st1(ws)
                if x:
                    base,label,rows=x
                    log(f'ST1 found by RAM scan 0x{base:08X} ({label}).')
                    return base,attempts,rows
            except Exception as e:
                attempts.append({'scan_error':repr(e)})
        time.sleep(.6)
    return None,attempts,None

def auto_route_to_difficulty(ws,log):
    result={}
    ok,samp=wait_initial_logo(ws,log,limit=120)
    result['logo']={'ended':ok,'samples':samp}
    log('Waiting 6 seconds for frontend/save-data initialization.')
    time.sleep(6)

    route=[]
    for attempt in range(1,7):
        row={'attempt':attempt}
        log(f'Auto-entry attempt {attempt}: START -> CROSS (Story).')
        try:
            row['start']=tap(ws,'start')
            time.sleep(2)
            row['cross_story']=tap(ws,'cross')
        except Exception as e:
            row['error']=repr(e)
        hit,samples=wait_campaign(ws,log,limit=9)
        row['campaign_samples']=samples
        route.append(row)
        if hit:
            result['frontend_route']=route
            result['campaign_loaded']=True
            break
        log('Campaign module not loaded yet; retrying.')
        time.sleep(1)
    else:
        result['frontend_route']=route
        result['campaign_loaded']=False
        return False,result

    log('Campaign frontend loaded. Waiting for campaign menu.')
    time.sleep(5)
    try:
        result['down_to_new_game']=tap(ws,'down')
        time.sleep(1.2)
        result['cross_new_game']=tap(ws,'cross')
        log('Selected New Game (DOWN -> CROSS).')
        time.sleep(2.5)
    except Exception as e:
        result['new_game_error']=repr(e)
        return False,result
    return True,result




import zlib, binascii

def png_rgba(path,w,h,rgba):
    def chunk(tag,data):
        return struct.pack(">I",len(data))+tag+data+struct.pack(">I",binascii.crc32(tag+data)&0xffffffff)
    rows=[]
    stride=w*4
    for y in range(h):
        rows.append(b"\x00"+rgba[y*stride:(y+1)*stride])
    data=b"".join(rows)
    p=Path(path)
    p.write_bytes(b"\x89PNG\r\n\x1a\n"+chunk(b"IHDR",struct.pack(">IIBBBBB",w,h,8,6,0,0,0))
                  +chunk(b"IDAT",zlib.compress(data,9))+chunk(b"IEND",b""))

def rgba8888_visible(raw):
    out=bytearray()
    rowbytes=512*4
    for y in range(272):
        row=raw[y*rowbytes:(y+1)*rowbytes]
        out.extend(row[:480*4])
    return bytes(out)

def rgb565_visible(raw):
    out=bytearray(480*272*4)
    p=0
    rowbytes=512*2
    for y in range(272):
        row=raw[y*rowbytes:(y+1)*rowbytes]
        for x in range(480):
            v=row[x*2] | (row[x*2+1]<<8)
            r=((v>>11)&31)*255//31
            g=((v>>5)&63)*255//63
            b=(v&31)*255//31
            out[p:p+4]=bytes((r,g,b,255)); p+=4
    return bytes(out)

def capture(ws,out,label):
    rows=[]
    for addr in (0x04000000,0x04044000):
        item={"address_hex":f"0x{addr:08X}"}
        try:
            r4=readmem(ws,addr,512*272*4)
            p=out/f"{label}_{addr:08X}_rgba8888.png"
            png_rgba(p,480,272,rgba8888_visible(r4))
            item["rgba8888"]=p.name
        except Exception as e:item["rgba8888_error"]=repr(e)
        try:
            r2=readmem(ws,addr,512*272*2)
            p=out/f"{label}_{addr:08X}_rgb565.png"
            png_rgba(p,480,272,rgb565_visible(r2))
            item["rgb565"]=p.name
        except Exception as e:item["rgb565_error"]=repr(e)
        rows.append(item)
    return rows


def wait_story_bink_start(ws, log, limit=45):
    t0=time.time()
    samples=[]
    while time.time()-t0 < limit:
        th=threads(ws)
        active=has_bink(th)
        samples.append({"t":round(time.time()-t0,3),"active":active})
        if active:
            log("Story Bink thread detected. This moment is movie t=0.")
            return True, samples
        time.sleep(.15)
    return False, samples

def capture_rgba_pair(ws, out, label):
    rows=[]
    for addr in (0x04000000,0x04044000):
        item={"address_hex":f"0x{addr:08X}"}
        try:
            raw=readmem(ws,addr,512*272*4)
            p=out/f"{label}_{addr:08X}_rgba8888.png"
            png_rgba(p,480,272,rgba8888_visible(raw))
            item["full"]=p.name

            # Subtitle band crop: y=180..271, stored as separate PNG for quick review.
            vis=rgba8888_visible(raw)
            crop=bytearray()
            rowbytes=480*4
            for y in range(180,272):
                crop.extend(vis[y*rowbytes:(y+1)*rowbytes])
            cp=out/f"{label}_{addr:08X}_subtitleband.png"
            png_rgba(cp,480,92,bytes(crop))
            item["subtitleband"]=cp.name
        except Exception as e:
            item["error"]=repr(e)
        rows.append(item)
    return rows



def capture_both_formats(ws, out, label):
    """
    Save both PSP framebuffer candidates at 0x04000000 / 0x04044000
    as BOTH RGBA8888 and RGB565.  This deliberately avoids guessing
    which presentation format/menu buffer is active.
    """
    rows=[]
    for addr in (0x04000000,0x04044000):
        row={"address_hex":f"0x{addr:08X}"}
        try:
            raw4=readmem(ws,addr,512*272*4)
            p=out/f"{label}_{addr:08X}_rgba8888.png"
            png_rgba(p,480,272,rgba8888_visible(raw4))
            row["rgba8888"]=p.name
        except Exception as e:
            row["rgba8888_error"]=repr(e)
        try:
            raw2=readmem(ws,addr,512*272*2)
            p=out/f"{label}_{addr:08X}_rgb565.png"
            png_rgba(p,480,272,rgb565_visible(raw2))
            row["rgb565"]=p.name
        except Exception as e:
            row["rgb565_error"]=repr(e)
        rows.append(row)
    return rows

def snap(ws,out,shots,label,log,note=None):
    try:
        campaign_word=read32(ws,CAMPAIGN_RENDER_CALL)
    except Exception:
        campaign_word=None
    th=threads(ws)
    item={
        "index":len(shots),
        "label":label,
        "note":note,
        "wall_time":time.strftime("%F %T"),
        "campaign_word_hex":None if campaign_word is None else f"0x{campaign_word:08X}",
        "campaign_loaded":campaign_word==CAMPAIGN_EXPECTED_WORD,
        "bink_active":has_bink(th),
        "threads":th,
        "files":capture_both_formats(ws,out,f"{len(shots):03d}_{label}"),
    }
    shots.append(item)
    log(f"SCREENSHOT {len(shots)-1:03d}: {label} campaign={item['campaign_loaded']} bink={item['bink_active']}")
    return item

def tap_with_shots(ws,out,shots,button,label,log,hold=.28,after=(0.45,1.25,2.5)):
    snap(ws,out,shots,f"{label}_before",log,note=f"about to press {button}")
    result=tap(ws,button,hold=hold)
    last=0.0
    for sec in after:
        time.sleep(max(0.0,sec-last)); last=sec
        snap(ws,out,shots,f"{label}_after_{str(sec).replace('.','p')}s",log)
    return result

def wait_campaign_screens(ws,out,shots,log,attempt,limit=9.0):
    t0=time.time()
    next_shot=1.5
    samples=[]
    while time.time()-t0 < limit:
        try:w=read32(ws,CAMPAIGN_RENDER_CALL)
        except Exception:w=None
        elapsed=time.time()-t0
        samples.append({"t":round(elapsed,3),"word_hex":None if w is None else f"0x{w:08X}"})
        if w==CAMPAIGN_EXPECTED_WORD:
            snap(ws,out,shots,f"attempt{attempt}_campaign_detected",log)
            return True,samples
        if elapsed>=next_shot:
            snap(ws,out,shots,f"attempt{attempt}_campaign_wait_{next_shot:.1f}s".replace(".","p"),log)
            next_shot+=2.0
        time.sleep(.25)
    snap(ws,out,shots,f"attempt{attempt}_campaign_timeout",log)
    return False,samples


def snap_simple(ws,out,shots,label,log):
    try:
        cw=read32(ws,CAMPAIGN_RENDER_CALL)
    except Exception:
        cw=None
    th=threads(ws)
    item={
        "index":len(shots),
        "label":label,
        "campaign_word_hex":None if cw is None else f"0x{cw:08X}",
        "campaign_loaded":cw==CAMPAIGN_EXPECTED_WORD,
        "bink_active":has_bink(th),
        "files":capture_both_formats(ws,out,f"{len(shots):03d}_{label}"),
    }
    shots.append(item)
    log(f"SCREENSHOT {len(shots)-1:03d}: {label} campaign={item['campaign_loaded']} bink={item['bink_active']}")
    return item

def wait_seconds_with_optional_shot(ws,out,shots,log,total,label):
    t0=time.time()
    while time.time()-t0 < total:
        time.sleep(min(.10, max(.01,total-(time.time()-t0))))
    return snap_simple(ws,out,shots,label,log)

def wait_campaign_and_story_bink(ws,log,limit=15):
    t0=time.time()
    campaign=False
    bink=False
    samples=[]
    while time.time()-t0<limit:
        try:
            w=read32(ws,CAMPAIGN_RENDER_CALL)
        except Exception:
            w=None
        th=threads(ws)
        active=has_bink(th)
        if w==CAMPAIGN_EXPECTED_WORD:
            campaign=True
        if active:
            bink=True
        samples.append({
            "t":round(time.time()-t0,3),
            "campaign_word_hex":None if w is None else f"0x{w:08X}",
            "campaign":campaign,
            "bink":active,
        })
        if campaign and bink:
            log(f"Campaign module + story Bink confirmed at {time.time()-t0:.2f}s.")
            return True,samples
        time.sleep(.20)
    return False,samples


GENERIC_LOADER=0x0893D454
RAW_CALL_RA=0x0893E760
TEX_CALL_SITE=0x0893D980

def add_exec_bp(ws,address):
    return safe(ws,'cpu.breakpoint.add',address=address,enabled=True,log=False)

def remove_exec_bp(ws,address):
    return safe(ws,'cpu.breakpoint.remove',address=address)

def wait_step(ws,timeout=15.0):
    end=time.time()+timeout
    counts=Counter()
    while time.time()<end:
        evs=ws.poll(min(.20,max(.02,end-time.time())))
        for ev in evs:
            counts[str(ev.get('event','<none>'))]+=1
            if ev.get('event')=='cpu.stepping':
                return ev,dict(counts)
        st=safe(ws,'cpu.status')
        if st.get('ok') and st['response'].get('stepping'):
            return {
                'event':'cpu.stepping',
                'synthetic_from_status':True,
                'pc':st['response'].get('pc'),
            },dict(counts)
        time.sleep(.03)
    return None,dict(counts)

def get_gpr(ws):
    r=safe(ws,'cpu.getAllRegs')
    if not r.get('ok'):
        return r,{}
    try:
        cat=next(x for x in r['response']['categories'] if x.get('name')=='GPR')
        return r,dict(zip(cat['registerNames'],cat['uintValues']))
    except Exception:
        return r,{}

def set_reg(ws,name,value):
    return ws.request('cpu.setReg',timeout=5,name=name,value=value)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--port",type=int,required=True)
    ap.add_argument("--out",required=True)
    ap.add_argument("--iso",required=True)
    a=ap.parse_args()

    out=Path(a.out)
    out.mkdir(parents=True,exist_ok=True)
    trace=out/"stage42g_fix10_trace.txt"
    report=out/"stage42g_fix10_report.json"
    shots=[]
    rep={
        "stage":"42G_FIX10_DEBUGGER_PREFLIGHT_AUTOENTRY_REGISTER_512_PROOF",
        "iso":a.iso,
        "purpose":(
            "Avoid JIT/code-memory ambiguity entirely: stop immediately before "
            "the subtitle texture-image call and override its live arguments "
            "a1/a2/a3 from 256/128/256 to 512/512/512."
        ),
        "expected_call":{
            "loader_pc_hex":"0x0893D454",
            "loader_ra_hex":"0x0893E760",
            "texture_call_site_hex":"0x0893D980",
            "before":{"a1":256,"a2":128,"a3":256},
            "after":{"a1":512,"a2":512,"a3":512},
        },
        "started":time.strftime("%F %T"),
    }
    ws=None

    def log(s):
        line=f'[{time.strftime("%H:%M:%S")}] {s}'
        print(line,flush=True)
        with trace.open("a",encoding="utf-8") as f:
            f.write(line+"\n")

    try:
        for _ in range(160):
            try:
                ws=WS(a.port);break
            except Exception:
                time.sleep(.25)
        if not ws:
            raise RuntimeError("debugger unavailable")

        rep["version"]=ws.request("version",name="bia42g-fix10-debugger-preflight",version="1.0")
        log("Debugger attached to Stage42G 512x512 probe ISO.")

        # Fix10: no framebuffer reads before auto-entry, and no blind fixed-6s START.
        # Observe startup Bink state for up to 12 seconds:
        # - if a startup/logo Bink is seen, wait until it ends, then add 5 seconds.
        # - if no Bink is seen during the full 12-second observation window,
        #   assume the debugger attached after startup video ended and proceed.
        rep["fix10_no_preentry_framebuffer_reads"]=True
        log("Fix10: observing startup Bink state before START (no screenshots/VRAM reads).")

        observe_t0=time.time()
        seen_bink=False
        bink_samples=[]
        while time.time()-observe_t0 < 12.0:
            th=threads(ws)
            active=has_bink(th)
            seen_bink = seen_bink or active
            bink_samples.append({
                "t":round(time.time()-observe_t0,2),
                "active":active
            })

            if seen_bink and not active:
                log("Fix10: startup Bink ended; adding 5s title settle.")
                time.sleep(5.0)
                break
            time.sleep(.25)
        else:
            if seen_bink:
                # Bink was still active at 12 sec; keep waiting for its real end.
                log("Fix10: startup Bink still active after 12s; waiting up to 45s total.")
                hard_deadline=observe_t0+45.0
                while time.time()<hard_deadline:
                    th=threads(ws)
                    active=has_bink(th)
                    bink_samples.append({
                        "t":round(time.time()-observe_t0,2),
                        "active":active
                    })
                    if not active:
                        log("Fix10: startup Bink ended; adding 5s title settle.")
                        time.sleep(5.0)
                        break
                    time.sleep(.25)
                else:
                    raise RuntimeError("Startup Bink did not end within 45 seconds")
            else:
                log("Fix10: no startup Bink observed for 12s; treating title as ready.")

        rep["fix10_startup_bink_seen"]=seen_bink
        rep["fix10_startup_bink_samples"]=bink_samples

        rep["start"]=tap(ws,"start")
        log("Fix10: START sent automatically after title readiness gate.")

        # Wider menu settles to prevent a delayed START from shifting later inputs.
        time.sleep(8.0)
        rep["cross_story"]=tap(ws,"cross")
        log("Fix10: CROSS #1 sent (Story).")

        time.sleep(3.5)
        rep["cross_new_game"]=tap(ws,"cross")
        log("Fix10: CROSS #2 sent (New Game).")

        time.sleep(3.5)
        log("Fix10: difficulty screen should now be stable; arming RAW loader breakpoint.")

        # First stop at the proven generic loader and make sure this is specifically
        # the SUBTITLETEXTURE.RAW load (RA == 0x0893E760).
        rep["loader_breakpoint_add"]=add_exec_bp(ws,GENERIC_LOADER)
        rep["cross_difficulty"]=tap(ws,"cross")
        log("Difficulty selected; waiting for SUBTITLETEXTURE.RAW loader call.")

        loader_hits=[]
        counts=Counter()
        raw_loader=False
        deadline=time.time()+45.0

        while time.time()<deadline and not raw_loader:
            ev,c=wait_step(ws,min(12.0,max(.25,deadline-time.time())))
            counts.update(c)
            if ev is None:
                continue
            st=safe(ws,'cpu.status')
            regs,gm=get_gpr(ws)
            pc=int(st.get('response',{}).get('pc',0))&0xffffffff if st.get('ok') else 0
            ra=int(gm.get('ra',0))&0xffffffff if gm else 0
            loader_hits.append({
                "pc_hex":f"0x{pc:08X}",
                "ra_hex":f"0x{ra:08X}",
                "event":ev,
            })
            log(f"Loader stop PC=0x{pc:08X} RA=0x{ra:08X}")

            if pc==GENERIC_LOADER and ra==RAW_CALL_RA:
                raw_loader=True
                remove_exec_bp(ws,GENERIC_LOADER)
                rep["tex_call_breakpoint_add"]=add_exec_bp(ws,TEX_CALL_SITE)
                log("RAW loader identified. Armed texture-call-site breakpoint at 0x0893D980.")

            safe(ws,'cpu.resume')
            time.sleep(.06)

        rep["loader_hits"]=loader_hits
        if not raw_loader:
            remove_exec_bp(ws,GENERIC_LOADER)
            raise RuntimeError("SUBTITLETEXTURE.RAW loader call was not observed")

        # Now stop immediately before the texture-image call.
        ev,c=wait_step(ws,20.0)
        counts.update(c)
        if ev is None:
            remove_exec_bp(ws,TEX_CALL_SITE)
            raise RuntimeError("Texture call site 0x0893D980 was not reached")

        st=safe(ws,'cpu.status')
        regs_before,gm=get_gpr(ws)
        pc=int(st.get('response',{}).get('pc',0))&0xffffffff if st.get('ok') else 0
        if pc!=TEX_CALL_SITE:
            remove_exec_bp(ws,TEX_CALL_SITE)
            raise RuntimeError(f"Unexpected stepping PC 0x{pc:08X}, wanted 0x{TEX_CALL_SITE:08X}")

        before={k:int(gm.get(k,0))&0xffffffff for k in ('a0','a1','a2','a3','t0')}
        rep["texture_call_regs_before"]={k:f"0x{v:08X}" for k,v in before.items()}
        log(
            "Texture call args before override: "
            + " ".join(f"{k}=0x{v:08X}" for k,v in before.items())
        )

        if before['a1']!=0x100 or before['a2']!=0x80 or before['a3']!=0x100:
            raise RuntimeError(
                "Unexpected texture args before override: "
                f"a1=0x{before['a1']:X} a2=0x{before['a2']:X} a3=0x{before['a3']:X}"
            )

        # PPSSPP cpu.setReg requires stepping; we are stopped on the breakpoint here.
        writes={}
        for reg in ('a1','a2','a3'):
            writes[reg]=set_reg(ws,reg,0x200)
        rep["register_writes"]=writes

        regs_after,gm2=get_gpr(ws)
        after={k:int(gm2.get(k,0))&0xffffffff for k in ('a0','a1','a2','a3','t0')}
        rep["texture_call_regs_after"]={k:f"0x{v:08X}" for k,v in after.items()}
        log(
            "Texture call args after override: "
            + " ".join(f"{k}=0x{v:08X}" for k,v in after.items())
        )

        if after['a1']!=0x200 or after['a2']!=0x200 or after['a3']!=0x200:
            raise RuntimeError("cpu.setReg readback mismatch")

        remove_exec_bp(ws,TEX_CALL_SITE)
        safe(ws,'cpu.resume')
        log("Resumed with live texture args set to 512/512/512.")

        # The movie should now start with the existing Stage42G 1 MiB RAW.
        success,samples=wait_campaign_and_story_bink(ws,log,limit=30)
        rep["movie_start"]={"success":success,"samples":samples}
        if not success:
            raise RuntimeError("Story Bink did not start after register override")

        snap_simple(ws,out,shots,"story_movie_started_after_reg_override",log)
        movie_t0=time.time()
        for target in (8.0,14.0,16.0,18.0):
            while time.time()-movie_t0 < target:
                time.sleep(min(.10,max(.01,target-(time.time()-movie_t0))))
            snap_simple(ws,out,shots,f"story_movie_t{int(target):02d}s",log)

        rep["event_counts"]=dict(counts)
        rep["screenshots"]=shots
        rep["completed"]=True
        rep["finished"]=time.strftime("%F %T")
        report.write_text(json.dumps(rep,ensure_ascii=False,indent=2),encoding="utf-8")
        log("STAGE42G FIX10 DEBUGGER-PREFLIGHT AUTO-ENTRY / REGISTER PROOF COMPLETE.")
        return 0

    except Exception as e:
        try:
            remove_exec_bp(ws,GENERIC_LOADER)
            remove_exec_bp(ws,TEX_CALL_SITE)
        except Exception:
            pass
        rep["event_counts"]=dict(locals().get('counts',{}))
        rep["screenshots"]=shots
        rep["completed"]=False
        rep["error"]=repr(e)
        rep["finished"]=time.strftime("%F %T")
        report.write_text(json.dumps(rep,ensure_ascii=False,indent=2),encoding="utf-8")
        log("STAGE42G FIX10 FAILED: "+repr(e))
        return 1
    finally:
        if ws:
            ws.close()

if __name__=="__main__":
    sys.exit(main())
