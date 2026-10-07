"""Resumable operator shell. Scientific execution stays blocked until verified final gates."""
from __future__ import annotations
import argparse,datetime,hashlib,json,os,shutil,subprocess,sys,tarfile,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
FROZEN=ROOT.parent/'confirmatory'
SCI=ROOT/'scientific/attempts'
STATE=ROOT/'operator'
TAG='5a749734a0a63f3e1c662bb91dd829e6f288dc5c'
CHUNK=1024**3

def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(p.read_text())
def exclusive(p,v):
 p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:json.dump(v,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
def atomic(p,v):
 p.parent.mkdir(parents=True,exist_ok=True)
 with tempfile.NamedTemporaryFile(mode='w',dir=p.parent,delete=False) as f:
  json.dump(v,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno());tmp=Path(f.name)
 os.replace(tmp,p)
def inside(base,relative):
 p=base/relative
 if p.is_symlink() or not p.resolve().is_relative_to(base.resolve()):raise RuntimeError('Unsafe evidence member '+relative)
 return p

def assignments():
 out=[]
 for h,n in (l.split(maxsplit=1) for l in (FROZEN/'SHA256SUMS').read_text().splitlines()):
  if sha(inside(FROZEN,n.strip()))!=h:raise RuntimeError('Frozen hash mismatch '+n)
 for family in read(FROZEN/'design/MANIFEST.json')['experiments']:
  if not family['optional']:
   p=inside(FROZEN,family['path'])
   if sha(p)!=family['sha256']:raise RuntimeError('Manifest hash mismatch')
   out.extend(read(p)['assignments'])
 if len(out)!=930 or len({a['trial_id'] for a in out})!=930:raise RuntimeError('Scientific schedule changed')
 return out

def disk_check(headroom=3*1024**3):
 free=shutil.disk_usage(ROOT).free
 if free-headroom<6*1024**3:raise RuntimeError('DISK_STOP: free minus operation headroom below6GiB')
 return {'free_bytes':free,'free_gib':free/1024**3,'floor_bytes':6*1024**3,'headroom_bytes':headroom,'passed':True}

def validate_result(r):
 if r.get('role')!='scientific' or r.get('scientific_denominator') is not True:raise RuntimeError('Invalid scientific provenance')
 if r.get('endpoint') not in ['recovered','lost','integrity_failure','unknown']:raise RuntimeError('Invalid endpoint label')

def inventory_check(path):
 if not (path/'RESULT.json').exists():raise RuntimeError('Unfinished attempt cannot be verified as finished')
 listed=read(path/'SHA256.json');bad=[]
 for n,h in listed.items():
  p=inside(path,n)
  if not p.is_file() or sha(p)!=h:bad.append(n)
 if bad:raise RuntimeError('Evidence hash mismatch '+repr(bad))
 return {'trial_id':path.name,'checked_members':len(listed),'passed':True}

def status(write=True):
 schedule=assignments();families={};durations=[]
 for a in schedule:
  family=families.setdefault(a['experiment'],{'assigned':0,'started':0,'complete':0,'technically_invalid':0,'integrity_failure':0,'unknown':0,'remaining':0})
  family['assigned']+=1;path=SCI/a['trial_id']
  if not path.exists():family['remaining']+=1;continue
  family['started']+=1
  if not (path/'RESULT.json').exists():family['unknown']+=1;continue
  r=read(path/'RESULT.json');validate_result(r);family['complete']+=1
  if r.get('technical_eligible') is not True:family['technically_invalid']+=1
  if r['endpoint'] in ['unknown','integrity_failure']:family[r['endpoint']]+=1
  if r.get('wall_seconds') is not None:durations.append(r['wall_seconds'])
 total=lambda k:sum(v[k] for v in families.values())
 remaining=total('remaining');eta=(sum(durations)/len(durations)*remaining) if durations else None
 value={'utc':now(),'families':families,'assigned':930,'started':total('started'),'complete':total('complete'),'remaining':remaining,'disk_free_bytes':shutil.disk_usage(ROOT).free,'last_batch':read(STATE/'LAST_BATCH.json') if (STATE/'LAST_BATCH.json').exists() else None,'eta_seconds':eta,'eta_scope':'observed scientific trial costs only; missing families can invalidate forecast','overlapping_flags':'complete includes finished unknown/integrity failures; technically_invalid overlaps endpoint categories; directories without a result are started/unknown and never retried','scientific_acquisition_ready':False}
 if write:
  atomic(STATE/'status.json',value)
  text='# Operator status\n\nUpdated '+value['utc']+'. Assigned930, started'+str(value['started'])+', finished'+str(value['complete'])+', remaining'+str(remaining)+'. Disk free '+format(value['disk_free_bytes']/1024**3,'.2f')+'GiB. ETA '+str(eta)+' seconds.\n\n'+value['overlapping_flags']+'\n\n'+ '\n'.join(f"{k}: {json.dumps(v,sort_keys=True)}" for k,v in families.items())+'\n'
  (STATE/'STATUS.md').write_text(text)
 return value

def preflight():
 assignments();tag=subprocess.check_output(['git','rev-parse','prereg-connection-lifetime-mac-v2^{}'],cwd=ROOT,text=True).strip()
 if tag!=TAG:raise RuntimeError('Frozen repository tag changed')
 p=STATE/'FINAL_INPUT_LOCK.json'
 if not p.exists():raise RuntimeError('BLOCKED: final input lock, all-cell qualification and operator demonstration remain pending')
 lock=read(p)
 # These are receipt paths, verified by hash below, never substitute a status checkbox for evidence.
 for key in ['qualification_receipt','operator_demonstration_receipt','resource_receipt','backend_script']:
  if key not in lock:raise RuntimeError('Missing final receipt '+key)
 for n,h in lock['input_hashes'].items():
  if sha(inside(ROOT,n))!=h:raise RuntimeError('Final input hash mismatch '+n)
 for key in ['qualification_receipt','operator_demonstration_receipt','resource_receipt','backend_script']:
  if lock[key] not in lock['input_hashes']:raise RuntimeError('Unbound final receipt '+key)
 q=read(inside(ROOT,lock['qualification_receipt']));expected=set()
 for spec in read(FROZEN/'design/MANIFEST.json')['experiments']:
  if not spec['optional']:expected.update((a['experiment'],a['condition_id']) for a in read(FROZEN/spec['path'])['qualification_assignments'])
 receipts=q['cells']
 if len(receipts)!=95 or {(r['family'],r['condition_id']) for r in receipts}!=expected:raise RuntimeError('All95 current cells not independently qualified')
 for receipt in receipts:
  a=inside(ROOT,receipt['audit_path'])
  if sha(a)!=receipt['audit_sha256'] or read(a).get('independent_pass') is not True:raise RuntimeError('Missing independent qualification pass')
  attempt=inside(ROOT,receipt['attempt_path']);inventory_check(attempt)
 demo=read(inside(ROOT,lock['operator_demonstration_receipt']))
 if demo.get('excluded_qualification_only') is not True or not all(demo.get(k) is True for k in ['status_passed','run_batch_passed','verify_passed','archive_roundtrip_passed']):raise RuntimeError('Operator demonstration not completed')
 resources=read(inside(ROOT,lock['resource_receipt']))
 if resources.get('registered_campaign_fits_current_retained_storage') is not True:raise RuntimeError('Storage forecast not qualified')
 for a in assignments():
  p=SCI/a['trial_id']
  if p.exists():
   if not (p/'RESULT.json').exists():raise RuntimeError('Unresolved started/unknown scientific attempt')
   r=read(p/'RESULT.json');validate_result(r)
   if r['endpoint'] in ['unknown','integrity_failure'] or r.get('technical_eligible') is not True:raise RuntimeError('Unresolved scientific failure; batch stop remains active')
   inventory_check(p)
 return {'utc':now(),'passed':True,'scientific_assigned':930,'lock_sha256':sha(p=STATE/'FINAL_INPUT_LOCK.json'),'disk':disk_check(lock['operation_headroom_bytes'])}

def run_batch(n):
 if n<1:raise RuntimeError('Positive bounded batch size required')
 check=preflight();lock=read(STATE/'FINAL_INPUT_LOCK.json')
 fd=os.open(STATE/'RUNNING.lock',os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
 os.write(fd,str(os.getpid()).encode());os.close(fd)
 batch=STATE/'batches'/('batch-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'));batch.mkdir(parents=True,exist_ok=False)
 rows=[]
 try:
  chosen=[a for a in assignments() if not (SCI/a['trial_id']).exists()][:n]
  exclusive(batch/'PLAN.json',{'utc':now(),'assignments':chosen,'preflight':check,'automatic_retry':False})
  for a in chosen:
   preflight();out=SCI/a['trial_id'];out.mkdir(parents=True,exist_ok=False)
   exclusive(out/'assignment.json',a);exclusive(out/'START.json',{'utc':now(),'role':'scientific','scientific_denominator':True,'final_lock_sha256':sha(STATE/'FINAL_INPUT_LOCK.json'),'retry_permitted':False})
   with (out/'backend-console.txt').open('xb') as console:
    response=subprocess.run([sys.executable,str(inside(ROOT,lock['backend_script'])),'--assignment',str(out/'assignment.json'),'--attempt-dir',str(out)],stdout=console,stderr=subprocess.STDOUT)
   if response.returncode or not (out/'RESULT.json').exists():raise RuntimeError('Backend failed or endpoint unknown; retained started attempt, no retry')
   r=read(out/'RESULT.json');validate_result(r);inventory_check(out);rows.append({'trial_id':a['trial_id'],'endpoint':r['endpoint'],'technical_eligible':r.get('technical_eligible')})
   if r.get('technical_eligible') is not True or r['endpoint'] in ['unknown','integrity_failure']:raise RuntimeError('Trial failed registered gate; stop batch')
  final={'utc':now(),'assigned':len(chosen),'finished':len(rows),'attempts':rows,'passed':True,'automatic_retry':False};exclusive(batch/'STOP.json',final);atomic(STATE/'LAST_BATCH.json',final)
 except BaseException as e:
  final={'utc':now(),'finished':len(rows),'attempts':rows,'passed':False,'error':repr(e),'automatic_retry':False};exclusive(batch/'STOP.json',final);atomic(STATE/'LAST_BATCH.json',final);raise
 finally:(STATE/'RUNNING.lock').unlink();status()

def qualification_demo(n,path):
 """Execute exactly one prospectively registered fresh excluded operator demonstration."""
 if n!=1:raise RuntimeError('Operator demonstration is bounded to exactly one excluded attempt')
 plan=read(path);assignments();disk_check()
 if plan.get('role')!='excluded_operator_demonstration' or plan.get('maximum_attempts')!=1:raise RuntimeError('Invalid excluded demonstration plan')
 a=plan['assignment']
 if a.get('role')!='qualification' or not a['trial_id'].startswith('qualification-operator-demonstration-'):raise RuntimeError('Fresh excluded operator ID required')
 original={}
 for spec in read(FROZEN/'design/MANIFEST.json')['experiments']:
  if not spec['optional']:original.update({v['trial_id']:v for v in read(FROZEN/spec['path'])['qualification_assignments']})
 compare={k:v for k,v in a.items() if k not in ['original_qualification_id','technical_amendment_id','scientific_denominator']};compare['trial_id']=a['original_qualification_id']
 if compare!=original[compare['trial_id']]:raise RuntimeError('Demo condition differs from frozen qualification')
 candidate=inside(ROOT,plan['source_directory'])
 for name,h in plan['source_hashes'].items():
  if sha(inside(ROOT,name))!=h:raise RuntimeError('Demo source lock mismatch '+name)
 receipt=inside(ROOT,plan['prior_independent_pass'])
 if read(receipt).get('independent_pass') is not True or sha(receipt)!=plan['prior_independent_pass_sha256']:raise RuntimeError('No independently qualified implementation')
 out=ROOT/'qualification/attempts'/a['trial_id']
 if out.exists():raise RuntimeError('Consumed demo ID; no retry')
 import importlib
 sys.path.insert(0,str(ROOT));sys.path.insert(0,str(candidate))
 module=importlib.import_module(plan['qualification_module']);audit=importlib.import_module('independent_audit').audit
 module.verify_frozen_base()
 consumed=STATE/'demonstrations'/a['trial_id'];consumed.mkdir(parents=True,exist_ok=False)
 exclusive(consumed/'PLAN.json',plan);exclusive(consumed/'START.json',{'utc':now(),'maximum_attempts':1,'excluded_qualification_only':True,'scientific_started':status()['started']})
 passed=module.run_one(a)
 try:review=audit(a)
 except Exception as e:review={'trial_id':a['trial_id'],'independent_pass':False,'error':repr(e)}
 exclusive(consumed/'INDEPENDENT_VERIFICATION.json',review)
 result={'utc':now(),'trial_id':a['trial_id'],'controller_passed':passed,'independent_pass':review['independent_pass'],'run_batch_passed':bool(passed and review['independent_pass']),'excluded_qualification_only':True,'automatic_retry':False}
 exclusive(consumed/'STOP.json',result)
 if not result['run_batch_passed']:raise RuntimeError('Excluded demo failed; preserve and stop')
 return result

def verify_archive(out):
 out=Path(out);members=read(out/'TRANSFER_MANIFEST.json')['members'];chunk_manifest=read(out/'CHUNKS.json');chunks=chunk_manifest['chunks']
 proc=subprocess.Popen(['zstd','-q','-d','-c'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 import threading
 failure=[]
 def feed():
  try:
   combined=hashlib.sha256()
   for c in chunks:
    p=inside(out,c['name'])
    if c['bytes']>CHUNK or p.stat().st_size!=c['bytes'] or sha(p)!=c['sha256']:raise RuntimeError('Chunk size/hash mismatch')
    with p.open('rb') as f:
     while b:=f.read(1024**2):combined.update(b);proc.stdin.write(b)
   if combined.hexdigest()!=chunk_manifest['full_compressed_sha256']:raise RuntimeError('Combined compressed stream hash mismatch')
   proc.stdin.close()
  except BaseException as e:
   failure.append(repr(e))
   try:proc.stdin.close()
   except Exception:pass
 worker=threading.Thread(target=feed,daemon=True);worker.start();seen=set()
 try:
  with tarfile.open(fileobj=proc.stdout,mode='r|') as tf:
   for m in tf:
    if not m.isfile() or m.name not in members or m.name in seen:raise RuntimeError('Unexpected/duplicate archive member')
    h=hashlib.sha256();size=0;f=tf.extractfile(m)
    while b:=f.read(1024**2):h.update(b);size+=len(b)
    if {'sha256':h.hexdigest(),'bytes':size}!=members[m.name]:raise RuntimeError('Roundtrip member mismatch')
    seen.add(m.name)
  # Drain legal tar padding so decoder/feeder cannot hang on unread stdout.
  while trailing:=proc.stdout.read(1024**2):
   if any(trailing):raise RuntimeError('Unexpected trailing archive data')
  worker.join(timeout=30)
  if worker.is_alive():raise RuntimeError('Chunk feeder did not finish')
  err=proc.stderr.read();code=proc.wait(timeout=30)
  if code or failure or seen!=set(members):raise RuntimeError('Incomplete roundtrip '+repr(failure)+err.decode(errors='replace'))
  return {'passed':True,'members_checked':len(seen),'chunk_count':len(chunks),'offload_verified':False}
 finally:
  if proc.poll() is None:proc.kill()
  proc.wait(timeout=30);worker.join(timeout=5)
  for stream in [proc.stdin,proc.stdout,proc.stderr]:
   try:stream.close()
   except Exception:pass


def archive(ids):
 """Completed excluded qualification archive demonstration; originals always retained."""
 disk_check();paths=[inside(ROOT/'qualification/attempts',n) for n in ids]
 for p in paths:
  if not p.is_dir():raise RuntimeError('Missing qualification attempt')
  inventory_check(p)
  r=read(p/'RESULT.json')
  if r.get('role')!='qualification' or r.get('scientific_denominator') is not False:raise RuntimeError('Archive demonstration accepts excluded qualifications only')
 out=STATE/'archives'/('qualification-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'));out.mkdir(parents=True,exist_ok=False)
 members={}
 for path in paths:
  for p in sorted(path.rglob('*')):
   if p.is_symlink():raise RuntimeError('Evidence symlinks not permitted')
   if p.is_file():members[str(p.relative_to(ROOT))]={'sha256':sha(p),'bytes':p.stat().st_size}
 needed=sum(v['bytes'] for v in members.values());disk_check(2*needed+1024**3)
 exclusive(out/'TRANSFER_MANIFEST.json',{'utc':now(),'members':members,'excluded_qualification_only':True,'originals_retained':True,'offload_verified':False})
 try:
  with tempfile.TemporaryFile() as errors, (out/'evidence.tar.zst').open('xb') as compressed:
   proc=subprocess.Popen(['zstd','-q','-T1','-3','-c'],stdin=subprocess.PIPE,stdout=compressed,stderr=errors)
   try:
    with tarfile.open(fileobj=proc.stdin,mode='w|') as tf:
     for n in members:tf.add(inside(ROOT,n),arcname=n,recursive=False)
    proc.stdin.close();code=proc.wait()
    if code:errors.seek(0);raise RuntimeError('Compression failed '+errors.read().decode(errors='replace'))
   except BaseException:
    proc.kill();proc.wait()
    try:proc.stdin.close()
    except Exception:pass
    raise
  stream=out/'evidence.tar.zst';chunks=[]
  with stream.open('rb') as f:
   while True:
    first=f.read(min(CHUNK,1024**2))
    if not first:break
    p=out/('evidence.tar.zst-'+str(len(chunks)+1).zfill(3));size=len(first)
    with p.open('xb') as chunk:
     chunk.write(first)
     while size<CHUNK:
      b=f.read(min(CHUNK-size,1024**2))
      if not b:break
      chunk.write(b);size+=len(b)
    chunks.append({'name':p.name,'sha256':sha(p),'bytes':size})
  exclusive(out/'CHUNKS.json',{'chunks':chunks,'full_compressed_sha256':sha(stream),'maximum_chunk_bytes':CHUNK})
  roundtrip=verify_archive(out);seen_count=roundtrip['members_checked']
  exclusive(out/'ROUNDTRIP_VERIFICATION.json',{'utc':now(),'passed':True,'members_checked':seen_count,'chunk_count':len(chunks),'local_only':True,'offload_verified':False,'originals_retained':True})
  return {'archive':str(out),'passed':True,'offload_verified':False,'originals_retained':True}
 except BaseException as e:exclusive(out/'ARCHIVE_FAILURE.json',{'utc':now(),'error':repr(e),'originals_retained':True});raise

def main():
 if sys.platform=='darwin' and os.environ.get('IDBV2_OPERATOR_CAFFEINATED')!='1':
  env=dict(os.environ,IDBV2_OPERATOR_CAFFEINATED='1');os.execvpe('caffeinate',['caffeinate','-dimsu',sys.executable,str(Path(__file__).resolve()),*sys.argv[1:]],env)
 ap=argparse.ArgumentParser(description=__doc__);sub=ap.add_subparsers(dest='command',required=True)
 for name in ['status','preflight','disk-check']:sub.add_parser(name)
 sub.add_parser('verify').add_argument('--archive',type=Path)
 batch=sub.add_parser('run-batch');batch.add_argument('n',type=int);batch.add_argument('--qualification-plan',type=Path)
 sub.add_parser('archive').add_argument('--qualification-id',action='append',required=True)
 args=ap.parse_args()
 if args.command=='status':v=status()
 elif args.command=='preflight':v=preflight()
 elif args.command=='disk-check':v=disk_check()
 elif args.command=='verify' and args.archive:v=verify_archive(args.archive)
 elif args.command=='verify':v={'passed':True,'attempts':[inventory_check(p) for p in sorted(SCI.iterdir()) if p.is_dir()]} if SCI.exists() else {'passed':True,'attempts':[],'scientific_started':0}
 elif args.command=='archive':v=archive(args.qualification_id)
 else:
  if args.qualification_plan:v=qualification_demo(args.n,args.qualification_plan)
  else:run_batch(args.n);v=status()
 print(json.dumps(v,indent=2))
if __name__=='__main__':
 try:main()
 except Exception as e:print(json.dumps({'utc':now(),'status':'BLOCKED_OR_STOPPED','error':repr(e)}),file=sys.stderr);raise SystemExit(2)
