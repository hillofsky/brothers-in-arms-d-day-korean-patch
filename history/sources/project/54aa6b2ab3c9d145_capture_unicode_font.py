#!/usr/bin/env python3
"""BIA STEP091: non-destructive Unicode-after-decode breakpoint at 0x089F5710.

The instruction at 0x089F5704 calls UTF8 decoder at 0x08E02C10.
At 0x089F5710, a0 contains decoded Unicode, s3 contains font object,
v0 contains input string pointer. A conditional execution breakpoint on a0 >= 0x80
avoids stopping on the English mission title. PSP ISO/RAM is never written.
"""
import argparse, datetime, json, struct, time, traceback
from pathlib import Path
import stage071_known_good as kg

ROM_PC=0x089F5710
ENTRY_PC=0x089F5668
CODE_SIG={0x089F5668:0x27BDFF70,0x089F5704:0x0E380B04,
          0x089F570C:0x00000000,0x089F5710:0x8E650054}
RAM0,RAM1=0x08000000,0x0A000000
SOURCE_ADDR=0x09E7B040
SOURCE=b'\xed\x94\x84\xeb\x9e\x91\xec\x8a\xa4 \xec\x9c\xa0\xed\x83\x80 \xed\x95\xb4\xeb\xb3\x80 \xec\x9d\xb8\xea\xb7\xbc'
CONDITION='a0 >= 0x80 && a0 <= 0xFFFF'
FONT_CACHE={}

def now():return datetime.datetime.now().astimezone().isoformat(timespec='milliseconds')
def fmt(v):return f'0x{v:08X}' if isinstance(v,int) else None
def valid(a,n=1):return isinstance(a,int) and RAM0<=a and n>=0 and a+n<=RAM1

def small(ws,address,n=96):
    d={'address':fmt(address),'requested':n}
    if not valid(address,n):d['status']='NOT_MAPPED_RAM';return d
    try:
        data=kg.memread(ws,address,n)
        d.update(status='OK',data_hex=data.hex(),utf8_preview=data[:96].split(b'\0')[0].decode('utf-8','replace'))
    except Exception as ex:d.update(status='READ_ERROR',error=str(ex))
    return d

def regs(ws):
    r=ws.request('cpu.getAllRegs',8)
    for c in r.get('categories',[]):
        if c.get('name')=='GPR':
            return dict(zip(c.get('registerNames',[]),c.get('uintValues',[])))
    return {}

def font_info(ws,ptr,codepoint):
    result={'font_pointer':fmt(ptr),'codepoint':f'U+{codepoint:04X}', 'lookup':'NOT_PROVEN'}
    if not valid(ptr,0x58):result['error']='FONT_PTR_NOT_RAM';return result
    try:
        if ptr not in FONT_CACHE:
            hdr=kg.memread(ws,ptr,0x60)
            at=lambda off:struct.unpack_from('<I',hdr,off)[0]
            base,count,buckets,n,enabled=tuple(at(i) for i in (0x40,0x44,0x4c,0x50,0x54))
            cached={'font_ptr':fmt(ptr),'record_ptr':fmt(base),'record_count':count,
                    'bucket_ptr':fmt(buckets),'bucket_modulus':n,'unicode_lookup_enabled':bool(enabled),
                    'font_header_hex':hdr.hex(),'records_valid':False}
            if 0<count<=2048 and valid(base,count*8):
                buf=kg.memread(ws,base,count*8)
                cached['records_valid']=True
                cached['record_sha256']=__import__('hashlib').sha256(buf).hexdigest()
                cached['records']=[(struct.unpack_from('<I',buf,k*8)[0],
                                    struct.unpack_from('<H',buf,k*8+4)[0],
                                    struct.unpack_from('<H',buf,k*8+6)[0]) for k in range(count)]
                cached['nonascii_count']=sum(1 for _,c,_ in cached['records'] if c>127)
                cached['hangul_record_count']=sum(1 for _,c,_ in cached['records'] if 0xAC00<=c<=0xD7A3)
            FONT_CACHE[ptr]=cached
        cached=FONT_CACHE[ptr]
        result.update({k:v for k,v in cached.items() if k!='records'})
        if cached['records_valid']:
            matches=[{'entry':i,'linked_next':fmt(nx),'unicode':f'U+{c:04X}','glyph_index':gi}
                     for i,(nx,c,gi) in enumerate(cached['records']) if c==codepoint]
            result['lookup']='FOUND' if matches else 'MISSING'
            result['matching_records']=matches[:3]
    except Exception as exc:result['error']=repr(exc)
    return result

