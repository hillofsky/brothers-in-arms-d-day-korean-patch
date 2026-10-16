#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BIA STEP 084: evidence-only, offline forensics on verified STEP083 FIX1 RAM.
Never writes game ISO, interacts with PPSSPP, or claims visual text verification.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import zipfile
import zlib

BASE = 0x08000000
LIMIT = 0x0A000000
RAM_SIZE = LIMIT - BASE
EXPECTED_RAM_SHA = '3644544b0b5e633240bcfc3af677639e2ae55e2c96191190fcf79933090dbbfa'
EXPECTED_INPUT_SHA = '0398fced4d6d2923edda750f47924cfcc37652045d511daf890ccaf468c98e18'
EXPECTED_ISO_SHA = 'ca320d514c32d34767e7255ea3079f7449783cdb2b98ec49797a87bdd69544d9'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def find_refs(ram, addr, limit=24):
    pat = struct.pack('<I', addr)
    hits = []
    idx = 0
    total = 0
    while True:
        idx = ram.find(pat, idx)
        if idx < 0:
            break
        total += 1
        if len(hits) < limit:
            hits.append('0x%08X' % (BASE + idx))
        idx += 1
    return {'total': total, 'first_addresses': hits}


def get_member(z, name):
    candidates = {p.filename.replace('\\', '/'): p for p in z.infolist()}
    if name not in candidates:
        raise ValueError('Required file missing: ' + name)
    obj = candidates[name]
    if obj.file_size > 34 * 1024 * 1024:
        raise ValueError('Zip member unusually large: ' + name)
    return z.read(obj)


