"""Consume one prospectively recorded, unused original environment qualification slot."""
import datetime,json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT))
from provision_vm import save,sha,gate,disk_check
import qualification_environment as host
import independent_audit

def main():
 gate();host.verify_frozen_base();disk_check(3*1024**3)
 plan=json.loads((HERE/'QUALIFICATION_PLAN_001.json').read_text());a=plan['assignment']
 if a!=next(x for x in host.assignments() if x['trial_id']==a['trial_id']):raise RuntimeError('Frozen assignment differs')
 if (host.ATTEMPTS/a['trial_id']).exists():raise RuntimeError('Qualification slot already consumed')
 for n,h in plan['source_hashes'].items():
  if sha(HERE/n)!=h or sha(HERE/'EXECUTED_SOURCE'/n)!=h:raise RuntimeError('Source input differs: '+n)
 save(HERE/'QUALIFICATION_CONSUMED_001.json',{'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'trial_id':a['trial_id'],'scientific_started':0,'automatic_retry':False})
 passed=host.run_one(a);audit=None
 if passed:
  try:audit=independent_audit.audit(a)
  except Exception as e:audit={'independent_pass':False,'audit_error':repr(e)}
 save(HERE/'QUALIFICATION_VERIFICATION_001.json',{'controller_passed':passed,'audit':audit,'scientific_started':0,'campaign_ready':False})
 save(HERE/'QUALIFICATION_STOP_001.json',{'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'controller_passed':passed,'independent_pass':bool(audit and audit['independent_pass']),'automatic_retry':False,'scientific_started':0})
 if not passed or not audit or not audit['independent_pass']:raise SystemExit(2)
if __name__=='__main__':main()
