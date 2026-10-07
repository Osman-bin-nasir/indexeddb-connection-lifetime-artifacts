"""One prospectively declared neutral strace/toolchain test. No scientific/qualification assignment."""
import datetime,json,shlex,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).parent
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'repairs/009'))
import qualification_fault_scope as host
from provision_vm import save,sha,gate,disk_check
TRACE=['strace','-f','-ttt','-T','-yy','-xx','-s','0','-v','-e','trace=write,pwrite64,writev,pwritev,pwritev2,fsync,fdatasync,sync,syncfs,openat,close,close_range,dup,dup3,fcntl,lseek,fstat,newfstatat,statx,clone,clone3,execve,sendmsg,recvmsg']
def main():
 gate();host.verify_frozen_base();disk_check(3*1024**3)
 plan=json.loads((HERE/'SUPPORT_PLAN_001.json').read_text())
 for n,h in plan['source_hashes'].items():
  if sha(ROOT/n)!=h:raise RuntimeError('Declared support source changed '+n)
 if subprocess.run(['pgrep','-f','qemu-system-aarch64'],capture_output=True).returncode==0:raise RuntimeError('Another QEMU exists; support not consumed')
 out=ROOT/'support/byte_capture'/plan['support_id'];out.mkdir(parents=True,exist_ok=False)
 save(out/'START.json',{'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'role':'support_only','scientific_denominator':False,'qualification_cells_passed':0,'no_browser_or_target_or_assigned_fault':True,'plan':plan})
 events=host.Events(out/'events.jsonl');vm=None;error=None;passed=False
 try:
  disk=out/'root.qcow2';subprocess.run(['qemu-img','create','-f','qcow2','-F','qcow2','-b',str(host.BASE),str(disk)],capture_output=True,check=True)
  vm=host.VM(disk,out/'boot',2233,'byte-support-'+str(time.monotonic_ns()),events,memory=1024)
  host.remote(vm.port,'cat > /tmp/neutral_io.py',input=(HERE/'neutral_io.py').read_bytes())
  r=host.remote(vm.port,' '.join(map(shlex.quote,TRACE+['python3','/tmp/neutral_io.py'])),timeout=90,check=False)
  (out/'witness.json').write_bytes(r.stdout);(out/'strace.raw').write_bytes(r.stderr);save(out/'TRACE_COMMAND.json',{'argv':TRACE,'returncode':r.returncode,'capture_destination':'host SSH stderr, no guest capture log','no_timing_gate_relaxed':True})
  tools=host.remote(vm.port,"strace --version; sudo bpftrace --info; sudo bpftrace -l 'kprobe:vfs*write*'; sudo dmsetup targets",timeout=30,check=False)
  (out/'TOOLS.stdout').write_bytes(tools.stdout);(out/'TOOLS.stderr').write_bytes(tools.stderr)
  # Presence is an engineering check only, not sufficient for browser capture qualification.
  witness=json.loads(r.stdout);raw=r.stderr.decode();checks={'neutral_io_exited':r.returncode==0,'witness_has_fd_reuse':len({x['ofd'] for x in witness['witness'] if x['kind']=='identity'})==2,'all_requested_io_visible':all(k+'(' in raw for k in ['write','pwrite64','writev','pwritev','fsync','fdatasync']),'child_traced':'CLONE' in raw and 'child' in raw,'full_4096_payload_visible':('\\x00\\x01\\x02' in raw and '\\xfd\\xfe\\xff' in raw),'device_and_inode_visible':'st_ino=' in raw and 'st_dev=' in raw,'normal_trace_exit':'exited with 0' in raw,'no_known_strace_error':not any(k in raw for k in ['Operation not permitted','strace: invalid','strace: attach:'])}
  passed=all(checks.values());save(out/'SUPPORT_VERIFICATION.json',{'passed':passed,'checks':checks,'browser_capture_qualified':False,'offset_ofd_parser_pending':True,'capture_loss_at_fault_pending':True,'scientific_started':0,'qualification_cells_passed':0})
 except BaseException as e:error=repr(e);events('SUPPORT_ERROR',error=error)
 finally:
  if vm:vm.quit()
  events.file.close();save(out/'STOP.json',{'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'passed':passed,'error':error,'scientific_started':0,'qualification_cells_passed':0,'automatic_retry':False})
  save(out/'SHA256.json',{str(p.relative_to(out)):sha(p) for p in sorted(out.rglob('*')) if p.is_file()})
 if not passed:raise SystemExit(2)
if __name__=='__main__':main()
