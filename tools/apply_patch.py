#!/usr/bin/env python3
"""Apply a verified BIA xdelta patch without modifying the input ISO."""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for buf in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(buf)
    return h.hexdigest()


def check_file(path, info, label):
    if not path.is_file():
        raise RuntimeError(f'{label} not found: {path}')
    n = path.stat().st_size
    want_n = info.get('size_bytes')
    if want_n is None or n != want_n:
        raise RuntimeError(f'{label} size mismatch: actual {n} / expected {want_n}')
    real = digest(path)
    want = info.get('sha256')
    if not want or real.lower() != want.lower():
        raise RuntimeError(f'{label} SHA-256 mismatch: actual {real} / expected {want}')
    print(f'{label}: SHA256 OK ({real})', flush=True)


def assemble(manifest, assets_dir, work_dir):
    parts = manifest.get('xdelta', {}).get('parts', [])
    if not parts:
        raise RuntimeError('manifest has no patch parts')
    for p in parts:
        name = p['filename']
        if Path(name).name != name:
            raise RuntimeError('unsafe patch path')
        check_file(assets_dir / name, p, f'Patch part {name}')
    if len(parts) == 1:
        return assets_dir / parts[0]['filename'], False
    patch = work_dir / (manifest['xdelta']['filename'] + '.joined')
    with patch.open('xb') as out:
        for p in parts:
            with (assets_dir / p['filename']).open('rb') as src:
                shutil.copyfileobj(src, out, length=4 * 1024 * 1024)
    check_file(patch, manifest['xdelta'], 'Reassembled patch')
    return patch, True


def main():
    a = argparse.ArgumentParser(description='Apply the BIA D-Day xdelta release (checks both hashes).')
    a.add_argument('--source', type=Path, required=True, help='untouched ULUS10193 USA v1.01 ISO')
    a.add_argument('--manifest', type=Path, required=True)
    a.add_argument('--output', type=Path, required=True)
    a.add_argument('--xdelta', default='xdelta3', help='xdelta3 executable path')
    args = a.parse_args()
    m = json.loads(args.manifest.read_text(encoding='utf-8-sig'))
    if m.get('game_id') != 'ULUS10193' or m.get('version') != 'v0.1.0-beta':
        raise RuntimeError('Unsupported manifest/version')
    source = args.source.resolve()
    out = args.output.resolve()
    if source == out:
        raise RuntimeError('Output must not equal source ISO')
    if out.exists():
        raise RuntimeError('Refusing to overwrite existing output ISO')
    tmp = out.with_name(out.name + '.incomplete')
    if tmp.exists():
        raise RuntimeError('Previous incomplete output exists; inspect/remove it yourself')
    check_file(source, m['original_iso'], 'Original ISO')
    out.parent.mkdir(parents=True, exist_ok=True)
    patch = None
    joined = False
    try:
        patch, joined = assemble(m, args.manifest.parent.resolve(), out.parent)
        print('Applying patch; untouched input will be preserved...', flush=True)
        cp = subprocess.run([args.xdelta, '-d', '-f', '-s', str(source), str(patch), str(tmp)], check=False)
        if cp.returncode:
            raise RuntimeError(f'xdelta3 exited with code {cp.returncode}')
        check_file(tmp, m['patched_iso'], 'Recreated Korean ISO')
        os.replace(tmp, out)
        print(f'SUCCESS: {out}', flush=True)
    finally:
        if tmp.exists():
            tmp.unlink()
        if joined and patch is not None and patch.exists():
            patch.unlink()


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f'FAILED: {e}', file=sys.stderr)
        sys.exit(1)