def state(ws):return ws.request('cpu.status',6)
def safe_resume(ws,report):
    try:
        before=state(ws)
        if before.get('stepping'):
            ws.send('cpu.resume')
            time.sleep(.15)
            after=state(ws)
            report.setdefault('resume_events',[]).append({'before':before,'after':after})
            if after.get('stepping'):report.setdefault('warnings',[]).append('CPU_REMAINS_STEPPING')
    except Exception as ex:report.setdefault('warnings',[]).append('RESUME_FAILED: '+repr(ex))

def capture_hit(ws,i,phase,status):
    g=regs(ws)
    d={'index':i,'at':now(),'phase':phase,'status':status,
       'pc':fmt(g.get('pc')),'ra':fmt(g.get('ra')),
       'registers':{k:fmt(v) for k,v in g.items() if isinstance(v,int)},
       'hit_at_expected_pc':g.get('pc')==(ROM_PC if phase=='unicode' else ENTRY_PC)}
    if not d['hit_at_expected_pc']:
        d['warning']='UNEXPECTED_PC_WHILE_STEPPING'
        return d
    if phase=='unicode':
        cp=g.get('a0',0)
        d['codepoint']=f'U+{cp:04X}'
        d['character']=chr(cp) if 0<=cp<=0x10FFFF else '?'
        d['input_text']=small(ws,g.get('v0'),96)
        d['font']=font_info(ws,g.get('s3'),cp)
        d['font_info_source']='MIPS renderer 0x089F5710 uses $s3 ($19) font object, reads +0x54, +0x40, +0x4c, +0x50'
        for x in ('a1','a2','sp'):
            d['register_data_'+x]=small(ws,g.get(x),64)
    else:
        d['input_text']=small(ws,g.get('a2'),96)
        d['font']=font_info(ws,g.get('a1'),ord('프'))
        d['font_info_source']='Renderer entry a1 interpreted as font; test only, not Unicode proof'
    return d

