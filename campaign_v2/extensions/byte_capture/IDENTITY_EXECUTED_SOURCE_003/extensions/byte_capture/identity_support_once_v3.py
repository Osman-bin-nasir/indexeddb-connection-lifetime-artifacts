"""Neutral kernel identity support only. Exactly one fresh declared attempt, no browser or assigned fault."""
import datetime,json,queue,shlex,subprocess,sys,threading,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).parent
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'repairs/009'))
import qualification_fault_scope as host
from provision_vm import save,sha,gate,disk_check
from engineering_once_v2 import TRACE

def main():
 gate();host.verify_frozen_base();disk_check(3*1024**3);plan=json.loads((HERE/'IDENTITY_SUPPORT_PLAN_003.json').read_text())
 for n,h in plan['source_hashes'].items():
  if sha(ROOT/n)!=h:raise RuntimeError('Declared support source changed '+n)
 if subprocess.run(['pgrep','-f','qemu-system-aarch64'],capture_output=True).returncode==0:raise RuntimeError('QEMU already active, no support consumed')
 out=ROOT/'support/byte_identity'/plan['support_id'];out.mkdir(parents=True,exist_ok=False)
 save(out/'START.json',{'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'role':'support_only','scientific_denominator':False,'no_browser_or_target_or_fault':True,'plan':plan})
 events=host.Events(out/'events.jsonl');vm=bpf=None;error=None;passed=False;bfperror=None
 try:
  disk=out/'root.qcow2';subprocess.run(['qemu-img','create','-f','qcow2','-F','qcow2','-b',str(host.BASE),str(disk)],capture_output=True,check=True)
  vm=host.VM(disk,out/'boot',2233,'identity-support-'+str(time.monotonic_ns()),events,memory=1024)
  host.remote(vm.port,'cat > /tmp/file_identity.bt',input=(HERE/'file_identity_v3.bt').read_bytes());host.remote(vm.port,'cat > /tmp/neutral_io.py',input=(HERE/'neutral_io.py').read_bytes())
  st=json.loads(host.remote(vm.port,"python3 -c 'import os,json; s=os.stat(\"/tmp\");print(json.dumps({\"major\":os.major(s.st_dev),\"minor\":os.minor(s.st_dev)}))'").stdout);dev=(st['major']<<20)|st['minor'];save(out/'KERNEL_DEVICE_ENCODING.json',{'major_minor':st,'kernel_dev_t':dev})
  command='sudo bash -c '+shlex.quote('echo $$ > /tmp/idbv2-bpf.pid; exec env BPFTRACE_PERF_RB_PAGES=1024 bpftrace -q /tmp/file_identity.bt '+str(dev))
  bfperror=(out/'identity.stderr').open('xb');bpf=subprocess.Popen(host.ssh(vm.port)+[command],stdout=subprocess.PIPE,stderr=bfperror);q=queue.Queue();log=(out/'identity.raw').open('xb')
  def read():
   for line in bpf.stdout:log.write(line);log.flush();q.put(line)
   log.close();q.put(None)
  thread=threading.Thread(target=read,daemon=True);thread.start();end=time.monotonic()+30
  while time.monotonic()<end:
   item=q.get(timeout=max(.1,end-time.monotonic()))
   if item==b'READY\n':break
   if item is None:raise RuntimeError('Kernel capture exited before READY')
  else:raise RuntimeError('Kernel capture readiness not observed')
  r=host.remote(vm.port,shlex.join(TRACE+['python3','/tmp/neutral_io.py']),timeout=90,check=False);(out/'witness.json').write_bytes(r.stdout);(out/'strace.raw').write_bytes(r.stderr);save(out/'TRACE_RESPONSE.json',{'returncode':r.returncode})
  pid=int(host.remote(vm.port,'cat /tmp/idbv2-bpf.pid').stdout);host.remote(vm.port,'sudo kill -INT '+str(pid));bpf.wait(timeout=15);thread.join(timeout=10);bfperror.close();bfperror=None
  text=(out/'identity.raw').read_text();checks={'neutral_io_success':r.returncode==0,'kernel_file_records':any(l.startswith('FILE ') for l in text.splitlines()),'kernel_return_records':any(l.startswith('RETURN ') for l in text.splitlines()),'kernel_capture_ended_cleanly':text.rstrip().endswith('END') and bpf.returncode==0,'no_capture_diagnostics':not (out/'identity.stderr').read_text().strip()}
  passed=all(checks.values());save(out/'SUPPORT_VERIFICATION.json',{'passed':passed,'checks':checks,'role':'support_only','qualification_cells_passed':0,'scientific_started':0,'cross_stream_identity_join_pending':True})
 except BaseException as e:error=repr(e);events('SUPPORT_ERROR',error=error)
 finally:
  if bpf and bpf.poll() is None:bpf.terminate();bpf.wait(timeout=15)
  if bfperror:bfperror.close()
  if vm:vm.quit()
  events.file.close();save(out/'STOP.json',{'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'passed':passed,'error':error,'scientific_started':0,'qualification_cells_passed':0,'automatic_retry':False});save(out/'SHA256.json',{str(p.relative_to(out)):sha(p) for p in out.rglob('*') if p.is_file()})
 if not passed:raise SystemExit(2)
if __name__=='__main__':main()
