#!/usr/bin/env python3
# BIA STEP086: minimal read-only live mission2 string/font-access watch.
# Only debugger watchpoints; no PSP memory.write or ISO writes.
import argparse, base64, datetime, json, time, traceback
from pathlib import Path
import stage071_known_good as kg

MARK='프랑스 유타 해변 인근'.encode('utf-8')
TARGETS=[
    ('mission2_utf8_source',0x09E7B040,len(MARK)),
    ('hangul_page_index_peu',0x09E75528,2),
    ('mission2_fontA_glyph_pointer',0x09B1CF24+0x54,4),
    ('mission2_fontB_glyph_pointer',0x09B1F0BC+0x54,4),
]

def save(out,data):
    (out/'step086_watch_report.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')

def verify_mission(ws):
    got=kg.memread(ws,0x09E7B040,len(MARK))
    if got!=MARK:raise RuntimeError('MISSION2_UTF8_ANCHOR_NOT_MATCHED; refusing stale-address instrumentation: %s'%got.hex())
    before=kg.memread(ws,0x09E7B034,12)
    if not before.startswith(b'D-Day 06:00'):
        raise RuntimeError('MISSION2_TIME_ANCHOR_NOT_MATCHED: %r'%before)
    return {'address':'0x09E7B040','utf8':got.decode('utf-8'),'adjacent_time':'D-Day 06:00'}

def watch(ws,out,report):
    added=[]
    try:
        report['cpu_before']=ws.request('cpu.status',10)
        for name,addr,size in TARGETS:
            response=ws.request('memory.breakpoint.add',12,address=addr,size=size,
                                enabled=False,log=True,read=True,write=False,
                                logFormat=f'STEP086_{name} pc={{pc:x}} ra={{ra:x}}')
            added.append((name,addr,size))
            report.setdefault('added_watchpoints',[]).append({'name':name,'address':hex(addr),'size':size,'response':response})
        samples=[]
        for i in range(8):
            time.sleep(0.5)
            bp=ws.request('memory.breakpoint.list',10)
            status=ws.request('cpu.status',10)
            watched=[]
            for name,addr,size in TARGETS:
                v=next((b for b in bp.get('breakpoints',[]) if b.get('address')==addr and b.get('size')==size),None)
                watched.append({'name':name,'address':hex(addr),'hits':v.get('hits') if v else None,'found':v is not None})
            samples.append({'elapsed_seconds':(i+1)*.5,'stepping':status.get('stepping'),'hits':watched})
            if status.get('stepping'):
                raise RuntimeError('UNEXPECTED_CPU_PAUSE_DURING_NONPAUSING_WATCH; will remove watchpoints')
        report['samples']=samples
        report['last_hits']=samples[-1]['hits']
        report['cpu_after']=ws.request('cpu.status',10)
        report['sampled_pc_logs']=getattr(ws,'diagnostic_logs',[])[:250]
        report['dropped_log_messages_locally']=getattr(ws,'diagnostic_log_dropped',0)
        report['interpretation']='Hits>0 proves RAM address accessed during sample; zero hits cannot disprove earlier one-time loading, nor prove renderer path.'
    finally:
        clean=[]
        for name,addr,size in reversed(added):
            try:
                x=ws.request('memory.breakpoint.remove',10,address=addr,size=size)
                clean.append({'name':name,'removed':True})
            except Exception as e:clean.append({'name':name,'removed':False,'error':str(e)})
        report['watch_cleanup']=clean
        # Isolated PPSSPP will exit on caller cleanup even if breakpoint removal fails.

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--port',required=True,type=int)
    p.add_argument('--output',required=True)
    p.add_argument('--expected',required=True)
    p.add_argument('--listener-pid',required=True,type=int)
    a=p.parse_args()
    out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
    report={'step':'STEP_086','status':'RUNNING','read_only_game_memory':True,
            'psp_ram_writes':False,'iso_modified':False,'pid_prechecked_by_launcher':a.listener_pid,
            'mission2_korean_render_fixed':False,'watchpoint_mode':'log only, no pause',
            'source_screenshot':'copied native PPSSPP key 1 image from launcher'}
    ws=None
    try:
        ws=kg.WS(a.port)
        report['version']=ws.request('version',10,name='bia-step086-readwatch',version='1.0')
        game=ws.request('game.status',10)
        if game.get('game',{}).get('id')!='ULUS10193':raise RuntimeError('GAME_ID_MISMATCH: '+str(game))
        report['game_status']=game
        report['scene_anchor']=verify_mission(ws)
        watch(ws,out,report)
        report['status']='WATCH_TRACE_COLLECTED_UNVERIFIED'
        print('Watchpoint hits:',report['last_hits'],flush=True)
    except Exception as e:
        report['status']='FAILED';report['error']=str(e);report['traceback']=traceback.format_exc()
        raise
    finally:
        if ws:
            try:ws.close()
            except Exception:pass
        report['completed_at']=datetime.datetime.now().astimezone().isoformat(timespec='seconds')
        save(out,report)

if __name__=='__main__':main()
