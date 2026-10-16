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


PAUSE_OFFSETS = [0x000, 0x06E, 0x28F, 0x59D]

def arm_pause_reads(ws, log):
    rows = []
    for off in PAUSE_OFFSETS:
        a = KNOWN_ST1_BASE + off
        r = safe(
            ws, 'memory.breakpoint.add',
            address=a, size=8,
            enabled=True, log=False,
            read=True, write=False, change=False
        )
        rows.append({
            'offset_hex': hex(off),
            'address_hex': f'0x{a:08X}',
            'result': r,
        })
        if r.get('ok'):
            log(f'Pause-on-read armed: ST1+0x{off:X} = 0x{a:08X}')
    return rows

def remove_pause_read(ws, address):
    return safe(ws, 'memory.breakpoint.remove', address=address, size=8)

def active_bp_snapshot(ws):
    x = bp_list(ws)
    if not x.get('ok'):
        return x
    return {
        'ok': True,
        'total_hits': x.get('total_hits', 0),
        'breakpoints': [
            {
                'address': int(b.get('address', 0)),
                'address_hex': f"0x{int(b.get('address',0)):08X}",
                'hits': int(b.get('hits', 0)),
                'enabled': bool(b.get('enabled', False)),
                'log': bool(b.get('log', False)),
                'read': bool(b.get('read', False)),
                'write': bool(b.get('write', False)),
                'size': int(b.get('size', 0)),
            }
            for b in x.get('breakpoints', [])
        ]
    }

def capture_stepping_state(ws, stepping_event, previous_hits, log):
    status = safe(ws, 'cpu.status')
    pc = None
    if status.get('ok'):
        pc = status['response'].get('pc')
        try:
            pc = int(pc)
        except Exception:
            pc = None

    snap = active_bp_snapshot(ws)
    triggered = []
    if snap.get('ok'):
        for b in snap.get('breakpoints', []):
            addr = int(b.get('address', 0))
            hits = int(b.get('hits', 0))
            old = int(previous_hits.get(addr, 0))
            if hits > old:
                triggered.append({
                    'address': addr,
                    'address_hex': f'0x{addr:08X}',
                    'old_hits': old,
                    'new_hits': hits,
                    'delta': hits - old,
                })

    detail = {
        'stepping_event': stepping_event,
        'status': status,
        'pc': pc,
        'pc_hex': f'0x{pc:08X}' if pc is not None else None,
        'triggered_breakpoints': triggered,
        'breakpoint_snapshot': snap,
        'regs': safe(ws, 'cpu.getAllRegs'),
        'backtrace': safe(ws, 'hle.backtrace'),
        'threads': safe(ws, 'hle.thread.list'),
        'modules': safe(ws, 'hle.module.list'),
    }

    if pc is not None:
        detail['disasm'] = safe(
            ws, 'memory.disasm',
            address=max(RAM_START, pc - 0x180),
            count=192,
            displaySymbols=True,
            compact=False
        )
        try:
            detail['pc_bytes_hex'] = readmem(ws, max(RAM_START, pc - 0x40), 0x100).hex()
        except Exception as e:
            detail['pc_bytes_error'] = repr(e)

    for t in triggered:
        addr = int(t['address'])
        try:
            detail.setdefault('trigger_memory', []).append({
                'address_hex': f'0x{addr:08X}',
                'bytes_hex': readmem(ws, max(RAM_START, addr - 0x20), 0x80).hex(),
            })
        except Exception as e:
            detail.setdefault('trigger_memory', []).append({
                'address_hex': f'0x{addr:08X}',
                'error': repr(e),
            })

    if pc is not None:
        log(f'Captured cpu.stepping reader PC 0x{pc:08X}; triggered={len(triggered)}')
    else:
        log(f'Captured cpu.stepping event without PC; triggered={len(triggered)}')
    return detail, snap

