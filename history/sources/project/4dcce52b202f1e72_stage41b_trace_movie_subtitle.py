#!/usr/bin/env python3
import argparse, base64, hashlib, json, os, socket, struct, time, secrets, sys
from collections import Counter, defaultdict
from pathlib import Path

class MiniWS:
    def __init__(self, host, port, timeout=1.0):
        self.host=host; self.port=port; self.sock=None; self.ticket=1000; self.pending=[]
        self.connect(timeout)
    def connect(self, timeout):
        last=None
        for af, host in [(socket.AF_INET6, '::1'), (socket.AF_INET, '127.0.0.1')]:
            try:
                s=socket.socket(af, socket.SOCK_STREAM); s.settimeout(timeout); s.connect((host,self.port)); self.host=host; self.sock=s; break
            except Exception as e:
                last=e
                try:s.close()
                except:pass
        if not self.sock: raise RuntimeError(f'Cannot connect debugger port {self.port}: {last}')
        key=base64.b64encode(secrets.token_bytes(16)).decode()
        req=(f'GET /debugger HTTP/1.1\r\nHost: {self.host}:{self.port}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n'
             f'Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\nSec-WebSocket-Protocol: debugger.ppsspp.org\r\n\r\n')
        self.sock.sendall(req.encode('ascii'))
        data=b''
        while b'\r\n\r\n' not in data:
            chunk=self.sock.recv(4096)
            if not chunk: raise RuntimeError('Debugger handshake closed')
            data+=chunk
        head=data.split(b'\r\n\r\n',1)[0].decode('latin1','replace')
        if ' 101 ' not in head.split('\r\n')[0]: raise RuntimeError('WebSocket handshake failed: '+head[:300])
        accept=None
        for ln in head.split('\r\n')[1:]:
            if ln.lower().startswith('sec-websocket-accept:'): accept=ln.split(':',1)[1].strip()
        exp=base64.b64encode(hashlib.sha1((key+'258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode()).digest()).decode()
        if accept and accept!=exp: raise RuntimeError('Bad websocket accept')
        self.sock.settimeout(0.5)
    def _send_frame(self, opcode, payload=b''):
        if isinstance(payload,str): payload=payload.encode('utf-8')
        mask=secrets.token_bytes(4); n=len(payload); b1=0x80|opcode
        if n<126: hdr=bytes([b1,0x80|n])
        elif n<=0xffff: hdr=bytes([b1,0x80|126])+struct.pack('!H',n)
        else: hdr=bytes([b1,0x80|127])+struct.pack('!Q',n)
        enc=bytes(c^mask[i%4] for i,c in enumerate(payload))
        self.sock.sendall(hdr+mask+enc)
    def send_json(self,obj): self._send_frame(1,json.dumps(obj,separators=(',',':'),ensure_ascii=False))
    def _recvn(self,n):
        out=b''
        while len(out)<n:
            c=self.sock.recv(n-len(out))
            if not c: raise EOFError('websocket closed')
            out+=c
        return out
    def recv_json(self, timeout=0.5):
        self.sock.settimeout(timeout)
        fragments=[]; started=False
        while True:
            h=self._recvn(2); b1,b2=h; op=b1&0xf; fin=bool(b1&0x80); n=b2&0x7f
            if n==126:n=struct.unpack('!H',self._recvn(2))[0]
            elif n==127:n=struct.unpack('!Q',self._recvn(8))[0]
            mask=self._recvn(4) if b2&0x80 else None
            payload=self._recvn(n) if n else b''
            if mask: payload=bytes(c^mask[i%4] for i,c in enumerate(payload))
            if op==8: raise EOFError('websocket close frame')
            if op==9: self._send_frame(10,payload); continue
            if op==10: continue
            if op==1:
                fragments=[payload]; started=True
            elif op==0 and started: fragments.append(payload)
            else: continue
            if fin:
                raw=b''.join(fragments).decode('utf-8','replace')
                return json.loads(raw)
    def request(self,event, timeout=10, **params):
        self.ticket+=1; t=self.ticket
        q={'event':event,'ticket':t}; q.update(params); self.send_json(q)
        deadline=time.time()+timeout
        while time.time()<deadline:
            try:r=self.recv_json(min(0.5,max(0.01,deadline-time.time())))
            except socket.timeout: continue
            if r.get('ticket')==t:
                if r.get('event')=='error': raise RuntimeError(f"{event}: {r.get('message')}")
                return r
            self.pending.append(r)
        raise TimeoutError(f'No response: {event}')
    def collect(self, seconds, sink=None):
        out=[]
        if self.pending:
            out.extend(self.pending); self.pending=[]
        deadline=time.time()+seconds
        while time.time()<deadline:
            try:r=self.recv_json(min(0.5,max(0.01,deadline-time.time())))
            except socket.timeout: continue
            out.append(r)
            if sink: sink(r)
        return out
    def close(self):
        try:self._send_frame(8,b'')
        except:pass
        try:self.sock.close()
        except:pass

def jdump(path,obj):
    Path(path).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')

def safe_req(ws,event,**params):
    try:return ws.request(event,**params)
    except Exception as e:return {'event':event,'error':repr(e),'params':params}

def press(ws, name, frames=5):
    try:
        return ws.request('input.buttons.press', timeout=5, button=name, duration=frames)
    except Exception as e:
        return {'error':repr(e),'button':name}

def read_bytes(ws,addr,size):
    r=ws.request('memory.read',address=addr,size=size,replacements=True)
    return base64.b64decode(r.get('base64',''))

def is_prefix(ws,addr,prefix):
    try:return read_bytes(ws,addr,len(prefix))==prefix
    except:return False

def wait_for_subtitle_buffer(ws, outlog, known_addr=0x08E1F28A, total=120):
    needle='베이커:'.encode('utf-8')
    t0=time.time(); last_search=0
    while time.time()-t0<total:
        if is_prefix(ws,known_addr,needle):
            outlog(f'Known ST1 address verified: 0x{known_addr:08X}')
            return known_addr
        elapsed=time.time()-t0
        if elapsed>35 and time.time()-last_search>7:
            last_search=time.time()
            outlog('Known address not live; scanning 32 MiB RAM for UTF-8 베이커: ...')
            try:
                r=ws.request('memory.search',timeout=15,address=0x08000000,size=0x02000000,type='bytes',base64=base64.b64encode(needle).decode(),align=1,maxResults=20)
                ms=r.get('matches',[])
                if ms:
                    outlog('Search hits: '+', '.join(f'0x{x:08X}' for x in ms[:8]))
                    return ms[0]
            except Exception as e: outlog('RAM search warning: '+repr(e))
        time.sleep(0.25)
    return None

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--port',type=int,required=True); ap.add_argument('--pid',type=int,required=True)
    ap.add_argument('--out',required=True); ap.add_argument('--iso',required=True)
    args=ap.parse_args()
    out=Path(args.out); out.mkdir(parents=True,exist_ok=True)
    textlog=out/'stage41b_trace.txt'; eventlog=out/'stage41b_breakpoint_events.jsonl'
    def log(s):
        line=f'[{time.strftime("%H:%M:%S")}] {s}'; print(line,flush=True)
        with textlog.open('a',encoding='utf-8') as f:f.write(line+'\n')
    report={'stage':'41B','purpose':'Trace the dedicated Bink/ST1 subtitle reader/renderer using an interpreter-mode RAM read watchpoint. No ISO patching.',
            'source_iso':args.iso,'expected_pid':args.pid,'debugger_port':args.port,'started':time.strftime('%Y-%m-%d %H:%M:%S')}
    ws=None
    try:
        # PPSSPP may need a moment to open the server.
        last=None
        for i in range(80):
            try: ws=MiniWS('::1',args.port,0.5); break
            except Exception as e: last=e; time.sleep(0.25)
        if not ws: raise RuntimeError(f'Debugger did not open: {last}')
        ver=ws.request('version',name='bia-stage41b',version='1.0'); report['version']=ver
        gotpid=ver.get('pid'); log(f'Debugger attached: pid={gotpid} path={ver.get("path")}')
        if gotpid is not None and int(gotpid)!=args.pid: raise RuntimeError(f'Refusing wrong PPSSPP: expected PID {args.pid}, got {gotpid}')
        safe_req(ws,'client.config.set',acknowledgeDeferred=True)
        # Let boot/logos settle, then best-effort route to Story -> New Game -> default difficulty.
        log('Waiting for boot, then attempting Story/New Game route automatically.')
        time.sleep(8)
        nav=[]
        for name,wait in [('start',2.0),('cross',2.0),('cross',2.0),('cross',1.0)]:
            nav.append({'button':name,'result':press(ws,name,6)}); time.sleep(wait)
        report['auto_navigation']=nav
        log('Automatic route sent. If the movie is not starting, use the PPSSPP window and enter 스토리 > 새 게임 > 난이도 manually; this tracer keeps waiting.')
        addr=wait_for_subtitle_buffer(ws,log)
        report['subtitle_address']=addr
        if addr is None: raise RuntimeError('Korean ST1 buffer was not found within timeout.')
        sample=read_bytes(ws,addr,96)
        report['subtitle_sample_hex']=sample.hex(); report['subtitle_sample_utf8']=sample.decode('utf-8','replace')
        watch_size=12
        bpadd=ws.request('memory.breakpoint.add',address=addr,size=watch_size,enabled=False,log=True,read=True,write=False,change=False)
        report['memory_breakpoint_add']=bpadd
        log(f'Log-only read watchpoint armed: 0x{addr:08X}+0x{watch_size:X}. Collecting 32 seconds...')
        hits=[]
        def sink(ev):
            if ev.get('event')=='cpu.breakpoint.hit' and ev.get('hit',{}).get('kind')=='memory':
                h=ev['hit']
                if h.get('breakpoint',{}).get('start')==addr:
                    hits.append(ev)
                    with eventlog.open('a',encoding='utf-8') as f:f.write(json.dumps(ev,ensure_ascii=False)+'\n')
        ws.collect(32,sink)
        safe_req(ws,'memory.breakpoint.remove',address=addr,size=watch_size)
        report['memory_hit_count']=len(hits)
        pcs=Counter(); meta={}
        for ev in hits:
            h=ev['hit']; pc=int(h.get('pc',0)); pcs[pc]+=1; meta.setdefault(pc,h)
        report['unique_pcs']=[{'pc':pc,'pc_hex':f'0x{pc:08X}','count':cnt,'example':meta[pc]} for pc,cnt in pcs.most_common()]
        if not pcs: raise RuntimeError('ST1 buffer was present but no memory read breakpoint hit was observed. Interpreter mode/watchpoint path needs re-check.')
        log('Watchpoint PCs: '+', '.join(f'0x{pc:08X} x{cnt}' for pc,cnt in pcs.most_common(8)))
        # Try candidates in frequency order; stop on first executable hit.
        detailed=None
        for cand,cnt in pcs.most_common(6):
            log(f'Arming execution breakpoint at candidate 0x{cand:08X} (seen {cnt} memory reads) ...')
            safe_req(ws,'cpu.breakpoint.add',address=cand,enabled=True,log=True)
            deadline=time.time()+18
            exec_event=None
            while time.time()<deadline:
                try:ev=ws.recv_json(0.5)
                except socket.timeout: continue
                if ev.get('event')=='cpu.breakpoint.hit':
                    h=ev.get('hit',{})
                    if h.get('kind')=='exec' and int(h.get('pc',0))==cand:
                        exec_event=ev; break
            if exec_event:
                log(f'Execution breakpoint HIT at 0x{cand:08X}; collecting paused-state evidence.')
                mods=safe_req(ws,'hle.module.list'); threads=safe_req(ws,'hle.thread.list')
                regs=safe_req(ws,'cpu.getAllRegs'); bt=safe_req(ws,'hle.backtrace')
                dis=safe_req(ws,'memory.disasm',address=max(0x08000000,cand-0x80),count=72,displaySymbols=True,compact=False)
                compact=safe_req(ws,'memory.disasm',address=max(0x08000000,cand-0x80),count=72,displaySymbols=True,compact=True)
                frames=[]
                for fr in bt.get('frames',[])[:8] if isinstance(bt,dict) else []:
                    pc=int(fr.get('pc',0)); entry=int(fr.get('entry',pc))
                    frames.append({'frame':fr,'disasm':safe_req(ws,'memory.disasm',address=max(0x08000000,entry-0x20),count=40,displaySymbols=True,compact=False)})
                owner=None
                for m in mods.get('modules',[]) if isinstance(mods,dict) else []:
                    a=int(m.get('address',0)); sz=int(m.get('size',0))
                    if a<=cand<a+sz: owner=m; break
                detailed={'candidate':cand,'candidate_hex':f'0x{cand:08X}','hit':exec_event,'module':owner,'modules':mods,'threads':threads,'regs':regs,'backtrace':bt,'disasm':dis,'compact':compact,'frame_disasm':frames}
                safe_req(ws,'cpu.breakpoint.remove',address=cand)
                break
            safe_req(ws,'cpu.breakpoint.remove',address=cand)
        report['detailed_hit']=detailed
        if detailed is None: raise RuntimeError('Memory reader PCs were observed, but none re-hit as execution breakpoints within the capture window.')
        # Human-friendly compact disassembly dump.
        lines=detailed.get('compact',{}).get('lines',[]) if isinstance(detailed.get('compact'),dict) else []
        (out/'stage41b_candidate_disasm.txt').write_text('\n'.join(lines),encoding='utf-8')
        report['completed']=True; report['finished']=time.strftime('%Y-%m-%d %H:%M:%S')
        jdump(out/'stage41b_report.json',report)
        log('STAGE41B SUCCESS: dedicated movie subtitle reader evidence captured.')
        return 0
    except Exception as e:
        report['completed']=False; report['error']=repr(e); report['finished']=time.strftime('%Y-%m-%d %H:%M:%S')
        jdump(out/'stage41b_report.json',report)
        log('STAGE41B FAILED: '+repr(e))
        return 1
    finally:
        if ws: ws.close()

if __name__=='__main__': sys.exit(main())
