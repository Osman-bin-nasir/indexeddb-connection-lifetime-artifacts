"""Bounded, once-only excluded qualification. No scientific acquisition code."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
ROOT=Path(__file__).resolve().parents[2]
ADMIN=Path(__file__).parent
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ADMIN))
from qualification_candidate import assignments,run_one
from provision_vm import sha,disk_check,save

def stamp():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def atomic(path,value):
    temp=path.with_suffix(path.suffix+'.tmp')
    with temp.open('w') as f:json.dump(value,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
    os.replace(temp,path)

def integrity(out):
    inventory=json.loads((out/'SHA256.json').read_text())
    if any(sha(out/n)!=h for n,h in inventory.items()):raise RuntimeError('Raw inventory mismatch: '+out.name)
    r=json.loads((out/'RESULT.json').read_text())
    if r['scientific_denominator'] or r['scientific_assignments_started']:raise RuntimeError('Unexpected scientific role')
    return r

def execute():
    plan=json.loads((ADMIN/'QUALIFICATION_BATCH_PLAN.json').read_text())
    lock=json.loads((ADMIN/'QUALIFICATION_BATCH_HASHES.json').read_text())
    if (ADMIN/'QUALIFICATION_BATCH_STARTED.json').exists():raise RuntimeError('Batch already started; no automatic restart')
    verify_inputs(lock)
    smoke=json.loads((ADMIN/'SMOKE_VERIFICATION.json').read_text())
    if not smoke['independent_smoke_pass']:raise RuntimeError('Required repaired-path smoke did not pass')
    expected={a['trial_id']:a for a in assignments()}
    for a in plan['assignments']:
        if expected.get(a['trial_id'])!=a or a['role']!='qualification':raise RuntimeError('Frozen assignment mismatch')
        if (ROOT/'qualification/attempts'/a['trial_id']).exists():raise RuntimeError('Assigned trial already attempted')
    disk_check(3*1024**3)
    save(ADMIN/'QUALIFICATION_BATCH_STARTED.json',{'started_utc':stamp(),'maximum_assigned_attempts':len(plan['assignments']),
        'science_authorized_in_this_runner':False,'automatic_retry':False})
    snapshot=ADMIN/'BATCH_EXECUTED_SOURCE';snapshot.mkdir(exist_ok=False)
    for name in lock:
        (snapshot/name).write_bytes((ADMIN/name).read_bytes())
    completed=[];failure=None;current=None
    try:
        for index,a in enumerate(plan['assignments']):
            verify_inputs(lock);disk_check(3*1024**3)
            current=a['trial_id']
            update(plan,completed,current,'RUNNING_EXCLUDED_QUALIFICATION',None)
            print(json.dumps({'batch_index':index+1,'trial_id':current,'scientific_started':0,'utc':stamp()}),flush=True)
            passed=run_one(a)
            result=integrity(ROOT/'qualification/attempts'/current)
            completed.append(result)
            if not passed or not result['qualification_passed']:
                failure={'trial_id':current,'reasons':result['reasons'],'endpoint':result['endpoint']};break
            current=None
    except Exception as e:
        failure={'trial_id':current,'error':repr(e)}
    status='STOPPED_FAILURE_NO_RETRY' if failure else 'SUPPORTED_CELL_QUALIFICATION_BATCH_COMPLETE'
    update(plan,completed,current,status,failure)
    save(ADMIN/'QUALIFICATION_BATCH_STOP.json',{'stopped_utc':stamp(),'status':status,'finished_attempts':len(completed),
        'failure':failure,'scientific_started':0,'scientific_batch_started':False,'further_qualification_launched':False})
    print(json.dumps({'status':status,'finished':len(completed),'failure':failure,'scientific_started':0}),flush=True)
    if failure:raise SystemExit(2)

def verify_inputs(lock):
    for name,digest in lock.items():
        if sha(ADMIN/name)!=digest:raise RuntimeError('Batch input changed: '+name)
    frozen=ROOT.parent/'confirmatory'
    for line in (frozen/'SHA256SUMS').read_text().splitlines():
        h,n=line.split(maxsplit=1)
        if sha(frozen/n.strip())!=h:raise RuntimeError('Frozen design changed')

def update(plan,completed,current,status,failure):
    elapsed=sum(x['wall_seconds'] for x in completed)
    remaining=len(plan['assignments'])-len(completed)
    estimate=(elapsed/len(completed)*remaining) if completed else None
    value={'updated_utc':stamp(),'status':status,'assigned_excluded_qualifications':len(plan['assignments']),
        'finished_attempts':len(completed),'passed':sum(x['qualification_passed'] for x in completed),
        'failed':sum(not x['qualification_passed'] for x in completed),'current_trial':current,
        'unstarted_after_current':remaining-(1 if current and current not in {x['trial_id'] for x in completed} else 0),
        'failure':failure,'disk_free_bytes':shutil.disk_usage(ROOT).free,'disk_floor_bytes':6*1024**3,
        'estimated_remaining_qualification_seconds':estimate,'eta_scope':'this excluded qualification batch only; excludes unimplemented families and scientific acquisition',
        'scientific_assigned':930,'scientific_started':0,'unsupported_qualification_cells':56,
        'automatic_retry':False,'completed_trial_ids':[x['trial_id'] for x in completed]}
    atomic(ADMIN/'QUALIFICATION_BATCH_STATUS.json',value)
    (ADMIN/'QUALIFICATION_BATCH_STATUS.md').write_text(f'''# Excluded qualification batch status

Updated UTC: {value['updated_utc']}. Status: {status}.
Assigned: {len(plan['assignments'])}. Finished: {len(completed)}. Passed: {value['passed']}. Failed: {value['failed']}.
Current: {current}. Scientific trials started: **0 / 930**.
Missing execution paths: 56 qualification cells. No scientific batch is running.
Estimated remaining seconds for this qualification batch only: {estimate}.
Disk free GiB: {value['disk_free_bytes']/1024**3:.3f}; hard floor: 6 GiB.
Failure: {failure}. No automatic retry.
''')

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('command',choices=['run','status']);a=ap.parse_args()
    if a.command=='run':execute()
    else:
        p=ADMIN/'QUALIFICATION_BATCH_STATUS.json'
        print(p.read_text() if p.exists() else '{"status":"NOT_STARTED","scientific_started":0}')
if __name__=='__main__':main()
