import sys, tempfile, json, struct
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'scripts'))
import passive_owner_watch as p
class MockWS:
    def __init__(self,port): self.port=port;self.calls=[]
    def request(self,event,secs=8,**kw):
        self.calls.append((event,kw))
        if event=='version':
            assert kw['name']=='bia-step095-fix2';return {'event':'version'}
        if event=='game.status':return {'game':{'id':'ULUS10193'}}
        raise AssertionError('unexpected API: '+event)
    def close(self):pass
class Mem:
    @staticmethod
    def read(obj,addr,size):
        b=bytearray(size)
        if addr==p.OWNER:
            struct.pack_into('<I',b,0,p.EXPECTED_VTABLE)
            struct.pack_into('<I',b,0x28,p.DEFAULT_FONT)
        if addr==p.DEFAULT_FONT:
            struct.pack_into('<I',b,0x44,150)
        return bytes(b)
oldws=p.kg.WS
oldmem=p.kg.memread
oldargv=sys.argv
p.kg.WS=MockWS;p.kg.memread=Mem.read
try:
    with tempfile.TemporaryDirectory() as d:
        d=Path(d);(d/'stop.signal').write_text('1')
        sys.argv=['prog','--port','26420','--output',str(d),'--ready-file',str(d/'ready.signal'),
                  '--stop-file',str(d/'stop.signal'),'--listener-pid','666','--timeout','1']
        p.main()
        rpt=json.loads((d/'step095_fix2_passive_report.json').read_text())
        assert rpt['status']=='PASSIVE_CAPTURE_COMPLETE_NO_PATCH',rpt
        assert rpt['breakpoints_installed']==0 and rpt['cpu_pause_commands_sent']==0
        assert json.loads((d/'ready.signal').read_text())['status']=='PASSIVE_ARMED'
    print('PASS: simulated full watcher ready/stop/report without breakpoints')
finally:
    sys.argv=oldargv;p.kg.WS=oldws;p.kg.memread=oldmem
