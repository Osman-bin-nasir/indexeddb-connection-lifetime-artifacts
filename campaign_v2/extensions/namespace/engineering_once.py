"""Excluded pre-target namespace engineering, no target transaction or assigned fault."""
import datetime,hashlib,json,shlex,subprocess,sys,tarfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).parent
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'repairs/009'))
import qualification_fault_scope as host
from live_capture import capture
from provision_vm import save,sha,gate,disk_check

def extract(source,out,events):
 helper=None
 try:
  helperdisk=out/'helper.qcow2';subprocess.run(['qemu-img','create','-f','qcow2','-F','qcow2','-b',str(host.BASE),str(helperdisk)],capture_output=True,check=True)
  helper=host.VM(helperdisk,out/'boot',2234,'namespace-helper-'+str(time.monotonic_ns()),events,memory=1024)
  helper.attach_evidence_after_boot(source)
  config={'device':'/dev/vdc','data_volume':False,'fstype':'ext4','profile':PROFILE,'output':'/tmp/idbv2-extract'}
  r=host.remote(helper.port,'sudo /opt/idbv2/venv/bin/python /opt/idbv2/worker/guest_forensics.py',input=json.dumps(config).encode(),timeout=60,check=False)
  (out/'extract.stdout').write_bytes(r.stdout);(out/'extract.stderr').write_bytes(r.stderr)
  save(out/'EXTRACTION_RESPONSE.json',{'returncode':r.returncode,'role':'support_only','no_target_or_fault':True})
  if r.returncode:return {'available':False,'returncode':r.returncode}
  with (out/'extract.tar').open('xb') as f:subprocess.run(host.ssh(helper.port)+['sudo tar -C /tmp/idbv2-extract -cf - .'],stdout=f,stderr=subprocess.PIPE,timeout=60,check=True)
  files=out/'extract';files.mkdir()
  with tarfile.open(out/'extract.tar') as t:t.extractall(files,filter='data')
  inventory=json.loads((files/'inventory.json').read_text());ok=all(sha(files/'files'/x['relative_path'])==x['sha256'] for x in inventory['files'])
  return {'available':True,'returncode':0,'files_hash_match':ok,'files':len(inventory['files']),'read_only':inventory['block_read_only'],'replay_performed':inventory['replay_performed']}
 finally:
  if helper:helper.quit()

