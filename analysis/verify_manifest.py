#!/usr/bin/env python3
"""Verify a prepared release manifest only. Never acquires or repairs data."""
import argparse
import hashlib
import json
from pathlib import Path


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--release-root',type=Path,default=Path(__file__).resolve().parents[1])
    args=ap.parse_args();root=args.release_root.resolve()
    manifest=json.loads((root/'FILE_MANIFEST.json').read_text())
    errors=[];checked=0
    for row in manifest['files']:
        rel=Path(row['path'])
        if rel.is_absolute() or '..' in rel.parts:
            errors.append({'path':row['path'],'reason':'Unsafe relative path in manifest'});continue
        p=root/rel
        if not p.is_file() or p.is_symlink():errors.append({'path':row['path'],'reason':'Missing or symbolic link'});continue
        with p.open('rb') as f:got=hashlib.file_digest(f,'sha256').hexdigest()
        if got!=row['sha256'] or p.stat().st_size!=row['bytes']:errors.append({'path':row['path'],'reason':'Hash or byte count mismatch'})
        checked+=1
    print(json.dumps({'role':'release_file_integrity_only_not_remote_archive_or_image_recovery_verification','files_checked':checked,'files_expected':len(manifest['files']),'passed':not errors,'errors':errors},indent=2))
    raise SystemExit(bool(errors))


if __name__=='__main__':main()
