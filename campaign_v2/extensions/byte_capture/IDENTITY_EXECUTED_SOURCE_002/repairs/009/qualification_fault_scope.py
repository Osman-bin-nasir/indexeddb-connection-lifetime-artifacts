"""Excluded qualification only. No scientific assignment or automatic retry exists here."""
from __future__ import annotations
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import queue
import shlex
import shutil
import socket
import subprocess
import tarfile
import threading
import time

from payload import contract
from provision_vm import ROOT, KEY, PRIVATE, gate, sha, save, disk_check
from qmp_client import QMP
from forensic_formats import inspect
from identity_io import write_identity,read_identity
from boot_mounts import checked_inventory
from fault_agent import FaultAgent
from live_capture import capture

BASE=ROOT/'repairs/003/mount-pinned-base.qcow2'
SEED=ROOT/'provision/vm/seed.iso'
ATTEMPTS=ROOT/'qualification/attempts'
FILES=['guest_worker.py','transaction.js','guest_forensics.py']


class Events:
    def __init__(self,path):
        self.file=Path(path).open('x')
        self.lock=threading.Lock()
        self.values=[]
    def __call__(self,kind,**values):
        item={'host_monotonic_ns':time.monotonic_ns(),'kind':kind,**values}
        with self.lock:
            self.file.write(json.dumps(item)+'\n');self.file.flush()
            self.values.append(item)
        return item
    def qmp(self,item):
        self('QMP',**item)


def ssh(port):
    return ['ssh','-i',str(KEY),'-p',str(port),'-o','BatchMode=yes',
            '-o','StrictHostKeyChecking=accept-new','-o',f'UserKnownHostsFile={PRIVATE/"known_hosts"}',
            '-o','ConnectTimeout=3','research@127.0.0.1']


def remote(port,cmd,*,input=None,timeout=30,check=True):
    return subprocess.run(ssh(port)+[cmd],input=input,capture_output=True,timeout=timeout,check=check)


def vm_args(disk,path,port,name,memory=6144,readonly_disk=None):
    if memory==1024 and readonly_disk is not None:
        raise RuntimeError('Forensic helper must boot before evidence is attached')
    args=['qemu-system-aarch64','-name',name,'-machine','virt,accel=hvf','-cpu','host','-smp','4',
          '-m',str(memory),'-bios','/opt/homebrew/share/qemu/edk2-aarch64-code.fd',
          '-drive',f'file={disk},if=virtio,format=qcow2,cache=none',
          '-drive',f'file={SEED},if=virtio,format=raw,readonly=on',
          '-device','virtio-net-pci,netdev=net0','-netdev',f'user,id=net0,hostfwd=tcp:127.0.0.1:{port}-:22',
          '-qmp',f'unix:{path},server=on,wait=off','-nographic']
    if readonly_disk:
        args+=['-drive',f'file={readonly_disk},if=virtio,format=qcow2,cache=none,readonly=on']
    if memory==1024:
        args+=['-device','pcie-root-port,id=evidence-port,slot=1,chassis=1']
    return args


