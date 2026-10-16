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



BAKER_ADDR = KNOWN_ST1_BASE + 0x06E

def add_mem_read_pause(ws, address):
    return safe(
        ws, 'memory.breakpoint.add',
        address=address, size=8,
        enabled=True, log=False,
        read=True, write=False, change=False
    )

def remove_mem_bp(ws, address):
    return safe(ws, 'memory.breakpoint.remove', address=address, size=8)

def add_exec_bp(ws, address):
    return safe(ws, 'cpu.breakpoint.add', address=address, enabled=True, log=False)

def remove_exec_bp(ws, address):
    return safe(ws, 'cpu.breakpoint.remove', address=address)

def get_gpr_map(reg_result):
    try:
        cats = reg_result['response']['categories']
        gpr = next(x for x in cats if x.get('name') == 'GPR')
        return dict(zip(gpr['registerNames'], gpr['uintValues']))
    except Exception:
        return {}

def capture_memory(ws, address, before=0x80, after=0x180):
    start = max(RAM_START, int(address) - before)
    size = before + after
    try:
        data = readmem(ws, start, size)
        return {
            'start': start,
            'start_hex': f'0x{start:08X}',
            'size': len(data),
            'hex': data.hex(),
        }
    except Exception as e:
        return {'error': repr(e)}

def disasm_at(ws, address, before=0x100, count=160):
    return safe(
        ws, 'memory.disasm',
        address=max(RAM_START, int(address)-before),
        count=count,
        displaySymbols=True,
        compact=False
    )

def wait_for_stepping(ws, timeout):
    deadline = time.time() + timeout
    counts = Counter()
    while time.time() < deadline:
        evs = ws.poll(min(.20, max(.02, deadline-time.time())))
        for ev in evs:
            counts[str(ev.get('event','<none>'))] += 1
            if ev.get('event') == 'cpu.stepping':
                return ev, dict(counts)
        # Fallback if the async stepping notification was consumed by request().
        st = safe(ws, 'cpu.status')
        if st.get('ok') and st['response'].get('stepping'):
            return {
                'event': 'cpu.stepping',
                'synthetic_from_status': True,
                'pc': st['response'].get('pc'),
            }, dict(counts)
        time.sleep(.05)
    return None, dict(counts)

def capture_state(ws, label, stepping_event=None):
    status = safe(ws, 'cpu.status')
    regs = safe(ws, 'cpu.getAllRegs')
    bt = safe(ws, 'hle.backtrace')
    gpr = get_gpr_map(regs)
    pc = None
    if status.get('ok'):
        try: pc = int(status['response'].get('pc'))
        except Exception: pc = None

    state = {
        'label': label,
        'stepping_event': stepping_event,
        'status': status,
        'pc': pc,
        'pc_hex': f'0x{pc:08X}' if pc is not None else None,
        'regs': regs,
        'backtrace': bt,
        'threads': safe(ws, 'hle.thread.list'),
        'modules': safe(ws, 'hle.module.list'),
    }

    if pc is not None:
        state['pc_disasm'] = disasm_at(ws, pc, before=0x160, count=192)

    # Save RAM around registers that are likely to carry the source line,
    # temporary line buffer, object/context, or stack.
    interesting = {}
    for name in ('v0','v1','a0','a1','a2','a3','t0','t1','t2','t3',
                 's0','s1','s2','s3','s4','s5','s6','s7','sp','fp','ra'):
        val = gpr.get(name)
        if val is None:
            continue
        val = int(val) & 0xFFFFFFFF
        if RAM_START <= val < RAM_END:
            interesting[name] = {
                'value': val,
                'value_hex': f'0x{val:08X}',
                'memory': capture_memory(ws, val, before=0x40, after=0x100),
            }
    state['interesting_register_memory'] = interesting

    # Explicitly preserve the Korean ST1 source and a larger stack window.
    state['st1_window'] = capture_memory(ws, KNOWN_ST1_BASE+0x06E, before=0x80, after=0x280)
    sp = gpr.get('sp')
    if sp is not None and RAM_START <= int(sp) < RAM_END:
        state['stack_window'] = capture_memory(ws, int(sp), before=0x100, after=0x700)

    return state

