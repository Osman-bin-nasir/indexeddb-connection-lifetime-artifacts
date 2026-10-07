"""Neutral engineering snapshot smoke: tmpfs token, no browser/target/fault/qualification."""
import datetime,json,shlex,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];ADMIN=Path(__file__).parent
sys.path[:0]=[str(ADMIN),str(ROOT/'repairs/005'),str(ROOT)]
from qualification_fault_scope import BASE,VM,Events,remote,verify_frozen_base
from provision_vm import sha,save,disk_check
from live_capture import capture

def main():
 verify_frozen_base();disk_check(3*1024**3)
 out=ROOT/'support/live_snapshot/support-live-snapshot-20261004-00001';out.mkdir(parents=True,exist_ok=False)
 save(out/'START.json',{'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'role':'engineering_support','scientific_denominator':False,'qualification_assignment':None,'browser':False,'target_write':False,'fault':False,'source_sha256':sha(Path(__file__)),'live_capture_sha256':sha(ADMIN/'live_capture.py')})
 events=Events(out/'events.jsonl');vm=None;passed=False
 try:
  disk=out/'support.qcow2';subprocess.run(['qemu-img','create','-f','qcow2','-F','qcow2','-b',str(BASE),str(disk)],check=True,capture_output=True)
  vm=VM(disk,out/'boot',2233,'live-support-'+str(time.monotonic_ns()),events)
  token='support-live-snapshot-20261004-00001'
  remote(vm.port,"python3 -c "+shlex.quote("import pathlib; p=pathlib.Path('/dev/shm/idbv2-snapshot-token'); p.write_text("+repr(token)+")"))
  old_boot=vm.boot;old_pid=vm.proc.pid;view=capture(vm,disk,out,events)
  vm.qmp.execute('cont');vm.ready_after(time.monotonic_ns(),expected_boot=old_boot)
  observed=remote(vm.port,'cat /dev/shm/idbv2-snapshot-token').stdout.decode()
  passed=observed==token and vm.boot==old_boot and vm.proc.pid==old_pid and sha(disk)==view['sha256']
  save(out/'VERIFICATION.json',{'passed':passed,'tmpfs_token_retained':observed==token,'unchanged_boot_id':vm.boot==old_boot,'same_qemu_pid':vm.proc.pid==old_pid,'captured_disk_unchanged':sha(disk)==view['sha256'],'source_node_read_only':view['disk_node_read_only'],'scientific_started':0,'qualification_started':0})
 finally:
  if vm:vm.quit()
  events.file.close();save(out/'STOP.json',{'passed':passed,'scientific_started':0,'qualification_started':0})
  save(out/'SHA256.json',{str(p.relative_to(out)):sha(p) for p in sorted(out.rglob('*')) if p.is_file()})
 print(json.dumps({'passed':passed,'role':'engineering_support','scientific_started':0}),flush=True)
 if not passed:raise SystemExit(2)
if __name__=='__main__':main()
