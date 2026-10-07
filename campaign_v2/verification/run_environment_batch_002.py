"""Bounded once-only environment qualification; preserve attempts and stop on first failure."""
import datetime,json,os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];HERE=ROOT/'extensions/environment'
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(HERE))
from provision_vm import gate,sha,save,disk_check
import qualification_environment as host
from independent_audit import audit

def atomic(p,v):
 t=p.with_suffix('.tmp');t.write_text(json.dumps(v,indent=2)+'\n');os.replace(t,p)
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def main():
 plan=json.loads((HERE/'QUALIFICATION_BATCH_PLAN_002.json').read_text());rows=[];current=None;error=None
 def status(state):
  atomic(HERE/'QUALIFICATION_BATCH_STATUS_002.json',{'utc':now(),'status':state,'assigned_excluded':len(plan['assignments']),'started':len(rows)+(current is not None),'finished':len(rows),'independently_passed':sum(r.get('independent_pass') is True for r in rows),'failed':sum(r.get('independent_pass') is not True for r in rows),'current':current,'remaining':len(plan['assignments'])-len(rows)-(current is not None),'attempts':rows,'failure':error,'disk_free_bytes':__import__('shutil').disk_usage(ROOT).free,'scientific_started':0,'automatic_retry':False})
 gate();host.verify_frozen_base();disk_check(3*1024**3)
 first=json.loads((HERE/'QUALIFICATION_VERIFICATION_001.json').read_text())
 if not first['controller_passed'] or not first['audit']['independent_pass']:raise RuntimeError('First environment slot not independently qualified')
 for n,h in plan['source_hashes'].items():
  if sha(ROOT/n)!=h:raise RuntimeError('Prospective source changed '+n)
 frozen={a['trial_id']:a for a in host.assignments()}
 for a in plan['assignments']:
  if a!=frozen[a['trial_id']] or (host.ATTEMPTS/a['trial_id']).exists():raise RuntimeError('Assignment changed or consumed '+a['trial_id'])
 save(HERE/'QUALIFICATION_BATCH_CONSUMED_002.json',{'utc':now(),'maximum_attempts':15,'scientific_started':0,'automatic_retry':False});status('RUNNING')
 try:
  for a in plan['assignments']:
   for n,h in plan['source_hashes'].items():
    if sha(ROOT/n)!=h:raise RuntimeError('Input changed mid-batch '+n)
   disk_check(3*1024**3);current=a['trial_id'];status('RUNNING')
   passed=host.run_one(a)
   try:r=audit(a)
   except Exception as e:r={'trial_id':a['trial_id'],'independent_pass':False,'audit_error':repr(e)}
   r['controller_pass']=passed;rows.append(r);current=None;status('RUNNING')
   os.system('python3 '+__import__('shlex').quote(str(ROOT/'verification/campaign_progress_v4.py')))
   if not passed or not r['independent_pass']:raise RuntimeError('First failed qualification stopped the batch: '+a['trial_id'])
  status('ENVIRONMENT_QUALIFIED_OTHER_GATES_PENDING')
 except BaseException as e:error=repr(e);status('STOPPED_FAILURE');raise
 finally:
  save(HERE/'QUALIFICATION_BATCH_STOP_002.json',{'utc':now(),'passed':error is None and len(rows)==len(plan['assignments']),'finished':len(rows),'error':error,'automatic_retry':False,'scientific_started':0})
if __name__=='__main__':main()
