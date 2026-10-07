"""Excluded support-only volume engineering. No browser, target, fault assignment or endpoint."""
import datetime,json,shlex,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).parent
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'repairs/007'))
import qualification_workloads as host
from provision_vm import save,sha,disk_check,gate

original_args=host.vm_args
DATA=None

def args(*a,**kw):
 value=original_args(*a,**kw)
 return value+['-drive',f'file={DATA},if=none,id=support-data,format=qcow2,cache=none','-device','virtio-blk-pci,drive=support-data,serial=idbv2-data']

def run(profile):
 global DATA
 gate();host.verify_frozen_base();disk_check(3*1024**3)
 out=ROOT/'support/volumes'/('support-volume-'+profile+'-20261004-00001');out.mkdir(parents=True,exist_ok=False)
 save(out/'START.json',{'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'role':'support_only','qualification_assignment':None,'scientific_assignment':None,'scientific_denominator':False,'source_hashes':{p.name:sha(p) for p in HERE.glob('*.py')},'host_module_sha256':sha(Path(host.__file__)),'fresh_matched_data_bytes':1024**3,'no_browser_or_target':True,'purpose':'serial/blank-device guards, mkfs/mount/default flags, root/data separation and mount/probe continuity across engineering reset','helper_vm_module_role_field':'Imported module labels6GiB VM_START role qualification; this support has no assigned qualification and is excluded'})
 events=host.Events(out/'events.jsonl');vm=None;passed=False;error=None
 try:
  DATA=out/'data.qcow2';root=out/'root-overlay.qcow2'
  subprocess.run(['qemu-img','create','-f','qcow2',str(DATA),'1G'],capture_output=True,check=True)
  subprocess.run(['qemu-img','create','-f','qcow2','-F','qcow2','-b',str(host.BASE),str(root)],capture_output=True,check=True)
  host.vm_args=args
  vm=host.VM(root,out/'boot',2235,'volume-support-'+str(time.monotonic_ns()),events)
  sysctls='cat /proc/sys/vm/dirty_writeback_centisecs /proc/sys/vm/dirty_expire_centisecs /proc/sys/vm/dirty_ratio /proc/sys/vm/dirty_background_ratio'
  before=host.remote(vm.port,sysctls).stdout
  result=host.remote(vm.port,'sudo /opt/idbv2/venv/bin/python -c '+shlex.quote((HERE/'guest_volume.py').read_text()),input=json.dumps({'role':'support','filesystem':profile}).encode(),timeout=120,check=False)
  (out/'volume-setup.stdout').write_bytes(result.stdout);(out/'volume-setup.stderr').write_bytes(result.stderr);save(out/'VOLUME_SETUP_RESPONSE.json',{'returncode':result.returncode})
  if result.returncode:raise RuntimeError('Volume provisioning support failed; exact response preserved')
  records=[json.loads(l) for l in result.stdout.splitlines()];ready=next(x for x in records if x.get('kind')=='DATA_VOLUME_READY');save(out/'VOLUME_READY.json',ready)
  payload=b'neutral volume continuity probe, no IndexedDB or target transaction\n'
  probe="import os,pathlib,hashlib; p=pathlib.Path('/var/lib/idbv2/neutral-support-probe'); p.write_bytes("+repr(payload)+"); f=p.open('rb'); os.fsync(f.fileno()); f.close(); d=os.open(str(p.parent),os.O_DIRECTORY); os.fsync(d);os.close(d);print(hashlib.sha256(p.read_bytes()).hexdigest())"
  original_probe=host.remote(vm.port,'python3 -c '+shlex.quote(probe)).stdout.decode().strip();boot=vm.boot
  reset=vm.qmp.execute('system_reset');health=vm.ready_after(reset['dispatch_ns'],boot)
  mount=json.loads(host.remote(vm.port,'findmnt -J /var/lib/idbv2').stdout);fstab=host.remote(vm.port,'cat /etc/fstab').stdout.decode();after=host.remote(vm.port,sysctls).stdout
  readprobe=host.remote(vm.port,'sha256sum /var/lib/idbv2/neutral-support-probe').stdout.decode().split()[0]
  actual=mount['filesystems'][0];opts=set(actual['options'].split(','));expected_fs='xfs' if profile=='xfs_defaults' else 'ext4'
  checks={'dedicated_serial':ready['data_serial']=='idbv2-data','matched_size':ready['data_size_bytes']==1024**3,'root_data_separate':ready['root_device']=='/dev/vda1' and ready['data_device']=='/dev/vdc','fstype':actual['fstype']==expected_fs,'exact_data_source':actual['source']=='/dev/vdc','fstab_persisted':ready['fstab_added'] in fstab,'unchanged_sysctls':before==after,'reset_boot_changed':boot!=vm.boot,'neutral_probe_hash_preserved':readprobe==original_probe,'custom_options_present':profile!='ext4_commit30' or {'commit=30','discard'}<=opts,'defaults_no_custom_mount_arguments':profile=='ext4_commit30' or ready['mount_arguments']==['mount','-t',expected_fs,'/dev/vdc','/var/lib/idbv2']}
  save(out/'SUPPORT_VERIFICATION.json',{'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'passed':all(checks.values()),'checks':checks,'role':'support_only','scientific_denominator':False,'qualification_cells_passed':0,'post_reset_mount':mount,'health':health,'old_boot_id':boot,'new_boot_id':vm.boot,'no_browser_or_target':True})
  passed=all(checks.values())
  if not passed:raise RuntimeError('Volume support contract failed')
 except Exception as e:error=repr(e);events('SUPPORT_ERROR',error=error)
 finally:
  if vm:vm.quit()
  host.vm_args=original_args;events.file.close()
  save(out/'STOP.json',{'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'passed':passed,'error':error,'role':'support_only','qualification_cells_passed':0,'scientific_started':0,'automatic_retry':False,'image_sha256':{p.name:sha(p) for p in out.glob('*.qcow2')}})
  save(out/'SHA256.json',{str(p.relative_to(out)):sha(p) for p in sorted(out.rglob('*')) if p.is_file()})
 if not passed:raise RuntimeError('Support stopped: '+str(error))
 return out

def main():
 # No concurrent VM work, even if a preceding qualification failed.
 for p in [ROOT/'repairs/007/QUALIFICATION_BATCH_STOP.json',ROOT/'repairs/008/QUEUED_SMOKE_STOP.json']:
  if not p.exists():raise RuntimeError('Previous supervisor not finished; no support started')
 for profile in ['ext4_commit30','ext4_defaults','xfs_defaults']:print(str(run(profile)),flush=True)
if __name__=='__main__':main()
