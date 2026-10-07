"""Append-only continuation that consumes, but never retries, completed ineligible slots."""
import argparse,datetime,hashlib,importlib.util,json,os,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE))
import correction_lock_v3 as v3
from pin_contract import VERSION
spec=importlib.util.spec_from_file_location('preserved_operator_v4',ROOT/'operator/operator_v4.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
b=m.base
ADDENDUM=HERE/'LOCK_ADDENDUM_006.json'
RECEIPT=HERE/'AUTHOR_CONTINUATION_354_420_WITH_UNKNOWN_001.json'
PRELAUNCH_DISPOSITION=HERE/'DISPOSITION_354_PREMEASUREMENT_FAILURE_001.json'
BASE_DIGEST='287861a467ffd6ebdd566efc81ac455555e6d2e7b59f66979f71774fd87bc785'

def sha(path):
 with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(path):return json.loads(Path(path).read_text())
def verify_addendum(digest):
 if sha(ADDENDUM)!=digest:raise RuntimeError('Continuation addendum hash mismatch')
 a=read(ADDENDUM)
 if a.get('base_addendum_sha256')!=BASE_DIGEST:raise RuntimeError('Unexpected base correction')
 v3.verify_addendum(BASE_DIGEST)
 for name,key in ((a['continuation_entrypoint'],'continuation_entrypoint_sha256'),(a['author_direction_receipt'],'author_direction_receipt_sha256')):
  p=(ROOT/name).resolve()
  if not p.is_relative_to(ROOT.resolve()) or sha(p)!=a[key]:raise RuntimeError('Continuation receipt/source changed: '+name)
 for name,h in a['pinned_files'].items():
  p=(ROOT/name).resolve()
  if not p.is_relative_to(ROOT.resolve()) or sha(p)!=h:raise RuntimeError('Append-only disposition/source changed: '+name)
 rec=read(RECEIPT)
 if rec.get('user_instruction_verbatim')!='why did you stop ?? complete all420' or rec.get('assignment_353_disposition','').find('unknown')<0:
  raise RuntimeError('Missing author continuation direction')
 return a

def verify_prelaunch_disposition(out):
 out=Path(out);d=read(PRELAUNCH_DISPOSITION)
 if out.name!='scientific-trace_category_timelines-00004' or d.get('trial_id')!=out.name or d.get('measurement_started') is not False or d.get('retry_permitted') is not False:
  raise RuntimeError('Unresolved incomplete attempt without explicit disposition: '+out.name)
 actual={str((ROOT/name).relative_to(ROOT)):sha(ROOT/name) for name in d['evidence_hashes']}
 if actual!=d['evidence_hashes']:raise RuntimeError('Prelaunch disposition evidence changed')
 if (out/'RESULT.json').exists() or d.get('result_json_absent') is not True:raise RuntimeError('Unexpected result in prelaunch disposition')
 return {'trial_id':out.name,'eligible':False,'endpoint':'unknown','measurement_started':False,'reason':d['reason'],'retry_permitted':False,'disposition_sha256':sha(PRELAUNCH_DISPOSITION)}

def classify(out,allow_ineligible=True):
 """Verify immutable raw inventories, then report endpoint eligibility without recoding it."""
 out=Path(out);b.inventory_check(out);m.retention.verify_inventory(out,'OPERATOR_SHA256.json')
 r=read(out/'RESULT.json');b.validate_result(r)
 registered=read(out/'REGISTERED_ENDPOINT.json')
 if registered.get('controller_result_sha256')!=sha(out/'RESULT.json') or registered.get('controller_endpoint')!=r.get('endpoint') or registered.get('registered_endpoint')!=r.get('endpoint') or registered.get('controller_result_unchanged') is not True or registered.get('scientific_trial_increment')!=0:
  raise RuntimeError('Endpoint record integrity mismatch: '+out.name)
 integ=read(out/'OPERATOR_INTEGRATION_RESULT.json')
 audit=read(out/'INDEPENDENT_VERIFICATION.json')
 audit_pass=audit.get('independent_pass') is True; audit_source='original'
 if not audit_pass:
  try:
   corrected,audit_source=v3.effective_verification(out)
   audit_pass=corrected.get('independent_pass') is True
  except RuntimeError:
   audit_pass=False
 integration_pass=(integ.get('independent_pass') is True or audit_source=='append_only_validator_correction_v1')
 eligible=(r.get('technical_eligible') is True and r.get('endpoint') in ('recovered','lost') and integration_pass and audit_pass)
 if r.get('technical_eligible') is True and r.get('endpoint') in ('recovered','lost') and not eligible:
  raise RuntimeError('Eligible controller result lacks an independent pass: '+out.name)
 if not eligible and not allow_ineligible:
  raise RuntimeError('Ineligible trial is not permitted by this operation: '+out.name)
 return {'trial_id':out.name,'eligible':eligible,'endpoint':r.get('endpoint'),'technical_eligible':r.get('technical_eligible'),'reasons':r.get('reasons',[]),'raw_inventories_verified':True,'independent_pass':audit_pass,'retry_permitted':False}

def selected(n):
 if not 1<=n<=20:raise RuntimeError('Bounded continuation must contain 1-20 assignments')
 schedule=b.assignments();release=read(ROOT/'operator/ACQUISITION_RELEASE_003.json');allowed=set(release['assignment_ids_authorized'])
 selected=[]
 for i,a in enumerate(schedule,1):
  if i>420:break
  if a['trial_id'] in allowed and not (b.SCI/a['trial_id']).exists():selected.append(a)
  if len(selected)==n:break
 if len(selected)!=n:raise RuntimeError('Insufficient unused registered assignments through420')
 return selected

def base_preflight_preserving_ineligible():
 """Recheck every frozen readiness gate while treating recorded failed slots as consumed."""
 schedule=b.assignments();tag=subprocess.check_output(['git','rev-parse','prereg-connection-lifetime-mac-v2^{}'],cwd=ROOT,text=True).strip()
 if tag!=b.TAG:raise RuntimeError('Frozen repository tag changed')
 p=ROOT/'operator/FINAL_INPUT_LOCK.json'
 if not p.exists():raise RuntimeError('Final input lock missing')
 lock=read(p)
 for key in ['qualification_receipt','operator_demonstration_receipt','resource_receipt','backend_script']:
  if key not in lock:raise RuntimeError('Missing final receipt '+key)
 for name,h in lock['input_hashes'].items():
  if sha(b.inside(ROOT,name))!=h:raise RuntimeError('Final input hash mismatch '+name)
 for key in ['qualification_receipt','operator_demonstration_receipt','resource_receipt','backend_script']:
  if lock[key] not in lock['input_hashes']:raise RuntimeError('Unbound final receipt '+key)
 q=read(b.inside(ROOT,lock['qualification_receipt']));expected=set()
 for spec in read(b.FROZEN/'design/MANIFEST.json')['experiments']:
  if not spec['optional']:expected.update((a['experiment'],a['condition_id']) for a in read(b.FROZEN/spec['path'])['qualification_assignments'])
 if len(q['cells'])!=95 or {(x['family'],x['condition_id']) for x in q['cells']}!=expected:raise RuntimeError('All 95 qualification cells not independently represented')
 for x in q['cells']:
  p=b.inside(ROOT,x['audit_path'])
  if sha(p)!=x['audit_sha256'] or read(p).get('independent_pass') is not True:raise RuntimeError('Qualification audit failed')
  b.inventory_check(b.inside(ROOT,x['attempt_path']))
 demo=read(b.inside(ROOT,lock['operator_demonstration_receipt']))
 if demo.get('excluded_qualification_only') is not True or not all(demo.get(k) is True for k in ['status_passed','run_batch_passed','verify_passed','archive_roundtrip_passed']):raise RuntimeError('Operator demonstration incomplete')
 resources=read(b.inside(ROOT,lock['resource_receipt']))
 if resources.get('bounded_batch_resource_gate_passed') is not True:raise RuntimeError('Bounded resource gate failed')
 for a in schedule:
  p=b.SCI/a['trial_id']
  if p.exists():
   if not (p/'RESULT.json').exists():verify_prelaunch_disposition(p);continue
   b.validate_result(read(p/'RESULT.json'));b.inventory_check(p)
 return {'utc':b.now(),'passed':True,'scientific_assigned':930,'lock_sha256':sha(ROOT/'operator/FINAL_INPUT_LOCK.json'),'disk':b.disk_check(lock['operation_headroom_bytes']),'completed_ineligible_attempts_are_consumed':True}

def resource(chosen):
 lock=read(ROOT/'operator/FINAL_INPUT_LOCK.json');q=read(ROOT/lock['qualification_receipt'])
 costs={(r['family'],r['condition_id']):2*r['allocated_bytes'] for r in q['cells']}
 scratch=read(ROOT/'operator/BOUNDED_RESOURCE_RECEIPT_RESUME006_002.json')['archive_scratch_headroom_bytes']
 headroom=max(lock['operation_headroom_bytes'],sum(costs[a['experiment'],a['condition_id']] for a in chosen)+scratch)
 return {'method':'twice measured qualified allocation per exact assignment plus frozen archive scratch and operation headroom','assignment_ids':[a['trial_id'] for a in chosen],'trial_headroom_bytes':sum(costs[a['experiment'],a['condition_id']] for a in chosen),'archive_scratch_headroom_bytes':scratch,'disk':b.disk_check(headroom)}

def preflight(digest,n=1):
 verify_addendum(digest);old=b.preflight;b.preflight=base_preflight_preserving_ineligible
 try:original=m.preflight()
 finally:b.preflight=old
 existing=[]
 for a in b.assignments():
  out=b.SCI/a['trial_id']
  if out.exists():existing.append(verify_prelaunch_disposition(out) if not (out/'RESULT.json').exists() else classify(out,allow_ineligible=True))
 chosen=selected(n);res=resource(chosen)
 if not res['disk']['passed']:raise RuntimeError('Resource/storage gate failed')
 return {'utc':b.now(),'passed':True,'continuation_addendum_sha256':digest,'validator_version':VERSION,'frozen_preflight':original,'next_trial_id':chosen[0]['trial_id'],'selected_assignments':[a['trial_id'] for a in chosen],'resources':res,'existing_attempts_integrity_verified':len(existing),'existing_ineligible_preserved':[x['trial_id'] for x in existing if not x['eligible']],'author_override_receipt_sha256':sha(RECEIPT),'no_attempt_started':True}

def counts():
 value=b.status(write=False);eligible=0;ineligible=[];failures=[]
 for a in b.assignments():
  out=b.SCI/a['trial_id']
  if not out.exists() or not (out/'RESULT.json').exists():continue
  try:
   r=read(out/'RESULT.json');audit=read(out/'INDEPENDENT_VERIFICATION.json');audit_pass=audit.get('independent_pass') is True
   if not audit_pass:
    try:review,_=v3.effective_verification(out);audit_pass=review.get('independent_pass') is True
    except RuntimeError:pass
   if r.get('technical_eligible') is True and r.get('endpoint') in ('recovered','lost') and audit_pass:eligible+=1
   else:
    row={'trial_id':a['trial_id'],'endpoint':r.get('endpoint'),'reasons':r.get('reasons',[])};ineligible.append(row);failures.append(a['trial_id'])
  except Exception as e:failures.append({'trial_id':a['trial_id'],'error':repr(e)})
 value.update(independent_valid_total=eligible,eligible_scientific_count=eligible,completed_ineligible=ineligible,unresolved_independent_failures=failures,continuation_validator='v6-consume-ineligible-without-retry',scientific_acquisition_ready=False,continuation_authorization='assignments312-420; completed ineligible attempts consumed without retry')
 return value

def batch(digest,n):
 check=preflight(digest,n);chosen=selected(n);lock=read(ROOT/'operator/FINAL_INPUT_LOCK.json')
 fd=os.open(ROOT/'operator/RUNNING.lock',os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.write(fd,str(os.getpid()).encode());os.close(fd)
 directory=ROOT/'operator/batches'/('batch-validator-v2-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'));directory.mkdir(parents=True,exist_ok=False)
 rows=[];error=None
 try:
  b.exclusive(directory/'PLAN.json',{'utc':b.now(),'assignments':chosen,'preflight':check,'automatic_retry':False,'continue_after_completed_ineligible':True,'author_receipt_sha256':sha(RECEIPT)})
  for a in chosen:
   verify_addendum(digest)
   for name,h in lock['input_hashes'].items():
    if sha(b.inside(ROOT,name))!=h:raise RuntimeError('Final source/input changed: '+name)
   for name,h in lock['external_input_hashes'].items():
    if sha(Path(name))!=h:raise RuntimeError('External runtime changed: '+name)
   resource([a]);out=b.SCI/a['trial_id'];out.mkdir(parents=True,exist_ok=False)
   b.exclusive(out/'assignment.json',a)
   b.exclusive(out/'START.json',{'utc':b.now(),'role':'scientific','scientific_denominator':True,'engine_reserved':True,'preflight_passed':True,'preflight_receipt':check,'final_lock_sha256':sha(ROOT/'operator/FINAL_INPUT_LOCK.json'),'validator_addendum_sha256':BASE_DIGEST,'continuation_addendum_sha256':digest,'retry_permitted':False,'author_continuation_receipt_sha256':sha(RECEIPT)})
   with (out/'backend-console.txt').open('xb') as console:
    result=subprocess.run([sys.executable,str(HERE/'backend_dispatch_validator_v3.py'),'--assignment',str(out/'assignment.json'),'--attempt-dir',str(out)],stdout=console,stderr=subprocess.STDOUT)
   if not (out/'RESULT.json').is_file():raise RuntimeError('Consumed attempt lacks a result; stop')
   b.exclusive(out/'OPERATOR_SHA256.json',{str(p.relative_to(out)):sha(p) for p in out.rglob('*') if p.is_file()})
   row=classify(out,allow_ineligible=True);row['backend_exit_code']=result.returncode;rows.append(row);b.atomic(ROOT/'operator/status.json',counts())
   if result.returncode and row['eligible']:raise RuntimeError('Backend failed despite eligible endpoint; stop')
 except BaseException as e:error=repr(e);raise
 finally:
  receipt={'utc':b.now(),'assigned':len(chosen),'finished':len(rows),'attempts':rows,'passed':error is None,'error':error,'automatic_retry':False,'continues_after_completed_ineligible':True,'author_receipt_sha256':sha(RECEIPT)}
  b.exclusive(directory/'STOP.json',receipt);b.atomic(ROOT/'operator/LAST_BATCH.json',receipt)
  (ROOT/'operator/RUNNING.lock').unlink();b.atomic(ROOT/'operator/status.json',counts())
 return receipt

def main():
 if sys.platform=='darwin' and os.environ.get('IDBV2_OPERATOR_CAFFEINATED')!='1':
  env=dict(os.environ,IDBV2_OPERATOR_CAFFEINATED='1');raise SystemExit(subprocess.call(['caffeinate','-dimsu',sys.executable,str(Path(__file__).resolve()),*sys.argv[1:]],env=env))
 ap=argparse.ArgumentParser();ap.add_argument('--addendum-sha256',required=True);sp=ap.add_subparsers(dest='command',required=True)
 sp.add_parser('status');p=sp.add_parser('preflight');p.add_argument('--n',type=int,default=1);p=sp.add_parser('run-batch');p.add_argument('n',type=int);sp.add_parser('verify')
 args=ap.parse_args();verify_addendum(args.addendum_sha256)
 if args.command=='status':v=counts()
 elif args.command=='preflight':v=preflight(args.addendum_sha256,args.n)
 elif args.command=='run-batch':v=batch(args.addendum_sha256,args.n)
 else:v={'verified':[classify(b.SCI/a['trial_id'],True) for a in b.assignments() if (b.SCI/a['trial_id']).exists()]}
 print(json.dumps(v,indent=2))
if __name__=='__main__':main()