def watch_once(ws,report,addr,condition,limit,seconds,phase):
    name='unicode_hits' if phase=='unicode' else 'entry_control_hits'
    bps=ws.request('cpu.breakpoint.list',8).get('breakpoints',[])
    if any(x.get('address')==addr for x in bps):raise RuntimeError('EXISTING_BREAKPOINT_AT_'+fmt(addr))
    initial=state(ws)
    if initial.get('stepping'):raise RuntimeError('CPU_ALREADY_STEPPING: refusing to overwrite debugger state')
    installed=False
    try:
        params={'address':addr,'enabled':True,'log':False}
        if condition:params['condition']=condition
        add=ws.request('cpu.breakpoint.add',10,**params);installed=True
        report.setdefault('breakpoint_install',[]).append({'address':fmt(addr),'phase':phase,'condition':condition,'reply':add})
        end=time.monotonic()+seconds
        prev_ticks=None
        while len(report.setdefault(name,[]))<limit and time.monotonic()<end:
            st=state(ws)
            if not st.get('stepping'):
                time.sleep(.07);continue
            hit=capture_hit(ws,len(report[name]),phase,st)
            report[name].append(hit)
            if not hit['hit_at_expected_pc']:
                report.setdefault('warnings',[]).append('UNEXPECTED_PAUSE_AT_'+str(hit.get('pc')))
                break
            safe_resume(ws,report)
            if report.get('warnings') and 'CPU_REMAINS_STEPPING' in report['warnings']:
                break
            time.sleep(.06)
        report.setdefault('breakpoint_counts',[]).append({'phase':phase,'samples':len(report[name])})
    finally:
        if installed:
            try:
                res=ws.request('cpu.breakpoint.remove',8,address=addr)
                report.setdefault('breakpoint_cleanup',[]).append({'address':fmt(addr),'removed':True,'response':res})
            except Exception as ex:
                report.setdefault('breakpoint_cleanup',[]).append({'address':fmt(addr),'removed':False,'error':str(ex)})
        safe_resume(ws,report)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--port',type=int,required=True)
    ap.add_argument('--output',required=True)
    ap.add_argument('--listener-pid',type=int,required=True)
    a=ap.parse_args()
    out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
    r={'step':'STEP_091','status':'STARTED','type':'runtime_unicode_glyph_font_selection_probe',
       'goal':'identify font pointer at Unicode postdecoder for mission2 Korean text',
       'iso_modified':False,'ram_writes':False,'full_ram_dump':False,
       'render_fixed':False,'listener_pid_checked_by_launcher':a.listener_pid,
       'korean_anchor':fmt(SOURCE_ADDR),'unicode_pc':fmt(ROM_PC),'conditional_expression':CONDITION,
       'max_unicode_samples':12,'max_control_samples':2}
    ws=None
    try:
        ws=kg.WS(a.port)
        r['ppsspp_version']=ws.request('version',8,name='bia-step091',version='1.0')
        gs=ws.request('game.status',8);r['game_status']=gs
        if gs.get('game',{}).get('id')!='ULUS10193':raise RuntimeError('WRONG_GAME')
        raw=kg.memread(ws,SOURCE_ADDR,len(SOURCE))
        if raw!=SOURCE:raise RuntimeError('KOREAN_MISSION2_ANCHOR_MISMATCH')
        r['verified_korean_anchor']=True
        r['code_signatures']=[]
        for addr,word in CODE_SIG.items():
            got=struct.unpack('<I',kg.memread(ws,addr,4))[0]
            r['code_signatures'].append({'pc':fmt(addr),'expected':fmt(word),'actual':fmt(got),'match':got==word})
            if got!=word:raise RuntimeError('RENDERER_CODE_SIGNATURE_CHANGED_AT_'+fmt(addr))
        r['existing_exec_breakpoints']=len(ws.request('cpu.breakpoint.list',8).get('breakpoints',[]))
        r['before_cpu_status']=state(ws)
        if r['before_cpu_status'].get('stepping'):raise RuntimeError('CPU_ALREADY_PAUSED_BEFORE_PROBE')
        # Narrow conditional at a *decoded Unicode codepoint*, not the English-title entry point.
        watch_once(ws,r,ROM_PC,CONDITION,12,12.0,'unicode')
        if not r.get('unicode_hits'):
            # Control: even a zero Unicode count might be because nothing rendered.
            # Record at most two generic entries to distinguish active renderer from no path.
            watch_once(ws,r,ENTRY_PC,None,2,3.0,'entry')
        # Classify only from actual runtime; never infer Korean font if no matching characters.
        confirmed=[]
        for s in r.get('unicode_hits',[]):
            if s.get('character') in '프랑스 유타 해변 인근독일군 박격포반제4보병사단과 합류':
                confirmed.append(s)
        r['mission2_korean_codepoint_hits']=len(confirmed)
        if confirmed:
            if any(x.get('font',{}).get('lookup')=='MISSING' for x in confirmed):
                r['status']='KOREAN_RENDERER_FONT_LOOKUP_MISSING_PROVEN_NO_FIX'
            elif all(x.get('font',{}).get('lookup')=='FOUND' for x in confirmed):
                r['status']='KOREAN_RENDERER_GLYPH_LOOKUP_PRESENT_RENDER_UNVERIFIED'
            else:r['status']='KOREAN_RENDERER_HIT_STRUCTURE_PARTIAL_NO_FIX'
        else:r['status']='NO_MISSION2_KOREAN_RENDERER_HITS_UNVERIFIED'
        if any(not x['removed'] for x in r.get('breakpoint_cleanup',[])):
            raise RuntimeError('OWN_EXEC_BREAKPOINT_LEAK')
        r['end_cpu_status']=state(ws)
        if r['end_cpu_status'].get('stepping'):raise RuntimeError('CPU_NOT_RESUMED_AT_END')
    except Exception as ex:
        r['status']='FAILED';r['error']=str(ex);r['traceback']=traceback.format_exc()
        raise
    finally:
        if ws:
            for pc in (ROM_PC,ENTRY_PC):
                if any(x['address']==fmt(pc) for x in r.get('breakpoint_install',[])) and not any(x['address']==fmt(pc) and x.get('removed') for x in r.get('breakpoint_cleanup',[])):
                    try:
                        ws.request('cpu.breakpoint.remove',6,address=pc)
                        r.setdefault('breakpoint_cleanup',[]).append({'address':fmt(pc),'removed':True,'final_cleanup':True})
                    except Exception as ex:r.setdefault('warnings',[]).append('LAST_REMOVE '+repr(ex))
            safe_resume(ws,r)
            try:ws.close()
            except Exception:pass
        r['completed_at']=now()
        (out/'step091_unicode_font_report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
        (out/'STEP_091.md').write_text('# STEP 091 — Korean Unicode font-selection probe\n\nStatus: '+r['status']+'\n\nISO and RAM were not modified. Rendering fix not applied.\n',encoding='utf-8')
        print('STEP091:',r['status'],flush=True)

if __name__=='__main__':main()
