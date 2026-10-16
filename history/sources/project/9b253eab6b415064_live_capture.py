#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""STEP085 hotkey-confirmed-frame, read-only capture via isolated PPSSPP WebSocket."""
import argparse
import datetime
import hashlib
import json
import struct
import traceback
import zlib
from pathlib import Path
import stage071_known_good as kg

BASE = 0x08000000
LIMIT = 0x0A000000
RAM_SIZE = LIMIT - BASE

def sha(data):
    return hashlib.sha256(data).hexdigest()

def save_json(p, value):
    Path(p).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')

def pointer_refs(data, p, max_results=32):
    encoded = struct.pack('<I', p)
    start, total, addresses = 0, 0, []
    while True:
        hit = data.find(encoded, start)
        if hit < 0:
            break
        total += 1
        if len(addresses) < max_results:
            addresses.append('0x%08X' % (BASE + hit))
        start = hit + 1
    return {'total': total, 'first_addresses': addresses}

def analyze(ram, expected):
    assert len(ram) == RAM_SIZE
    def get(addr, n):
        if not BASE <= addr or not 0 <= n or addr + n > LIMIT:
            return None
        return ram[addr-BASE:addr-BASE+n]
    def u16(addr):
        raw = get(addr, 2)
        return struct.unpack('<H', raw)[0] if raw is not None else None
    def u32(addr):
        raw = get(addr, 4)
        return struct.unpack('<I', raw)[0] if raw is not None else None
    font_info = []
    chars = sorted(set(''.join(expected['strings'])))
    for ft in expected['font_objects']:
        addr = int(ft['runtime'],16)
        obj = get(addr,0x490)
        if obj is None:
            font_info.append({'address':ft['runtime'], 'error':'font object not in RAM'});continue
        gp = u32(addr+0x54)
        count = u16(addr+0x50)
        matches, missing = [], []
        for c in chars:
            cp = ord(c)
            page = u32(addr+0x58+(cp>>8)*4)
            index = u16(page+2*(cp & 0xff)) if page else None
            recorded = u16(gp+24*index) if gp and index is not None and index < 4096 else None
            record = {'character': c, 'unicode':'U+%04X'%cp, 'glyph_index':index,
                      'record_unicode':('U+%04X'%recorded if recorded is not None else None),
                      'match':recorded==cp}
            (matches if record['match'] else missing).append(record)
        wa,ha,ta = u32(addr+0x474),u32(addr+0x478),u32(addr+0x488)
        font_info.append({'address':ft['runtime'], 'object_sha256':sha(obj),
            'static_object_match':sha(obj)==ft['sha256'], 'glyph_count':count,
            'glyph_array':('0x%08X'%gp if gp else None),
            'all_sample_characters_match':len(missing)==0,
            'tested_characters':len(chars), 'matched':matches, 'missing':missing,
            'widths':[u16(wa+2*i) for i in range(4)] if wa else [],
            'heights':[u16(ha+2*i) for i in range(4)] if ha else [],
            'textures':[('0x%08X'%u32(ta+4*i) if u32(ta+4*i) else None) for i in range(4)] if ta else [],
            'object_pointer_refs':pointer_refs(ram,addr)})
    strings = []
    for phrase in expected['strings']:
        needle = phrase.encode('utf-8')
        found, idx = [], 0
        while len(found)<30:
            k=ram.find(needle,idx)
            if k<0: break
            addr=BASE+k
            found.append({'address':'0x%08X'%addr,'pointer_refs':pointer_refs(ram,addr)})
            idx=k+1
        strings.append({'phrase':phrase,'matches':found})
    atlas_base=int(expected['atlas_runtime_base'],16)
    atlas=get(atlas_base,0x20000)
    return {'fonts':font_info,'korean_strings':strings,
      'atlas':{'address':expected['atlas_runtime_base'], 'sha256':sha(atlas) if atlas is not None else None,
               'matches_static':bool(atlas is not None and sha(atlas)==expected['atlas_128k_sha256'])},
      'caveat':'Loaded font pages and RAM string matches do NOT establish draw-time font selection.'}

def capture(ws, out, report, ex):
    status=ws.request('cpu.status',10)
    report['cpu_status_before']=status
    was_stepping=bool(status.get('stepping'))
    did_pause=False
    try:
        if not was_stepping:
            kg.pause(ws)
            did_pause=True
        report['cpu_status_during']=ws.request('cpu.status',10)
        # Capture output buffers IMMEDIATELY after pausing: prior snapshot caught wrong scene.
        frames=[]
        for i, addr in enumerate(kg.VRAMS):
            buf=kg.memread(ws,addr,kg.VRAM_SIZE)
            name='hotkey_vram%d_rgb565.png'%i
            kg.savepng(out/name,kg.rgb565(buf))
            frames.append({'buffer':i,'address':'0x%08X'%addr,'file':name,'raw_sha256':sha(buf)})
        report['frames']=frames
        print('VRAM screenshots captured; dumping RAM (32 MiB) now...',flush=True)
        blocks=[]
        for i in range(0,RAM_SIZE,0x100000):
            blocks.append(kg.memread(ws,BASE+i,0x100000))
            if i%0x400000==0:
                print('RAM %d/32 MiB'%(i//0x100000),flush=True)
        ram=b''.join(blocks)
        if len(ram)!=RAM_SIZE:
            raise RuntimeError('Memory size mismatch: %d'%len(ram))
        (out/'hotkey_ram_32MiB.zlib').write_bytes(zlib.compress(ram,6))
        report['ram_size']=len(ram)
        report['ram_sha256']=sha(ram)
        report['memory_analysis']=analyze(ram,ex)
    finally:
        if did_pause:
            try: kg.resume(ws)
            except Exception as e: report['resume_warning']=repr(e)

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--port',type=int,required=True)
    p.add_argument('--output',required=True)
    p.add_argument('--expected',required=True)
    p.add_argument('--listener-pid',type=int,required=True)
    args=p.parse_args()
    out=Path(args.output)
    out.mkdir(parents=True,exist_ok=True)
    ex=json.loads(Path(args.expected).read_text(encoding='utf-8-sig'))
    report={'step':'STEP_085','status':'RUNNING','type':'hotkey_scene_capture',
      'read_only':True, 'iso_modified':False, 'requested_scene':'Mission 2 visible > fallback',
      'pid_prechecked_by_launcher':args.listener_pid,
      'visual_result':'UNREVIEWED - operator pressed hotkey; verify PNG before diagnosing rendering',
      'rendering_fix_verified':False}
    ws=None
    try:
        ws=kg.WS(args.port)
        report['ppsspp_version']=ws.request('version',10,name='bia-step085-readonly',version='1.0')
        game=ws.request('game.status',10)
        report['game_status']=game
        if game.get('game',{}).get('id')!='ULUS10193':
            raise RuntimeError('Wrong game ID; abort capture before memory: '+repr(game))
        capture(ws,out,report,ex)
        report['status']='CAPTURE_COLLECTED_VISUAL_UNVERIFIED'
        print('Evidence saved. Mission2 > is NOT auto-verified; inspect host_window_at_hotkey.png.',flush=True)
    except Exception as e:
        report['status']='FAILED'
        report['exception']=repr(e)
        report['traceback']=traceback.format_exc()
        raise
    finally:
        if ws:
            try: ws.close()
            except Exception: pass
        report['completed_at']=datetime.datetime.now().astimezone().isoformat(timespec='seconds')
        save_json(out/'step085_capture_report.json',report)

if __name__=='__main__':
    main()