def dump_backtrace_functions(ws, state):
    out = []
    try:
        frames = state['backtrace']['response']['frames']
    except Exception:
        return out

    seen = set()
    for fr in frames:
        entry = int(fr.get('entry', 0)) & 0xFFFFFFFF
        pc = int(fr.get('pc', 0)) & 0xFFFFFFFF
        if not (RAM_START <= entry < RAM_END):
            continue
        key = (entry, pc)
        if key in seen:
            continue
        seen.add(key)
        out.append({
            'entry': entry,
            'entry_hex': f'0x{entry:08X}',
            'frame_pc': pc,
            'frame_pc_hex': f'0x{pc:08X}',
            'frame_code': fr.get('code'),
            'entry_disasm': safe(
                ws, 'memory.disasm',
                address=entry, count=220,
                displaySymbols=True, compact=False
            ),
            'frame_pc_disasm': disasm_at(ws, pc, before=0x100, count=128),
        })
    return out

def install_unwind_breakpoints(ws, initial_state, log):
    bps = []
    try:
        frames = initial_state['backtrace']['response']['frames']
    except Exception:
        return bps

    # Frame 0 is the current parser.  Later frame PCs are return/continuation
    # sites in the callers.  Catch them as the current parser unwinds.
    for idx, fr in enumerate(frames[1:8], start=1):
        pc = int(fr.get('pc', 0)) & 0xFFFFFFFF
        if not (RAM_START <= pc < RAM_END):
            continue
        r = add_exec_bp(ws, pc)
        bps.append({
            'frame_index': idx,
            'address': pc,
            'address_hex': f'0x{pc:08X}',
            'result': r,
        })
        if r.get('ok'):
            log(f'Unwind exec breakpoint: frame {idx} continuation 0x{pc:08X}')
    return bps

