"""Bounded continuation through a separately locked scientific audit correction."""
import argparse,datetime,importlib.util,json,os,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE))
from correction_lock import verify_addendum,effective_verification,sha,read
from pin_contract import VERSION
spec=importlib.util.spec_from_file_location('preserved_operator_v4',ROOT/'operator/operator_v4.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
b=m.base

def verify_attempt(out):
 b.inventory_check(out);m.retention.verify_inventory(out,'OPERATOR_SHA256.json')
 r=read(out/'RESULT.json');b.validate_result(r)
 review,source=effective_verification(out)
 if review.get('trial_id')!=out.name or review.get('scientific_denominator') is not True or review.get('independent_pass') is not True:
  raise RuntimeError('Independent scientific verification failed: '+out.name)
 if r.get('technical_eligible') is not True or r['endpoint'] not in ('recovered','lost'):
  raise RuntimeError('Unresolved scientific endpoint: '+out.name)
 return {'trial_id':out.name,'eligible':True,'registered_endpoint':read(out/'REGISTERED_ENDPOINT.json')['registered_endpoint'],'audit_source':source}

def counts():
 value=b.status(write=False);eligible=0;failures=[]
 for a in b.assignments():
  out=b.SCI/a['trial_id']
  if not out.exists():continue
  try:
   review,source=effective_verification(out);r=read(out/'RESULT.json')
   if review.get('independent_pass') is True and review.get('scientific_denominator') is True and r.get('technical_eligible') is True and r.get('endpoint') in ('lost','recovered'):eligible+=1
   else:failures.append(a['trial_id'])
  except Exception as e:failures.append({'trial_id':a['trial_id'],'error':repr(e)})
 value.update(independent_valid_total=eligible,eligible_scientific_count=eligible,unresolved_independent_failures=failures,historical_validator_rejections=1,resolved_validator_rejections=1,validator_version=VERSION,scientific_acquisition_ready=False,new_scientific_attempts_this_correction=0)
 return value

def selected(n):
 if not 1<=n<=20:raise RuntimeError('Bounded continuation must contain1-20 assignments')
 schedule=b.assignments();chosen=[a for a in schedule if not (b.SCI/a['trial_id']).exists()][:n]
 if len(chosen)!=n:raise RuntimeError('Insufficient unused assignments')
 release=read(ROOT/'operator/ACQUISITION_RELEASE_003.json')
 if any(a['trial_id'] not in release['assignment_ids_authorized'] for a in chosen):raise RuntimeError('Outside the existing221-420 authorization')
 return chosen

def resource(chosen):
 lock=read(ROOT/'operator/FINAL_INPUT_LOCK.json');q=read(ROOT/lock['qualification_receipt'])
 costs={(r['family'],r['condition_id']):2*r['allocated_bytes'] for r in q['cells']}
 scratch=read(ROOT/'operator/BOUNDED_RESOURCE_RECEIPT_RESUME006_002.json')['archive_scratch_headroom_bytes']
 headroom=max(lock['operation_headroom_bytes'],sum(costs[a['experiment'],a['condition_id']] for a in chosen)+scratch)
 return {'method':'twice the measured qualified allocation for each exact assignment plus unchanged archive scratch; maximum with frozen operation headroom','assignment_ids':[a['trial_id'] for a in chosen],'trial_headroom_bytes':sum(costs[a['experiment'],a['condition_id']] for a in chosen),'archive_scratch_headroom_bytes':scratch,'disk':b.disk_check(headroom)}

def preflight(digest,n=1):
 addendum=verify_addendum(digest)
 original=m.preflight()
 for a in b.assignments():
  out=b.SCI/a['trial_id']
  if out.exists():verify_attempt(out)
 chosen=selected(n)
 return {'utc':b.now(),'passed':True,'validator_version':VERSION,'addendum_sha256':digest,'frozen_preflight':original,'next_trial_id':chosen[0]['trial_id'],'selected_assignments':[a['trial_id'] for a in chosen],'resources':resource(chosen),'original_failures_preserved':True,'no_attempt_started':True,'osf_correction_posting':'local amendment recorded; not yet posted'}

def batch(digest,n):
 check=preflight(digest,n);chosen=selected(n);lock=read(ROOT/'operator/FINAL_INPUT_LOCK.json')
 fd=os.open(ROOT/'operator/RUNNING.lock',os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.write(fd,str(os.getpid()).encode());os.close(fd)
 directory=ROOT/'operator/batches'/('batch-validator-v1-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'));directory.mkdir(parents=True,exist_ok=False)
 rows=[];error=None
 try:
  b.exclusive(directory/'PLAN.json',{'utc':b.now(),'assignments':chosen,'preflight':check,'automatic_retry':False})
  for a in chosen:
   verify_addendum(digest)
   for name,h in lock['input_hashes'].items():
    if sha(b.inside(ROOT,name))!=h:raise RuntimeError('Final source/input changed: '+name)
   for name,h in lock['external_input_hashes'].items():
    if sha(Path(name))!=h:raise RuntimeError('External runtime changed: '+name)
   resource([a])
   out=b.SCI/a['trial_id'];out.mkdir(parents=True,exist_ok=False)
   b.exclusive(out/'assignment.json',a)
   b.exclusive(out/'START.json',{'utc':b.now(),'role':'scientific','scientific_denominator':True,'engine_reserved':True,'preflight_passed':True,'preflight_receipt':check,'final_lock_sha256':sha(ROOT/'operator/FINAL_INPUT_LOCK.json'),'validator_addendum_sha256':digest,'retry_permitted':False})
   with (out/'backend-console.txt').open('xb') as console:
    result=subprocess.run([sys.executable,str(HERE/'backend_dispatch_validator_v1.py'),'--assignment',str(out/'assignment.json'),'--attempt-dir',str(out)],stdout=console,stderr=subprocess.STDOUT)
   if (out/'RESULT.json').exists():b.exclusive(out/'OPERATOR_SHA256.json',{str(p.relative_to(out)):sha(p) for p in out.rglob('*') if p.is_file()})
   if result.returncode:raise RuntimeError('Consumed trial failed; stop without retry')
   rows.append(verify_attempt(out));b.atomic(ROOT/'operator/status.json',counts())
 except BaseException as e:error=repr(e);raise
 finally:
  receipt={'utc':b.now(),'assigned':n,'finished':len(rows),'attempts':rows,'passed':error is None,'error':error,'automatic_retry':False}
  b.exclusive(directory/'STOP.json',receipt);b.atomic(ROOT/'operator/LAST_BATCH.json',receipt)
  (ROOT/'operator/RUNNING.lock').unlink();b.atomic(ROOT/'operator/status.json',counts())
 return receipt

def main():
 if sys.platform=='darwin' and os.environ.get('IDBV2_OPERATOR_CAFFEINATED')!='1':
  env=dict(os.environ,IDBV2_OPERATOR_CAFFEINATED='1');raise SystemExit(subprocess.call(['caffeinate','-dimsu',sys.executable,str(Path(__file__).resolve()),*sys.argv[1:]],env=env))
 ap=argparse.ArgumentParser();ap.add_argument('--addendum-sha256',required=True)
 sp=ap.add_subparsers(dest='command',required=True)
 sp.add_parser('status');p=sp.add_parser('preflight');p.add_argument('--n',type=int,default=1)
 p=sp.add_parser('run-batch');p.add_argument('n',type=int)
 sp.add_parser('verify')
 args=ap.parse_args();verify_addendum(args.addendum_sha256)
 if args.command=='status':v=counts()
 elif args.command=='preflight':v=preflight(args.addendum_sha256,args.n)
 elif args.command=='run-batch':v=batch(args.addendum_sha256,args.n)
 else:v={'verified':[verify_attempt(b.SCI/a['trial_id']) for a in b.assignments() if (b.SCI/a['trial_id']).exists()]}
 print(json.dumps(v,indent=2))
if __name__=='__main__':main()