ID='support-pretarget-namespace-20261004-00001'
PROFILE='/var/lib/idbv2/'+ID+'/profile'
def main():
 gate();host.verify_frozen_base();disk_check(3*1024**3)
 plan=json.loads((HERE/'SUPPORT_PLAN_001.json').read_text())
 for n,h in plan['source_hashes'].items():
  if sha(ROOT/n)!=h:raise RuntimeError('Prospective source changed '+n)
 # Do not compete with a registered qualification VM or assume its stop file means pass.
 env=ROOT/'extensions/environment/QUALIFICATION_BATCH_STOP_002.json'
 if not env.exists() or not json.loads(env.read_text())['passed']:raise RuntimeError('Environment batch not independently passed/finished; no support started')
 out=ROOT/'support/namespace'/ID;out.mkdir(parents=True,exist_ok=False)
 save(out/'START.json',{'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'role':'support_only','scientific_denominator':False,'qualification_cells_passed':0,'no_target_write':True,'no_assigned_fault':True,'plan':plan})
 events=host.Events(out/'events.jsonl');vm=worker=None;error=None;passed=False;views=[]
 try:
  disk=out/'root.qcow2';subprocess.run(['qemu-img','create','-f','qcow2','-F','qcow2','-b',str(host.BASE),str(disk)],capture_output=True,check=True)
  vm=host.VM(disk,out/'boot',2233,'namespace-support-'+str(time.monotonic_ns()),events)
  # The imported worker requires enum qualification. This is an engineering configuration,
  # not an assigned qualification slot, and remains explicitly support-only in all receipts.
  a=next(x for x in host.assignments() if x['experiment']=='fault_scope_comparison' and x['fault']=='browser_sigkill')
  a=dict(a,trial_id=ID);spec=host.contract(a)
  host.remote(vm.port,'sudo mkdir -p '+shlex.quote(PROFILE)+' && sudo chown -R research:research /var/lib/idbv2')
  worker=host.Worker(vm,spec,out,events)
  prep=worker.command('prepare');save(out/'STRICT_SENTINEL_PRECONDITION.json',prep)
  if prep['guest']['precondition_oracle']['endpoint']!='lost' or not prep['guest']['precondition_oracle']['sentinel_valid']:raise RuntimeError('Strict sentinel/target absence not confirmed')
  original_boot=vm.boot;original_pid=vm.proc.pid
  # Capture a neutral baseline without a target write, then retain original guest RAM.
  before=out/'before';before.mkdir();first=capture(vm,disk,before,events);views.append(first)
  baseline=extract(disk,before,events);save(before/'OBSERVATION.json',baseline)
  vm.qmp.execute('cont')
  r=host.remote(vm.port,'/opt/idbv2/venv/bin/python -c '+shlex.quote((HERE/'namespace_precondition.py').read_text()),input=json.dumps({'phase':'strict_sentinel_complete_target_absent','profile':PROFILE}).encode(),check=False)
  (out/'namespace.stdout').write_bytes(r.stdout);(out/'namespace.stderr').write_bytes(r.stderr)
  if r.returncode:raise RuntimeError('Pre-target directory namespace support failed')
  namespace=json.loads(r.stdout)
  after=out/'after';after.mkdir();active=Path(first['active_after_snapshot']);second=capture(vm,active,after,events);views.append(second)
  observed=extract(active,after,events);save(after/'OBSERVATION.json',observed)
  checks={'after_namespace_available':observed['available'],'after_member_hashes':observed.get('files_hash_match',False),'after_nonempty':observed.get('files',0)>0,'read_only_no_replay':observed.get('read_only') is True and observed.get('replay_performed') is False,'original_boot_preserved':original_boot==vm.boot==first['original_boot_id']==second['original_boot_id'],'original_qemu_preserved':original_pid==vm.proc.pid==first['original_qemu_pid']==second['original_qemu_pid'],'original_images_unchanged':all(sha(Path(x['source']))==x['sha256'] for x in views),'directories_only':namespace['file_fsync_performed'] is False and all(x['directory_fsync_returned'] for x in namespace['directories']),'no_target_requested':not any(x['kind']=='GUEST_RECORD' and (x['guest'].get('command')=='write' or x['guest'].get('event',{}).get('kind')=='ACK') for x in events.values)}
  passed=all(checks.values());save(out/'SUPPORT_VERIFICATION.json',{'checks':checks,'passed':passed,'before':baseline,'after':observed,'role':'support_only','qualification_cells_passed':0,'no_fault_or_target':True,'callback_attribution':'not established'})
  if not passed:raise RuntimeError('Namespace engineering checks failed')
 except BaseException as e:error=repr(e);events('SUPPORT_ERROR',error=error)
 finally:
  if vm and vm.qmp:
   try:vm.qmp.execute('cont')
   except Exception:pass
  if worker:
   try:worker.close()
   except Exception as e:events('CLEANUP_ERROR',error=repr(e))
  if vm:vm.quit()
  events.file.close()
  save(out/'STOP.json',{'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'passed':passed,'error':error,'scientific_started':0,'qualification_cells_passed':0,'automatic_retry':False,'image_sha256':{str(p.relative_to(out)):sha(p) for p in out.rglob('*.qcow2')}})
  save(out/'SHA256.json',{str(p.relative_to(out)):sha(p) for p in sorted(out.rglob('*')) if p.is_file()})
 if not passed:raise SystemExit(2)
if __name__=='__main__':main()