class VM:
    def __init__(self,disk,out,port,name,events,memory=6144,readonly_disk=None):
        self.out=Path(out);self.out.mkdir(exist_ok=False)
        self.port=port;self.events=events;self.qmp=None
        self.sockdir=Path('/tmp')/f'idbv2-{name}'
        self.sockdir.mkdir(mode=0o700,exist_ok=False)
        self.path=self.sockdir/'qmp.sock'
        with socket.socket() as s:
            s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
            s.bind(('127.0.0.1',port))
        args=vm_args(disk,self.path,port,name,memory,readonly_disk)
        self.started=time.monotonic_ns()
        self.console=(self.out/'console.txt').open('xb')
        self.proc=subprocess.Popen(args,stdin=subprocess.DEVNULL,stdout=self.console,stderr=subprocess.STDOUT)
        events('VM_START',command=args,pid=self.proc.pid,role='qualification' if memory==6144 else 'forensic_helper')
        try:
            self.ready_after(self.started)
            lock=json.loads((Path(__file__).parent/'REPAIRED_BASE_LOCK.json').read_text())
            value=checked_inventory(remote,self.port,self.out,'mount-identity',lock['fstab'])
            self.events('AUXILIARY_MOUNT_IDENTITY',stage='boot',identity=value)
            self.qmp=QMP(self.path,lambda item:events('QMP',vm_pid=self.proc.pid,qmp_path=str(self.path),**item))
        except Exception:
            self.quit()
            raise
    def attach_evidence_after_boot(self,disk):
        # A cloned evidence root has the same LABEL/UUID. Never expose it at helper boot.
        source=remote(self.port,'findmnt -nr -o SOURCE /').stdout.decode().strip()
        if source!='/dev/vda1':raise RuntimeError('Unexpected forensic helper boot root')
        self.qmp.execute('blockdev-add',{'driver':'qcow2','node-name':'evidence-node','read-only':True,
                         'file':{'driver':'file','filename':str(disk),'read-only':True,
                                 'cache':{'direct':True,'no-flush':False}}})
        self.qmp.execute('device_add',{'driver':'virtio-blk-pci','drive':'evidence-node',
                         'id':'evidence-device','serial':'idbv2-evidence','bus':'evidence-port'})
        end=time.monotonic()+15
        while time.monotonic()<end:
            result=remote(self.port,'test -b /dev/vdc && cat /sys/block/vdc/ro /sys/block/vdc/serial',check=False)
            if result.returncode==0 and result.stdout.decode().splitlines()==['1','idbv2-evidence']:
                self.events('EVIDENCE_ATTACHED_AFTER_HELPER_BOOT',device='/dev/vdc',serial='idbv2-evidence',read_only=True,
                            helper_root=source,query_block=self.qmp.execute('query-block'))
                return
            time.sleep(0.1)
        raise RuntimeError('Evidence hot-plug identity/read-only state not confirmed')
    def ready_after(self,start,old_boot=None,expected_boot=None):
        deadline=start+180_000_000_000
        observations=[]
        while time.monotonic_ns()<deadline:
            if self.proc.poll() is not None:raise RuntimeError('QEMU exited during readiness')
            cmd="python3 -c 'import json,pathlib,time; print(json.dumps({\"boot_id\":pathlib.Path(\"/proc/sys/kernel/random/boot_id\").read_text().strip(),\"uptime\":pathlib.Path(\"/proc/uptime\").read_text(),\"machine\":__import__(\"platform\").machine(),\"guest_ns\":time.monotonic_ns()}))'"
            try:
                result=remote(self.port,cmd,timeout=10,check=False)
                value=json.loads(result.stdout) if result.returncode==0 else None
            except (subprocess.TimeoutExpired,json.JSONDecodeError):value=None
            if value and value['machine']=='aarch64' and (old_boot is None or value['boot_id']!=old_boot) and (expected_boot is None or value['boot_id']==expected_boot):
                now=time.monotonic_ns()
                if observations and observations[-1]['identity']['boot_id']!=value['boot_id']:observations=[]
                if not observations or now-observations[-1]['host_ns']>=2_500_000_000:
                    observations.append({'host_ns':now,'identity':value})
                    self.events('HEALTHY_OBSERVATION',port=self.port,observation=observations[-1])
                if len(observations)>=3 and now-observations[0]['host_ns']>=5_000_000_000:
                    self.boot=value['boot_id'];self.ready=time.monotonic_ns()
                    return observations
            else:observations=[]
            time.sleep(0.25)
        raise RuntimeError('READINESS_180S: three healthy observations spanning 5s were not obtained')
    def quit(self):
        if self.proc.poll() is None:
            try:
                if self.qmp:self.qmp.execute('quit')
                else:self.proc.terminate()
                self.proc.wait(timeout=15)
            except Exception:
                self.proc.kill();self.proc.wait(timeout=10)
                self.events('VM_CLEANUP_FORCE_EXIT',pid=self.proc.pid)
        if self.qmp:
            self.qmp.close();self.qmp=None
        self.console.close()