def trace_pause_reads(ws, log, seconds, out_jsonl):
    previous_hits = {}
    first = active_bp_snapshot(ws)
    if first.get('ok'):
        previous_hits = {
            int(b['address']): int(b['hits'])
            for b in first.get('breakpoints', [])
        }

    details = []
    event_counts = Counter()
    deadline = time.time() + seconds
    last_status_check = 0.0

    while time.time() < deadline:
        # First consume queued/asynchronous debugger events.
        evs = ws.poll(min(.20, max(.02, deadline - time.time())))
        stepping_events = []
        for ev in evs:
            event_counts[str(ev.get('event', '<none>'))] += 1
            if ev.get('event') == 'cpu.stepping':
                stepping_events.append(ev)

        # Fallback: a stepping notification may have been consumed by a request loop
        # and not be present here. Periodically ask CPU status and treat stepping=True
        # as the same pause condition.
        now = time.time()
        if not stepping_events and now - last_status_check >= .75:
            last_status_check = now
            st = safe(ws, 'cpu.status')
            if st.get('ok') and st['response'].get('stepping'):
                stepping_events.append({
                    'event': 'cpu.stepping',
                    'synthetic_from_status': True,
                    'pc': st['response'].get('pc'),
                })

        if not stepping_events:
            continue

        # Handle only one stepping state at a time. Any duplicate notification for the
        # same pause is harmless and will disappear after resume.
        ev = stepping_events[0]
        detail, snap = capture_stepping_state(ws, ev, previous_hits, log)
        details.append(detail)
        with out_jsonl.open('a', encoding='utf-8') as f:
            f.write(json.dumps(detail, ensure_ascii=False) + '\n')

        triggered_addrs = [
            int(x['address']) for x in detail.get('triggered_breakpoints', [])
        ]

        # Remove the exact breakpoint(s) responsible so we do not stop repeatedly on
        # the same subtitle. If hit counters were unavailable, remove all pause points
        # only after preserving this PC.
        if triggered_addrs:
            for addr in triggered_addrs:
                remove_pause_read(ws, addr)
                previous_hits.pop(addr, None)
                log(f'Removed triggered pause breakpoint at 0x{addr:08X}')
        else:
            # Preserve the captured PC, but avoid a deadlock/repeated pause if the
            # backend did not expose which breakpoint fired.
            current = active_bp_snapshot(ws)
            if current.get('ok'):
                for b in current.get('breakpoints', []):
                    if b.get('enabled') and b.get('read') and not b.get('write'):
                        addr = int(b['address'])
                        if addr in [KNOWN_ST1_BASE + o for o in PAUSE_OFFSETS]:
                            remove_pause_read(ws, addr)
                            previous_hits.pop(addr, None)
                log('Could not identify exact trigger; removed remaining pause-read points.')

        rr = fire_resume(ws)
        detail['resume'] = rr
        time.sleep(.20)

        # Refresh counters after removals/resume.
        current = active_bp_snapshot(ws)
        if current.get('ok'):
            previous_hits = {
                int(b['address']): int(b['hits'])
                for b in current.get('breakpoints', [])
            }

        if len(details) >= len(PAUSE_OFFSETS):
            break

    return details, dict(event_counts)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', type=int, required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--iso', required=True)
    a = ap.parse_args()

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    trace = out / 'stage41b_fix6_trace.txt'
    detail_jsonl = out / 'stage41b_fix6_reader_hits.jsonl'
    report_path = out / 'stage41b_fix6_report.json'

    rep = {
        'stage': '41B_FIX6',
        'source_iso': a.iso,
        'purpose': (
            'Capture the reader PC from PPSSPP cpu.stepping events generated by '
            'enabled read memory breakpoints. Fix5 proved the breakpoint hit but '
            'ignored cpu.stepping.'
        ),
        'started': time.strftime('%F %T'),
    }
    ws = None

    def log(s):
        line = f'[{time.strftime("%H:%M:%S")}] {s}'
        print(line, flush=True)
        with trace.open('a', encoding='utf-8') as f:
            f.write(line + '\n')

    try:
        for _ in range(160):
            try:
                ws = WS(a.port)
                break
            except Exception:
                time.sleep(.25)
        if not ws:
            raise RuntimeError('debugger unavailable')

        rep['version'] = ws.request('version', name='bia41b-fix6', version='1.0')
        rep['cpu_status_start'] = safe(ws, 'cpu.status')
        log('Debugger attached. Keeping the proven fully automatic entry route.')

        ok, nav = auto_route_to_difficulty(ws, log)
        rep['auto_navigation'] = nav
        if not ok:
            raise RuntimeError('Automatic route failed before difficulty screen.')

        # Flush old frontend/log noise BEFORE adding any subtitle read breakpoint.
        rep['pre_arm_flush'] = flush_existing_events(ws, log, seconds=.20)

        rep['pause_read_add'] = arm_pause_reads(ws, log)
        rep['bp_list_before_difficulty'] = active_bp_snapshot(ws)

        # Select Normal only after all pause-on-read breakpoints are active.
        rep['cross_normal'] = tap(ws, 'cross')
        log('Selected Normal with pause-on-read subtitle breakpoints active.')

        # This is the core Fix6 capture. The first reader should pause the CPU and
        # emit cpu.stepping. Capture several subtitle locations if possible.
        details, event_types = trace_pause_reads(
            ws, log, seconds=95, out_jsonl=detail_jsonl
        )
        rep['event_types'] = event_types
        rep['reader_hit_details'] = details
        rep['reader_hit_count'] = len(details)

        # Verify the Korean ST1 still loaded, and record RAM copies for continuity.
        base, attempts, rows = wait_st1(ws, log, limit=35)
        rep['st1_search'] = attempts
        rep['st1_base_hex'] = f'0x{base:08X}' if base is not None else None
        rep['st1_verify'] = rows
        if base is not None:
            try:
                rep['subtitle_ram_copies'] = scan_all_occurrences(ws, NEEDLES)
            except Exception as e:
                rep['subtitle_ram_copies_error'] = repr(e)

        # Remove anything left over.
        cleanup = []
        for off in PAUSE_OFFSETS:
            cleanup.append(remove_pause_read(ws, KNOWN_ST1_BASE + off))
        rep['cleanup'] = cleanup
        rep['bp_list_end'] = active_bp_snapshot(ws)

        # Compact text summary for quick handoff.
        lines = [
            'BIA Stage41B Fix6 - movie subtitle reader PCs',
            f"Captured stepping states: {len(details)}",
            '',
        ]
        for i, d in enumerate(details, 1):
            tr = ', '.join(
                x.get('address_hex', '?')
                for x in d.get('triggered_breakpoints', [])
            )
            lines.append(
                f"{i}. PC={d.get('pc_hex')} triggered=[{tr}]"
            )
        (out / 'stage41b_fix6_reader_pcs.txt').write_text(
            '\n'.join(lines), encoding='utf-8'
        )

        if not details or not any(d.get('pc') is not None for d in details):
            raise RuntimeError(
                'No cpu.stepping reader PC was captured. '
                'Fix5 confirmed the breakpoint itself hits, so inspect the saved '
                'status/event diagnostics rather than reverting automatic entry.'
            )

        rep['completed'] = True
        rep['finished'] = time.strftime('%F %T')
        report_path.write_text(
            json.dumps(rep, ensure_ascii=False, indent=2), encoding='utf-8'
        )
        log('STAGE41B FIX6 SUCCESS: subtitle reader PC captured.')
        return 0

    except Exception as e:
        rep['completed'] = False
        rep['error'] = repr(e)
        if ws:
            rep['cpu_status_failure'] = safe(ws, 'cpu.status')
            rep['bp_list_failure'] = active_bp_snapshot(ws)
            rep['threads_failure'] = safe(ws, 'hle.thread.list')
        rep['finished'] = time.strftime('%F %T')
        report_path.write_text(
            json.dumps(rep, ensure_ascii=False, indent=2), encoding='utf-8'
        )
        log('STAGE41B FIX6 FAILED: ' + repr(e))
        return 1
    finally:
        if ws:
            ws.close()

if __name__ == '__main__':
    sys.exit(main())
