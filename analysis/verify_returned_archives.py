#!/usr/bin/env python3
"""Read-only size/SHA-256 verification of manually returned archive chunks.

No network, no extraction, no deletion and no campaign-file changes.
Place each Drive download at RETURN_ROOT/ARCHIVE_ID/ORIGINAL_CHUNK_NAME.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('inventory', type=Path)
parser.add_argument('return_root', type=Path)
parser.add_argument('--archive', help='Check one named archive; otherwise all inventory objects')
args = parser.parse_args()
inventory = json.loads(args.inventory.read_text())
if args.archive:
    inventory = [row for row in inventory if row['id'] == args.archive]
    if not inventory:
        parser.error('Archive ID is absent from inventory')

reports = []
for row in inventory:
    full = hashlib.sha256()
    report = {'archive': row['id'], 'chunks': [], 'passed': False}
    complete = True
    for chunk in row['chunks']:
        path = args.return_root / row['id'] / chunk['name']
        record = {'path': str(path), 'expected_bytes': chunk['bytes'],
                  'expected_sha256': chunk['sha256'], 'passed': False}
        if not path.is_file():
            record['status'] = 'MISSING'; complete = False
        else:
            h = hashlib.sha256()
            with path.open('rb') as source:
                for block in iter(lambda: source.read(16 * 1024 * 1024), b''):
                    h.update(block); full.update(block)
            record['bytes'] = path.stat().st_size
            record['sha256'] = h.hexdigest()
            record['passed'] = (record['bytes'] == chunk['bytes'] and
                                record['sha256'] == chunk['sha256'])
            record['status'] = 'PASS' if record['passed'] else 'MISMATCH'
            complete = complete and record['passed']
        report['chunks'].append(record)
    if complete:
        report['full_compressed_sha256'] = full.hexdigest()
        report['expected_full_compressed_sha256'] = row['full_compressed_sha256']
        report['passed'] = full.hexdigest() == row['full_compressed_sha256']
    reports.append(report)

summary = {'scope': 'Returned compressed bytes only; not original member reconstruction',
           'archives': len(reports), 'passed': sum(x['passed'] for x in reports),
           'missing_chunks': sum(c['status'] == 'MISSING' for x in reports for c in x['chunks']),
           'mismatched_chunks': sum(c['status'] == 'MISMATCH' for x in reports for c in x['chunks']),
           'results': reports}
print(json.dumps(summary, indent=2))
sys.exit(0 if all(x['passed'] for x in reports) else 1)
