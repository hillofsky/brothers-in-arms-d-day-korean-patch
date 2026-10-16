#!/usr/bin/env python3
"""Checks the exact STEP095 FIX1 runtime regression without needing PPSSPP."""
import sys, json, base64, struct
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import ws_readonly as w
import passive_owner_watch as watcher

class Socket:
    def __init__(self): self.timeout=12
    def gettimeout(self): return self.timeout
    def settimeout(self,s): self.timeout=s

# Avoid a network connection while testing real WS.request method.
obj=w.WS.__new__(w.WS)
obj.ticket=0
obj.socket=Socket()
sent=[]
obj.send_json=lambda msg: sent.append(msg)
def recv():
    pkt=sent[-1]
    if pkt['event']=='version':
        return {'ticket': pkt['ticket'], 'event':'version','name':'PPSSPP','version':'1.0'}
    elif pkt['event']=='game.status':
        return {'ticket': pkt['ticket'], 'event':'game.status', 'game':{'id':'ULUS10193'}}
    elif pkt['event']=='memory.read':
        return {'ticket':pkt['ticket'], 'event':'memory.read', 'base64':base64.b64encode(b'\x00'*pkt['size']).decode('ascii')}
    raise AssertionError(pkt)
obj.recv_json=recv

# Exact call signature that failed on user's PC in FIX1.
result=obj.request('version',8,name='bia-step095-fix2',version='1.0')
assert result['event']=='version'
assert sent[-1]['name']=='bia-step095-fix2'
assert sent[-1]['version']=='1.0'
assert obj.request('game.status',7)['game']['id']=='ULUS10193'
assert len(w.memread(obj,watcher.OWNER,0x38))==0x38
assert sent[-1]['event']=='memory.read'
assert obj.socket.gettimeout()==12
try:
    obj.request('cpu.pause')
except ValueError: pass
else: raise AssertionError('Unsafe CPU command not blocked')
try:
    obj.request('memory.write',8,address=watcher.OWNER,base64='AAAA')
except ValueError: pass
else: raise AssertionError('Unsafe memory write not blocked')
print('PASS: version name parameter no longer collides; game.status and RAM read work; unsafe API denied')
