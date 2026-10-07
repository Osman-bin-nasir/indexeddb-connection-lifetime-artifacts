"""Once-only bounded qualification on the repaired base, never scientific acquisition."""
import datetime,json,os,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];ADMIN=ROOT/'repairs/009'
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ADMIN))
from provision_vm import sha,save,disk_check,gate
from qualification_fault_scope import assignments,run_one,verify_frozen_base
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
 gate();verify_frozen_base();disk_check(3*1024**3)
 import subprocess
 tag=subprocess.check_output(['git','rev-parse','prereg-connection-lifetime-mac-v2^{}'],cwd=ROOT,text=True).strip()
 if tag!='5a749734a0a63f3e1c662bb91dd829e6f288dc5c':raise RuntimeError('Frozen repository tag changed')
 if len(plan['assignments'])!=3:raise RuntimeError('Bounded qualification plan changed')
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
 value={'utc':stamp(),'status':state,'assigned_excluded':len(plan['assignments']),'finished':len(rows),'independently_passed':passed,'failed':len(rows)-passed,'current':current,'remaining':remaining,'failure':failure,'disk_free_bytes':shutil.disk_usage(ROOT).free,'scientific_assigned':930,'scientific_started':0,'qualified_cells_on_current_paths':52+passed,'required_cells':95,'qualification_only_remaining_seconds':eta,'automatic_retry':False,'attempts':rows}
 atomic(ADMIN/'QUALIFICATION_BATCH_STATUS.json',value)
 from campaign_progress_v3 import main as update
 update()
 (ADMIN/'QUALIFICATION_BATCH_STATUS.md').write_text(f"# Plan009 excluded SysRq qualification\n\nUpdated UTC: {value['utc']}. {state}.\n\nFinished {len(rows)}/{len(plan['assignments'])}, independently passed {passed}, failed {len(rows)-passed}. Current {current}. Scientific started **0/930**. Required cells qualified on repaired base: {52+passed}/95. Other registered methods remain unqualified. Remaining qualification-only estimate seconds: {eta}. Disk free: {value['disk_free_bytes']/1024**3:.3f} GiB. No automatic retry.\n")
def main():
 plan=json.loads((ADMIN/'QUALIFICATION_BATCH_PLAN.json').read_text());preflight(plan)
 if '--preflight' in sys.argv:
  print(json.dumps({'preflight':'passed','assigned_excluded':3,'scientific_started':0,'disk_free_gib':shutil.disk_usage(ROOT).free/1024**3}));return
 if (ADMIN/'QUALIFICATION_BATCH_STARTED.json').exists():raise RuntimeError('Consumed batch; no restart')
 if not json.loads((ADMIN/'SMOKE_VERIFICATION.json').read_text())['independent_pass']:raise RuntimeError('Smoke not independently passed')
 for a in plan['assignments']:
  if (ROOT/'qualification/attempts'/a['trial_id']).exists():raise RuntimeError('Consumed attempt')
 snapshot=ADMIN/'BATCH_EXECUTED_SOURCE';snapshot.mkdir(exist_ok=False)
 for n in json.loads((ADMIN/'BATCH_SOURCE_HASHES.json').read_text()):
  target=snapshot/n;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((ROOT/n).read_bytes())
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
 state='STOPPED_FAILURE_NO_RETRY' if failure else 'SYSRQ_CELLS_QUALIFIED_OTHER_GATES_PENDING'
 status(plan,rows,current,state,failure)
 save(ADMIN/'QUALIFICATION_BATCH_STOP.json',{'utc':stamp(),'state':state,'failure':failure,'scientific_started':0,'automatic_retry':False})
 if failure:raise SystemExit(2)
if __name__=='__main__':main()
