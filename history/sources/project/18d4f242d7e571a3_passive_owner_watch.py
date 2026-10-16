#!/usr/bin/env python3
"""BIA STEP095 FIX1: passive, breakpoint-free, read-only owner+0x28 field observation.

This does NOT identify a write instruction. It records time-series field changes
and captures owner/font headers for debugging, without pausing CPU.
"""
import argparse, datetime, hashlib, json, struct, time, traceback
from pathlib import Path
import ws_readonly as kg

OWNER=0x09A69A90
FONT_FIELD=OWNER+0x28
EXPECTED_VTABLE=0x08D67A88
DEFAULT_FONT=0x09A74150


def now(): return datetime.datetime.now().astimezone().isoformat(timespec='milliseconds')
def hx(x): return '0x%08X' % x if isinstance(x,int) else None

def owner_sample(ws):
    raw=kg.memread(ws,OWNER,0x38)
    q=lambda at:struct.unpack_from('<I',raw,at)[0]
    result={'ts':now(),'owner':hx(OWNER), 'vtable':hx(q(0)),
            'vtable_matches_prior_snapshot':q(0)==EXPECTED_VTABLE,
            'font_field_0x28':hx(q(0x28)), 'field_0x2c':hx(q(0x2c)),
            'font_matches_prior_default':q(0x28)==DEFAULT_FONT,
            'owner_prefix_hex':raw.hex()}
    p=q(0x28)
    if 0x08000000<=p<0x09FFFFA0:
        try:
            font=kg.memread(ws,p,0x60)
            nq=lambda at:struct.unpack_from('<I',font,at)[0]
            result['font']={'address':hx(p),'records_ptr':hx(nq(0x40)),
                'record_count_at_0x44':nq(0x44), 'header_sha256':hashlib.sha256(font).hexdigest(),
                'header_hex':font.hex()}
        except Exception as e:result['font_read_error']=str(e)
    return result


def write_report(path, report):
    tmp=path.with_suffix('.tmp')
    tmp.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    tmp.replace(path)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--port',type=int,required=True)
    ap.add_argument('--output',required=True)
    ap.add_argument('--ready-file',required=True)
    ap.add_argument('--stop-file',required=True)
    ap.add_argument('--listener-pid',type=int,required=True)
    ap.add_argument('--timeout',type=int,default=900)
    a=ap.parse_args()
    out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
    stop,ready=Path(a.stop_file),Path(a.ready_file)
    rptfile=out/'step095_fix1_passive_report.json'
    rpt={'step':'STEP_095_FIX1','started':now(),'status':'STARTED',
         'method':'passive WebSocket memory.read while CPU runs',
         'breakpoints_installed':0,'cpu_pause_commands_sent':0,
         'cpu_resume_commands_sent':0,'emulated_ram_writes':0,
         'iso_writes':0,'cpu_paused_by_probe':False,'full_ram_dump':False,
         'owner_address':hx(OWNER),'font_field_address':hx(FONT_FIELD),
         'listener_pid_verified_by_launcher':a.listener_pid,
         'field_events':[],'errors':[],'samples_total':0}
    ws=None
    try:
        ws=kg.WS(a.port)
        rpt['version']=ws.request('version',8,name='bia-step095-fix1',version='1.0')
        deadline=time.monotonic()+30
        while True:
            gs=ws.request('game.status',7)
            if gs.get('game',{}).get('id')=='ULUS10193':break
            if time.monotonic()>deadline:
                raise RuntimeError('EXPECTED_ULUS10193_NOT_BOOTED')
            time.sleep(.3)
        rpt['game_status_at_arm']=gs
        # No breakpoints: arming cannot force a CPU pause during START or mission loading.
        rpt['armed_at']=now();rpt['status']='ARMED_PASSIVE'
        ready.write_text('passive_armed',encoding='utf-8')
        print('STEP095 FIX1 passive watcher armed (NO BREAKPOINTS)',flush=True)
        last=None;heartbeat=time.monotonic();end=time.monotonic()+min(a.timeout,1200)
        failures=0
        while time.monotonic()<end:
            if stop.exists():rpt['stop_signal_seen']=now();break
            try:
                sample=owner_sample(ws)
                rpt['samples_total']+=1;failures=0
                signature=(sample['vtable'],sample['font_field_0x28'],sample['field_0x2c'],
                           sample.get('font',{}).get('record_count_at_0x44'))
                if signature!=last:
                    if len(rpt['field_events'])<1000:
                        rpt['field_events'].append(sample)
                    else:rpt['dropped_field_events']=rpt.get('dropped_field_events',0)+1
                    last=signature
                if time.monotonic()-heartbeat>=3:
                    rpt['last_sample']=sample
                    write_report(rptfile,rpt)
                    heartbeat=time.monotonic()
            except Exception as e:
                failures+=1
                if len(rpt['errors'])<40:
                    rpt['errors'].append({'at':now(),'exception':repr(e)})
                if failures>=4:
                    raise RuntimeError('MEMORY_POLL_UNAVAILABLE_4X: '+repr(e))
                time.sleep(.35)
            time.sleep(.22)
        if time.monotonic()>=end:rpt['status']='TIMEOUT_NO_SCREENSHOT'
        else:rpt['status']='PASSIVE_CAPTURE_COMPLETE_NO_PATCH'
        rpt['field_change_count']=max(0,len(rpt['field_events'])-1)
    except Exception as e:
        rpt['status']='FAILED';rpt['fatal_error']=repr(e)
        rpt['traceback']=traceback.format_exc()
        raise
    finally:
        rpt['finished']=now()
        write_report(rptfile,rpt)
        (out/'STEP_095_FIX1.md').write_text(
            '# STEP 095 FIX1 — Passive font owner observation\n\n'
            'Status: '+rpt['status']+'\n\n'
            'No CPU pause, no breakpoints, no ISO or PSP memory writes.\n'
            'Any observed pointer transition is not a proven writing instruction.\n',encoding='utf-8')
        if ws:
            try:ws.close()
            except Exception:pass
        print('STEP095 FIX1:',rpt['status'],flush=True)

if __name__=='__main__':main()
