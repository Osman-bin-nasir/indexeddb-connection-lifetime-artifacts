"""Run a prospectively hash-bound bounded qualification job once; stop on first failure."""
import argparse,datetime,hashlib,importlib,json,os,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from provision_vm import gate,sha,save,disk_check

def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def atomic(p,v):
 t=p.with_suffix('.tmp');t.write_text(json.dumps(v,indent=2)+'\n');os.replace(t,p)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--plan',required=True,type=Path);args=ap.parse_args()
 plan=json.loads(args.plan.read_text());folder=args.plan.parent;rows=[];current=None;error=None
 gate();disk_check(3*1024**3)
 for n,h in plan['source_hashes'].items():
  if sha(ROOT/n)!=h:raise RuntimeError('Prospective job source differs '+n)
 tag=subprocess.check_output(['git','rev-parse','prereg-connection-lifetime-mac-v2^{commit}'],cwd=ROOT,text=True).strip()
 if tag!=plan['frozen_tag_commit']:raise RuntimeError('Frozen tag differs')
 for line in (ROOT.parent/'confirmatory/SHA256SUMS').read_text().splitlines():
  h,n=line.split(maxsplit=1)
  if sha(ROOT.parent/'confirmatory'/n.strip())!=h:raise RuntimeError('Frozen scientific design differs')
 sys.path.insert(0,str(ROOT/plan['source_directory']))
 host=importlib.import_module(plan['candidate_module']);audit=importlib.import_module('independent_audit').audit
 host.verify_frozen_base();frozen={a['trial_id']:a for a in host.assignments()}
 for a in plan['assignments']:
  original=a.get('original_qualification_id',a['trial_id']);canonical={k:v for k,v in a.items() if k not in ['original_qualification_id','technical_amendment_id','scientific_denominator']};canonical['trial_id']=original
  if canonical!=frozen[original] or a['role']!='qualification':raise RuntimeError('Condition differs from frozen qualification')
  if (host.ATTEMPTS/a['trial_id']).exists():raise RuntimeError('Consumed attempt ID '+a['trial_id'])
 def status(state):
  atomic(folder/(plan['job_id']+'_STATUS.json'),{'utc':now(),'state':state,'maximum_attempts':len(plan['assignments']),'finished':len(rows),'independently_passed':sum(x.get('independent_pass') is True for x in rows),'current':current,'remaining':len(plan['assignments'])-len(rows)-(current is not None),'attempts':rows,'error':error,'scientific_started':0,'automatic_retry':False,'free_bytes':shutil.disk_usage(ROOT).free})
 save(folder/(plan['job_id']+'_CONSUMED.json'),{'utc':now(),'maximum_attempts':len(plan['assignments']),'scientific_started':0,'automatic_retry':False})
 try:
  for a in plan['assignments']:
   for n,h in plan['source_hashes'].items():
    if sha(ROOT/n)!=h:raise RuntimeError('Source changed mid-job '+n)
   disk_check(3*1024**3);current=a['trial_id'];status('RUNNING')
   passed=host.run_one(a)
   try:r=audit(a)
   except BaseException as e:r={'trial_id':a['trial_id'],'independent_pass':False,'audit_error':repr(e)}
   r['controller_pass']=passed;save(folder/('AUDIT_'+a['trial_id']+'.json'),r);rows.append(r);current=None;status('RUNNING')
   if not passed or not r['independent_pass']:raise RuntimeError('Qualification job stopped on first failure: '+a['trial_id'])
  status('QUALIFIED_OTHER_CAMPAIGN_GATES_PENDING')
 except BaseException as e:error=repr(e);status('STOPPED_FAILURE');raise
 finally:save(folder/(plan['job_id']+'_STOP.json'),{'utc':now(),'passed':error is None and len(rows)==len(plan['assignments']),'finished':len(rows),'error':error,'scientific_started':0,'automatic_retry':False})
if __name__=='__main__':main()
