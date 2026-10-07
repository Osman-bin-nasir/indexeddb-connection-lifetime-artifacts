"""Once-only excluded twelve-cell qualification, after independent ordinary qualification."""
import argparse,datetime,json,os,shutil,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];ADMIN=Path(__file__).parent
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ADMIN))
from provision_vm import sha,save,disk_check
from qualification_workloads import assignments,run_one,verify_frozen_base
from independent_audit import audit

def stamp():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def atomic(path,value):
 tmp=path.with_suffix(path.suffix+'.tmp')
 with tmp.open('w') as f:json.dump(value,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
 os.replace(tmp,path)
def frozen():
 for line in (ROOT.parent/'confirmatory/SHA256SUMS').read_text().splitlines():
  h,n=line.split(maxsplit=1)
  if sha(ROOT.parent/'confirmatory'/n.strip())!=h:raise RuntimeError('Frozen design changed')
 if subprocess.check_output(['git','rev-parse','prereg-connection-lifetime-mac-v2^{}'],text=True).strip()!='5a749734a0a63f3e1c662bb91dd829e6f288dc5c':raise RuntimeError('Frozen tag changed')
def preflight():
 for n,h in json.loads((ADMIN/'EXECUTION_SOURCE_HASHES_V2.json').read_text()).items():
  if sha(ADMIN/n)!=h:raise RuntimeError('Extension input changed: '+n)
 frozen();verify_frozen_base();disk_check(3*1024**3)
 expected={a['trial_id']:a for a in assignments()}
 plan=json.loads((ADMIN/'QUALIFICATION_PLAN.json').read_text())
 if len(plan['assignments'])!=12:raise RuntimeError('Qualification count changed')
 for a in plan['assignments']:
  if expected.get(a['trial_id'])!=a:raise RuntimeError('Registered assignment changed')
 return plan

def ordinary_gate():
 p=ROOT/'extensions/fault_scope/STOP.json'
 if not p.exists():return False
 stop=json.loads(p.read_text());status=json.loads((p.parent/'STATUS.json').read_text())
 if stop['failure'] or stop['state']!='NONQMP_CELLS_QUALIFIED_OTHER_GATES_PENDING':raise RuntimeError('Preceding fault-scope batch failed; workload qualification remains stopped')
 if status['finished']!=8 or status['independently_passed']!=8 or status['failed']:raise RuntimeError('Preceding fault-scope final checks did not pass')
 cmd="import json,pathlib,sys; r=pathlib.Path('campaign_v2').resolve(); p=r/'extensions/fault_scope'; sys.path[:0]=[str(p),str(r)]; from independent_audit import audit; plan=json.loads((p/'QUALIFICATION_PLAN.json').read_text()); rows=[audit(a) for a in plan['assignments']]; assert all(x['independent_pass'] for x in rows); print(json.dumps({'audited':len(rows),'passed':True}))"
 result=subprocess.run([sys.executable,'-c',cmd],cwd=ROOT.parent,capture_output=True,check=True,timeout=120)
 save(ADMIN/'PRECEDING_GATE_VERIFICATION.json',{'utc':stamp(),'stdout':result.stdout.decode(),'stderr':result.stderr.decode(),'returncode':result.returncode,'scientific_started':0})
 return True

def update(plan,rows,current,state,error=None):
 atomic(ADMIN/'STATUS.json',{'utc':stamp(),'status':state,'assigned':12,'started':len(rows)+(1 if current and current not in {r['trial_id'] for r in rows} else 0),'finished':len(rows),'independently_passed':sum(r['independent_pass'] for r in rows),'failed':sum(not r['independent_pass'] for r in rows),'current':current,'remaining':12-len(rows),'rows':rows,'failure':error,'scientific_started':0,'disk_free_bytes':shutil.disk_usage(ROOT).free,'automatic_retry':False})

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('command',choices=['preflight','run-after-ordinary']);a=ap.parse_args();plan=preflight()
 if a.command=='preflight':print(json.dumps({'registered_cells':12,'source_inputs_match':True,'scientific_started':0,'preceding_fault_scope_completion_required':True}));return
 if (ADMIN/'SUPERVISOR_CONSUMED_V2.json').exists():raise RuntimeError('Supervisor consumed; no automatic restart')
 save(ADMIN/'SUPERVISOR_CONSUMED_V2.json',{'utc':stamp(),'maximum_attempts':12,'no_scientific_acquisition':True,'no_automatic_retry':True})
 rows=[];current=None;error=None
 try:
  until=time.monotonic()+7200
  while not ordinary_gate():
   preflight();update(plan,rows,None,'WAITING_FOR_FAULT_SCOPE_BATCH')
   if time.monotonic()>until:raise RuntimeError('Bounded wait elapsed; no qualification attempted')
   time.sleep(30)
  # Both source locks are verified before any extension attempt is consumed.
  for spec in plan['assignments']:
   if (ROOT/'qualification/attempts'/spec['trial_id']).exists():raise RuntimeError('Qualification ID already consumed')
  with __import__('socket').socket() as s:s.bind(('127.0.0.1',2233))
  snapshot=ADMIN/'EXECUTED_SOURCE';snapshot.mkdir(exist_ok=False)
  lock=json.loads((ADMIN/'EXECUTION_SOURCE_HASHES_V2.json').read_text())
  for n in lock:(snapshot/n).write_bytes((ADMIN/n).read_bytes())
  save(ADMIN/'START.json',{'utc':stamp(),'maximum_attempts':12,'scientific_started':0})
  for spec in plan['assignments']:
   preflight();current=spec['trial_id'];update(plan,rows,current,'RUNNING_EXCLUDED_QUALIFICATION')
   ok=run_one(spec)
   try:review=audit(spec)
   except Exception as e:
    r=json.loads((ROOT/'qualification/attempts'/current/'RESULT.json').read_text());review={'trial_id':current,'independent_pass':False,'endpoint':r['endpoint'],'reasons':r['reasons'],'audit_error':repr(e),'wall_seconds':r['wall_seconds']}
   rows.append(review)
   if not ok or not review['independent_pass']:error=review;break
   current=None
 except Exception as e:error={'trial_id':current,'error':repr(e)}
 state='STOPPED_FAILURE_NO_RETRY' if error else 'WORKLOAD_CELLS_QUALIFIED_OTHER_GATES_PENDING'
 update(plan,rows,current,state,error)
 save(ADMIN/'STOP.json',{'utc':stamp(),'state':state,'failure':error,'scientific_started':0,'no_retry':True})
 if error:raise SystemExit(2)
if __name__=='__main__':main()
