"""No-write/no-fault browser-process diagnostic, not an assigned qualification."""
import datetime,json,subprocess,sys,time,shlex
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];ADMIN=Path(__file__).parent;PRIOR=ROOT/'extensions/fault_scope'
sys.path[:0]=[str(PRIOR),str(ROOT)]
from qualification_fault_scope import BASE,VM,Worker,Events,remote,verify_frozen_base
from payload import contract
from provision_vm import sha,save,disk_check

def main():
 verify_frozen_base();disk_check(3*1024**3)
 out=ROOT/'support/snapshot_diagnostics/support-sigkill-snapshot-forensics-20261004-00001';out.mkdir(parents=True,exist_ok=False)
 image=ROOT/'qualification/attempts/qualification-amendment-005-fault_scope_comparison-00002/overlay.qcow2';before=sha(image)
 save(out/'START.json',{'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'role':'engineering_support','source_sha256':before,'source_script_sha256':sha(Path(__file__)),'scientific_denominator':False,'qualification_assignment':None,'browser':False,'fault':False,'read_only':True})
 events=Events(out/'events.jsonl');vm=None
 try:
  disk=out/'helper.qcow2';subprocess.run(['qemu-img','create','-f','qcow2','-F','qcow2','-b',str(BASE),str(disk)],check=True,capture_output=True)
  vm=VM(disk,out/'boot',2233,'sigkill-forensics-'+str(time.monotonic_ns()),events,memory=1024)
  vm.attach_evidence_after_boot(image)
  spec={'device':'/dev/vdc','data_volume':False,'fstype':'ext4','profile':'/var/lib/idbv2/qualification-amendment-005-fault_scope_comparison-00002/profile','output':'/tmp/idbv2-extract-diagnostic'}
  result=remote(vm.port,'sudo /opt/idbv2/venv/bin/python /opt/idbv2/worker/guest_forensics.py',input=json.dumps(spec).encode(),check=False)
  (out/'forensics.stdout').write_bytes(result.stdout);(out/'forensics.stderr').write_bytes(result.stderr);save(out/'RESPONSE.json',{'returncode':result.returncode})
  print(result.stderr.decode(errors='replace'),flush=True)
 finally:
  if vm:vm.quit()
  events.file.close();after=sha(image)
  save(out/'STOP.json',{'source_unchanged':before==after,'source_sha256_before':before,'source_sha256_after':after,'scientific_started':0,'qualification_started':0})
  save(out/'SHA256.json',{str(p.relative_to(out)):sha(p) for p in sorted(out.rglob('*')) if p.is_file()})
  if before!=after:raise RuntimeError('Evidence hash changed')
if __name__=='__main__':main()
