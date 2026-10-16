#!/usr/bin/env python3
"""STEP 095: armed-before-mission, read-only observation of font owner+0x28 writes.

Reads only PSP memory/registers. Installs its own debugger breakpoints, pauses
briefly for snapshots, removes them on exit. Does not patch PSP RAM or ISO.
"""
import argparse, datetime, json, struct, time, traceback
from pathlib import Path
import stage071_known_good as kg
import capture_unicode_font as core

OWNER=0x09A69A90
FIELD=OWNER+0x28
VTABLE=0x08D67A88
KNOWN_FONT=0x09A74150
CODE={0x089F2428:0xAE050028,0x089F9874:0xAE050028,0x088861DC:0x0E27C904,
      0x089F6E5C:0x8E040028,0x089F6EF4:0x00802825,0x089F6F0C:0x0160F809}
SETTER=0x089F2428
COPIER=0x089F9874
MAX_HITS=24

def now():return datetime.datetime.now().astimezone().isoformat(timespec='milliseconds')
def fmt(x):return core.fmt(x)
def u32(ws,addr):return struct.unpack('<I',kg.memread(ws,addr,4))[0]
def snap(ws,a,n):return core.small(ws,a,n)

def resume(ws,r):
    for i in range(4):
        try:
            s=core.state(ws)
            if not s.get('stepping'):return True
            ws.send('cpu.resume');time.sleep(.14)
        except Exception as e:
            r.setdefault('warnings',[]).append('RESUME_EXCEPTION:'+repr(e))
    try:return not core.state(ws).get('stepping')
    except Exception:return False

