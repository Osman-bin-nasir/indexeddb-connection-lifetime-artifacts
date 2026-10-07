"""Exactly one separately recorded author-requested excluded full-path smoke."""
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(Path(__file__).parent))
from provision_vm import save,sha
from qualification_candidate import run_one

def main():
    admin=Path(__file__).parent
    if (admin/'SMOKE_CONSUMED.json').exists():raise RuntimeError('Smoke already consumed; no automatic retry')
    spec=json.loads((admin/'FULL_PATH_SMOKE_ASSIGNMENT.json').read_text())
    lock=json.loads((admin/'SMOKE_EXECUTION_HASHES.json').read_text())
    for name,digest in lock.items():
        if sha(admin/name)!=digest:raise RuntimeError('Prospective smoke inputs changed')
    save(admin/'SMOKE_CONSUMED.json',{'trial_id':spec['trial_id'],'maximum_attempts':1,'scientific_acquisition':False,'osf_posting_before_smoke':False})
    passed=run_one(spec)
    save(admin/'FULL_PATH_SMOKE_STOP.json',{'passed_by_controller':passed,'scientific_started':0,'automatic_retry':False,'further_qualification_authorized_by_this_receipt':False})
    if not passed:raise SystemExit(2)

if __name__=='__main__':main()
