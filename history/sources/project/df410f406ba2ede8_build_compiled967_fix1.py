#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import importlib.util
import json
import math
import re
import shutil
import struct
import sys
from collections import Counter, defaultdict
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(r"PROJECT_ROOT")
ORIGINAL_ISO = ROOT / "Brothers in Arms - D-Day (USA) (v1.01).iso"
SOURCE_ISO = ROOT / "BIA_STAGE69_FIX2_NONMDI_INT92_TEST.iso"
OUTPUT_ISO = ROOT / "BIA_STAGE74_FIX1_COMPILED967_BULK_TEST.iso"

PARTS = ["PSP_GAME", "USRDIR", "SYSTEM"]

CAMPAIGN_BASE = 0x08E03020
MENU_BASE = 0x08E2D020
STRIDE = 0x78000

BASE_FONT_COUNT = 847
FIRST_KO_GLYPH = 151
PAGE_START_OLD = 0x5000
PAGE_SHIFT = 0x300
PAGE_START_NEW = PAGE_START_OLD + PAGE_SHIFT
AUX_OLD = 0xA800
AUX_NEW = AUX_OLD + PAGE_SHIFT
BASE_META_END = 0xA860
EXT_META_END = 0xAB30
EXTRA_PAGE_START = 0xAC00
PAYLOAD_START = 0x10000

KNOWN_FIRST_FONT_OFFSETS = [(30, 0x7F64), (30, 0xA0FC)]
KNOWN_FIRST_TEXTURE_OBJECT = 0x09A8D6D0

DSL_SIG_A = 0x40055140
DSL_SIG_B = 0x80
DSL_B8_OLD = 0xB8000807
DSL_B8_NEW = 0xB8000909

def read_tsv(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))

