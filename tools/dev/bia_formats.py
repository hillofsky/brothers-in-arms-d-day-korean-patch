# Recovered pure file-format functions from historical bia_stage36_base.py.
# Runtime/debugger/Windows APIs intentionally excluded.
from __future__ import annotations
from pathlib import Path
import struct, os, zlib

def iso_norm_name(raw: bytes) -> str:
    if raw == b"\x00":
        return "."
    if raw == b"\x01":
        return ".."
    s = raw.decode("ascii", "replace")
    if ";" in s:
        s = s.split(";", 1)[0]
    return s.upper()

def iso_read_record(f, off):
    f.seek(off)
    b = f.read(1)
    if not b:
        return None
    ln = b[0]
    if ln == 0:
        return {"length": 0}
    rec = b + f.read(ln - 1)
    if len(rec) != ln or ln < 34:
        return None
    nlen = rec[32]
    return {
        "length": ln,
        "extent": struct.unpack_from("<I", rec, 2)[0],
        "size": struct.unpack_from("<I", rec, 10)[0],
        "flags": rec[25],
        "name": iso_norm_name(rec[33:33+nlen]),
        "record_offset": off,
    }

def iso_list_dir(f, extent, size):
    pos = extent * 2048
    end = pos + size
    while pos < end:
        f.seek(pos)
        b = f.read(1)
        if not b:
            break
        ln = b[0]
        if ln == 0:
            pos = ((pos // 2048) + 1) * 2048
            continue
        rec = iso_read_record(f, pos)
        if not rec:
            raise RuntimeError(f"Bad ISO directory record at 0x{pos:X}")
        yield rec
        pos += rec["length"]

def iso_find_record(iso: Path, parts):
    with iso.open("rb") as f:
        f.seek(16 * 2048)
        pvd = f.read(2048)
        if len(pvd) != 2048 or pvd[0] != 1 or pvd[1:6] != b"CD001":
            raise RuntimeError("ISO9660 PVD not found")

        root_len = pvd[156]
        root = pvd[156:156+root_len]
        extent = struct.unpack_from("<I", root, 2)[0]
        size = struct.unpack_from("<I", root, 10)[0]

        found = None
        for part in parts:
            found = None
            for rec in iso_list_dir(f, extent, size):
                if rec["name"] == part.upper():
                    found = rec
                    break
            if not found:
                raise RuntimeError(f"ISO path not found: {'/'.join(parts)}")
            extent, size = found["extent"], found["size"]
        return found

def iso_read_file(iso: Path, parts):
    rec = iso_find_record(iso, parts)
    with iso.open("rb") as f:
        f.seek(rec["extent"] * 2048)
        data = f.read(rec["size"])
    if len(data) != rec["size"]:
        raise RuntimeError("Short ISO read")
    return rec, data

def patch_dir_record_extent_size(f, record_offset, extent, size):
    f.seek(record_offset + 2)
    f.write(struct.pack("<I", extent))
    f.write(struct.pack(">I", extent))
    f.seek(record_offset + 10)
    f.write(struct.pack("<I", size))
    f.write(struct.pack(">I", size))

def update_volume_space_size(f, total_sectors):
    sector = 16
    while True:
        off = sector * 2048
        f.seek(off)
        vd = bytearray(f.read(2048))
        if len(vd) != 2048 or vd[1:6] != b"CD001":
            break
        typ = vd[0]
        if typ in (1, 2):
            struct.pack_into("<I", vd, 80, total_sectors)
            struct.pack_into(">I", vd, 84, total_sectors)
            f.seek(off)
            f.write(vd)
        if typ == 255:
            break
        sector += 1

def align_up(v, a):
    return (v + a - 1) & ~(a - 1)

def append_iso_file_and_repoint(iso: Path, target_parts, payload: bytes):
    rec = iso_find_record(iso, target_parts)
    with iso.open("r+b") as f:
        f.seek(0, os.SEEK_END)
        eof = f.tell()
        new_off = align_up(eof, 2048)
        if new_off > eof:
            f.write(b"\x00" * (new_off - eof))

        f.seek(new_off)
        f.write(payload)

        padded_end = align_up(new_off + len(payload), 2048)
        if padded_end > new_off + len(payload):
            f.write(b"\x00" * (padded_end - (new_off + len(payload))))

        new_extent = new_off // 2048
        patch_dir_record_extent_size(
            f, rec["record_offset"], new_extent, len(payload)
        )
        update_volume_space_size(f, padded_end // 2048)

    return {
        "old_extent": rec["extent"],
        "old_size": rec["size"],
        "new_extent": new_extent,
        "new_size": len(payload),
    }

def overwrite_iso_same_size(iso: Path, target_parts, payload: bytes):
    rec = iso_find_record(iso, target_parts)
    if len(payload) != rec["size"]:
        raise RuntimeError("same-size overwrite required")
    with iso.open("r+b") as f:
        f.seek(rec["extent"] * 2048)
        f.write(payload)

def valid_zlib_header(two):
    if len(two) != 2:
        return False
    cmf, flg = two
    return (cmf & 0x0F) == 8 and ((cmf << 8) + flg) % 31 == 0

def parse_mdi(data: bytes):
    streams = []
    pos = 6
    idx = 0

    while pos + 4 <= len(data):
        csize = struct.unpack_from("<I", data, pos)[0]
        zpos = pos + 4

        if (
            csize > 0
            and zpos + csize <= len(data)
            and valid_zlib_header(data[zpos:zpos+2])
        ):
            dec = zlib.decompress(data[zpos:zpos+csize])
            streams.append({
                "index": idx,
                "size_field_pos": pos,
                "zpos": zpos,
                "csize": csize,
                "decoded": dec,
            })
            pos = zpos + csize
            idx += 1
            continue

        # Optional 4-byte region/load marker before the next stream.
        if pos + 8 <= len(data):
            c2 = struct.unpack_from("<I", data, pos + 4)[0]
            z2 = pos + 8
            if (
                c2 > 0
                and z2 + c2 <= len(data)
                and valid_zlib_header(data[z2:z2+2])
            ):
                pos += 4
                continue

        raise RuntimeError(f"MDI parse failed at 0x{pos:X}")

    if pos != len(data):
        raise RuntimeError("MDI parse did not end at EOF")

    return streams

def rebuild_mdi(original: bytes, replacements: dict[int, bytes]):
    streams = parse_mdi(original)
    by_pos = []
    for idx, dec in replacements.items():
        st = streams[idx]
        comp = zlib.compress(dec, 9)
        by_pos.append((st["size_field_pos"], st, comp))

    by_pos.sort()
    out = bytearray()
    cur = 0

    for pos, st, comp in by_pos:
        out += original[cur:pos]
        out += struct.pack("<I", len(comp))
        out += comp
        cur = st["zpos"] + st["csize"]

    out += original[cur:]
    return bytes(out)
