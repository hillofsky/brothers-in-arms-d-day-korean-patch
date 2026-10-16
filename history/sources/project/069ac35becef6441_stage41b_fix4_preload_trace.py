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


def arm_preload_watchpoints(ws, log):
    """Arm ST1 source read/write watchpoints BEFORE the movie/ST1 load begins."""
    rows = []
    for off in WATCH_OFFSETS:
        a = KNOWN_ST1_BASE + off
        r = safe(
            ws, 'memory.breakpoint.add',
            address=a, size=8, enabled=False, log=True,
            read=True, write=True, change=False
        )
        rows.append({
            'offset_hex': hex(off),
            'address_hex': f'0x{a:08X}',
            'result': r,
        })
        if r.get('ok'):
            log(f'Preload R/W watchpoint armed: ST1+0x{off:X} = 0x{a:08X}')
    return rows

def remove_preload_watchpoints(ws):
    rows = []
    for off in WATCH_OFFSETS:
        rows.append(safe(
            ws, 'memory.breakpoint.remove',
            address=KNOWN_ST1_BASE + off, size=8
        ))
    return rows

def drain_hits(ws, seconds, evfile, limit=12000):
    hits = []
    end = time.time() + seconds
    while time.time() < end:
        for ev in ws.poll(min(.5, max(.05, end-time.time()))):
            if ev.get('event') == 'cpu.breakpoint.hit' and ev.get('hit', {}).get('kind') == 'memory':
                hits.append(ev)
                with evfile.open('a', encoding='utf-8') as f:
                    f.write(json.dumps(ev, ensure_ascii=False) + '\n')
        if len(hits) >= limit:
            break
    return hits

def scan_all_occurrences(ws, needles):
    """Find all RAM copies of selected UTF-8 strings using supported memory.read."""
    found = {label: [] for _, _, label in needles}
    chunk = 0x20000
    overlap = max(len(n) for _, n, _ in needles) - 1
    carry = b''
    for a in range(RAM_START, RAM_END, chunk):
        data = readmem(ws, a, min(chunk, RAM_END-a))
        buf = carry + data
        ba = a - len(carry)
        for off, needle, label in needles:
            start = 0
            while True:
                p = buf.find(needle, start)
                if p < 0:
                    break
                addr = ba + p
                if RAM_START <= addr < RAM_END and addr not in found[label]:
                    found[label].append(addr)
                start = p + 1
        carry = buf[-overlap:] if overlap else b''
    return {
        k: [f'0x{x:08X}' for x in sorted(v)]
        for k, v in found.items()
    }

def collect_pc_summary(hits):
    pcs = Counter()
    kind_counts = Counter()
    examples = {}
    for ev in hits:
        h = ev.get('hit', {})
        pc = int(h.get('pc', 0))
        if pc:
            pcs[pc] += 1
            examples.setdefault(pc, h)
        bp = h.get('breakpoint', {})
        # Preserve whatever fields PPSSPP exposes for read/write classification.
        kind_counts[json.dumps(bp, sort_keys=True, ensure_ascii=False)] += 1
    return pcs, kind_counts, examples

def auto_enter_prearmed(ws, log, evfile):
    result = {}
    ok, samp = wait_initial_logo(ws, log, limit=120)
    result['logo'] = {'ended': ok, 'samples': samp}

    log('Waiting 6 seconds for frontend/save-data initialization.')
    time.sleep(6.0)

    route = []
    for attempt in range(1, 7):
        log(f'Auto-entry attempt {attempt}: START -> CROSS (Story).')
        row = {'attempt': attempt}
        try:
            row['start'] = tap(ws, 'start')
            time.sleep(2.0)
            row['cross_story'] = tap(ws, 'cross')
        except Exception as e:
            row['error'] = repr(e)
        hit, samples = wait_campaign(ws, log, limit=9)
        row['campaign_samples'] = samples
        route.append(row)
        if hit:
            result['frontend_route'] = route
            result['campaign_loaded'] = True
            break
        log('Campaign module not loaded yet; retrying title/menu input.')
        time.sleep(1.0)
    else:
        result['frontend_route'] = route
        result['campaign_loaded'] = False
        return False, result, []

    log('Campaign frontend loaded. Waiting for campaign menu.')
    time.sleep(5.0)

    ng = {}
    try:
        ng['down_to_new_game'] = tap(ws, 'down')
        time.sleep(1.2)
        ng['cross_new_game'] = tap(ws, 'cross')
        log('Selected New Game (DOWN -> CROSS).')
        time.sleep(2.5)

        # Critical Fix4 change: arm before difficulty CROSS starts movie/ST1 loading.
        ng['preload_watchpoints'] = arm_preload_watchpoints(ws, log)
        # Drain any stale debugger messages before starting the movie.
        ng['pre_cross_pending'] = len(ws.poll(.15))

        ng['cross_normal'] = tap(ws, 'cross')
        log('Selected default Normal difficulty (CROSS) with ST1 watchpoints already active.')
    except Exception as e:
        ng['error'] = repr(e)
        result['new_game_route'] = ng
        return False, result, []

    result['new_game_route'] = ng

    # Collect from the instant difficulty is selected, including ST1 load/copy/parser accesses.
    log('Collecting preload ST1 read/write events immediately...')
    early_hits = drain_hits(ws, 18, evfile, limit=12000)
    result['early_hit_count'] = len(early_hits)
    return True, result, early_hits

