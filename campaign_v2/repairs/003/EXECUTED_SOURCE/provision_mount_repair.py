"""Single-use, separately derived base; no browser, fault or scientific assignment."""
import datetime,json,os,shlex,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];ADMIN=Path(__file__).parent
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ADMIN))
from qualification import VM,Events,BASE,remote,verify_frozen_base
from provision_vm import sha,save,disk_check
from boot_mounts import transform,checked_inventory

def main():
 lock=verify_frozen_base();disk_check(3*1024**3)
 for n,h in json.loads((ADMIN/'PROVISION_SOURCE_HASHES.json').read_text()).items():
  if sha(ADMIN/n)!=h:raise RuntimeError('Prospective source changed')
 out=ROOT/'support/boot_diagnostics/support-mount-repair-provision-20261004-00001';out.mkdir(parents=True,exist_ok=False)
 save(out/'START.json',{'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'role':'engineering_provision','scientific_denominator':False,'qualification_assignment':None,'browser':False,'fault':False,'source_base_sha256':sha(BASE)})
 disk=ADMIN/'mount-pinned-base.qcow2'
 if disk.exists():raise RuntimeError('Derived base exists; no overwrite')
 subprocess.run(['qemu-img','create','-f','qcow2','-F','qcow2','-b',str(BASE),str(disk)],check=True,capture_output=True)
 events=Events(out/'events.jsonl');vm=None;success=False
 try:
  vm=VM(disk,out/'boot',2233,'support-mount-provision-'+str(__import__('time').monotonic_ns()),events)
  before=checked_inventory(remote,vm.port,out,'mount-inventory-before')
  new=transform(before['fstab']);(out/'fstab-before.txt').write_text(before['fstab']);(out/'fstab-after.txt').write_text(new)
  script="""sudo python3 -c 'import os,pathlib,sys; p=pathlib.Path("/etc/fstab"); data=sys.stdin.buffer.read(); temp=p.with_name("fstab.idbv2-003"); fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o644); f=os.fdopen(fd,"wb"); f.write(data); f.flush(); os.fsync(f.fileno()); f.close(); os.replace(temp,p); d=os.open(p.parent,os.O_DIRECTORY); os.fsync(d); os.close(d); print("file-and-directory-fsync-completed")'"""
  r=remote(vm.port,script,input=new.encode());(out/'fstab-write.stdout').write_bytes(r.stdout)
  remote(vm.port,'sudo systemctl daemon-reload')
  after=checked_inventory(remote,vm.port,out,'mount-inventory-after',new)
  files={'chromium':'/opt/idbv2/browsers/chromium-1243/chrome-linux-arm64/chrome',**{n:'/opt/idbv2/worker/'+n for n in lock['worker_files']}}
  hashes={n:remote(vm.port,'sha256sum '+shlex.quote(p)).stdout.decode().split()[0] for n,p in files.items()}
  if any(hashes[n]!=h for n,h in lock['worker_files'].items()) or hashes['chromium']!='839efe5fd8b6a773dd81b2e10afdc15f3c0a17316fb82b5908c0533306c4ed9e':raise RuntimeError('Pinned guest measurement payload changed')
  save(out/'PAYLOAD_HASHES.json',hashes)
  r=remote(vm.port,'sudo sync && sudo systemctl poweroff',check=False);(out/'shutdown.stdout').write_bytes(r.stdout);(out/'shutdown.stderr').write_bytes(r.stderr)
  vm.proc.wait(timeout=60)
  if vm.proc.returncode!=0:raise RuntimeError('Unclean QEMU shutdown')
  vm.quit();vm=None
  r=subprocess.run(['qemu-img','check','--output=json',str(disk)],check=True,capture_output=True);(out/'QEMU_IMG_CHECK.json').write_bytes(r.stdout)
  if sha(BASE)!=lock['derived_base_sha256']:raise RuntimeError('Original base changed')
  disk.chmod(0o444)
  save(ADMIN/'REPAIRED_BASE_LOCK.json',{**lock,'parent_base_sha256':lock['derived_base_sha256'],'derived_base_sha256':sha(disk),'derived_base_path':str(disk),'technical_amendment':'003','fstab':new,'guest_payload_sha256':hashes,'no_previous_cell_pass_carried_forward':True,'technical_hash_lock_complete':False})
  success=True
 finally:
  if vm:vm.quit()
  events.file.close()
  save(out/'STOP.json',{'passed':success,'source_base_unchanged':sha(BASE)==lock['derived_base_sha256'],'derived_base_sha256':sha(disk),'qualification_started':0,'scientific_started':0})
  save(out/'SHA256.json',{str(p.relative_to(out)):sha(p) for p in sorted(out.rglob('*')) if p.is_file()})
 if not success:raise RuntimeError('Provisioning failed; preserve and stop')
 print('Derived mount-selector repair built; no cell qualified or science started',flush=True)
if __name__=='__main__':main()
