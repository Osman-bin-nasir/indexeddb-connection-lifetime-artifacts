"""Once-only neutral qualification of mapper tooling. No registered cell, browser, target transaction or assigned fault."""
import datetime,json,shlex,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).parent
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'extensions/environment'))
import qualification_environment as host
from provision_vm import save,sha,gate,disk_check
from log_decode import decode,replay_prefix
from block_trace_v2 import BlockTrace

def main():
 gate();host.verify_frozen_base();disk_check(3*1024**3);plan=json.loads((HERE/'SUPPORT_PLAN_004.json').read_text())
 for n,h in plan['source_hashes'].items():
  if sha(ROOT/n)!=h:raise RuntimeError('Prospective support source changed '+n)
 if subprocess.run(['pgrep','-f','qemu-system-aarch64'],capture_output=True).returncode==0:raise RuntimeError('Active QEMU, no support consumed')
 save(HERE/'SUPPORT_CONSUMED_004.json',{'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'maximum_attempts':1,'scientific_started':0,'qualification_cells_passed':0})
 rows=[]
 for assignment in plan['support_assignments']:
  disk_check(3*1024**3);out=ROOT/'support/block_state'/assignment['support_id'];out.mkdir(parents=True,exist_ok=False)
  save(out/'START.json',{'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'role':'support_only','no_browser_or_target_or_assigned_fault':True,'scientific_denominator':False,'plan':plan,'assignment':assignment})
  events=host.Events(out/'events.jsonl');vm=trace=None;error=None;passed=False;original_args=host.vm_args
  try:
   root=out/'root.qcow2';data=out/'data.qcow2';log=out/'log.qcow2'
   subprocess.run(['qemu-img','create','-f','qcow2','-F','qcow2','-b',str(host.BASE),str(root)],check=True,capture_output=True)
   for p in [data,log]:subprocess.run(['qemu-img','create','-f','qcow2',str(p),'1G'],check=True,capture_output=True)
   save(out/'BLANK_INPUT_HASHES.json',{'data':sha(data),'log':sha(log),'size_bytes':1024**3})
   def vm_args(*a,**kw):
    args=original_args(*a,**kw)
    for name,p,slot in [('data',data,2),('log',log,3)]:
     args+=['-device',f'pcie-root-port,id={name}-port,slot={slot},chassis={slot}','-drive',f'file={p},if=none,id={name}-drive,format=qcow2,cache=none','-device',f'virtio-blk-pci,drive={name}-drive,serial=idbv2-{name},bus={name}-port']
    return args
   host.vm_args=vm_args;vm=host.VM(root,out/'boot',2235,'mapper-support-'+str(time.monotonic_ns()),events,memory=1024)
   trace=BlockTrace(host,vm,out,events)
   command='sudo python3 -c '+shlex.quote((HERE/'guest_mapper_v2.py').read_text());config={'role':'support','command':'neutral','mapper':assignment['mapper']}
   r=host.remote(vm.port,command,input=json.dumps(config).encode(),timeout=90,check=False);(out/'mapper.stdout').write_bytes(r.stdout);(out/'mapper.stderr').write_bytes(r.stderr);save(out/'MAPPER_RESPONSE.json',{'returncode':r.returncode,'configuration':config})
   if r.returncode:raise RuntimeError('Neutral mapper path failed')
   records=[json.loads(l) for l in r.stdout.splitlines()];save(out/'MAPPER_RECORDS.json',records)
   trace=host.remote(vm.port,"sudo cat /sys/kernel/tracing/events/block/block_rq_issue/format; sudo cat /sys/kernel/tracing/events/block/block_bio_queue/format",check=False);(out/'TRACE_FORMATS.stdout').write_bytes(trace.stdout);(out/'TRACE_FORMATS.stderr').write_bytes(trace.stderr)
   trace.close(reset=False);trace=None
   observed=(out/'block-trace.raw').read_text()
   boundary=json.loads((out/'BLOCK_TRACE_BOUNDARY.json').read_text())
   if not observed.rstrip().endswith('END') or boundary['diagnostics']:raise RuntimeError('Block trace incomplete/diagnostics')
   if not any(l.startswith('BLOCK ') and ' W' in l for l in observed.splitlines()):raise RuntimeError('Neutral block writes not observed')
   save(out/'BLOCK_TRACE_SUPPORT_CHECK.json',{'observed_block_events':sum(l.startswith('BLOCK ') for l in observed.splitlines()),'flush_fua_strings':[l.split()[-1] for l in observed.splitlines() if l.startswith('BLOCK ') and 'F' in l.split()[-1]],'end_observed':True,'diagnostics_clear':True,'no_scientific_cell':True})
   paused=vm.qmp.execute('stop');status=vm.qmp.execute('query-status')
   if status['return']['status']!='paused':raise RuntimeError('Quiesce failed')
   vm.quit();vm=None
   for p in [root,data,log]:p.chmod(0o444)
   hashes={p.name:sha(p) for p in [root,data,log]};save(out/'IMMUTABLE_CAPTURE.json',{'sha256':hashes,'pause':paused,'guest_volatile_state_discarded':True,'not_a_scientific_boundary':True})
   checks={'neutral_guest_pass':any(v['kind']=='NEUTRAL_MAPPER_PASS' for v in records),'both_neutral_direct_writes_recorded':len([v for v in records if v['kind']=='NEUTRAL_WRITE_WITNESS'])==2}
   if assignment['mapper']=='dm_log_writes':
    raw=out/'log.raw';subprocess.run(['qemu-img','convert','-f','qcow2','-O','raw',str(log),str(raw)],check=True,capture_output=True);meta=decode(raw);save(out/'LOG_DECODE.json',meta)
    marks={e['mark']:e['ordinal'] for e in meta['entries'] if e['mark']};checks['three_neutral_marks']=set(marks)=={'neutral-before','neutral-ack','neutral-boundary'};checks['flush_or_fua_recorded']=any(e['flags']&3 for e in meta['entries'])
    blank=out/'blank.raw';subprocess.run(['qemu-img','create','-f','raw',str(blank),'1G'],check=True,capture_output=True)
    for name in ['neutral-before','neutral-ack','neutral-boundary']:
     replay=out/(name+'.raw');replay_prefix(raw,blank,replay,marks[name])
     with replay.open('rb') as rf:a=rf.read(8192)
     expected=(bytes(8192) if name=='neutral-before' else b'A'*4096+bytes(4096) if name=='neutral-ack' else b'A'*4096+b'B'*4096);checks[name+'_replay_matches']=a==expected
    checks['original_log_unchanged']=sha(log)==hashes[log.name]
   if assignment['mapper']=='dm_flakey_drop_writes':checks['transition_validated']=any(v['kind']=='FLAKEY_TRANSITION' and 'drop_writes' in v['table'] for v in records)
   passed=all(checks.values());save(out/'SUPPORT_VERIFICATION.json',{'passed':passed,'checks':checks,'role':'support_only','qualification_cells_passed':0,'scientific_started':0,'real_filesystem_and_browser_qualification_pending':True})
  except BaseException as e:error=repr(e);events('SUPPORT_ERROR',error=error)
  finally:
   if trace:
    try:trace.close(reset=False)
    except Exception as e:events('TRACE_CLEANUP_ERROR',error=repr(e))
   if vm:vm.quit()
   host.vm_args=original_args;events.file.close();save(out/'STOP.json',{'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'passed':passed,'error':error,'scientific_started':0,'qualification_cells_passed':0,'automatic_retry':False});save(out/'SHA256.json',{str(p.relative_to(out)):sha(p) for p in out.rglob('*') if p.is_file()})
  rows.append({'support_id':assignment['support_id'],'passed':passed,'error':error});save(HERE/('SUPPORT_RESULT_004_'+assignment['mapper']+'.json'),rows[-1])
  if not passed:break
 save(HERE/'SUPPORT_STOP_004.json',{'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'rows':rows,'passed':len(rows)==1 and all(r['passed'] for r in rows),'scientific_started':0,'qualification_cells_passed':0,'automatic_retry':False})
 if len(rows)!=1 or not all(r['passed'] for r in rows):raise SystemExit(2)
if __name__=='__main__':main()