def wait_st1(ws, log, limit=90):
    t0 = time.time()
    attempts = []
    lastfull = -999
    while time.time() - t0 < limit:
        s, rows = verify_st1(ws, KNOWN_ST1_BASE)
        attempts.append({'t': round(time.time()-t0, 2), 'known_score': s})
        if s >= 2:
            log(f'ST1 verified at known Stage41A base 0x{KNOWN_ST1_BASE:08X}.')
            return KNOWN_ST1_BASE, attempts, rows
        if time.time() - t0 - lastfull > 12:
            lastfull = time.time() - t0
            try:
                x = scan_st1(ws)
                if x:
                    base, label, rows = x
                    log(f'ST1 found by RAM scan at 0x{base:08X} ({label}).')
                    return base, attempts, rows
            except Exception as e:
                attempts.append({'scan_error': repr(e)})
        time.sleep(.7)
    return None, attempts, None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', type=int, required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--iso', required=True)
    a = ap.parse_args()

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    trace = out / 'stage41b_fix4_trace.txt'
    evfile = out / 'stage41b_fix4_events.jsonl'
    rep = {
        'stage': '41B_FIX4',
        'source_iso': a.iso,
        'purpose': (
            'Keep fully automatic Stage41A/Fix3 entry, but pre-arm ST1 R/W watchpoints '
            'before difficulty selection so the load/copy/parser access cannot be missed.'
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

        rep['version'] = ws.request('version', name='bia41b-fix4', version='1.0')
        rep['cpu_status_start'] = safe(ws, 'cpu.status')
        log('Debugger attached. Automatic entry retained; ST1 tracing is pre-armed.')

        navok, nav, early_hits = auto_enter_prearmed(ws, log, evfile)
        rep['auto_navigation'] = nav
        if not navok:
            raise RuntimeError('Automatic route failed before/during New Game.')

        # Even if ST1 loading happened during the early 18 sec collection, verify it now.
        base, attempts, rows = wait_st1(ws, log, limit=90)
        rep['st1_search'] = attempts
        if base is None:
            rep['preload_hits_before_failure'] = len(early_hits)
            raise RuntimeError('Korean ST1 did not verify after automatic New Game route.')

        rep['st1_base_hex'] = f'0x{base:08X}'
        rep['st1_verify'] = rows

        # One full RAM copy scan while the movie is active. This can expose a second
        # working/subtitle buffer even if the source ST1 was preprocessed immediately.
        log('Scanning RAM once for duplicate Korean subtitle buffers.')
        try:
            rep['subtitle_ram_copies'] = scan_all_occurrences(ws, NEEDLES)
        except Exception as e:
            rep['subtitle_ram_copies_error'] = repr(e)

        # Continue collecting because later subtitle records may be consumed on demand.
        log('Continuing watchpoint collection through the movie.')
        later_hits = drain_hits(ws, 75, evfile, limit=12000)
        all_hits = early_hits + later_hits

        pcs, bp_shapes, examples = collect_pc_summary(all_hits)
        rep['memory_hit_count'] = len(all_hits)
        rep['early_memory_hit_count'] = len(early_hits)
        rep['later_memory_hit_count'] = len(later_hits)
        rep['reader_writer_pcs'] = [
            {
                'pc_hex': f'0x{pc:08X}',
                'count': cnt,
                'example': examples.get(pc),
            }
            for pc, cnt in pcs.most_common()
        ]
        rep['breakpoint_event_shapes'] = [
            {'count': cnt, 'breakpoint_json': shape}
            for shape, cnt in bp_shapes.most_common(30)
        ]

        rep['candidate_disasm'] = []
        for pc, cnt in pcs.most_common(16):
            rep['candidate_disasm'].append({
                'pc_hex': f'0x{pc:08X}',
                'count': cnt,
                'disasm': safe(
                    ws, 'memory.disasm',
                    address=max(RAM_START, pc-0x120),
                    count=144,
                    displaySymbols=True,
                    compact=False
                ),
            })

        rep['watchpoint_remove'] = remove_preload_watchpoints(ws)
        rep['threads_end'] = safe(ws, 'hle.thread.list')

        if not pcs:
            raise RuntimeError(
                'ST1 loaded but no R/W watchpoint event was emitted even though watchpoints '
                'were armed before difficulty selection. This distinguishes JIT/interpreter '
                'watchpoint behavior from a timing miss.'
            )

        # Save a compact candidate list.
        lines = [
            'BIA Stage41B Fix4 - ST1 preload reader/writer PCs',
            f'ST1 base: 0x{base:08X}',
            f'early hits: {len(early_hits)}',
            f'later hits: {len(later_hits)}',
            '',
        ]
        for pc, cnt in pcs.most_common(30):
            lines.append(f'0x{pc:08X} hits={cnt}')
        (out / 'stage41b_fix4_candidates.txt').write_text(
            '\n'.join(lines), encoding='utf-8'
        )

        rep['completed'] = True
        rep['finished'] = time.strftime('%F %T')
        (out / 'stage41b_fix4_report.json').write_text(
            json.dumps(rep, ensure_ascii=False, indent=2), encoding='utf-8'
        )
        log('STAGE41B FIX4 SUCCESS: preload ST1 access PCs captured.')
        return 0

    except Exception as e:
        rep['completed'] = False
        rep['error'] = repr(e)
        rep['threads_at_failure'] = safe(ws, 'hle.thread.list') if ws else None
        rep['watchpoint_list_at_failure'] = safe(ws, 'memory.breakpoint.list') if ws else None
        rep['finished'] = time.strftime('%F %T')
        (out / 'stage41b_fix4_report.json').write_text(
            json.dumps(rep, ensure_ascii=False, indent=2), encoding='utf-8'
        )
        log('STAGE41B FIX4 FAILED: ' + repr(e))
        return 1
    finally:
        if ws:
            ws.close()

if __name__ == '__main__':
    sys.exit(main())