class Worker:
    def __init__(self,vm,spec,out,events,recovery=False):
        self.events=events;self.items=[];self.condition=threading.Condition();self.next=0
        self.error=(Path(out)/('recovery-stderr.txt' if recovery else 'worker-stderr.txt')).open('xb')
        self.proc=subprocess.Popen(ssh(vm.port)+['xvfb-run -a -s "-screen 0 1440x1000x24" /opt/idbv2/venv/bin/python /opt/idbv2/worker/guest_worker.py'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.error)
        self.thread=threading.Thread(target=self.read,daemon=True);self.thread.start()
        config=dict(spec);config['profile']=f'/var/lib/idbv2/{spec["trial_id"]}/profile'
        try:
            self.send(config)
            self.wait(lambda x:x['guest'].get('kind')=='WORKER_READY',90)
        except Exception:
            self.close()
            raise
    def read(self):
        for raw in self.proc.stdout:
            received=time.monotonic_ns()
            try:item=json.loads(raw)
            except json.JSONDecodeError:
                self.events('WORKER_NON_JSON',text=raw.decode(errors='replace'));continue
            value=self.events('GUEST_RECORD',guest=item,receipt_ns=received)
            with self.condition:self.items.append(value);self.condition.notify_all()
        with self.condition:self.condition.notify_all()
    def send(self,value):
        self.proc.stdin.write((json.dumps(value)+'\n').encode());self.proc.stdin.flush()
    def wait(self,predicate,timeout=30):
        end=time.monotonic()+timeout
        with self.condition:
            while True:
                for value in self.items:
                    if predicate(value):return value
                if self.proc.poll() is not None:raise RuntimeError('Guest worker exited before required record')
                if time.monotonic()>=end:raise TimeoutError('Required guest record missing')
                self.condition.wait(min(0.1,end-time.monotonic()))
    def command(self,name,timeout=30):
        self.next+=1;request_id=self.next
        sent=time.monotonic_ns();self.send({'command':name,'request_id':request_id})
        value=self.wait(lambda x:x['guest'].get('kind')=='RESPONSE' and x['guest'].get('request_id')==request_id,timeout)
        if not value['guest']['ok']:raise RuntimeError(f'Guest {name}: {value["guest"]["error"]}')
        return {'host_send_ns':sent,'host_receive_ns':value['receipt_ns'],'guest':value['guest']['value']}
    def page_event(self,name):
        return self.wait(lambda x:x['guest'].get('kind')=='PAGE_EVENT' and x['guest']['event']['kind']==name)
    def close(self):
        if self.proc.poll() is None:
            try:self.send({'command':'exit','request_id':999999});self.proc.wait(timeout=15)
            except Exception:self.proc.terminate();self.proc.wait(timeout=10)
        self.thread.join(timeout=5);self.error.close()


def assignments():
    manifest=json.loads((ROOT.parent/'confirmatory/design/MANIFEST.json').read_text())
    all=[]
    for spec in manifest['experiments']:
        if spec['optional']:continue
        path=ROOT.parent/'confirmatory'/spec['path']
        if sha(path)!=spec['sha256']:raise RuntimeError('Assignment hash mismatch')
        all+=json.loads(path.read_text())['qualification_assignments']
    if len(all)!=95:raise RuntimeError('Qualification denominator changed')
    return all


def mapped_close(samples,event):
    # Each page clock measurement is bracketed by host send/receipt and guest samples.
    best=min(samples,key=lambda s:s['host_receive_ns']-s['host_send_ns'])
    mid=(best['host_send_ns']+best['host_receive_ns'])//2
    estimate=mid+round((event['guest']['event']['page_ms']-best['guest']['page_ms'])*1e6)
    uncertainty=(best['host_receive_ns']-best['host_send_ns'])/2
    return {'estimate_ns':estimate,'uncertainty_ns':uncertainty,'method':'paired monotonic sample midpoint',
            'selected_sample':best,'observed_close_diagnostic':event}


def wait_deadline(deadline):
    while True:
        remaining=deadline-time.monotonic_ns()
        if remaining<=0:return
        if remaining>2_000_000:time.sleep((remaining-1_000_000)/1e9)


def verify_frozen_base():
    lock=json.loads((Path(__file__).parent/'REPAIRED_BASE_LOCK.json').read_text())
    parent=ROOT/'provision/vm/provisioned.qcow2'
    if sha(parent)!=lock['parent_base_sha256'] or sha(SEED)!=lock['seed_sha256']:raise RuntimeError('Parent or seed input changed')
    if sha(BASE)!=lock['derived_base_sha256']:raise RuntimeError('Derived base hash mismatch')
    for name in FILES:
        if sha(ROOT/name)!=lock['worker_files'][name]:raise RuntimeError('Worker changed since provisioned image lock')
    return lock


def run_one(assignment):
    gate();lock=verify_frozen_base();disk_check(3*1024**3)
    if assignment['role']!='qualification':raise RuntimeError('Scientific acquisition refused')
    out=ATTEMPTS/assignment['trial_id'];out.mkdir(parents=True,exist_ok=False)
    started=time.monotonic_ns();free_before=shutil.disk_usage(ROOT).free
    events=Events(out/'events.jsonl');spec=contract(assignment)
    save(out/'assignment.json',assignment);save(out/'payload_contract.json',spec)
    save(out/'START.json',{'role':'qualification','scientific_denominator':False,'started_ns':started,
                          'base_lock':lock,'source_hashes':{p.name:sha(p) for p in ROOT.glob('*.py')},
                          'disk_free_before':free_before,'candidate_repair_source_hashes':{p.name:sha(p) for p in Path(__file__).parent.glob('*.py')}})
    vm=worker=helper=agent=None;endpoint='unknown';reasons=[];passed=False
    try:
        # This initial implementation only accepts cells whose entire measurement path exists.
        if assignment['instrumentation']!='ordinary' or assignment['mapper']!='none' or assignment['planned_uptime_ms'] is not None or assignment['workload']!='single_256_bytes' or assignment['fault'] != 'sysrq_reboot' or assignment['experiment']!='fault_scope_comparison':
            raise RuntimeError('Required extended cell implementation not yet qualified; acquisition forbidden')
        disk=out/'overlay.qcow2'
        subprocess.run(['qemu-img','create','-f','qcow2','-F','qcow2','-b',str(BASE),str(disk)],check=True,capture_output=True)
        name='qual-'+str(time.monotonic_ns())
        vm=VM(disk,out/'boot',2233,name,events)
        profile=f'/var/lib/idbv2/{assignment["trial_id"]}/profile'
        identity={'trial_id':assignment['trial_id'],'profile':profile,'base_sha256':lock['derived_base_sha256'],
                  'overlay':str(disk),'role':'qualification'}
        setup=f'sudo mkdir -p {shlex.quote(profile)} && sudo chown -R research:research /var/lib/idbv2'
        remote(vm.port,setup)
        observation=write_identity(remote,vm.port,identity,out)
        if observation!=identity:raise RuntimeError('Wrong profile/overlay identity')
        events('ATTEMPT_IDENTITY',identity=observation,query_block=vm.qmp.execute('query-block'))
        inventory=remote(vm.port,"findmnt -J /; cat /proc/sys/vm/dirty_writeback_centisecs /proc/sys/vm/dirty_expire_centisecs /proc/sys/vm/dirty_ratio /proc/sys/vm/dirty_background_ratio; uname -a")
        (out/'guest-filesystem-sysctls.txt').write_bytes(inventory.stdout)
        if b'commit=30' not in inventory.stdout or b'discard' not in inventory.stdout:raise RuntimeError('Wrong reference filesystem mount')
        worker=Worker(vm,spec,out,events)
        worker.command('prepare')
        agent=FaultAgent(ssh,vm.port,assignment,profile,events,out)
        if assignment['fault']=='browser_sigkill':
            probe=agent.probe();events('BROWSER_TREE_PREFAULT_PROBE',evidence=probe)
        samples=[worker.command('clock') for _ in range(9)]
        worker.command('write')
        ack=worker.page_event('ACK')
        if ack['guest']['event']['durability_observed']!=assignment['durability']:raise RuntimeError('Durability hint mismatch')
        close=None
        if assignment['close_ms'] is not None:close=worker.page_event('CLOSE_RETURNED')
        if assignment['timing_anchor']=='observed_close_estimate':
            mapping=mapped_close(samples,close)
            if mapping['estimate_ns']>close['receipt_ns']+mapping['uncertainty_ns']:raise RuntimeError('Contradictory close clock mapping')
            deadline=mapping['estimate_ns']+assignment['fault_after_close_ms']*1_000_000
        else:
            mapping=None;deadline=ack['receipt_ns']+assignment['fault_after_ack_ms']*1_000_000
        events('SCHEDULED_FAULT',deadline_ns=deadline,ack=ack,close=close,clock_samples=samples,mapping=mapping)
        wait_deadline(deadline)
        fault=agent.dispatch()
        overshoot=(fault['dispatch_ns']-deadline)/1e6
        events('FAULT_DISPATCH',fault=fault,deadline_ns=deadline,overshoot_ms=overshoot)
        if overshoot<0 or overshoot>25:reasons.append('dispatch_timing_ineligible')
        if assignment['held']:
            prior=[x for x in worker.items if x['guest'].get('kind')=='CONNECTION_TELEMETRY' and x['receipt_ns']<=fault['dispatch_ns']]
            if not prior or prior[-1]['guest']['state']['original_closed'] or not prior[-1]['guest']['state']['original_present']:
                reasons.append('held_connection_not_confirmed')
            events('HELD_EVIDENCE',last_telemetry=prior[-1] if prior else None)
        old_boot=vm.boot
        if assignment['fault']=='browser_sigkill':
            selected=agent.wait('SIGKILL_SELECTED_TREE',10)
            dispatched=agent.wait('SIGKILL_DISPATCH_RESULT',10)
            exits=agent.wait('SIGKILL_EXIT_EVIDENCE',10)
            health=vm.ready_after(fault['dispatch_ns'],expected_boot=old_boot)
            if any(x['fault_agent']['boot_id']!=old_boot for x in [selected,dispatched,exits]):raise RuntimeError('SIGKILL agent boot identity changed')
            events('SIGKILL_CLASSIFICATION',selected_tree=selected,dispatch=dispatched,exits=exits,unchanged_boot_id=vm.boot==old_boot)
        else:
            request=agent.wait('SYSRQ_REBOOT_REQUEST',10)
            health=vm.ready_after(fault['dispatch_ns'],old_boot)
            console=(vm.out/'console.txt').read_bytes()
            serial_lines=[line.decode(errors='replace') for line in console.splitlines() if b'sysrq:' in line.lower()]
            if not any('Resetting' in line for line in serial_lines):raise RuntimeError('No independent SysRq Resetting serial evidence')
            events('SYSRQ_CLASSIFICATION',request=request,serial_lines=serial_lines,boot_id_changed=vm.boot!=old_boot)
        value=checked_inventory(remote,vm.port,out,'mount-identity-after-fault',lock['fstab'])
        events('AUXILIARY_MOUNT_IDENTITY',stage='post-fault',identity=value)
        events('FAULT_IDENTITY',old_boot_id=old_boot,new_boot_id=vm.boot,readiness=health,
               classification=assignment['fault'],independent_boot_id_changed=vm.boot!=old_boot)
        vm.qmp.execute('query-status')
        agent.close();agent=None
        if assignment['fault']=='browser_sigkill':
            # Close only the now-dead browser's controller transport. Keep the kernel alive.
            if worker.proc.stdin and not worker.proc.stdin.closed:worker.proc.stdin.close()
            try:worker.proc.wait(timeout=15)
            except subprocess.TimeoutExpired:worker.proc.terminate();worker.proc.wait(timeout=5)
            worker.thread.join(timeout=5);worker.error.close();worker=None
            view=capture(vm,disk,out,events);before=view['sha256']
            view.update(path=str(disk),fault_to_capture_ms=(view['captured_ns']-fault['dispatch_ns'])/1e6,capture_after_guest_boot_activity=True)
            save(out/'IMMUTABLE_VIEW.json',view)
        else:
            vm.qmp.execute('stop');vm.quit();worker.close();worker=None;vm=None
            captured=time.monotonic_ns();disk.chmod(0o444);before=sha(disk)
            save(out/'IMMUTABLE_VIEW.json',{'sha256':before,'path':str(disk),'captured_ns':captured,
                'fault_to_capture_ms':(captured-fault['dispatch_ns'])/1e6,'capture_after_guest_boot_activity':True,
                'instantaneous_crash_state':False,'oracle_started':False,'original_boot_id':old_boot})
        helper_disk=out/'forensic-helper.qcow2'
        subprocess.run(['qemu-img','create','-f','qcow2','-F','qcow2','-b',str(BASE),str(helper_disk)],check=True,capture_output=True)
        helper=VM(helper_disk,out/'forensic-helper',2234,'helper-'+str(time.monotonic_ns()),events,memory=1024)
        helper.attach_evidence_after_boot(disk)
        config={'device':'/dev/vdc','data_volume':False,'fstype':'ext4','profile':profile,'output':'/tmp/idbv2-extract'}
        result=remote(helper.port,'sudo /opt/idbv2/venv/bin/python /opt/idbv2/worker/guest_forensics.py',input=json.dumps(config).encode(),timeout=60,check=False)
        (out/'forensic-extraction.stderr').write_bytes(result.stderr)
        save(out/'FORENSIC_RESPONSE.json',{'returncode':result.returncode,'stdout_bytes':len(result.stdout),'stderr_bytes':len(result.stderr)})
        (out/'forensic-extraction.json').write_bytes(result.stdout)
        if result.returncode:raise RuntimeError('Read-only forensic extraction failed; exact stdout/stderr preserved')
        archive=out/'forensic-extract.tar'
        with archive.open('xb') as target:
            subprocess.run(ssh(helper.port)+['sudo tar -C /tmp/idbv2-extract -cf - .'],stdout=target,stderr=subprocess.PIPE,check=True,timeout=60)
        helper.quit();helper=None
        if sha(disk)!=before:raise RuntimeError('Read-only evidence image changed during forensics')
        extract=out/'forensics';extract.mkdir()
        with tarfile.open(archive) as tf:tf.extractall(extract,filter='data')
        inventory=json.loads((extract/'inventory.json').read_text())
        formats=[]
        for item in inventory['files']:
            path=extract/'files'/item['relative_path']
            if sha(path)!=item['sha256']:raise RuntimeError('Forensic member hash mismatch')
            formats.append({'path':item['relative_path'],**inspect(path)})
        save(out/'FORENSIC_FORMATS.json',{'files':formats,'source_sha256':before,'callback_attribution':'not established'})
        if assignment['fault']=='browser_sigkill':
            resume=time.monotonic_ns();events('RECOVERY_SAME_GUEST_START',original_qemu_pid=vm.proc.pid,old_boot_id=old_boot)
            vm.qmp.execute('cont');vm.ready_after(resume,expected_boot=old_boot)
            observed=json.loads(remote(vm.port,"python3 -c 'import json,pathlib; print(json.dumps({\"boot_id\":pathlib.Path(\"/proc/sys/kernel/random/boot_id\").read_text().strip()}))'").stdout)
            if observed['boot_id']!=old_boot:raise RuntimeError('Original SIGKILL guest identity lost before reader')
            events('SIGKILL_ORACLE_SAME_GUEST',qemu_pid=vm.proc.pid,boot_id=observed['boot_id'],original_capture_pid=view['original_qemu_pid'],original_disk_sha256=sha(disk))
        else:
            recovery_disk=out/'recovery.qcow2'
            subprocess.run(['qemu-img','create','-f','qcow2','-F','qcow2','-b',str(disk),str(recovery_disk)],check=True,capture_output=True)
            vm=VM(recovery_disk,out/'recovery-boot',2233,'recovery-'+str(time.monotonic_ns()),events)
        # Original profile is independently verified before reader launch.
        read_identity(remote,vm.port,identity,out,'identity-before-recovery')
        worker=Worker(vm,spec,out,events,recovery=True)
        oracle=worker.command('oracle');save(out/'ORACLE.json',oracle)
        endpoint=oracle['guest']['endpoint']
        if endpoint not in {'recovered','lost'}:reasons.append('endpoint_not_interpretable')
        if sha(disk)!=before:raise RuntimeError('Original evidence changed during recovery')
        passed=not reasons
    except Exception as e:
        reasons.append(str(e));events('QUALIFICATION_ERROR',error=repr(e))
    finally:
        if agent:
            try:agent.close()
            except Exception as e:events('FAULT_AGENT_CLEANUP_ERROR',error=repr(e))
        if worker:
            try:worker.close()
            except Exception as e:events('WORKER_CLEANUP_ERROR',error=repr(e))
        for item in (vm,helper):
            if item:
                try:item.quit()
                except Exception as e:events('VM_CLEANUP_ERROR',error=repr(e))
        ended=time.monotonic_ns()
        image_hashes={p.name:sha(p) for p in out.glob('*.qcow2')}
        allocated=sum(p.stat().st_blocks*512 for p in out.rglob('*') if p.is_file())
        logical=sum(p.stat().st_size for p in out.rglob('*') if p.is_file())
        result={'trial_id':assignment['trial_id'],'role':'qualification','scientific_denominator':False,
                'qualification_passed':passed,'endpoint':endpoint,'reasons':reasons,
                'wall_seconds':(ended-started)/1e9,'allocated_bytes':allocated,'logical_bytes':logical,
                'free_before':free_before,'free_after':shutil.disk_usage(ROOT).free,'image_sha256':image_hashes,
                'retry_permitted':False,'technical_hash_lock_complete':False,
                'scientific_assignments_started':0}
        save(out/'RESULT.json',result)
        events('QUALIFICATION_FINISHED',result=result);events.file.close()
        save(out/'SHA256.json',{str(p.relative_to(out)):sha(p) for p in sorted(out.rglob('*')) if p.is_file()})
        print(json.dumps(result,indent=2),flush=True)
    return passed


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('command',choices=['next','status']);args=ap.parse_args()
    values=assignments()
    if args.command=='status':
        print(json.dumps({'assigned':95,'started':sum((ATTEMPTS/a['trial_id']).exists() for a in values),
                          'scientific_started':0,'optional_active':False},indent=2));return
    prior=[ATTEMPTS/a['trial_id'] for a in values if (ATTEMPTS/a['trial_id']).exists()]
    for path in prior:
        result=path/'RESULT.json'
        if not result.exists() or not json.loads(result.read_text())['qualification_passed']:
            raise RuntimeError('Failed or interrupted qualification: stop; no retry or continuation without resolution')
    next_assignment=next((a for a in values if not (ATTEMPTS/a['trial_id']).exists()),None)
    if next_assignment is None:print('No qualification assignments remain');return
    if not run_one(next_assignment):raise SystemExit(2)


if __name__=='__main__':main()
