"""Versioned audit selector; the frozen measurement controller is unchanged."""
import argparse,datetime,importlib.util,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE));sys.path.insert(0,str(ROOT/'operator'))
from correction_lock_v2 import verify_addendum
from pin_contract import VERSION
spec=importlib.util.spec_from_file_location('preserved_dispatch_v3',ROOT/'operator/backend_dispatch_v3.py')
prior=importlib.util.module_from_spec(spec);spec.loader.exec_module(prior)
core=prior.prior.core
rt=core.rt
read,sha,save,frozen,verify_sources=core.read,core.sha,core.save,core.frozen,core.verify_sources
route=core.route

def corrected_audit_path(family,directory):
 if family=='target_byte_diagnostics':return HERE/'audit_bytes_v1.py'
 if family=='trace_category_timelines':return HERE/'audit_timelines_v1.py'
 return directory/'independent_audit.py'

def execute(a,out,plan=None):
 role=a['role']
 if role!='scientific':raise RuntimeError('Validator continuation accepts only frozen scientific assignments')
 start=read(out/'START.json')
 addendum=verify_addendum(start['validator_addendum_sha256'])
 science,quals=frozen();verify_sources()
 if role=='scientific':
  if a!=science.get(a['trial_id']):raise RuntimeError('Assignment differs from frozen science')
  lock=ROOT/'operator/FINAL_INPUT_LOCK.json'
  if not lock.exists():raise RuntimeError('Final input lock absent, scientific execution blocked')
  start=read(out/'START.json')
  if start.get('final_lock_sha256')!=sha(lock) or start.get('preflight_passed') is not True:raise RuntimeError('No verified operator preflight reservation')
  for n,h in read(lock)['input_hashes'].items():
   if sha(ROOT/n)!=h:raise RuntimeError('Final scientific source/input changed '+n)
 elif role=='qualification':
  if plan is None or plan.get('role')!='excluded_operator_integration' or plan['maximum_attempts']!=1 or plan['assignment']!=a:raise RuntimeError('Prospective fresh excluded integration plan required')
  canonical={k:v for k,v in a.items() if k not in ['original_qualification_id','technical_amendment_id','scientific_denominator']};canonical['trial_id']=a['original_qualification_id']
  if canonical!=quals.get(canonical['trial_id']) or not a['trial_id'].startswith('qualification-operator-integration-'):raise RuntimeError('Integration condition differs or ID invalid')
  for n,h in plan['source_hashes'].items():
   if sha(ROOT/n)!=h:raise RuntimeError('Prospective integration source differs '+n)
 else:raise RuntimeError('Invalid role')
 rt.configure(role)
 if out.resolve()!=(rt.attempt_root()/a['trial_id']).resolve():raise RuntimeError('Wrong attempt output')
 rt.validate_reserved(out,a);rt.validate_assignment(out,a)
 folder,name=route(a);directory=rt.ENGINE/folder;sys.path.insert(0,str(directory));module=importlib.import_module(name)
 # The candidate may import another controller. Select this exact independent
 # audit by file, then restore the candidate folder for its local dependencies.
 sys.path.insert(0,str(directory));spec=importlib.util.spec_from_file_location('operator_independent_audit',corrected_audit_path(a['experiment'],directory));audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
 passed=module.run_one(a)
 try:review=audit.audit(a)
 except BaseException as e:review={'trial_id':a['trial_id'],'independent_pass':False,'error':repr(e)}
 save(out/'INDEPENDENT_VERIFICATION.json',review)
 save(out/'OPERATOR_INTEGRATION_RESULT.json',{'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'role':role,'scientific_denominator':role=='scientific','controller_pass':passed,'independent_pass':review.get('independent_pass') is True,'engine_manifest_sha256':sha(core.HERE/'ENGINE_SOURCE_MANIFEST.json'),'automatic_retry':False,'validator_version':VERSION,'validator_addendum_sha256':start['validator_addendum_sha256']})
 return bool(passed and review.get('independent_pass'))

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--assignment',type=Path,required=True);ap.add_argument('--attempt-dir',type=Path,required=True);args=ap.parse_args()
 a=read(args.assignment)
 success=execute(a,args.attempt_dir)
 if (args.attempt_dir/'RESULT.json').exists():save(args.attempt_dir/'REGISTERED_ENDPOINT.json',prior.projection.project(args.attempt_dir))
 raise SystemExit(0 if success else 2)

if __name__=='__main__':main()
