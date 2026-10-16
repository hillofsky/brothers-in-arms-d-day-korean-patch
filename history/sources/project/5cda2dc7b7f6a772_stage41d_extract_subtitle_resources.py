#!/usr/bin/env python3
import argparse, hashlib, json, math, os, re, struct, sys
from pathlib import Path

SECTOR = 2048
TARGETS = {"SUBTITLETEXTURE.RAW", "SUBTITLEHASHMAP.INI"}

def sha1_bytes(b):
    return hashlib.sha1(b).hexdigest()

class ISO9660:
    def __init__(self, path):
        self.path = Path(path)
        self.f = self.path.open("rb")
        self._read_pvd()

    def close(self):
        self.f.close()

    def read_at(self, off, size):
        self.f.seek(off)
        b = self.f.read(size)
        if len(b) != size:
            raise EOFError(f"Short read at 0x{off:X}: wanted {size}, got {len(b)}")
        return b

    def _read_pvd(self):
        pvd = self.read_at(16 * SECTOR, SECTOR)
        if pvd[0] != 1 or pvd[1:6] != b"CD001":
            raise ValueError("Primary Volume Descriptor not found at sector 16")
        self.pvd = pvd
        self.volume_id = pvd[40:72].decode("ascii", "replace").rstrip(" ")
        self.logical_block_size = int.from_bytes(pvd[128:130], "little")
        if self.logical_block_size != SECTOR:
            raise ValueError(f"Unexpected ISO logical block size {self.logical_block_size}")
        self.root = self._parse_record(pvd, 156, "<ROOT>")
        if not self.root or not self.root["is_dir"]:
            raise ValueError("Invalid ISO root directory record")

    def _parse_record(self, buf, off, parent):
        if off >= len(buf):
            return None
        ln = buf[off]
        if ln == 0:
            return None
        rec = buf[off:off+ln]
        if len(rec) < 34:
            return None
        name_len = rec[32]
        raw_name = rec[33:33+name_len]
        if raw_name == b"\x00":
            name = "."
        elif raw_name == b"\x01":
            name = ".."
        else:
            name = raw_name.decode("ascii", "replace")
            if ";" in name:
                name = name.split(";", 1)[0]
        extent = int.from_bytes(rec[2:6], "little")
        size = int.from_bytes(rec[10:14], "little")
        flags = rec[25]
        return {
            "name": name,
            "extent": extent,
            "size": size,
            "flags": flags,
            "is_dir": bool(flags & 0x02),
            "record_len": ln,
            "parent": parent,
        }

    def list_dir(self, node, path):
        data = self.read_at(node["extent"] * SECTOR, node["size"])
        pos = 0
        out = []
        while pos < len(data):
            ln = data[pos]
            if ln == 0:
                pos = ((pos // SECTOR) + 1) * SECTOR
                continue
            r = self._parse_record(data, pos, path)
            if r and r["name"] not in (".", ".."):
                out.append(r)
            pos += ln
        return out

    def walk(self):
        stack = [("", self.root)]
        seen_dirs = set()
        while stack:
            base, node = stack.pop()
            key = (node["extent"], node["size"])
            if key in seen_dirs:
                continue
            seen_dirs.add(key)
            for ch in self.list_dir(node, base or "/"):
                p = (base + "/" + ch["name"]).replace("//", "/")
                yield p, ch
                if ch["is_dir"]:
                    stack.append((p, ch))

    def extract(self, node):
        return self.read_at(node["extent"] * SECTOR, node["size"])

def decode_text(b):
    trials = []
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin1"):
        try:
            s = b.decode(enc)
            bad = s.count("\ufffd")
            trials.append((bad, enc, s))
        except Exception:
            pass
    if not trials:
        return "latin1", b.decode("latin1", "replace")
    trials.sort(key=lambda x: (x[0], 0 if x[1].startswith("utf") else 1))
    _, enc, s = trials[0]
    return enc, s

def printable_summary(text):
    chars = sorted({c for c in text if c.isprintable() and c not in "\r\n\t"})
    return "".join(chars)

def parse_ini_lines(text):
    rows = []
    for no, raw in enumerate(text.splitlines(), 1):
        s = raw.strip()
        if not s or s.startswith(("#", ";", "//")):
            rows.append({"line": no, "raw": raw, "kind": "comment_or_blank"})
            continue
        if "=" in s:
            k, v = s.split("=", 1)
            rows.append({"line": no, "raw": raw, "kind": "key_value",
                         "key": k.strip(), "value": v.strip()})
        else:
            toks = [x for x in re.split(r"[\s,;]+", s) if x]
            rows.append({"line": no, "raw": raw, "kind": "tokens", "tokens": toks})
    return rows

def write_pgm(path, w, h, pixels):
    assert len(pixels) >= w*h
    with Path(path).open("wb") as f:
        f.write(f"P5\n{w} {h}\n255\n".encode("ascii"))
        f.write(bytes(pixels[:w*h]))

def write_ppm(path, w, h, rgb):
    assert len(rgb) >= w*h*3
    with Path(path).open("wb") as f:
        f.write(f"P6\n{w} {h}\n255\n".encode("ascii"))
        f.write(bytes(rgb[:w*h*3]))

def rgb565_to_rgb(data):
    n = len(data)//2
    out = bytearray(n*3)
    for i in range(n):
        v = data[i*2] | (data[i*2+1] << 8)
        r = ((v >> 11) & 31) * 255 // 31
        g = ((v >> 5) & 63) * 255 // 63
        b = (v & 31) * 255 // 31
        j = i*3
        out[j:j+3] = bytes((r,g,b))
    return out

def rgba8888_to_rgb(data):
    n = len(data)//4
    out = bytearray(n*3)
    for i in range(n):
        j4=i*4; j3=i*3
        out[j3:j3+3] = data[j4:j4+3]
    return out

def t4_unpack(data):
    out = bytearray(len(data)*2)
    for i,b in enumerate(data):
        out[i*2] = (b & 0x0F) * 17
        out[i*2+1] = ((b >> 4) & 0x0F) * 17
    return out

def candidate_previews(raw, outdir):
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    candidates = []
    widths = [64, 128, 256, 512, 1024, 2048]
    formats = [
        ("T4_linear", 0.5),
        ("GRAY8", 1),
        ("RGB565", 2),
        ("RGBA8888", 4),
    ]
    for name, bpp in formats:
        pixels = int(len(raw) / bpp)
        if abs(pixels * bpp - len(raw)) > 0.01:
            continue
        for w in widths:
            if pixels % w:
                continue
            h = pixels // w
            if h < 16 or h > 4096:
                continue
            if h not in [16,32,64,128,256,512,1024,2048,4096] and not (32 <= h <= 2048):
                continue
            tag = f"{name}_{w}x{h}"
            try:
                if name == "T4_linear":
                    pix = t4_unpack(raw)
                    p = outdir / f"{tag}.pgm"
                    write_pgm(p, w, h, pix)
                elif name == "GRAY8":
                    p = outdir / f"{tag}.pgm"
                    write_pgm(p, w, h, raw)
                elif name == "RGB565":
                    p = outdir / f"{tag}.ppm"
                    write_ppm(p, w, h, rgb565_to_rgb(raw))
                else:
                    p = outdir / f"{tag}.ppm"
                    write_ppm(p, w, h, rgba8888_to_rgb(raw))
                candidates.append({
                    "format": name, "width": w, "height": h,
                    "file": p.name,
                })
            except Exception as e:
                candidates.append({
                    "format": name, "width": w, "height": h,
                    "error": repr(e),
                })
    return candidates

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iso", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    iso_path = Path(args.iso)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    report = {
        "stage": "41D",
        "source_iso": str(iso_path),
        "purpose": "Extract and analyze SubtitleManagerPreRendered resources.",
        "known_runtime": {
            "texture_loader": "0x0893E764",
            "hashmap_loader": "0x0893E58C",
            "texture_path": "disc0:/PSP_GAME/USRDIR/SYSTEM/SUBTITLETEXTURE.RAW",
            "hashmap_path": "disc0:/PSP_GAME/USRDIR/SYSTEM/SUBTITLEHASHMAP.INI",
        },
    }

    if not iso_path.exists():
        raise FileNotFoundError(iso_path)

    iso = ISO9660(iso_path)
    try:
        report["volume_id"] = iso.volume_id
        report["logical_block_size"] = iso.logical_block_size

        found = {}
        system_entries = []
        for path, node in iso.walk():
            bn = node["name"].upper()
            if "/PSP_GAME/USRDIR/SYSTEM/" in path.upper():
                system_entries.append({
                    "path": path,
                    "extent": node["extent"],
                    "size": node["size"],
                    "is_dir": node["is_dir"],
                })
            if bn in TARGETS:
                found[bn] = (path, node)

        (out / "system_directory_listing.json").write_text(
            json.dumps(system_entries, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        report["found"] = {}
        for name in sorted(TARGETS):
            if name not in found:
                report["found"][name] = None
                continue
            path, node = found[name]
            data = iso.extract(node)
            p = out / name
            p.write_bytes(data)
            report["found"][name] = {
                "iso_path": path,
                "extent_lbn": node["extent"],
                "file_offset_hex": f"0x{node['extent']*SECTOR:X}",
                "size": len(data),
                "sha1": sha1_bytes(data),
            }

        if any(report["found"][n] is None for n in TARGETS):
            raise RuntimeError("One or both subtitle resources were not found in ISO9660 tree.")

        ini = (out / "SUBTITLEHASHMAP.INI").read_bytes()
        enc, text = decode_text(ini)
        rows = parse_ini_lines(text)
        report["hashmap"] = {
            "encoding_guess": enc,
            "line_count": len(text.splitlines()),
            "printable_unique": printable_summary(text),
            "rows": rows,
        }
        (out / "SUBTITLEHASHMAP_decoded.txt").write_text(
            text, encoding="utf-8", errors="replace"
        )
        numbered = "\n".join(
            f"{i:05d}: {line}" for i, line in enumerate(text.splitlines(), 1)
        )
        (out / "SUBTITLEHASHMAP_numbered.txt").write_text(
            numbered, encoding="utf-8"
        )
        (out / "SUBTITLEHASHMAP_hex_head_tail.txt").write_text(
            "HEAD\n" + ini[:1024].hex(" ") +
            "\n\nTAIL\n" + ini[-1024:].hex(" "),
            encoding="utf-8"
        )

        raw = (out / "SUBTITLETEXTURE.RAW").read_bytes()
        report["texture"] = {
            "size": len(raw),
            "sha1": sha1_bytes(raw),
            "zero_fraction": (raw.count(0) / len(raw)) if raw else 0,
            "ff_fraction": (raw.count(255) / len(raw)) if raw else 0,
            "divisibility": {
                str(n): (len(raw) % n == 0)
                for n in [128,256,512,1024,2048,4096,8192,16384,32768,65536,131072,262144,524288]
            },
        }
        previews = candidate_previews(raw, out / "raw_previews")
        report["texture"]["candidate_previews"] = previews

        summary = []
        summary.append("BIA Stage41D - SubtitleManagerPreRendered resources")
        summary.append("")
        for n in ("SUBTITLEHASHMAP.INI","SUBTITLETEXTURE.RAW"):
            x = report["found"][n]
            summary.append(
                f"{n}: LBN={x['extent_lbn']} offset={x['file_offset_hex']} "
                f"size={x['size']} SHA1={x['sha1']}"
            )
        summary.append("")
        summary.append(f"INI encoding guess: {enc}")
        summary.append(f"INI lines: {report['hashmap']['line_count']}")
        summary.append(f"RAW size: {len(raw)}")
        summary.append(f"RAW preview candidates: {len(previews)}")
        summary.append("")
        summary.append("Runtime evidence from Stage41C:")
        summary.append("  0x0893E764 = SUBTITLETEXTURE.RAW loader")
        summary.append("  0x0893E58C = SUBTITLEHASHMAP.INI loader")
        summary.append("  SubtitleManagerPreRendered strings confirmed in BIAOFF runtime.")
        (out / "stage41d_summary.txt").write_text(
            "\n".join(summary), encoding="utf-8"
        )

        report["completed"] = True
        (out / "stage41d_report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        print("\n".join(summary))
        return 0
    finally:
        iso.close()

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"STAGE41D FAILED: {e!r}", file=sys.stderr)
        raise
