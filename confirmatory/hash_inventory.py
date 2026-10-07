#!/usr/bin/env python3
"""Refresh or verify the complete registration-package hash inventory offline."""
import argparse
import hashlib
from pathlib import Path

P = Path(__file__).resolve().parent

def files():
 return sorted(p for p in P.rglob('*') if p.is_file() and p.name != 'SHA256SUMS'
               and '__pycache__' not in p.parts and p.suffix not in ['.pyc', '.pyo'])

def digest(p):
 return hashlib.sha256(p.read_bytes()).hexdigest()

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--verify', action='store_true')
args = parser.parse_args()
lines = [f'{digest(p)}  {p.relative_to(P).as_posix()}' for p in files()]
expected = '\n'.join(lines) + '\n'
if args.verify:
 assert (P / 'SHA256SUMS').read_text() == expected, 'Hash mismatch or unlisted/missing active file'
else:
 (P / 'SHA256SUMS').write_text(expected)
print(f'{"Verified" if args.verify else "Inventoried"} {len(lines)} active files')
