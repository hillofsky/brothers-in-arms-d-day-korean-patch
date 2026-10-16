#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Collect second mission's LIVE font/atlas/FString state at visible '>' fallback.
Read-only PPSSPP debugger; uses STEP071 known-good WebSocket memory.read.
"""
import argparse, hashlib, json, datetime, struct, traceback, zlib, time
from pathlib import Path
import stage071_known_good as kg

BASE=0x08000000
RAM_SIZE=0x02000000

def dump_json(p,obj):
    p.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')

def probe_memory(ram,expected):
    def data(addr,n):
        if not (BASE<=addr<=BASE+len(ram)-n):
            return None
        return ram[addr-BASE:addr-BASE+n]
    def u16(addr):
        b=data(addr,2)
        return None if b is None else struct.unpack('<H',b)[0]
    def u32(addr):
        b=data(addr,4)
        return None if b is None else struct.unpack('<I',b)[0]
    out={'fonts':[], 'strings':[], 'atlas':{}}
    for ex in expected['font_objects']:
        addr=int(ex['runtime'],16);raw=data(addr,0x490)
        record={'runtime':ex['runtime'],'expected_sha256':ex['sha256']}
        if raw is None:
            record['error']='out of RAM range';out['fonts'].append(record);continue
        record.update({'runtime_sha256':hashlib.sha256(raw).hexdigest(),
                       'static_bytes_exact':hashlib.sha256(raw).hexdigest()==ex['sha256'],
                       'glyph_count':u16(addr+0x50),'glyph_ptr':hex(u32(addr+0x54) or 0),
                       'widths_ptr':hex(u32(addr+0x474) or 0),
                       'heights_ptr':hex(u32(addr+0x478) or 0),
                       'texture_array_ptr':hex(u32(addr+0x488) or 0),
                       'chars':{}})
        wa=u32(addr+0x474);ha=u32(addr+0x478);ta=u32(addr+0x488)
        record['renderer_page_arrays']={
           'widths':[u16(wa+i*2) for i in range(4)] if wa else [],
           'heights':[u16(ha+i*2) for i in range(4)] if ha else [],
           'textures':[hex(u32(ta+i*4) or 0) for i in range(4)] if ta else [],
        }
        for ch in expected['runtime_probe_cps']:
            cp=ord(ch);page_ptr=u32(addr+0x58+((cp>>8)*4))
            gi=u16(page_ptr+((cp&255)*2)) if page_ptr else None
            gp=u32(addr+0x54)
            rcp=u16(gp+gi*24) if (gp and gi is not None and gi < 4096) else None
            record['chars'][ch]={'unicode':f'U+{cp:04X}',
                                 'page_ptr':hex(page_ptr or 0),
                                 'glyph_index':gi,
                                 'glyph_record_cp':None if rcp is None else f'U+{rcp:04X}',
                                 'codepoint_verified':rcp==cp,
                                 'glyph_record_hex':(data(gp+gi*24,24) or b'').hex() if gp and gi is not None and gi<4096 else None}
        out['fonts'].append(record)
    atlas=int(expected['atlas_runtime_base'],16)
    raw=data(atlas,0x20000)
    out['atlas']={'runtime':hex(atlas),
                  'expected_sha256':expected['atlas_128k_sha256'],
                  'actual_sha256':hashlib.sha256(raw).hexdigest() if raw else None,
                  'byte_identical':bool(raw and hashlib.sha256(raw).hexdigest()==expected['atlas_128k_sha256'])}
    for s in expected['strings']:
        payload=s.encode('utf8'); positions=[];start=0
        while 1:
            i=ram.find(payload,start)
            if i<0 or len(positions)>=25:break
            positions.append(f'0x{BASE+i:08X}');start=i+1
        out['strings'].append({'korean':s,'found_in_ram':bool(positions),'addresses':positions})
    # Sample bytes of important source-English strings, too; these are not proof of rendering.
    for s in ['Ambush at Exit 4','You got the German K98 Rifle.','Mac: Keep moving Leggett!']:
        payload=s.encode('ascii');hits=[];start=0
        while 1:
            i=ram.find(payload,start)
            if i<0 or len(hits)>=15:break
            hits.append(f'0x{BASE+i:08X}');start=i+1
        out.setdefault('english_strings',[]).append({'english':s,'addresses':hits})
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--port',type=int,required=True)
    ap.add_argument('--outdir',required=True)
    ap.add_argument('--expected',required=True)
    ap.add_argument('--expected-pid',type=int,required=True)
    a=ap.parse_args()
    out=Path(a.outdir);out.mkdir(exist_ok=True,parents=True)
    ex=json.loads(Path(a.expected).read_text(encoding='utf-8-sig'))
    ws=None
    report={'step':'STEP_083_FIX1','status':'IN_PROGRESS','read_only':True,'iso_modified':False,
            'target_screen':'second mission text rendered as repeated >',
            'source':'live PPSSPP RAM at manually selected mission2 broken display',
            'verified_local_listener_pid_by_launcher':a.expected_pid,
            'visual_result':'not inferred from bytes; screenshot evidence reviewed separately'}
    try:
        ws=kg.WS(a.port)
        report['ppsspp_version']=ws.request('version',10,name='bia-step083-readonly',version='1.0')
        game=ws.request('game.status',10)
        report['game_status']=game
        if game.get('game',{}).get('id')!='ULUS10193':
            raise RuntimeError(f'Wrong game. Refusing memory access: {game}')
        status=ws.request('cpu.status',10)
        report['cpu_status_before_snapshot']=status
        # Freeze only our proven dedicated debugger process while collecting
        # a coherent snapshot; restore original running/paused state.
        was_stepping=bool(status.get('stepping'))
        did_pause=False
        try:
            if not was_stepping:
                kg.pause(ws)
                did_pause=True
            print('PPSSPP paused at requested broken frame. Reading 32 MiB RAM...',flush=True)
            blocks=[]
            for idx in range(0,RAM_SIZE,0x100000):
                block=kg.memread(ws,BASE+idx,0x100000)
                blocks.append(block)
                if idx%(0x400000)==0:print(f'RAM {idx//1048576}/32 MiB',flush=True)
            ram=b''.join(blocks)
            if len(ram)!=RAM_SIZE:raise RuntimeError(f'RAM dump truncated: {len(ram)} bytes')
            # Persist complete RAM before VRAM reads, so a VRAM failure does not lose it.
            (out/'live_psp_ram_32MiB.zlib').write_bytes(zlib.compress(ram,6))
            report['ram_uncompressed_bytes']=len(ram)
            report['ram_sha256']=hashlib.sha256(ram).hexdigest()
            report['ram_compressed_file']='live_psp_ram_32MiB.zlib'
            frames=[]
            for bi,addr in enumerate(kg.VRAMS):
                raw=kg.memread(ws,addr,kg.VRAM_SIZE)
                fn=f'live_vram{bi}_rgb565_preview.png'
                kg.savepng(out/fn,kg.rgb565(raw))
                frames.append({'buffer':bi,'address':hex(addr),'png':fn,'sha256':hashlib.sha256(raw).hexdigest()})
            report['vram_captures']=frames
        finally:
            # Resume even when RAM/VRAM probing raises; preserve pre-existing pause.
            if did_pause or (not was_stepping):
                try:kg.resume(ws)
                except Exception as resume_exc:report['resume_error']=str(resume_exc)
        report['font_probe']=probe_memory(ram,ex)
        report['runtime_font_records_fully_loaded']=sum(x.get('glyph_count')==878 for x in report['font_probe']['fonts'])
        report['runtime_atlas_matches_stage79']=report['font_probe']['atlas']['byte_identical']
        report['result_interpretation']='Live readback collected, NOT proof of correct Korean glyph rendering'
        report['diagnostic_next_step']='Compare runtime page pointers, glyph records and atlas to exact STEP082 static source; screenshot remains visual QA evidence.'
        report['status']='VERIFIED_LIVE_SNAPSHOT_COLLECTED'
        print('[SNAPSHOT] Stored coherent 32MiB RAM and per-font table/glyph/pixel checks',flush=True)
    except Exception as e:
        report['status']='FAILED'
        report['exception']=str(e)
        report['traceback']=traceback.format_exc()
        raise
    finally:
        if ws:
            try:ws.close()
            except Exception:pass
        report['completed_at']=datetime.datetime.now().astimezone().isoformat(timespec='seconds')
        dump_json(out/'step083_live_font_report.json',report)

if __name__=='__main__':main()
