#!/usr/bin/env python3
"""Verify local release assets without possessing game files."""
import json
import sys
from pathlib import Path
from apply_patch import check_file


def main():
    base = Path(sys.argv[1] if len(sys.argv) > 1 else 'manifest.json').resolve()
    m = json.loads(base.read_text(encoding='utf-8-sig'))
    for p in m['xdelta']['parts']:
        check_file(base.parent / p['filename'], p, p['filename'])
    print(f"Manifest targets game {m['game_id']}, version {m['version']}; original and patched ISO hashes require the user's own files.")


if __name__ == '__main__':
    main()