def inspect(ws,r,status):
    g=core.regs(ws)
    pc=g.get('pc',0)
    o={'time':now(),'pc':fmt(pc),'ra':fmt(g.get('ra')),
       'cpu':status,'registers':{k:fmt(v) for k,v in g.items() if isinstance(v,int)}}
    try:
        o['owner_ptr_current']=fmt(u32(ws,OWNER))
        o['owner_field_current']=fmt(u32(ws,FIELD))
        o['owner_vtable_matches']=u32(ws,OWNER)==VTABLE
    except Exception as e:o['owner_read_error']=str(e)
    if pc in CODE and u32(ws,pc)!=CODE[pc]:
        o['warning']='TRAP_AT_UNEXPECTED_CODE_SIGNATURE'
        o['target_is_owner']=False
        return o
    if pc==SETTER:
        o['kind']='DIRECT_SETTER';o['target_is_owner']=g.get('s0')==OWNER
        o['incoming_font']=fmt(g.get('a1'))
        o['setter_base']=fmt(g.get('s0'))
    elif pc==COPIER:
        o['kind']='COPY_INTO_OWNER';o['target_is_owner']=g.get('s0')==OWNER
        o['incoming_font']=fmt(g.get('a1'))
        o['copy_source_object']=fmt(g.get('a0'))
        if core.valid(g.get('a0'),0x40):o['copy_source_snapshot']=snap(ws,g['a0'],0x40)
    else:
        o['kind']='MEMORY_WRITE_OR_OTHER';o['target_is_owner']=o.get('owner_vtable_matches',False)
    if core.valid(g.get('sp'),80):o['stack']=snap(ws,g['sp'],80)
    if core.valid(g.get('a1'),64):o['a1_preview']=snap(ws,g['a1'],64)
    return o

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--port',type=int,required=True)
    ap.add_argument('--output',required=True)
    ap.add_argument('--listener-pid',type=int,required=True)
    ap.add_argument('--ready-file',required=True)
    ap.add_argument('--stop-file',required=True)
    ap.add_argument('--timeout',type=int,default=900)
    a=ap.parse_args()
    out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
    ready=Path(a.ready_file);stop=Path(a.stop_file)
    report={'step':'STEP_095','status':'ARMING','start':now(),
            'goal':'observe font initialization BEFORE user enters Mission 2; owner +0x28 font writer',
            'owner':fmt(OWNER),'field':fmt(FIELD),'expected_class_vtable':fmt(VTABLE),
            'iso_written':False,'emulated_ram_written':False,'registers_written':False,'full_ram_dump':False,
            'render_fixed':False,'listener_pid_verified_by_launcher':a.listener_pid,
            'hits':[],'breakpoint_add':[],'breakpoint_remove':[],'warnings':[]}
    ws=None;added=[]
    try:
        ws=kg.WS(a.port)
        report['version']=ws.request('version',8,name='bia-step095',version='1.0')
        deadline=time.monotonic()+20
        while True:
            gs=ws.request('game.status',8)
            if gs.get('game',{}).get('id')=='ULUS10193':break
            if time.monotonic()>deadline:raise RuntimeError('WRONG_OR_NOT_YET_RUNNING_GAME')
            time.sleep(.25)
        report['game_status_at_arm']=gs
        report['code_signatures']=[]
        for pc,expect in CODE.items():
            actual=u32(ws,pc)
            report['code_signatures'].append({'address':fmt(pc),'expected':fmt(expect),'actual':fmt(actual),'match':actual==expect})
            if actual!=expect:report['warnings'].append('SIGNATURE_NOT_LOADED_YET:'+fmt(pc))
        if core.state(ws).get('stepping'):raise RuntimeError('FOREIGN_PAUSED_CPU')
        old_exec=ws.request('cpu.breakpoint.list',8).get('breakpoints',[])
        old_mem=ws.request('memory.breakpoint.list',8).get('breakpoints',[])
        if any(b.get('address') in (SETTER,COPIER) for b in old_exec):raise RuntimeError('FOREIGN_EXEC_BP_COLLISION')
        if any(b.get('address')==FIELD for b in old_mem):raise RuntimeError('FOREIGN_MEMORY_BP_COLLISION')
        specs=[('cpu',SETTER,{'address':SETTER,'enabled':True,'log':False,'condition':f'a0 == {fmt(OWNER)}'}),
               ('cpu',COPIER,{'address':COPIER,'enabled':True,'log':False,'condition':f's0 == {fmt(OWNER)}'}),
               ('memory',FIELD,{'address':FIELD,'size':4,'enabled':True,'log':False,'read':False,'write':True})]
        for typ,addr,params in specs:
            ack=ws.request(f'{typ}.breakpoint.add',10,**params)
            added.append((typ,addr))
            report['breakpoint_add'].append({'type':typ,'address':fmt(addr),'reply':ack,'args':params})
        report['armed_at']=now();report['status']='ARMED'
        ready.write_text('armed',encoding='utf-8')
        until=time.monotonic()+min(a.timeout,1200)
        while time.monotonic()<until:
            if stop.exists():report['stop_signal_seen']=now();break
            st=core.state(ws)
            if st.get('stepping'):
                hit=inspect(ws,report,st)
                report['hits'].append(hit)
                if not resume(ws,report):
                    report['warnings'].append('CPU_NOT_RESUMED_DURING_TRACE')
                    break
                if len(report['hits'])>=MAX_HITS:
                    report['warnings'].append('MAX_HITS_REACHED')
                    break
            else:time.sleep(.08)
        if time.monotonic()>=until:report['warnings'].append('CAPTURE_TIMEOUT')
        report['owner_end']={'vtable':fmt(u32(ws,OWNER)),'font_field':fmt(u32(ws,FIELD)),
                             'font_field_equals_known_default':u32(ws,FIELD)==KNOWN_FONT}
        report['confirmed_owner_writer_hits']=sum(1 for h in report['hits'] if h.get('target_is_owner'))
        report['status']='OWNER_WRITER_OBSERVED_NO_PATCH' if report['confirmed_owner_writer_hits'] else 'NO_OWNER_WRITER_OBSERVED_NO_PATCH'
    except Exception as e:
        report['status']='FAILED';report['error']=repr(e);report['traceback']=traceback.format_exc()
        raise
    finally:
        if ws:
            for typ,addr in reversed(added):
                try:
                    ack=ws.request(f'{typ}.breakpoint.remove',8,address=addr,**({'size':4} if typ=='memory' else {}))
                    report['breakpoint_remove'].append({'type':typ,'address':fmt(addr),'removed':True,'reply':ack})
                except Exception as e:
                    report['breakpoint_remove'].append({'type':typ,'address':fmt(addr),'removed':False,'error':repr(e)})
            report['cpu_resumed_at_end']=resume(ws,report)
            try:report['cpu_final']=core.state(ws)
            except Exception as e:report['warnings'].append('FINAL_STATUS_UNAVAILABLE:'+repr(e))
            try:ws.close()
            except:pass
        if not all(x.get('removed') for x in report['breakpoint_remove']) or not report.get('cpu_resumed_at_end',False):
            report['status']='FAILED_CLEANUP_REQUIRES_REVIEW'
        report['finished']=now()
        (out/'step095_owner_writer_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        (out/'STEP_095.md').write_text('# STEP 095 — Owner +0x28 font writer\n\n'+report['status']+'\n\nNo ISO/RAM writes. Font rendering not yet fixed.\n',encoding='utf-8')
        print('STEP095:',report['status'],flush=True)

if __name__=='__main__':main()
