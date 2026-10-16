import importlib.util,json,struct,tempfile,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'scripts'))
import passive_owner_watch as p
class Fake:
    def __init__(self):self.calls=[]

def fake_read(ws, addr, size):
    ws.calls.append((addr,size))
    if addr==p.OWNER:
        b=bytearray(size)
        for off,val in ((0,p.EXPECTED_VTABLE),(0x28,p.DEFAULT_FONT),(0x2c,1234)):
            struct.pack_into('<I',b,off,val)
        return bytes(b)
    if addr==p.DEFAULT_FONT:
        b=bytearray(size)
        for off,val in ((0x40,0x0971BB20),(0x44,150)):
            struct.pack_into('<I',b,off,val)
        return bytes(b)
    raise RuntimeError('UNKNOWN_ADDR')
old=p.kg.memread
try:
    p.kg.memread=fake_read
    ws=Fake()
    o=p.owner_sample(ws)
    assert o['font_field_0x28']==p.hx(p.DEFAULT_FONT)
    assert o['font']['record_count_at_0x44']==150
    assert o['vtable_matches_prior_snapshot']
    assert ws.calls==[(p.OWNER,0x38),(p.DEFAULT_FONT,0x60)]
    with tempfile.TemporaryDirectory() as td:
        target=Path(td)/'report.json';p.write_report(target,o)
        assert json.loads(target.read_text())==o
    print('PASS: passive owner sampling and report serialization')
finally:p.kg.memread=old