def capture_unwind(ws, installed, log, jsonl_path, timeout=35):
    remaining = {
        int(x['address']): x for x in installed if x.get('result',{}).get('ok')
    }
    captured = []
    event_counts = Counter()
    deadline = time.time() + timeout

    while remaining and time.time() < deadline:
        ev, counts = wait_for_stepping(ws, min(3.0, max(.2, deadline-time.time())))
        event_counts.update(counts)
        if ev is None:
            continue

        st = safe(ws, 'cpu.status')
        pc = None
        if st.get('ok'):
            try: pc = int(st['response'].get('pc'))
            except Exception: pc = None

        if pc not in remaining:
            # Preserve unexpected stops, but don't let them deadlock the run.
            state = capture_state(ws, 'unexpected_stepping', ev)
            captured.append(state)
            with jsonl_path.open('a', encoding='utf-8') as f:
                f.write(json.dumps(state, ensure_ascii=False) + '\n')
            log(f'Unexpected stepping at {state.get("pc_hex")}; resuming.')
            fire_resume(ws)
            time.sleep(.12)
            continue

        meta = remaining.pop(pc)
        state = capture_state(ws, f'unwind_frame_{meta["frame_index"]}', ev)
        state['matched_breakpoint'] = meta
        captured.append(state)
        with jsonl_path.open('a', encoding='utf-8') as f:
            f.write(json.dumps(state, ensure_ascii=False) + '\n')

        log(f'Captured unwind continuation 0x{pc:08X} (frame {meta["frame_index"]}).')
        remove_exec_bp(ws, pc)
        fire_resume(ws)
        time.sleep(.12)

    # Remove any unused breakpoints.
    for pc in list(remaining):
        remove_exec_bp(ws, pc)

    return captured, dict(event_counts), [
        {'address_hex':f'0x{pc:08X}', **meta} for pc,meta in remaining.items()
    ]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', type=int, required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--iso', required=True)
    a = ap.parse_args()

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    trace = out / 'stage41c_trace.txt'
    jsonl = out / 'stage41c_unwind_states.jsonl'
    report_path = out / 'stage41c_report.json'

    rep = {
        'stage': '41C',
        'source_iso': a.iso,
        'purpose': (
            'Follow the confirmed Bink/ST1 UTF-8 parser at 0x0893DBEC through '
            'its caller continuation chain to locate the boundary between line '
            'copy/parsing and subtitle rendering.'
        ),
        'known_from_41B_FIX6': {
            'structure_pc': '0x088DAC30',
            'utf8_byte_reader_pc': '0x0893DBEC',
            'utf8_byte_reader_function': '0x0893DB50',
            'baker_source': '0x08E1F28A',
        },
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

        rep['version'] = ws.request('version', name='bia41c', version='1.0')
        log('Debugger attached. Reusing the verified fully automatic route.')

        ok, nav = auto_route_to_difficulty(ws, log)
        rep['auto_navigation'] = nav
        if not ok:
            raise RuntimeError('Automatic route failed before difficulty screen.')

        rep['pre_arm_flush'] = flush_existing_events(ws, log, seconds=.20)

        # Focus on the first Baker line.  Fix6 proved that the byte reader
        # accesses this exact ST1 region.
        rep['baker_read_bp'] = add_mem_read_pause(ws, BAKER_ADDR)
        if not rep['baker_read_bp'].get('ok'):
            raise RuntimeError('Could not arm Baker ST1 read breakpoint.')

        rep['cross_normal'] = tap(ws, 'cross')
        log('Selected Normal. Waiting for Baker ST1 byte reader.')

        ev, counts = wait_for_stepping(ws, 45)
        rep['pre_reader_event_types'] = counts
        if ev is None:
            raise RuntimeError('No cpu.stepping event for Baker ST1 read.')

        initial = capture_state(ws, 'baker_reader_stop', ev)
        rep['initial_reader_state'] = initial
        rep['backtrace_function_dumps'] = dump_backtrace_functions(ws, initial)

        pc = initial.get('pc')
        log(f'Baker read stop PC: {initial.get("pc_hex")}')
        if pc is None:
            raise RuntimeError('Reader stepping state had no PC.')

        # Fix6 established 0x0893DBEC as the direct lbu of the Korean source.
        # Do not hard-fail if a nearby instruction catches first; preserve evidence.
        rep['reader_pc_matches_fix6'] = (pc == 0x0893DBEC)

        # Install continuation breakpoints while the CPU is still paused, then
        # remove the memory breakpoint and allow the parser to unwind through
        # its caller chain.
        installed = install_unwind_breakpoints(ws, initial, log)
        rep['unwind_breakpoints'] = installed

        remove_mem_bp(ws, BAKER_ADDR)
        fire_resume(ws)
        time.sleep(.10)

        unwind, event_types, unused = capture_unwind(
            ws, installed, log, jsonl, timeout=35
        )
        rep['unwind_states'] = unwind
        rep['unwind_event_types'] = event_types
        rep['unused_unwind_breakpoints'] = unused

        # Preserve RAM copies after parsing as a check for a secondary/subtitle
        # work buffer.
        try:
            rep['subtitle_ram_copies_after_parse'] = scan_all_occurrences(ws, NEEDLES)
        except Exception as e:
            rep['subtitle_ram_copies_error'] = repr(e)

        # Compact handoff summary.
        lines = [
            'BIA Stage41C - Bink/ST1 parser unwind',
            f'Initial reader PC: {initial.get("pc_hex")}',
            f'Fix6 reader match: {rep["reader_pc_matches_fix6"]}',
            '',
            'Backtrace:',
        ]
        try:
            for i, fr in enumerate(initial['backtrace']['response']['frames']):
                lines.append(
                    f'{i:02d} entry=0x{int(fr.get("entry",0))&0xffffffff:08X} '
                    f'pc=0x{int(fr.get("pc",0))&0xffffffff:08X} '
                    f'{fr.get("code","")}'
                )
        except Exception:
            pass
        lines += ['', 'Captured unwind continuations:']
        for s in unwind:
            lines.append(f'{s.get("label")}: {s.get("pc_hex")}')
        (out / 'stage41c_summary.txt').write_text('\n'.join(lines), encoding='utf-8')

        if not unwind:
            raise RuntimeError(
                'Reader PC captured, but no caller continuation was captured. '
                'Use the saved full backtrace/disassembly rather than discarding 41C evidence.'
            )

        rep['completed'] = True
        rep['finished'] = time.strftime('%F %T')
        report_path.write_text(
            json.dumps(rep, ensure_ascii=False, indent=2), encoding='utf-8'
        )
        log('STAGE41C SUCCESS: parser caller unwind captured.')
        return 0

    except Exception as e:
        rep['completed'] = False
        rep['error'] = repr(e)
        if ws:
            rep['cpu_status_failure'] = safe(ws, 'cpu.status')
            rep['threads_failure'] = safe(ws, 'hle.thread.list')
        rep['finished'] = time.strftime('%F %T')
        report_path.write_text(
            json.dumps(rep, ensure_ascii=False, indent=2), encoding='utf-8'
        )
        log('STAGE41C FAILED: ' + repr(e))
        return 1
    finally:
        if ws:
            ws.close()

if __name__ == '__main__':
    sys.exit(main())
