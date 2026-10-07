"""Read only a preserved trace-worker deployment and original pinned reader; no target/fault/oracle."""
import datetime,hashlib,json,shlex,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).parent
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'repairs/009'))
import qualification_fault_scope as host
from provision_vm import save,sha,gate,disk_check

def main():
 gate();host.verify_frozen_base();disk_check(3*1024**3);plan=json.loads((HERE/'PLAN_001.json').read_text())
 source=Path(plan['source']);before=sha(source)
 if before!=plan['source_sha256']:raise RuntimeError('Original source hash mismatch')
 out=ROOT/'support/reader_probe'/plan['support_id'];out.mkdir(parents=True,exist_ok=False)
 save(out/'START.json',{'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'role':'support_only','scientific_started':0,'plan':plan})
 events=host.Events(out/'events.jsonl');vm=None;error=None
 try:
  disk=out/'helper.qcow2';subprocess.run(['qemu-img','create','-f','qcow2','-F','qcow2','-b',str(host.BASE),str(disk)],check=True,capture_output=True)
  vm=host.VM(disk,out/'helper',2234,'reader-probe-'+str(time.monotonic_ns()),events,memory=1024);vm.attach_evidence_after_boot(source)
  code="""import subprocess,pathlib,hashlib,json
root=pathlib.Path('/mnt/source');root.mkdir(exist_ok=True)
subprocess.run(['mount','-t','ext4','-o','ro,noload','/dev/vdc1',str(root)],check=True)
try:
 rows=[]
 for name in ['opt/idbv2/trace-worker.py','opt/idbv2/worker/guest_worker.py']:
  p=root/name;v={'path':name,'exists':p.exists()}
  if p.is_file():v.update(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
  rows.append(v)
 print(json.dumps({'files':rows,'original_block_read_only':subprocess.check_output(['blockdev','--getro','/dev/vdc'],text=True).strip()=='1'}))
finally:subprocess.run(['umount',str(root)],check=True)
"""
  r=host.remote(vm.port,'sudo python3 -c '+shlex.quote(code),check=False);(out/'probe.stdout').write_bytes(r.stdout);(out/'probe.stderr').write_bytes(r.stderr);save(out/'RESPONSE.json',{'returncode':r.returncode})
  if r.returncode:raise RuntimeError('Source probe unavailable')
  if sha(source)!=before:raise RuntimeError('Read-only source changed')
 except Exception as e:error=repr(e);events('SUPPORT_ERROR',error=error)
 finally:
  if vm:vm.quit()
  events.file.close();save(out/'STOP.json',{'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'error':error,'source_unchanged':sha(source)==before,'no_endpoint_reclassification':True,'scientific_started':0,'qualification_cells_passed':0})
  save(out/'SHA256.json',{str(p.relative_to(out)):sha(p) for p in out.rglob('*') if p.is_file()})
 if error:raise SystemExit(2)
if __name__=='__main__':main()
