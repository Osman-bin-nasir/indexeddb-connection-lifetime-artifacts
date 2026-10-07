"""Once-only bounded operator. Final gates are checked before consuming any slot."""
import argparse,datetime,importlib.util,json,os,subprocess,sys
from pathlib import Path
HERE=Path(__file__).parent;ROOT=HERE.parent
s=importlib.util.spec_from_file_location('operator_base',HERE/'operator.py');base=importlib.util.module_from_spec(s);s.loader.exec_module(base)
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def preflight():
 result=base.preflight();lock=base.read(HERE/'FINAL_INPUT_LOCK.json');resource=base.read(ROOT/lock['resource_receipt']);demo=base.read(ROOT/lock['operator_demonstration_receipt'])
 if resource.get('offload_verified') is not True or resource.get('resource_gate_passed') is not True:raise RuntimeError('BLOCKED: registered offload and measured archive headroom have not passed')
 if demo.get('assembled_backend_independent_pass') is not True or demo.get('console_sealed') is not True:raise RuntimeError('BLOCKED: assembled backend integration incomplete')
 if lock['backend_script']!='operator/backend_dispatch_v2.py':raise RuntimeError('Unexpected unqualified backend')
 if (HERE/'RUNNING.lock').exists():raise RuntimeError('Operator running lock exists; inspect process, never delete blindly')
 return result

def verify_attempt(out):
 base.inventory_check(out)
 r=base.read(out/'RESULT.json');base.validate_result(r)
 review=base.read(out/'INDEPENDENT_VERIFICATION.json')
 if review.get('trial_id')!=out.name or review.get('scientific_denominator') is not True or review.get('independent_pass') is not True:raise RuntimeError('Independent scientific verification failed')
 sealed=base.read(out/'OPERATOR_SHA256.json')
 for n,h in sealed.items():
  if base.sha(base.inside(out,n))!=h:raise RuntimeError('Operator/console evidence hash mismatch '+n)
 return {'trial_id':out.name,'passed':True,'raw_members':len(base.read(out/'SHA256.json')),'operator_members':len(sealed)}

def batch(n):
 if n<1:raise RuntimeError('Positive bounded batch size required')
 check=preflight();lock=base.read(HERE/'FINAL_INPUT_LOCK.json');chosen=[a for a in base.assignments() if not (base.SCI/a['trial_id']).exists()][:n]
 if not chosen:return {'finished':0,'remaining':0,'passed':True}
 resource=base.read(ROOT/lock['resource_receipt']);max_bytes=resource['max_trial_allocated_bytes']
 # A bounded batch retains all originals. Its conservative operation estimate
 # includes twice measured per-attempt growth and safe archive working space.
 headroom=max(lock['operation_headroom_bytes'],2*max_bytes*len(chosen)+resource['archive_scratch_headroom_bytes']);base.disk_check(headroom)
 fd=os.open(HERE/'RUNNING.lock',os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.write(fd,str(os.getpid()).encode());os.close(fd)
 directory=HERE/'batches'/('batch-v2-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'));directory.mkdir(parents=True,exist_ok=False);rows=[];error=None
 base.exclusive(directory/'PLAN.json',{'utc':now(),'assignments':chosen,'preflight':check,'bounded_headroom_bytes':headroom,'automatic_retry':False})
 try:
  for a in chosen:
   # Verify every final input again without hiding an already consumed failure.
   for p,h in lock['input_hashes'].items():
    if base.sha(base.inside(ROOT,p))!=h:raise RuntimeError('Final input/source changed '+p)
   base.disk_check(max(lock['operation_headroom_bytes'],2*max_bytes+resource['archive_scratch_headroom_bytes']))
   out=base.SCI/a['trial_id'];out.mkdir(parents=True,exist_ok=False)
   base.exclusive(out/'assignment.json',a);base.exclusive(out/'START.json',{'utc':now(),'role':'scientific','scientific_denominator':True,'engine_reserved':True,'preflight_passed':True,'preflight_receipt':check,'final_lock_sha256':base.sha(HERE/'FINAL_INPUT_LOCK.json'),'retry_permitted':False})
   with (out/'backend-console.txt').open('xb') as console:
    response=subprocess.run([sys.executable,str(ROOT/lock['backend_script']),'--assignment',str(out/'assignment.json'),'--attempt-dir',str(out)],stdout=console,stderr=subprocess.STDOUT)
   if (out/'RESULT.json').exists():
    # Separate seal after the backend and its console have closed. Never rewrite
    # the controller's raw SHA256.json, result or source evidence.
    base.exclusive(out/'OPERATOR_SHA256.json',{str(p.relative_to(out)):base.sha(p) for p in out.rglob('*') if p.is_file()})
   if response.returncode:raise RuntimeError('Backend/controller/independent failure; consumed slot, no retry')
   review=verify_attempt(out);r=base.read(out/'RESULT.json');rows.append({'trial_id':a['trial_id'],'endpoint':r['endpoint'],'technical_eligible':r['technical_eligible'],'independent_pass':review['passed']})
   if r['technical_eligible'] is not True or r['endpoint'] in ['unknown','integrity_failure']:raise RuntimeError('Registered technical or endpoint gate failed')
   base.status()
 except BaseException as e:error=repr(e);raise
 finally:
  final={'utc':now(),'assigned':len(chosen),'finished':len(rows),'attempts':rows,'passed':error is None,'error':error,'automatic_retry':False,'next_action':'Archive/offload at declared batch boundary; resume only after applicable storage and integrity checks pass.'};base.exclusive(directory/'STOP.json',final);base.atomic(HERE/'LAST_BATCH.json',final);(HERE/'RUNNING.lock').unlink();base.status()
 return final

def main():
 # Every CLI runs under caffeinate. No unattended science is launched by import.
 if sys.platform=='darwin' and os.environ.get('IDBV2_OPERATOR_CAFFEINATED')!='1':
  env=dict(os.environ,IDBV2_OPERATOR_CAFFEINATED='1');raise SystemExit(subprocess.call(['caffeinate','-dimsu',sys.executable,str(Path(__file__).resolve()),*sys.argv[1:]],env=env))
 ap=argparse.ArgumentParser();sp=ap.add_subparsers(dest='command',required=True)
 for name in ['status','preflight','disk-check']:sp.add_parser(name)
 p=sp.add_parser('run-batch');p.add_argument('n',type=int)
 p=sp.add_parser('verify');p.add_argument('--trial-id',nargs='*')
 p=sp.add_parser('archive');p.add_argument('archive_arguments',nargs=argparse.REMAINDER)
 args=ap.parse_args()
 if args.command=='status':value=base.status()
 elif args.command=='preflight':value=preflight()
 elif args.command=='disk-check':value=base.disk_check()
 elif args.command=='run-batch':value=batch(args.n)
 elif args.command=='archive':raise SystemExit(subprocess.call([sys.executable,str(HERE/'archive_v2.py'),*args.archive_arguments]))
 else:
  paths=[base.SCI/t for t in args.trial_id] if args.trial_id else [p for p in base.SCI.iterdir()] if base.SCI.exists() else []
  value={'verified':[verify_attempt(p) for p in paths]}
 print(json.dumps(value,indent=2))
if __name__=='__main__':main()
