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
 out=ROOT/'support/process_diagnostics/support-process-selection-20261004-00001';out.mkdir(parents=True,exist_ok=False)
 save(out/'START.json',{'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'role':'engineering_support','scientific_denominator':False,'qualification_assignment':None,'source_script_sha256':sha(Path(__file__)),'browser':True,'target_write':False,'prepare_sentinel':False,'fault':False,'worker_transport_role':'qualification build-phase guard; no assigned qualification is executed'})
 failed=json.loads((ROOT/'qualification/attempts/qualification-fault_scope_comparison-00002/assignment.json').read_text())
 spec=contract({**failed,'trial_id':'support-process-selection-20261004-00001'})
 events=Events(out/'events.jsonl');vm=worker=None
 try:
  disk=out/'support.qcow2';subprocess.run(['qemu-img','create','-f','qcow2','-F','qcow2','-b',str(BASE),str(disk)],check=True,capture_output=True)
  vm=VM(disk,out/'boot',2233,'process-probe-'+str(time.monotonic_ns()),events)
  profile='/var/lib/idbv2/'+spec['trial_id']+'/profile'
  remote(vm.port,'sudo mkdir -p '+shlex.quote(profile)+' && sudo chown -R research:research /var/lib/idbv2')
  worker=Worker(vm,spec,out,events)
  source=(PRIOR/'guest_fault_agent.py').read_text()
  command=source+"\nprint(json.dumps({'processes':list(inventory().values())}))\n"
  result=remote(vm.port,'sudo python3 -c '+shlex.quote(command.replace("if __name__=='__main__':main()","if False:main()")),check=False)
  (out/'process-inventory.stdout').write_bytes(result.stdout);(out/'process-inventory.stderr').write_bytes(result.stderr)
  save(out/'RESPONSE.json',{'returncode':result.returncode,'source_agent_sha256':sha(PRIOR/'guest_fault_agent.py')})
  if result.returncode:raise RuntimeError('Inventory diagnostic failed')
  records=json.loads(result.stdout)['processes'];chrome=[r for r in records if 'chrom' in Path(r['exe']).name.lower()]
  save(out/'CHROME_PROCESSES.json',{'profile_requested':profile,'executable_expected':spec.get('exe','/opt/idbv2/browsers/chromium-1243/chrome-linux-arm64/chrome'),'processes':chrome})
  print(json.dumps(chrome,indent=2),flush=True)
 finally:
  if worker:worker.close()
  if vm:vm.quit()
  events.file.close()
  save(out/'STOP.json',{'scientific_started':0,'assigned_qualification_started':0,'target_write':False,'fault':False})
  save(out/'SHA256.json',{str(p.relative_to(out)):sha(p) for p in sorted(out.rglob('*')) if p.is_file()})
if __name__=='__main__':main()
