#!/usr/bin/env python3
"""Hash release files after an authorized draft update; no source mutation."""
import argparse
import hashlib
import json
from pathlib import Path


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--release-root',type=Path,default=Path(__file__).resolve().parents[1])
    args=ap.parse_args();root=args.release_root.resolve();files=[]
    for p in sorted(root.rglob('*')):
        if not p.is_file() or p.is_symlink() or p.name=='FILE_MANIFEST.json' or '__pycache__' in p.parts:continue
        with p.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
        files.append({'path':str(p.relative_to(root)),'bytes':p.stat().st_size,'sha256':digest})
    result={'role':'draft_release_file_manifest_not_external_timestamp','algorithm':'SHA-256','manifest_excludes_itself':True,'file_count_excluding_manifest':len(files),'total_bytes_excluding_manifest':sum(r['bytes'] for r in files),'files':files}
    (root/'FILE_MANIFEST.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='files'},indent=2))


if __name__=='__main__':main()
