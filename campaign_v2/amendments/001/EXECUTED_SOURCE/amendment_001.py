"""Exactly one author-approved excluded attempt. No original-slot continuation or retry."""
import argparse
import datetime
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys

from provision_vm import ROOT,BASE as PUBLIC_BASE,sha,save,disk_check,gate
from qualification import BASE,SEED,KEY,ATTEMPTS,assignments,verify_frozen_base,run_one

NEW_ID='qualification-amendment-001-close_aligned_recovery_grid-00001'
OLD_ID='qualification-close_aligned_recovery_grid-00001'
ADMIN=ROOT/'amendments/001'
TAG='prereg-connection-lifetime-mac-v2'
TAG_OBJECT='3d67e066f112810738788550ff4c5d279d22eb8d'
TAG_COMMIT='5a749734a0a63f3e1c662bb91dd829e6f288dc5c'


def preflight(trial_id):
    if trial_id!=NEW_ID:raise RuntimeError('Only the exact amendment 001 ID is authorized')
    gate()
    approval=json.loads((ADMIN/'AUTHOR_APPROVAL_RECEIPT.json').read_text())
    if approval['authorized_qualification_ids']!=[NEW_ID] or approval['maximum_additional_attempts']!=1:
        raise RuntimeError('Approval scope mismatch')
    if approval['scientific_acquisition_authorized'] or approval['other_qualification_authorized']:
        raise RuntimeError('Unexpected authorization expansion')
    posted=json.loads((ADMIN/'OSF_POSTING_RECEIPT.json').read_text())
    if not posted['amendment_download_round_trip_verified'] or not posted['registration_metadata_link_verified']:
        raise RuntimeError('Prospective OSF posting/link has not been verified')
    for name in ['TECHNICAL_AMENDMENT_001.md','AUTHOR_APPROVAL_RECEIPT.json','ASSIGNMENT.json','EXECUTION_INPUTS.json']:
        if sha(ADMIN/name)!=posted['posted_file_hashes'][name]:raise RuntimeError('Posted amendment input changed: '+name)
    frozen=ROOT.parent/'confirmatory'
    for line in (frozen/'SHA256SUMS').read_text().splitlines():
        digest,name=line.split(maxsplit=1)
        if sha(frozen/name.strip())!=digest:raise RuntimeError('Frozen scientific file changed: '+name)
    local_object=subprocess.check_output(['git','rev-parse',TAG],cwd=ROOT,text=True).strip()
    local_commit=subprocess.check_output(['git','rev-parse',TAG+'^{}'],cwd=ROOT,text=True).strip()
    if (local_object,local_commit)!=(TAG_OBJECT,TAG_COMMIT):raise RuntimeError('Frozen local tag moved')
    remote=subprocess.check_output(['git','ls-remote','origin','refs/tags/'+TAG,'refs/tags/'+TAG+'^{}'],cwd=ROOT,text=True,timeout=30)
    remote_values={line.split()[1]:line.split()[0] for line in remote.splitlines()}
    if remote_values!={'refs/tags/'+TAG:TAG_OBJECT,'refs/tags/'+TAG+'^{}':TAG_COMMIT}:
        raise RuntimeError('Remote tag changed or is unavailable')
    if subprocess.check_output(['git','diff',TAG,'--','confirmatory'],cwd=ROOT.parent,text=True):
        raise RuntimeError('Frozen tracked design differs from tag')
    original=ATTEMPTS/OLD_ID
    current_files={str(p.relative_to(original)):sha(p) for p in sorted(original.rglob('*')) if p.is_file()}
    if current_files!=approval['original_preserved_inventory']:raise RuntimeError('Original failed evidence changed')
    old_result=json.loads((original/'RESULT.json').read_text())
    if old_result['endpoint']!='unknown' or old_result['qualification_passed']:raise RuntimeError('Original failure was reclassified')
    new=json.loads((ADMIN/'ASSIGNMENT.json').read_text())
    old=json.loads((original/'assignment.json').read_text())
    expected={**old,'trial_id':NEW_ID,'amendment_id':'001','original_failed_qualification_id':OLD_ID,'separate_amendment_ledger':True}
    if new!=expected:raise RuntimeError('Amendment condition differs from original registered condition')
    if NEW_ID in {x['trial_id'] for x in assignments()}:raise RuntimeError('Amendment ID overlaps frozen assignments')
    if (ATTEMPTS/NEW_ID).exists() or (ADMIN/'CONSUMPTION.json').exists():
        raise RuntimeError('Amendment authorization already consumed or attempted; no retry')
    lock=verify_frozen_base()
    if sha(PUBLIC_BASE)!=lock['public_base_sha256'] or sha(SEED)!=lock['seed_sha256']:
        raise RuntimeError('Public base or seed changed')
    inputs=json.loads((ADMIN/'EXECUTION_INPUTS.json').read_text())
    for name,digest in inputs['source_sha256'].items():
        if sha(ROOT/name)!=digest:raise RuntimeError('Execution source changed after prospective hash lock: '+name)
    if not KEY.exists() or KEY.stat().st_mode&0o077:raise RuntimeError('Private guest key missing or permissions too broad')
    with socket.socket() as s:s.bind(('127.0.0.1',2233))
    free=disk_check(3*1024**3)
    manifest=json.loads((frozen/'design/MANIFEST.json').read_text())
    total=sum(f['assignments'] for f in manifest['experiments'] if not f['optional'])
    if total!=930:raise RuntimeError('Scientific assignment count changed')
    return {'status':'PASS','checked_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'trial_id':NEW_ID,'original_failed_id':OLD_ID,'original_evidence_unchanged':True,
        'original_endpoint':'unknown','new_id_separate':True,'frozen_files_verified':30,
        'local_tag_object':local_object,'local_tag_commit':local_commit,'remote_tag_verified':True,
        'scientific_assigned':930,'scientific_authorized':False,'other_qualification_authorized':False,
        'registered_qualifications':95,'additional_qualification_authorized':1,'original_unstarted_qualification':94,
        'osf_amendment_url':posted['amendment_url'],'osf_link_verified':True,'source_inputs_verified':True,
        'base_and_seed_hashes_verified':True,'disk_free_bytes':free,'disk_floor_bytes':6*1024**3,
        'operation_headroom_bytes':3*1024**3,'ssh_port_2233_available':True,
        'stop_after_this_attempt_regardless_of_outcome':True,
        'execution_command':f'caffeinate -dimsu python3 campaign_v2/amendment_001.py run --trial-id {NEW_ID}'}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('command',choices=['preflight','run'])
    ap.add_argument('--trial-id',required=True,choices=[NEW_ID])
    args=ap.parse_args()
    checked=preflight(args.trial_id)
    print(json.dumps(checked,indent=2),flush=True)
    if args.command=='preflight':
        save(ADMIN/('PREFLIGHT-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.json'),checked)
        return
    # Exclusive receipt consumes this approval even if interrupted before VM launch.
    save(ADMIN/'CONSUMPTION.json',{'trial_id':NEW_ID,'consumed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
         'preflight':checked,'exactly_one_attempt_authorized':True,'automatic_retry':False})
    snapshot=ADMIN/'EXECUTED_SOURCE';snapshot.mkdir(exist_ok=False)
    for name in json.loads((ADMIN/'EXECUTION_INPUTS.json').read_text())['source_sha256']:
        target=snapshot/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((ROOT/name).read_bytes())
    result=run_one(json.loads((ADMIN/'ASSIGNMENT.json').read_text()))
    # Verify preserved original separately; never rewrite its result or inventory.
    approval=json.loads((ADMIN/'AUTHOR_APPROVAL_RECEIPT.json').read_text())
    original=ATTEMPTS/OLD_ID
    current={str(p.relative_to(original)):sha(p) for p in sorted(original.rglob('*')) if p.is_file()}
    save(ADMIN/'EXECUTION_STOP.json',{'trial_id':NEW_ID,'stopped_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
         'qualification_passed_by_runner':result,'original_unchanged':current==approval['original_preserved_inventory'],
         'scientific_started':0,'further_qualification_authorized':False,'automatic_retry_authorized':False,
         'stop_after_single_amendment_attempt':True})
    if current!=approval['original_preserved_inventory']:raise RuntimeError('Original evidence integrity check failed')
    if not result:raise SystemExit(2)


if __name__=='__main__':main()
