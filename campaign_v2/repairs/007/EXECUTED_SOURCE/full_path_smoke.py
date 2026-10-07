"""One fresh excluded attempt of the failed condition; stop on any failure."""
import datetime,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];ADMIN=Path(__file__).parent
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ADMIN))
from provision_vm import sha,save,disk_check,gate
from qualification_workloads import run_one,verify_frozen_base
from independent_audit import audit

def main():
 if (ADMIN/'SMOKE_CONSUMED.json').exists():raise RuntimeError('Already consumed; no retry')
 lock=json.loads((ADMIN/'EXECUTION_SOURCE_HASHES.json').read_text())
 for n,h in lock.items():
  if sha(ADMIN/n)!=h:raise RuntimeError('Prospective source changed: '+n)
 gate();verify_frozen_base();disk_check(3*1024**3)
 for line in (ROOT.parent/'confirmatory/SHA256SUMS').read_text().splitlines():
  h,n=line.split(maxsplit=1)
  if sha(ROOT.parent/'confirmatory'/n.strip())!=h:raise RuntimeError('Frozen design changed')
 a=json.loads((ADMIN/'FULL_PATH_SMOKE_ASSIGNMENT.json').read_text())
 snapshot=ADMIN/'EXECUTED_SOURCE';snapshot.mkdir(exist_ok=False)
 for n in lock:(snapshot/n).write_bytes((ADMIN/n).read_bytes())
 save(ADMIN/'SMOKE_CONSUMED.json',{'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'trial_id':a['trial_id'],'maximum_attempts':1,'scientific_acquisition':False,'osf_posting_before_smoke':False})
 passed=run_one(a)
 try:review=audit(a)
 except Exception as e:review={'trial_id':a['trial_id'],'independent_pass':False,'error':repr(e)}
 save(ADMIN/'SMOKE_VERIFICATION.json',review)
 save(ADMIN/'FULL_PATH_SMOKE_STOP.json',{'controller_passed':passed,'independent_pass':review['independent_pass'],'scientific_started':0,'automatic_retry':False})
 print(json.dumps(review,indent=2),flush=True)
 if not passed or not review['independent_pass']:raise SystemExit(2)
if __name__=='__main__':main()