def write_tsv(path: Path, fields, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(
            f, fieldnames=fields, delimiter="\t",
            lineterminator="\n", extrasaction="ignore"
        )
        w.writeheader()
        w.writerows(rows)

def sha256_file(path: Path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def sha256_bytes(data: bytes):
    return hashlib.sha256(data).hexdigest()

def align4(n):
    return (n + 3) & ~3

def load_helper():
    helper = ROOT / "bia_stage40i_tools" / "bia_stage40i_actual_resource_trace.py"
    if not helper.exists():
        raise RuntimeError(f"Missing helper: {helper}")
    spec = importlib.util.spec_from_file_location("bia_stage40i", helper)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    _, b = mod.load_helpers()
    return b

def parse_mdi_dict(b, blob: bytes):
    return {x["index"]: bytes(x["decoded"]) for x in b.parse_mdi(blob)}

def ptrloc(ptr: int, streams: dict[int, bytes], base=CAMPAIGN_BASE):
    if ptr < base:
        return None
    rel = ptr - base
    si = rel // STRIDE
    off = rel % STRIDE
    if si not in streams or off >= len(streams[si]):
        return None
    return int(si), int(off)

def read_c_string_at_ptr(ptr: int, n: int, streams: dict[int, bytes], base=CAMPAIGN_BASE):
    loc = ptrloc(ptr, streams, base)
    if loc is None:
        return None
    si, off = loc
    raw = streams[si][off:off+n]
    if len(raw) != n or not raw.endswith(b"\0"):
        return None
    return raw[:-1]

def read_fstring(streams: dict[int, bytes], si: int, off: int, base=CAMPAIGN_BASE):
    if si not in streams or off < 0 or off + 12 > len(streams[si]):
        return None
    ptr, n, cap = struct.unpack_from("<III", streams[si], off)
    if not (1 <= n <= cap <= 0x100000):
        return None
    raw = read_c_string_at_ptr(ptr, n, streams, base)
    if raw is None:
        return None
    text = None
    for enc in ("utf-8", "cp1252"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            pass
    return {
        "ptr": ptr, "n": n, "cap": cap, "raw": raw,
        "text": text,
    }

def resolve_ptr_bytes(streams, ptr, length, base=CAMPAIGN_BASE):
    loc = ptrloc(ptr, streams, base)
    if loc is None:
        return None
    si, off = loc
    if off + length > len(streams[si]):
        return None
    return streams[si][off:off+length]

def font_ascii_score(streams, si, off, base=CAMPAIGN_BASE):
    d = streams.get(si)
    if d is None or off < 0 or off + 0x490 > len(d):
        return -1, None
    count = struct.unpack_from("<H", d, off + 0x50)[0]
    if count < 1 or count > 4096:
        return -1, None
    glyph_ptr = struct.unpack_from("<I", d, off + 0x54)[0]
    gloc = ptrloc(glyph_ptr, streams, base)
    if gloc is None:
        return -1, None
    gs, go = gloc

    page0 = struct.unpack_from("<I", d, off + 0x58)[0]
    ploc = ptrloc(page0, streams, base)
    if ploc is None:
        return -1, None
    ps, po = ploc

    sample = [32] + list(range(48, 58)) + list(range(65, 91)) + list(range(97, 123))
    good = 0
    details = []
    for cp in sample:
        ep = po + cp * 2
        if ep + 2 > len(streams[ps]):
            continue
        gi = struct.unpack_from("<H", streams[ps], ep)[0]
        if gi >= count:
            continue
        ro = go + gi * 24
        if ro + 2 > len(streams[gs]):
            continue
        rcp = struct.unpack_from("<H", streams[gs], ro)[0]
        if rcp == cp:
            good += 1
        details.append((cp, gi, rcp))
    return good, {
        "count": count,
        "glyph_ptr": glyph_ptr,
        "glyph_stream": gs,
        "glyph_offset": go,
        "page0_ptr": page0,
    }

def read_u32_array(streams, ptr, count, base=CAMPAIGN_BASE):
    raw = resolve_ptr_bytes(streams, ptr, count * 4, base)
    if raw is None:
        return None
    return list(struct.unpack("<" + "I" * count, raw))

def normalize_font_object(obj: bytes, base=CAMPAIGN_BASE, stream_count=64):
    x = bytearray(obj)
    # Page pointer table and direct metadata pointers differ by MDI.
    x[0x54:0x458] = b"\0" * (0x458 - 0x54)
    for off in (0x474, 0x478, 0x488):
        x[off:off+4] = b"\0\0\0\0"
    # Also clear any remaining obvious MDI runtime pointers.
    hi = base + stream_count * STRIDE
    for off in range(0, len(x) - 3, 4):
        v = struct.unpack_from("<I", x, off)[0]
        if base <= v < hi:
            struct.pack_into("<I", x, off, 0)
    return bytes(x)

def similarity(a: bytes, b: bytes):
    if len(a) != len(b):
        return 0.0
    return sum(x == y for x, y in zip(a, b)) / len(a)

def candidate_info(streams, si, off, templates, known_metric_signatures, base=CAMPAIGN_BASE):
    d = streams.get(si)
    if d is None or off < 0 or off + 0x490 > len(d):
        return None
    count = struct.unpack_from("<H", d, off + 0x50)[0]
    if count != 151:
        return None

    ascii_score, ai = font_ascii_score(streams, si, off, base)
    if ascii_score < 55:
        return None

    wp = struct.unpack_from("<I", d, off + 0x474)[0]
    hp = struct.unpack_from("<I", d, off + 0x478)[0]
    tp = struct.unpack_from("<I", d, off + 0x488)[0]
    widths = read_u32_array(streams, wp, 4, base)
    heights = read_u32_array(streams, hp, 4, base)
    textures = read_u32_array(streams, tp, 4, base)
    if widths is None or heights is None or textures is None:
        return None

    metric_sig = (tuple(widths), tuple(heights))
    if known_metric_signatures and metric_sig not in known_metric_signatures:
        return None

    obj = bytes(d[off:off+0x490])
    norm = normalize_font_object(obj, base, len(streams))
    sims = [similarity(norm, t) for t in templates]
    best = max(sims) if sims else 0.0

    # Production font uses one texture object for its four pages.
    if len(set(textures)) != 1:
        return None
    tex = textures[0]
    if ptrloc(tex, streams, base) is None:
        return None

    return {
        "stream": si,
        "offset": off,
        "ascii_score": ascii_score,
        "similarities": sims,
        "best_similarity": best,
        "widths": widths,
        "heights": heights,
        "textures": textures,
        "texture_object": tex,
        "glyph_ptr": ai["glyph_ptr"],
    }

def scan_font_candidates(streams, templates, known_metric_signatures, base=CAMPAIGN_BASE):
    out = []
    needle = struct.pack("<H", 151)
    for si, d in streams.items():
        start = 0
        while True:
            pos = d.find(needle, start)
            if pos < 0:
                break
            start = pos + 1
            off = pos - 0x50
            if off < 0 or off % 4:
                continue
            c = candidate_info(
                streams, si, off, templates, known_metric_signatures, base
            )
            if c is not None:
                out.append(c)
    return out

def choose_font_pair(cands):
    # The proven first-mission path patches two instances of the same text font.
    # Pick one candidate best matching each first-mission template, but require
    # both to use the same underlying texture object.
    best = None
    for i, a in enumerate(cands):
        for j, b in enumerate(cands):
            if i == j:
                continue
            if a["texture_object"] != b["texture_object"]:
                continue
            if len(a["similarities"]) < 2 or len(b["similarities"]) < 2:
                continue
            for swapped in (False, True):
                s0 = a["similarities"][1 if swapped else 0]
                s1 = b["similarities"][0 if swapped else 1]
                score = s0 + s1
                item = (score, min(s0, s1), a, b, swapped)
                if best is None or item[0] > best[0]:
                    best = item
    if best is None:
        return None
    score, minscore, a, b, swapped = best
    if minscore < 0.90:
        return None
    return [a, b], {
        "pair_score": score,
        "min_template_similarity": minscore,
        "swapped": swapped,
    }

def font_lookup(streams, si, off, cp, base=CAMPAIGN_BASE):
    d = streams[si]
    count = struct.unpack_from("<H", d, off+0x50)[0]
    gptr = struct.unpack_from("<I", d, off+0x54)[0]
    gloc = ptrloc(gptr, streams, base)
    if gloc is None:
        return None
    gs, go = gloc
    pptr = struct.unpack_from("<I", d, off+0x58+(cp>>8)*4)[0]
    ploc = ptrloc(pptr, streams, base)
    if ploc is None:
        return None
    ps, po = ploc
    eo = po + (cp & 255) * 2
    if eo+2 > len(streams[ps]):
        return None
    gi = struct.unpack_from("<H", streams[ps], eo)[0]
    if gi >= count:
        return None
    ro = go + gi*24
    if ro+2 > len(streams[gs]):
        return None
    rcp = struct.unpack_from("<H", streams[gs], ro)[0]
    if rcp != cp:
        return None
    return gi

def decode_t4(atlas: bytes):
    if len(atlas) != 0x20000:
        raise RuntimeError(f"Unexpected atlas size: {len(atlas):#x}")
    pixels = bytearray(512*512)
    for y in range(512):
        for x in range(512):
            bx = x // 2
            off = (y//8)*2048 + (bx//16)*128 + (y%8)*16 + bx%16
            pixels[y*512+x] = ((atlas[off] >> (4*(x%2))) & 15) * 17
    return pixels

def encode_t4_from_image(base_atlas: bytes, image: Image.Image, changed_cells):
    pixels = image.tobytes()
    out = bytearray(base_atlas)
    for x0, y0 in changed_cells:
        for y in range(y0, y0+16):
            for x in range(x0, x0+17):
                bx = x // 2
                off = (y//8)*2048 + (bx//16)*128 + (y%8)*16 + bx%16
                shift = 4*(x%2)
                v = min(15, (pixels[y*512+x] + 8)//17)
                out[off] = (out[off] & ~(15 << shift)) | (v << shift)
    return bytes(out)

def build_font_assets(menu_streams, plan, additional_chars, texture_object):
    atlas_path = ROOT / "bia_stage39a_tools" / "stage39a_tmr18_512x512_swizzled.bin"
    if not atlas_path.exists():
        raise RuntimeError(f"Missing Stage39A atlas: {atlas_path}")
    base_atlas = atlas_path.read_bytes()
    if len(base_atlas) != 0x20000:
        raise RuntimeError("Stage39A atlas size mismatch")

    menu_meta = menu_streams[23]
    if len(menu_meta) < BASE_META_END:
        raise RuntimeError("Menu font metadata too small")
    base_meta = bytes(menu_meta[:BASE_META_END])

    # Historical proven menu font template.
    menu_font = menu_streams[19][0xE83C:0xE83C+0x490]
    if len(menu_font) != 0x490:
        raise RuntimeError("Menu font template unavailable")
    old_meta = struct.unpack_from("<I", menu_font, 0x54)[0]

    occupied = {(x["atlas_x"], x["atlas_y"]) for x in plan["layout"]}
    slots = [
        (page*128 + col*17, y)
        for page in range(4)
        for y in range(0,496,16)
        for col in range(7)
        if not (page == 0 and y < 256)
    ]
    free = [p for p in slots if p not in occupied]
    if len(additional_chars) > len(free):
        raise RuntimeError("Insufficient Stage43A free glyph cells")

    pixels = decode_t4(base_atlas)
    image = Image.frombytes("L", (512,512), bytes(pixels))
    draw = ImageDraw.Draw(image)
    font_path = Path(r"LOCAL_PATH")
    if not font_path.exists():
        raise RuntimeError(f"Missing Windows font used by proven Stage43A path: {font_path}")
    font = ImageFont.truetype(str(font_path), 16)

    newlayout = []
    changed_cells = []
    for idx, (ch, (x,y)) in enumerate(zip(additional_chars, free)):
        bbox = font.getbbox(ch)
        w = bbox[2]-bbox[0]
        h = bbox[3]-bbox[1]
        if w > 17 or h > 16:
            raise RuntimeError(f"Glyph does not fit 17x16 cell: {ch!r} bbox={bbox}")
        draw.rectangle((x,y,x+16,y+15), fill=0)
        draw.text(
            (x-bbox[0]+(17-w)//2, y-bbox[1]+(16-h)//2),
            ch, font=font, fill=255
        )
        newlayout.append({
            "char": ch,
            "codepoint": ord(ch),
            "glyph_index": BASE_FONT_COUNT + idx,
            "atlas_x": x,
            "atlas_y": y,
        })
        changed_cells.append((x,y))

    atlas = encode_t4_from_image(base_atlas, image, changed_cells)

    # Expand metadata exactly in the Stage43A style:
    # reserve +0x300 before the 44 Hangul pages, move aux block by +0x300.
    meta = bytearray(max(EXT_META_END, EXTRA_PAGE_START))
    meta[:BASE_FONT_COUNT*24] = base_meta[:BASE_FONT_COUNT*24]
    for hb in range(0xAC, 0xD8):
        old = PAGE_START_OLD + (hb-0xAC)*512
        new = PAGE_START_NEW + (hb-0xAC)*512
        meta[new:new+512] = base_meta[old:old+512]
    meta[AUX_NEW:AUX_NEW+0x30] = base_meta[AUX_OLD:AUX_OLD+0x30]

    template = base_meta[151*24:152*24]
    if len(template) != 24:
        raise RuntimeError("Glyph template missing")

    page_map = {hb: PAGE_START_NEW + (hb-0xAC)*512 for hb in range(0xAC,0xD8)}
    extra_hbs = sorted({ord(x["char"]) >> 8 for x in newlayout if not (0xAC <= (ord(x["char"])>>8) <= 0xD7)})
    cursor = EXTRA_PAGE_START
    for hb in extra_hbs:
        page_map[hb] = cursor
        need = cursor + 512
        if len(meta) < need:
            meta.extend(b"\xFF" * (need-len(meta)))
        else:
            meta[cursor:cursor+512] = b"\xFF"*512
        cursor += 512

    # Copy base metadata missing-value behavior into extra pages: 0xFFFF.
    for item in newlayout:
        cp = item["codepoint"]
        gi = item["glyph_index"]
        x = item["atlas_x"]
        y = item["atlas_y"]
        rec = bytearray(template)
        struct.pack_into("<H", rec, 0, cp)
        for roff, val in [
            (8, (x+.5)/128),
            (12, (y+.5)/256),
            (16, (x+17.5)/128),
            (20, (y+16.5)/256),
        ]:
            struct.pack_into("<f", rec, roff, val)
        go = gi*24
        if len(meta) < go+24:
            meta.extend(b"\0"*(go+24-len(meta)))
        meta[go:go+24] = rec

        hb = cp >> 8
        po = page_map[hb] + (cp & 255)*2
        if len(meta) < po+2:
            meta.extend(b"\xFF"*(po+2-len(meta)))
        struct.pack_into("<H", meta, po, gi)

    # Moved aux texture pointer array must point at this MDI's identified
    # original Latin16 texture object, just like Stage40Y.
    if len(meta) < AUX_NEW + 0x30:
        meta.extend(b"\0"*(AUX_NEW+0x30-len(meta)))
    for j in range(4):
        struct.pack_into("<I", meta, AUX_NEW+0x20+j*4, texture_object)

    return {
        "atlas": atlas,
        "meta": bytes(meta),
        "newlayout": newlayout,
        "page_map": page_map,
        "menu_font_template": menu_font,
        "old_menu_metabase": old_meta,
        "count": BASE_FONT_COUNT + len(newlayout),
        "meta_used_end": max(len(meta), cursor),
    }

def patch_font_object(mu, si, off, metabase, assets):
    d = mu[si]
    if struct.unpack_from("<H", d, off+0x50)[0] != 151:
        raise RuntimeError(f"Expected original 151-glyph font at stream {si} + {off:#x}")
    struct.pack_into("<H", d, off+0x50, assets["count"])
    struct.pack_into("<I", d, off+0x54, metabase)

    for hb, rel in assets["page_map"].items():
        struct.pack_into("<I", d, off+0x58+hb*4, metabase+rel)

    tmpl = assets["menu_font_template"]
    oldmeta = assets["old_menu_metabase"]
    for field in (0x474,0x478,0x488):
        ptr = struct.unpack_from("<I", tmpl, field)[0]
        if not (oldmeta <= ptr < oldmeta + BASE_META_END):
            raise RuntimeError(f"Menu font aux pointer outside expected metadata: {field:#x} -> {ptr:#x}")
        rel = ptr-oldmeta
        if AUX_OLD <= rel < AUX_OLD+0x30:
            rel += PAGE_SHIFT
        struct.pack_into("<I", d, off+field, metabase+rel)

def discover_dsl(dsl: bytes):
    sig = struct.pack("<II", DSL_SIG_A, DSL_SIG_B)
    locs = []
    start = 0
    while True:
        p = dsl.find(sig, start)
        if p < 0:
            break
        start = p+1
        if p+12 <= len(dsl):
            locs.append((p, struct.unpack_from("<III", dsl, p)))
    b8sig = struct.pack("<I", DSL_B8_OLD)
    b8s=[]
    start=0
    while True:
        p=dsl.find(b8sig,start)
        if p<0: break
        b8s.append(p)
        start=p+1
    return locs, b8s

def patch_dsl(dsl: bytes, atlasbase: int):
    locs, b8s = discover_dsl(dsl)
    if len(locs) != 1:
        raise RuntimeError(f"Expected exactly one DSL font relocation signature, found {len(locs)}")
    if len(b8s) != 1:
        raise RuntimeError(f"Expected exactly one DSL B8 font command, found {len(b8s)}")
    d = bytearray(dsl)
    p, old = locs[0]
    new = (old[0], 512, (-atlasbase) & 0xFFFFFFFF)
    struct.pack_into("<III", d, p, *new)
    struct.pack_into("<I", d, b8s[0], DSL_B8_NEW)
    return bytes(d), {
        "relocation_offset": hex(p),
        "old": [hex(x) for x in old],
        "new": [hex(x) for x in new],
        "b8_offset": hex(b8s[0]),
    }

def existing_first_mission_font_ok(streams, plan, required_chars):
    found=[]
    for si,off in KNOWN_FIRST_FONT_OFFSETS:
        if si not in streams or off+0x490>len(streams[si]):
            return False, []
        count=struct.unpack_from("<H",streams[si],off+0x50)[0]
        if count < 847:
            return False, []
        missing=[]
        for ch in sorted(required_chars):
            if font_lookup(streams,si,off,ord(ch)) is None:
                missing.append(ch)
        found.append({
            "stream":si,"offset":hex(off),"count":count,
            "missing":"".join(missing),
            "glyph_ptr":hex(struct.unpack_from("<I",streams[si],off+0x54)[0]),
        })
        if missing:
            return False, found
    return True, found

def find_payload_cursor(stream35: bytes):
    # For the already-patched first mission, append after all existing nonzero
    # bytes in stream35. For newly installed fonts, caller uses fixed 0x10000.
    nz = -1
    for i in range(len(stream35)-1, -1, -1):
        if stream35[i] != 0:
            nz=i
            break
    return align4(max(PAYLOAD_START, nz+1))

def build_payloads(mu, refs, cursor):
    cache={}
    rows=[]
    for r in refs:
        ko=r["korean"]
        payload=ko.encode("utf-8")+b"\0"
        if ko not in cache:
            cursor=align4(cursor)
            if cursor+len(payload)>=STRIDE:
                raise RuntimeError(f"stream35 payload overflow at {cursor:#x}: {ko!r}")
            mu[35][cursor:cursor+len(payload)] = payload
            ptr=CAMPAIGN_BASE+35*STRIDE+cursor
            cache[ko]=(ptr,len(payload),cursor)
            cursor += len(payload)

    for r in refs:
        si=int(r["metadata_stream"])
        off=int(r["metadata_offset"],16)
        rec=read_fstring({i:bytes(x) for i,x in mu.items()},si,off)
        # The evidence is against Stage43T/Stage69 English values.
        if rec is None or rec["text"] != r["english"]:
            raise RuntimeError(
                f"{r['mdi']}: FString evidence drift at stream {si}+{off:#x}: "
                f"expected={r['english']!r} got={None if rec is None else rec['text']!r}"
            )
        ptr,n,po=cache[r["korean"]]
        struct.pack_into("<III",mu[si],off,ptr,n,n)
        rows.append({
            "mdi":r["mdi"],
            "metadata_stream":si,
            "metadata_offset":hex(off),
            "resource_ids":r["resource_ids"],
            "english":r["english"],
            "korean":r["korean"],
            "payload_ptr":hex(ptr),
            "payload_offset_stream35":hex(po),
            "payload_bytes":n,
        })
    return rows, cursor, cache

def verify_patched_refs(streams, patch_rows):
    for r in patch_rows:
        si=int(r["metadata_stream"])
        off=int(r["metadata_offset"],16)
        rec=read_fstring(streams,si,off)
        if rec is None or rec["text"] != r["korean"]:
            raise RuntimeError(
                f"{r['mdi']}: patched FString readback failed {si}+{off:#x}"
            )

def prepare_one(b, mdi, refs, demand_row, plan, menu_streams, template_norms, metric_sigs, dry_only=False):
    _, src_blob = b.iso_read_file(SOURCE_ISO, PARTS+[mdi])
    src = parse_mdi_dict(b, src_blob)
    mu = {i:bytearray(v) for i,v in src.items()}

    if 34 not in src or 35 not in src:
        raise RuntimeError(f"{mdi}: streams 34/35 missing")

    required_chars = {c for r in refs for c in r["korean"] if ord(c) > 127}
    additional_chars = list(demand_row["additional_chars"])
    # Keep exact character order deterministic by Unicode code point.
    additional_chars = sorted(set(additional_chars), key=ord)

    discovery={
        "mdi":mdi,
        "required_nonascii":len(required_chars),
        "additional_chars":"".join(additional_chars),
        "additional_count":len(additional_chars),
    }

    is_first = (mdi == "D0_0130_.MDI")
    dsl_patched = None
    dsx_patched = None
    dsl_report = {"mode":"PRESERVED_EXISTING"} if is_first else None
    font_report = {}

    if is_first:
        ok, objs=existing_first_mission_font_ok(src,plan,required_chars)
        if not ok:
            raise RuntimeError(f"{mdi}: existing Stage43A first-mission font does not cover required text: {objs}")
        font_report={
            "mode":"PRESERVE_EXISTING_STAGE43A",
            "objects":objs,
        }
        cursor=find_payload_cursor(src[35])
    else:
        # For untouched missions, streams34/35 must be unused before we adopt
        # the proven Stage40Y layout.
        if any(src[34]) or any(src[35]):
            raise RuntimeError(
                f"{mdi}: source streams34/35 are not empty; refusing to assume safe scratch layout"
            )

        # Discover original production font objects from the original USA ISO,
        # not from heuristic 880-count false positives in STEP066.
        _, orig_blob = b.iso_read_file(ORIGINAL_ISO, PARTS+[mdi])
        orig = parse_mdi_dict(b, orig_blob)

        candidates=scan_font_candidates(orig,template_norms,metric_sigs)
        pair=choose_font_pair(candidates)
        if pair is None:
            top=sorted(candidates,key=lambda x:x["best_similarity"],reverse=True)[:10]
            raise RuntimeError(
                f"{mdi}: could not uniquely identify the two proven TMR18 font objects; "
                f"candidates={[(x['stream'],hex(x['offset']),round(x['best_similarity'],4),hex(x['texture_object'])) for x in top]}"
            )
        selected,pairinfo=pair
        tex=selected[0]["texture_object"]

        # Verify the same offsets are still pristine in Stage69 source.
        for c in selected:
            si=c["stream"];off=c["offset"]
            if struct.unpack_from("<H",src[si],off+0x50)[0] != 151:
                raise RuntimeError(f"{mdi}: Stage69 font object drift at {si}+{off:#x}")

        assets=build_font_assets(menu_streams,plan,additional_chars,tex)
        atlasbase=CAMPAIGN_BASE+34*STRIDE
        metabase=CAMPAIGN_BASE+35*STRIDE
        mu[34][:len(assets["atlas"])] = assets["atlas"]
        mu[35][:len(assets["meta"])] = assets["meta"]

        for c in selected:
            patch_font_object(mu,c["stream"],c["offset"],metabase,assets)

        # Verify every Stage39A base character plus per-MDI extras through both
        # patched production font objects.
        temp={i:bytes(x) for i,x in mu.items()}
        verify_chars={x["char"] for x in plan["layout"]} | set(additional_chars)
        for c in selected:
            missing=[ch for ch in sorted(verify_chars,key=ord)
                     if font_lookup(temp,c["stream"],c["offset"],ord(ch)) is None]
            if missing:
                raise RuntimeError(f"{mdi}: font readback missing chars after patch: {''.join(missing[:40])}")

        # Patch the per-MDI DSL/DSX descriptor with exactly the historically
        # proven pattern.
        stem=mdi[:-4]
        _, dsl=b.iso_read_file(SOURCE_ISO,PARTS+[stem+".DSL"])
        _, dsx=b.iso_read_file(SOURCE_ISO,PARTS+[stem+".DSX"])
        if b.dsx_logical_bytes(dsx) != dsl:
            raise RuntimeError(f"{mdi}: DSX logical bytes != DSL before patch")
        dsl_patched,dsl_report=patch_dsl(dsl,atlasbase)
        dsx_patched,_=b.rebuild_dsx_from_logical(dsx,dsl_patched)
        if b.dsx_logical_bytes(dsx_patched) != dsl_patched:
            raise RuntimeError(f"{mdi}: rebuilt DSX logical mismatch")

        font_report={
            "mode":"INSTALL_STAGE39A_PLUS_MDI_EXTRAS",
            "selected_objects":[
                {
                    "stream":c["stream"],
                    "offset":hex(c["offset"]),
                    "ascii_score":c["ascii_score"],
                    "best_similarity":c["best_similarity"],
                    "texture_object":hex(c["texture_object"]),
                    "widths":c["widths"],
                    "heights":c["heights"],
                } for c in selected
            ],
            "pair_info":pairinfo,
            "candidate_count":len(candidates),
            "texture_object":hex(tex),
            "font_count":assets["count"],
            "base_font_count":BASE_FONT_COUNT,
            "additional_chars":"".join(additional_chars),
            "atlas_sha256":sha256_bytes(assets["atlas"]),
            "metadata_bytes":len(assets["meta"]),
            "dsl":dsl_report,
        }
        cursor=PAYLOAD_START

    patch_rows,cursor,cache=build_payloads(mu,refs,cursor)

    changed={i:bytes(v) for i,v in mu.items() if bytes(v)!=src[i]}
    patched=b.rebuild_mdi(src_blob,changed)
    check=parse_mdi_dict(b,patched)
    for i,v in mu.items():
        if check[i] != bytes(v):
            raise RuntimeError(f"{mdi}: rebuilt MDI decoded stream mismatch {i}")
    verify_patched_refs(check,patch_rows)

    rep={
        "mdi":mdi,
        "target_refs":len(refs),
        "target_ids":len({rid for r in refs for rid in r["resource_ids"].split(";") if rid}),
        "unique_payloads":len(cache),
        "payload_end_stream35":hex(cursor),
        "changed_streams":";".join(map(str,sorted(changed))),
        "source_mdi_sha256":sha256_bytes(src_blob),
        "patched_mdi_sha256":sha256_bytes(patched),
        "font_mode":font_report["mode"],
        "dsl_mode":dsl_report["mode"] if "mode" in dsl_report else "PATCHED",
    }
    discovery["font_report"]=font_report

    return {
        "mdi":mdi,
        "patched_mdi":patched,
        "patched_dsl":dsl_patched,
        "patched_dsx":dsx_patched,
        "report":rep,
        "patch_rows":patch_rows,
        "discovery":discovery,
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--package-root",required=True)
    ap.add_argument("--outdir",required=True)
    args=ap.parse_args()
    pkg=Path(args.package_root)
    out=Path(args.outdir)
    out.mkdir(parents=True,exist_ok=True)

    b=load_helper()

    for p in (ORIGINAL_ISO,SOURCE_ISO):
        if not p.exists():
            raise RuntimeError(f"Required ISO missing: {p}")

    source_sha_before=sha256_file(SOURCE_ISO)

    refs_all=read_tsv(pkg/"evidence"/"allstream_fstring_refs.tsv")
    split=read_tsv(pkg/"evidence"/"campaign_final_apply_split.tsv")
    demands=read_tsv(pkg/"evidence"/"allstream_mdi_glyph_demand.tsv")
    plan=json.loads((pkg/"evidence"/"stage39a_font_plan.json").read_text(encoding="utf-8-sig"))

    compiled_ids={r["resource_id"] for r in split if r["final_apply_class"]=="COMPILED_MDI_PATCH"}
    if len(compiled_ids)!=967:
        raise RuntimeError(f"compiled ID count mismatch: {len(compiled_ids)}")

    refs=[]
    matched=set()
    for r in refs_all:
        ids={x for x in r["resource_ids"].split(";") if x}
        hit=ids & compiled_ids
        if hit:
            refs.append(r)
            matched |= hit
    if len(refs)!=2333 or len(matched)!=967:
        raise RuntimeError(f"target evidence mismatch refs={len(refs)} ids={len(matched)}")

    target_mdis=sorted({r["mdi"] for r in refs})
    if len(target_mdis)!=32:
        raise RuntimeError(f"target MDI count mismatch: {len(target_mdis)}")

    demand_by={r["mdi"]:r for r in demands}
    miss=[x for x in target_mdis if x not in demand_by]
    if miss:
        raise RuntimeError(f"Missing glyph demand rows: {miss}")

    # Menu font assets are the proven Stage39A/40Y production donor.
    _,menu_blob=b.iso_read_file(SOURCE_ISO,["PSP_GAME","USRDIR","SYSTEM","ON_MEMU_O.MDI"])
    menu_streams=parse_mdi_dict(b,menu_blob)

    # Validate base menu production font still has almost all 696 Stage39A mappings.
    menu_font_off=(19,0xE83C)
    base_exact=0
    for item in plan["layout"]:
        gi=font_lookup(menu_streams,menu_font_off[0],menu_font_off[1],item["codepoint"],MENU_BASE)
        if gi==item["glyph_index"]:
            base_exact+=1
    if base_exact < 690:
        raise RuntimeError(f"Menu donor font mapping drift: exact={base_exact}/696")

    # Build original first-mission font fingerprints from the two historically
    # proven production text font objects.
    _,first_orig_blob=b.iso_read_file(ORIGINAL_ISO,PARTS+["D0_0130_.MDI"])
    first_orig=parse_mdi_dict(b,first_orig_blob)
    templates=[]
    metric_sigs=set()
    first_template_report=[]
    for si,off in KNOWN_FIRST_FONT_OFFSETS:
        ccount=struct.unpack_from("<H",first_orig[si],off+0x50)[0]
        if ccount!=151:
            raise RuntimeError(f"Original first-mission known font count drift {si}+{off:#x}: {ccount}")
        asc,ai=font_ascii_score(first_orig,si,off)
        if asc<55:
            raise RuntimeError(f"Original first-mission known font ASCII mapping weak: {asc}")
        wp=struct.unpack_from("<I",first_orig[si],off+0x474)[0]
        hp=struct.unpack_from("<I",first_orig[si],off+0x478)[0]
        tp=struct.unpack_from("<I",first_orig[si],off+0x488)[0]
        widths=read_u32_array(first_orig,wp,4)
        heights=read_u32_array(first_orig,hp,4)
        textures=read_u32_array(first_orig,tp,4)
        if widths is None or heights is None or textures is None:
            raise RuntimeError("Could not read original first-mission font arrays")
        if len(set(textures))!=1:
            raise RuntimeError(f"Original first-mission font texture array not uniform: {textures}")
        if textures[0] != KNOWN_FIRST_TEXTURE_OBJECT:
            raise RuntimeError(
                f"Historical texture-object check failed: got {textures[0]:#x}, "
                f"expected {KNOWN_FIRST_TEXTURE_OBJECT:#x}"
            )
        metric_sigs.add((tuple(widths),tuple(heights)))
        obj=first_orig[si][off:off+0x490]
        templates.append(normalize_font_object(obj,CAMPAIGN_BASE,len(first_orig)))
        first_template_report.append({
            "stream":si,"offset":hex(off),"ascii_score":asc,
            "widths":widths,"heights":heights,"textures":[hex(x) for x in textures],
        })

    refs_by=defaultdict(list)
    for r in refs:
        refs_by[r["mdi"]].append(r)

    # ------------------ PASS 1: full dry run ------------------
    mdi_reports=[]
    discoveries=[]
    patch_rows=[]
    blocked=[]
    print("[PASS1] Full 32-MDI dry-run discovery/build",flush=True)
    for idx,mdi in enumerate(target_mdis,1):
        print(f"[dry {idx:02d}/32] {mdi}",flush=True)
        try:
            res=prepare_one(
                b,mdi,refs_by[mdi],demand_by[mdi],plan,menu_streams,
                templates,metric_sigs,dry_only=True
            )
            mdi_reports.append(res["report"])
            discoveries.append(res["discovery"])
            patch_rows.extend(res["patch_rows"])
        except Exception as e:
            blocked.append({"mdi":mdi,"error":repr(e)})

    (out/"font_template_reference.json").write_text(
        json.dumps({
            "menu_base_exact":base_exact,
            "first_mission_templates":first_template_report,
            "metric_signatures":[
                {"widths":list(a),"heights":list(b)} for a,b in sorted(metric_sigs)
            ],
        },ensure_ascii=False,indent=2),
        encoding="utf-8"
    )
    (out/"font_discovery.json").write_text(json.dumps(discoveries,ensure_ascii=False,indent=2),encoding="utf-8")
    if blocked:
        (out/"blocked_mdis.json").write_text(json.dumps(blocked,ensure_ascii=False,indent=2),encoding="utf-8")
        report={
            "step":"STEP_074_FIX1",
            "status":"BLOCKED_PREBUILD",
            "iso_built":False,
            "compiled_ids":967,
            "target_refs":2333,
            "target_mdis":32,
            "dryrun_passed_mdis":32-len(blocked),
            "blocked_count":len(blocked),
            "blocked":blocked,
            "source_iso":str(SOURCE_ISO),
            "source_sha256":source_sha_before,
            "output_iso":str(OUTPUT_ISO),
            "source_iso_preserved":sha256_file(SOURCE_ISO)==source_sha_before,
            "runtime_verified":False,
        }
        (out/"step074_fix1_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
        raise SystemExit(6)

    if len(patch_rows)!=2333:
        raise RuntimeError(f"Dry-run patched ref count {len(patch_rows)} != 2333")
    dry_ids=set()
    for r in patch_rows:
        dry_ids.update(x for x in r["resource_ids"].split(";") if x in compiled_ids)
    if len(dry_ids)!=967:
        raise RuntimeError(f"Dry-run patched ID count {len(dry_ids)} != 967")

    # ------------------ PASS 2: actual build ------------------
    if OUTPUT_ISO.exists():
        OUTPUT_ISO.unlink()
    shutil.copy2(SOURCE_ISO,OUTPUT_ISO)

    final_reports=[]
    final_patch_rows=[]
    iso_file_rows=[]

    print("[PASS2] Applying 32 MDIs after every dry-run gate passed",flush=True)
    for idx,mdi in enumerate(target_mdis,1):
        print(f"[apply {idx:02d}/32] {mdi}",flush=True)
        res=prepare_one(
            b,mdi,refs_by[mdi],demand_by[mdi],plan,menu_streams,
            templates,metric_sigs,dry_only=False
        )
        stem=mdi[:-4]

        # MDI always changes.
        b.append_iso_file_and_repoint(OUTPUT_ISO,PARTS+[mdi],res["patched_mdi"])
        _,rb=b.iso_read_file(OUTPUT_ISO,PARTS+[mdi])
        if rb!=res["patched_mdi"]:
            raise RuntimeError(f"{mdi}: final ISO MDI readback mismatch")
        iso_file_rows.append({
            "file":mdi,"kind":"MDI",
            "sha256":sha256_bytes(rb),"bytes":len(rb),"readback":1
        })

        # First mission already has the proven Stage43A DSL/DSX; preserve it.
        if res["patched_dsl"] is not None:
            dslname=stem+".DSL"; dsxname=stem+".DSX"
            # DSL same-size overwrite; DSX append/repoint follows proven path.
            b.overwrite_iso_same_size(OUTPUT_ISO,PARTS+[dslname],res["patched_dsl"])
            b.append_iso_file_and_repoint(OUTPUT_ISO,PARTS+[dsxname],res["patched_dsx"])
            _,rdsl=b.iso_read_file(OUTPUT_ISO,PARTS+[dslname])
            _,rdsx=b.iso_read_file(OUTPUT_ISO,PARTS+[dsxname])
            if rdsl!=res["patched_dsl"] or rdsx!=res["patched_dsx"]:
                raise RuntimeError(f"{mdi}: DSL/DSX final readback mismatch")
            iso_file_rows.extend([
                {"file":dslname,"kind":"DSL","sha256":sha256_bytes(rdsl),"bytes":len(rdsl),"readback":1},
                {"file":dsxname,"kind":"DSX","sha256":sha256_bytes(rdsx),"bytes":len(rdsx),"readback":1},
            ])

        final_reports.append(res["report"])
        final_patch_rows.extend(res["patch_rows"])

    if len(final_patch_rows)!=2333:
        raise RuntimeError(f"Final patched ref count {len(final_patch_rows)} != 2333")
    final_ids=set()
    for r in final_patch_rows:
        final_ids.update(x for x in r["resource_ids"].split(";") if x in compiled_ids)
    if len(final_ids)!=967:
        raise RuntimeError(f"Final patched ID count {len(final_ids)} != 967")

    # Preservation: Stage69 INT patch files.
    int_report=read_tsv(pkg/"evidence"/"int_file_patch_report.tsv")
    int_pres=[]
    for r in int_report:
        name=r["file"]
        _,s=b.iso_read_file(SOURCE_ISO,PARTS+[name])
        _,d=b.iso_read_file(OUTPUT_ISO,PARTS+[name])
        int_pres.append({
            "file":name,
            "source_sha256":sha256_bytes(s),
            "output_sha256":sha256_bytes(d),
            "preserved":int(s==d),
        })
    if not all(x["preserved"] for x in int_pres):
        raise RuntimeError("Stage69 INT preservation failed")

    movie=read_tsv(pkg/"evidence"/"movie_st1_lineage_verified.tsv")
    mov_pres=[]
    for r in movie:
        name=r["file"]
        _,s=b.iso_read_file(SOURCE_ISO,PARTS+[name])
        _,d=b.iso_read_file(OUTPUT_ISO,PARTS+[name])
        mov_pres.append({
            "file":name,
            "source_sha256":sha256_bytes(s),
            "output_sha256":sha256_bytes(d),
            "preserved":int(s==d),
        })
    if not all(x["preserved"] for x in mov_pres):
        raise RuntimeError("Movie ST1 preservation failed")

    menu_pres=[]
    for name in ("ON_MEMU_O.MDI","ON_MEMU.DSL","ON_MEMU.DSX"):
        _,s=b.iso_read_file(SOURCE_ISO,PARTS+[name])
        _,d=b.iso_read_file(OUTPUT_ISO,PARTS+[name])
        menu_pres.append({
            "file":name,
            "source_sha256":sha256_bytes(s),
            "output_sha256":sha256_bytes(d),
            "preserved":int(s==d),
        })
    if not all(x["preserved"] for x in menu_pres):
        raise RuntimeError("Menu/title resource preservation failed")

    source_sha_after=sha256_file(SOURCE_ISO)
    if source_sha_after!=source_sha_before:
        raise RuntimeError("Source Stage69 ISO changed during STEP074 FIX1")

    write_tsv(
        out/"mdi_build_report.tsv",
        ["mdi","target_refs","target_ids","unique_payloads","payload_end_stream35",
         "changed_streams","source_mdi_sha256","patched_mdi_sha256",
         "font_mode","dsl_mode"],
        final_reports
    )
    write_tsv(
        out/"compiled967_patch_refs.tsv",
        ["mdi","metadata_stream","metadata_offset","resource_ids","english","korean",
         "payload_ptr","payload_offset_stream35","payload_bytes"],
        final_patch_rows
    )
    write_tsv(
        out/"iso_file_readback.tsv",
        ["file","kind","sha256","bytes","readback"],iso_file_rows
    )
    write_tsv(
        out/"int92_preservation.tsv",
        ["file","source_sha256","output_sha256","preserved"],int_pres
    )
    write_tsv(
        out/"movie_st1_preservation.tsv",
        ["file","source_sha256","output_sha256","preserved"],mov_pres
    )
    write_tsv(
        out/"menu_preservation.tsv",
        ["file","source_sha256","output_sha256","preserved"],menu_pres
    )

    report={
        "step":"STEP_074_FIX1",
        "status":"BUILT_UNVERIFIED",
        "source_iso":str(SOURCE_ISO),
        "source_sha256_before":source_sha_before,
        "source_sha256_after":source_sha_after,
        "source_iso_preserved":source_sha_before==source_sha_after,
        "output_iso":str(OUTPUT_ISO),
        "output_sha256":sha256_file(OUTPUT_ISO),
        "compiled_mdi_ids_static_applied":len(final_ids),
        "compiled_mdi_reference_rows_patched":len(final_patch_rows),
        "target_mdis_patched":len(target_mdis),
        "mdi_readback_files":sum(1 for x in iso_file_rows if x["kind"]=="MDI"),
        "dsl_patched_files":sum(1 for x in iso_file_rows if x["kind"]=="DSL"),
        "dsx_patched_files":sum(1 for x in iso_file_rows if x["kind"]=="DSX"),
        "font_strategy":"Stage39A donor + per-MDI extra glyphs; D0_0130 existing Stage43A preserved",
        "first_mission_existing_font_preserved":True,
        "int92_files_preserved":len(int_pres),
        "movie_st1_files_preserved":len(mov_pres),
        "menu_files_preserved":len(menu_pres),
        "int92_runtime_status":"BUILT_UNVERIFIED",
        "compiled967_runtime_verified":False,
        "movie_106_repatched":False,
        "movie_playback_validation_resumed":False,
        "new_objective_title_fixed":False,
    }
    (out/"step074_fix1_report.json").write_text(
        json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8"
    )
    (out/"BUILD_COMPLETE.txt").write_text(
        "STEP_074 FIX1 BUILT_UNVERIFIED\n"
        "compiled IDs: 967\n"
        "FString refs: 2333\n"
        "MDIs: 32\n"
        f"output: {OUTPUT_ISO}\n"
        "runtime verification: NO\n",
        encoding="utf-8"
    )
    print(json.dumps(report,ensure_ascii=False),flush=True)

if __name__=="__main__":
    main()
