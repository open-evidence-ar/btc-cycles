#!/usr/bin/env python3
"""Normalize LF working tree and recompute manifest hashes to match stored LF blobs."""
from __future__ import annotations
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
MANIFEST = RAW / "manifest.txt"

def sha(text: bytes) -> str:
    return hashlib.sha256(text).hexdigest()

def lf_bytes(path: Path) -> bytes:
    raw = path.read_bytes()
    return raw.replace(b"\r\n", b"\n")

def main() -> int:
    if not MANIFEST.is_file():
        print("manifest.txt missing", file=sys.stderr)
        return 1
    lines = MANIFEST.read_text(encoding="utf-8").splitlines()
    header = lines[0]
    out = [header]
    changed = []
    for ln in lines[1:]:
        if not ln.strip():
            continue
        cells = ln.split("\t")
        assert len(cells) >= 6, f"bad manifest row: {ln}"
        filename = cells[-1]
        path = RAW / filename
        if not path.is_file():
            print(f"MISSING file: {filename}", file=sys.stderr)
            continue
        new_sha = sha(lf_bytes(path))
        if new_sha != cells[5]:
            changed.append(f"{filename}: {cells[5]} -> {new_sha}")
            cells[5] = new_sha
        out.append("\t".join(cells))
    MANIFEST.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"updated {len(changed)} manifest sha256 entries")
    for c in changed:
        print("  " + c)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())