"""Linux/offline tests: mock read-only WebSocket and static safety checks."""
import json, pathlib, sys, tempfile, struct, zipfile, hashlib
ROOT=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
import small_snapshot

def test_snapshot():
    class FakeWS:
        def request(self,event,seconds=8,**kw):
            assert event in ('version','game.status')
            return {'event':event,'name':'PPSSPP'} if event=='version' else {'event':event,'game':{'id':'ULUS10193'}}
    old=small_snapshot.memread
    calls=[]
    def fake(w,addr,size):
        calls.append((addr,size))
        b=bytearray(size)
        if addr==0x09A69A90:
            struct.pack_into('<I',b,0,0x08D67A88)
            struct.pack_into('<I',b,0x28,0x09A74150)
        if addr==0x09A74150:
            struct.pack_into('<I',b,0x44,150)
        if addr==0x09E7B040:
            raw='프랑스 유타 해변 인근'.encode('utf8');b[:len(raw)]=raw
        return bytes(b)
    small_snapshot.memread=fake
    try:
        result=small_snapshot.snapshot(FakeWS())
        assert result['memory_bytes_total']<=512
        assert result['results']['historical_owner']['vtable_matches_prior']
        assert result['results']['historical_owner']['font_matches_prior']
        assert result['results']['historical_font']['glyph_count_plus_0x44']==150
        assert result['results']['historical_korean_utf8']['contains_known_phrase']
        assert calls==[(0x09A69A90,0x38),(0x09A74150,0x60),(0x09E7B040,0x60)]
    finally:small_snapshot.memread=old

def test_unmapped_owner():
    class FakeWS:
        def request(self,event,seconds=8,**kw):return {'event':event}
    old=small_snapshot.memread
    small_snapshot.memread=lambda w,a,n:bytes(n)
    try:
        result=small_snapshot.snapshot(FakeWS())
        assert result['results']['historical_owner']['all_zero']
        assert not result['results']['historical_owner']['vtable_matches_prior']
        assert not result['results']['historical_owner']['font_matches_prior']
    finally:small_snapshot.memread=old

def test_safety():
    run=(ROOT/'RUN.ps1').read_text();launcher=(ROOT/'LAUNCH.ps1').read_text()
    assert 'Stop-Process' not in (run+launcher)
    assert 'TerminateProcess' not in (run+launcher)
    assert 'cpu.pause' not in (run+launcher)
    assert 'memory.write' not in (run+launcher)
    assert 'GetAsyncKeyState' not in (run+launcher)
    assert 'PPSSPP_EXITED_BEFORE_SCREENSHOT' in run
    assert 'SUPERVISOR_PROCESS_DISAPPEARED' in launcher
    assert 'fail_bia_STEP_095_FIX3_start_exit_capture_' not in launcher  # correct prefix fall_
    assert 'fall_bia_STEP_095_FIX3_start_exit_capture_' in launcher
    assert 'RUN_DONE.json' in launcher
    assert 'zip_stage' in launcher
    assert 'Get-WinEvent' in launcher
    assert 'PROJECT_STATE_APPEND.md' in launcher
    assert 'memory_bytes_total' in (ROOT/'small_snapshot.py').read_text()
    assert "allowed={'version','game.status','memory.read'}" in (ROOT/'ws_readonly.py').read_text()

def test_reject_unsafe_ws_api():
    from ws_readonly import WS
    ws=WS.__new__(WS);ws.ticket=0
    try:ws.request('cpu.pause')
    except ValueError:pass
    else:raise AssertionError('Unsafe event allowed')

def test_archive():
    with tempfile.TemporaryDirectory() as t:
        path=pathlib.Path(t)/'file.zip'
        with zipfile.ZipFile(path,'w') as z:
            for name in ('LAUNCH.ps1','RUN.ps1','small_snapshot.py','ws_readonly.py','README.md'):
                z.write(ROOT/name,name)
        with zipfile.ZipFile(path) as z:
            assert z.testzip() is None
            assert len(z.namelist())>=5

if __name__=='__main__':
    for test in (test_snapshot,test_unmapped_owner,test_safety,test_reject_unsafe_ws_api,test_archive):
        test();print('PASS',test.__name__)
