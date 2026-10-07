"""Once-only bounded qualification on the repaired base, never scientific acquisition."""
import datetime,json,os,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];ADMIN=ROOT/'repairs/004'
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ADMIN))
from provision_vm import sha,save,disk_check
from qualification_candidate import assignments,run_one,verify_frozen_base
from independent_audit import audit

def stamp():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def atomic(p,value):
 temp=p.with_suffix(p.suffix+'.tmp')
 with temp.open('w') as f:json.dump(value,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
 os.replace(temp,p)
def preflight(plan):
 locks=json.loads((ADMIN/'BATCH_SOURCE_HASHES.json').read_text())
 for n,h in locks.items():
  if sha(ROOT/n)!=h:raise RuntimeError('Locked batch input changed: '+n)
 verify_frozen_base();disk_check(3*1024**3)
 for line in (ROOT.parent/'confirmatory/SHA256SUMS').read_text().splitlines():
  h,n=line.split(maxsplit=1)
  if sha(ROOT.parent/'confirmatory'/n.strip())!=h:raise RuntimeError('Frozen design changed')
 expected={a['trial_id']:a for a in assignments()}
 for a in plan['assignments']:
  compare={k:v for k,v in a.items() if k not in ['original_qualification_id','technical_amendment_id','scientific_denominator']}
  compare['trial_id']=a['original_qualification_id']
  if compare!=expected[compare['trial_id']]:raise RuntimeError('Registered condition changed')
def status(plan,rows,current,state,failure=None):
 passed=sum(r['independent_pass'] for r in rows);remaining=len(plan['assignments'])-len(rows)
 seconds=sum(r.get('wall_seconds',0) for r in rows)
 eta=seconds/len(rows)*remaining if rows and state=='RUNNING_EXCLUDED_QUALIFICATION' else None
 value={'utc':stamp(),'status':state,'assigned_excluded':len(plan['assignments']),'finished':len(rows),'independently_passed':passed,'failed':len(rows)-passed,'current':current,'remaining':remaining,'failure':failure,'disk_free_bytes':shutil.disk_usage(ROOT).free,'scientific_assigned':930,'scientific_started':0,'qualified_cells_on_repaired_base':1+passed,'required_cells':95,'unimplemented_required_cells':56,'qualification_only_remaining_seconds':eta,'automatic_retry':False,'attempts':rows}
 atomic(ADMIN/'QUALIFICATION_BATCH_STATUS.json',value)
 from update_campaign_status import update
 update()
 (ADMIN/'QUALIFICATION_BATCH_STATUS.md').write_text(f"# Amendment 003 excluded qualification\n\nUpdated UTC: {value['utc']}. {state}.\n\nFinished {len(rows)}/{len(plan['assignments'])}, independently passed {passed}, failed {len(rows)-passed}. Current {current}. Scientific started **0/930**. Required cells qualified on repaired base: {1+passed}/95. Missing execution paths: 56. Remaining qualification-only estimate seconds: {eta}. Disk free: {value['disk_free_bytes']/1024**3:.3f} GiB. No automatic retry.\n")
def main():
 plan=json.loads((ADMIN/'QUALIFICATION_BATCH_PLAN.json').read_text());preflight(plan)
 if (ADMIN/'QUALIFICATION_BATCH_STARTED.json').exists():raise RuntimeError('Consumed batch; no restart')
 if not json.loads((ADMIN/'SMOKE_VERIFICATION.json').read_text())['independent_pass']:raise RuntimeError('Smoke not independently passed')
 for a in plan['assignments']:
  if (ROOT/'qualification/attempts'/a['trial_id']).exists():raise RuntimeError('Consumed attempt')
 save(ADMIN/'QUALIFICATION_BATCH_STARTED.json',{'utc':stamp(),'assigned':len(plan['assignments']),'role':'excluded_qualification','science':False,'automatic_retry':False})
 rows=[];failure=None;current=None
 try:
  for a in plan['assignments']:
   preflight(plan);current=a['trial_id'];status(plan,rows,current,'RUNNING_EXCLUDED_QUALIFICATION')
   print(json.dumps({'utc':stamp(),'trial_id':current,'scientific_started':0}),flush=True)
   ok=run_one(a)
   try:review=audit(a)
   except Exception as e:
    result=json.loads((ROOT/'qualification/attempts'/current/'RESULT.json').read_text());review={'trial_id':current,'independent_pass':False,'endpoint':result['endpoint'],'wall_seconds':result['wall_seconds'],'reasons':result['reasons'],'audit_error':repr(e)}
   rows.append(review)
   if not ok or not review['independent_pass']:failure=review;break
   current=None
 except Exception as e:failure={'trial_id':current,'error':repr(e)}
 state='STOPPED_FAILURE_NO_RETRY' if failure else 'IMPLEMENTED_CELLS_QUALIFIED_OTHER_GATES_PENDING'
 status(plan,rows,current,state,failure)
 save(ADMIN/'QUALIFICATION_BATCH_STOP.json',{'utc':stamp(),'state':state,'failure':failure,'scientific_started':0,'automatic_retry':False})
 if failure:raise SystemExit(2)
if __name__=='__main__':main()