def analyze(input_zip, expected_path, output_dir):
    output_dir.mkdir(parents=True, exist_ok=True)
    inp_sha = sha(input_zip.read_bytes())
    if inp_sha != EXPECTED_INPUT_SHA:
        raise ValueError('STEP083 FIX1 input ZIP SHA-256 mismatch: ' + inp_sha)
    ex = json.loads(expected_path.read_text(encoding='utf-8-sig'))
    with zipfile.ZipFile(input_zip) as z:
        snap = json.loads(get_member(z, 'outputs/step083_live_font_report.json').decode('utf-8-sig'))
        identity = json.loads(get_member(z, 'outputs/postflight_identity.json').decode('utf-8-sig'))
        raw = get_member(z, 'outputs/live_psp_ram_32MiB.zlib')
        # Limit decompression size; never trust a compressed archive blindly.
        dec = zlib.decompressobj()
        ram = dec.decompress(raw, RAM_SIZE + 1)
        if len(ram) > RAM_SIZE or dec.unconsumed_tail:
            raise ValueError('RAM exceeded expected 32 MiB')
        ram += dec.flush()
        if len(ram) != RAM_SIZE or not dec.eof:
            raise ValueError('RAM length/integrity invalid: %d' % len(ram))
        image_files = []
        for i in (0, 1):
            name = 'outputs/live_vram%d_rgb565_preview.png' % i
            p = output_dir / ('live_vram%d_preview.png' % i)
            p.write_bytes(get_member(z, name))
            image_files.append(p.name)
    if sha(ram) != EXPECTED_RAM_SHA or snap.get('ram_sha256') != EXPECTED_RAM_SHA:
        raise ValueError('RAM SHA-256 mismatch')
    if not identity.get('unchanged') or identity.get('postflight_iso_sha256', '').lower() != EXPECTED_ISO_SHA:
        raise ValueError('ISO preservation not proven by STEP083 FIX1')
    if snap.get('status') != 'VERIFIED_LIVE_SNAPSHOT_COLLECTED':
        raise ValueError('STEP083 FIX1 report was not a complete snapshot')

    def block(addr, n):
        if addr < BASE or n < 0 or addr + n > LIMIT:
            return None
        return ram[addr-BASE:addr-BASE+n]

    def u16(addr):
        x = block(addr, 2)
        return struct.unpack('<H', x)[0] if x is not None else None

    def u32(addr):
        x = block(addr, 4)
        return struct.unpack('<I', x)[0] if x is not None else None

    phrases = ex['strings']
    all_chars = sorted(set(''.join(phrases)))
    font_results = []
    all_correct = True
    for f in ex['font_objects']:
        addr = int(f['runtime'], 16)
        obj = block(addr, 0x490)
        if obj is None:
            raise ValueError('Font object out of RAM')
        obj_sha = sha(obj)
        count = u16(addr+0x50)
        glyphs = u32(addr+0x54)
        widths = u32(addr+0x474)
        heights = u32(addr+0x478)
        textures = u32(addr+0x488)
        matches = []
        misses = []
        for ch in all_chars:
            cp = ord(ch)
            pag = u32(addr+0x58+(cp>>8)*4)
            idx = u16(pag+((cp&255)*2)) if pag else None
            actual = u16(glyphs+idx*24) if idx is not None and idx < count else None
            entry = {'char':ch, 'unicode':'U+%04X' % cp,'index':idx, 'record_unicode': ('U+%04X' % actual if actual is not None else None)}
            (matches if actual==cp else misses).append(entry)
        valid = (obj_sha==f['sha256'] and count==878 and not misses)
        all_correct = all_correct and valid
        font_results.append({
            'runtime': f['runtime'], 'object_sha256':obj_sha, 'matches_static':obj_sha==f['sha256'],
            'glyph_count':count, 'glyph_array':'0x%08X' % (glyphs or 0),
            'chars_tested':len(all_chars), 'all_expected_characters_map_correctly':len(misses)==0,
            'matches':matches,'misses':misses,
            'renderer_page_arrays': {
                'widths': [u16(widths+i*2) for i in range(4)] if widths else [],
                'heights': [u16(heights+i*2) for i in range(4)] if heights else [],
                'textures': ['0x%08X' % (u32(textures+i*4) or 0) for i in range(4)] if textures else [],
            },
            'references_to_font_object': find_refs(ram,addr)
        })
    atlas_addr = int(ex['atlas_runtime_base'],16)
    atlas_data = block(atlas_addr,0x20000)
    atlas_ok = bool(atlas_data and sha(atlas_data)==ex['atlas_128k_sha256'])
    all_correct = all_correct and atlas_ok
    text_items=[]
    for phrase in phrases:
        pat=phrase.encode('utf-8')
        starts=[];j=0
        while True:
            j=ram.find(pat,j)
            if j<0:break
            addr=BASE+j
            starts.append({'address':'0x%08X' % addr,'pointer_references':find_refs(ram,addr)})
            j+=1
        text_items.append({'phrase':phrase,'utf8_occurrences':starts})
    targettex = int(font_results[0]['renderer_page_arrays']['textures'][0],16)
    texinfo = {'target_address':'0x%08X' % targettex,
               'references': find_refs(ram,targettex),
               'first_64_bytes_sha256':sha(block(targettex,64) or b''),
               'first_64_bytes_present':block(targettex,64) is not None}
    report={
        'step':'STEP_084','status':'VERIFIED_OFFLINE_MEMORY_CONSISTENCY' if all_correct else 'OFFLINE_STRUCTURAL_MISMATCH',
        'isolation': 'No emulator launched or controlled. No ISO or SAVEDATA files modified.',
        'input_zip':input_zip.name,'input_zip_sha256':inp_sha,'ram_sha256':sha(ram),
        'source_iso_sha256_at_STEP083': identity.get('postflight_iso_sha256'),
        'scene_caveat': 'The supplied VRAM0 PNG shows two soldiers but NO visible broken Korean or repeated > text (human inspection). No automatic image-to-text proof.',
        'runtime_korean_render_verified':False, 'mission2_gt_fallback_unresolved':True,
        'font_objects':font_results,
        'font_atlas':{'expected_base':ex['atlas_runtime_base'],'matches_expected_bytes':atlas_ok,'sha256':sha(atlas_data or b'')},
        'korean_strings':text_items,'texture_object':texinfo,
        'frame_previews':image_files,
        'next_required_evidence':'Capture the ACTUAL visible > text at the same time as its font consumer/call path; or collect trace/log from the active draw call. RAM tables alone do not prove draw-time selection.',
    }
    (output_dir/'step084_offline_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=[
        '# BIA STEP 084 — offline review of STEP 083 FIX1',
        '',
        f"- Status: **{report['status']}** (table/data consistency ONLY)",
        '- ISO/SAVEDATA changes: **NONE**; PPSSPP not launched.',
        f"- RAM: exact 32MiB, SHA-256 `{report['ram_sha256']}`.",
        f"- 2 font objects: {', '.join(str(x['glyph_count'])+' glyphs' for x in font_results)}.",
        f"- Unique characters across 3 Korean sample sentences: **{len(all_chars)}**, exact matches on both fonts: **{len(font_results)==2 and all(not x['misses'] for x in font_results)}**.",
        f"- Font atlas byte identity: **{atlas_ok}**.",
        '- The STEP083 FIX1 RAM dump is real, but VRAM0 was captured while two soldiers were on screen and no broken text was displayed.',
        '- **The glyph fallback defect is UNRESOLVED**. Loaded font != selected font at draw time.',
        '- Next: collect a confirmed broken-glyph frame and identify active string/font consumers, without changing Stage69/Stage79 ISO.',
        '', '## Pointer evidence (addresses are only candidates, not code-flow proof)',
    ]
    for font in font_results:
        refs=font['references_to_font_object']
        lines.append(f"- Font `{font['runtime']}`: {refs['total']} pointer references ({', '.join(refs['first_addresses'])}).")
    for item in text_items:
        lines.append(f"- `{item['phrase']}`: " + (', '.join(x['address'] for x in item['utf8_occurrences']) or 'not in RAM'))
    lines.extend(['', '## QA flags','- STEP079 compiled967: BUILT_UNVERIFIED','- STEP082 mission2 visually BROKEN; no repair applied','- INT92: BUILT_UNVERIFIED','- Six deferred movie playback tests: NOT RESUMED','- Popup `New Objective` English: NOT FIXED'])
    (output_dir/'STEP_084_DIAGNOSTICS.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('STEP084 result:',report['status'])
    print('Unique Korean chars:',len(all_chars),'matched both fonts:',all_correct)
    print('Screens: VRAM0 displays two soldiers/no visible text; visual render status UNVERIFIED')
    return report['status']=='VERIFIED_OFFLINE_MEMORY_CONSISTENCY'


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--input',required=True,type=Path)
    p.add_argument('--expected',required=True,type=Path)
    p.add_argument('--outdir',required=True,type=Path)
    a=p.parse_args()
    if not analyze(a.input,a.expected,a.outdir):
        raise SystemExit(2)

if __name__=='__main__':main()
