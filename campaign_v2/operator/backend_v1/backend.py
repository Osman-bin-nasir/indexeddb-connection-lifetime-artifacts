"""One registered attempt per process. Scientific execution requires the final lock.

The qualification mode requires a prospective fresh integration plan. It cannot
consume a scientific assignment or silently reuse an earlier qualification ID.
"""
import argparse,datetime,hashlib,importlib,importlib.util,json,os,sys
from pathlib import Path
HERE=Path(__file__).parent;ROOT=HERE.parents[1];sys.path.insert(0,str(ROOT))
import backend_runtime as rt

def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(Path(p).read_text())
def save(p,v):
 with Path(p).open('x') as f:json.dump(v,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
def route(a):
 f=a['experiment']
 if f in ['close_aligned_recovery_grid','held_connection_recovery_sweep','six_key_conditions']:return 'repairs/004','qualification_candidate'
 if f=='application_and_background_activity':return 'repairs/007','qualification_workloads'
 if f=='environment_sensitivity':return 'extensions/environment','qualification_environment'
 if f=='fault_scope_comparison':return ('repairs/010' if a['fault']=='browser_sigkill' else 'repairs/009'),'qualification_fault_scope'
 if f=='target_byte_diagnostics':return 'repairs/012','qualification_bytes'
 if f=='trace_category_timelines':return 'repairs/011','qualification_timelines'
 if f=='block_state_recovery':return ('extensions/block_log','qualification_log') if a['mapper']=='dm_log_writes' else ('repairs/013','qualification_mapped')
 raise RuntimeError('Unimplemented frozen family '+f)
def frozen():
 root=ROOT.parent/'confirmatory';manifest=read(root/'design/MANIFEST.json');science={};qualification={}
 for line in (root/'SHA256SUMS').read_text().splitlines():
  h,n=line.split(maxsplit=1)
  if sha(root/n.strip())!=h:raise RuntimeError('Frozen scientific input changed')
 for family in manifest['experiments']:
  if family['optional']:continue
  design=read(root/family['path']);science.update({a['trial_id']:a for a in design['assignments']});qualification.update({a['trial_id']:a for a in design['qualification_assignments']})
 return science,qualification
def verify_sources():
 m=read(HERE/'ENGINE_SOURCE_MANIFEST.json')
 for v in m['files']:
  if sha(ROOT/v['original'])!=v['original_sha256'] or sha(ROOT/v['generated'])!=v['generated_sha256']:raise RuntimeError('Engine/source adaptation hash changed '+v['original'])
def execute(a,out,plan=None):
 role=a['role'];science,quals=frozen();verify_sources()
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
 sys.path.insert(0,str(directory));spec=importlib.util.spec_from_file_location('operator_independent_audit',directory/'independent_audit.py');audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
 passed=module.run_one(a)
 try:review=audit.audit(a)
 except BaseException as e:review={'trial_id':a['trial_id'],'independent_pass':False,'error':repr(e)}
 save(out/'INDEPENDENT_VERIFICATION.json',review)
 save(out/'OPERATOR_INTEGRATION_RESULT.json',{'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'role':role,'scientific_denominator':role=='scientific','controller_pass':passed,'independent_pass':review.get('independent_pass') is True,'engine_manifest_sha256':sha(HERE/'ENGINE_SOURCE_MANIFEST.json'),'automatic_retry':False})
 return bool(passed and review.get('independent_pass'))
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--assignment',type=Path,required=True);ap.add_argument('--attempt-dir',type=Path,required=True);ap.add_argument('--qualification-plan',type=Path);args=ap.parse_args()
 success=execute(read(args.assignment),args.attempt_dir,read(args.qualification_plan) if args.qualification_plan else None)
 raise SystemExit(0 if success else 2)
if __name__=='__main__':main()
