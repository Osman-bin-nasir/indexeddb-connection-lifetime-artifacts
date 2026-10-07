"""One engineering identity/reboot smoke test. No browser or experiment assignment."""
import datetime
import json
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from provision_vm import save,sha,disk_check
from qualification import VM,Events,BASE,remote,verify_frozen_base
from identity_io import write_identity,read_identity

class SupportEvents(Events):
    def __call__(self,kind,**values):
        if kind=='VM_START':values['role']='engineering_support'
        return super().__call__(kind,**values)

def main():
    verify_frozen_base();disk_check(3*1024**3)
    trial='support-identity-reboot-20261004-00001'
    out=ROOT/'support/identity_diagnostics'/trial
    out.mkdir(parents=True,exist_ok=False)
    save(out/'START.json',{'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'role':'engineering_support',
        'scientific_denominator':False,'qualification_assignment':None,'browser_launched':False,'target_write':False,
        'recovery_oracle':False,'automatic_retry':False,'source_hashes':{p.name:sha(p) for p in Path(__file__).parent.glob('*.py')}})
    events=SupportEvents(out/'events.jsonl');vm=None;passed=False;error=None
    try:
        disk=out/'support.qcow2'
        subprocess.run(['qemu-img','create','-f','qcow2','-F','qcow2','-b',str(BASE),str(disk)],check=True,capture_output=True)
        vm=VM(disk,out/'boot',2233,trial,events)
        expected={'support_id':trial,'role':'engineering_support','scientific_denominator':False,'overlay':str(disk)}
        write_identity(remote,vm.port,expected,out)
        boot_before=vm.boot
        dispatch=vm.qmp.execute('system_reset')
        healthy=vm.ready_after(dispatch['dispatch_ns'],boot_before)
        read_identity(remote,vm.port,expected,out,'identity-after-reboot')
        save(out/'REBOOT_READBACK.json',{'boot_before':boot_before,'boot_after':vm.boot,'boot_changed':boot_before!=vm.boot,
            'healthy_observations':healthy,'identity_readback_matches':True,'only_administrative_file_tested':True})
        passed=boot_before!=vm.boot
    except Exception as e:
        error=repr(e);events('SUPPORT_ERROR',error=error)
    finally:
        if vm:vm.quit()
        events.file.close()
        save(out/'RESULT.json',{'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'role':'engineering_support',
            'support_smoke_passed':passed,'error':error,'scientific_started':0,'qualification_started':0,
            'campaign_qualified':False,'full_oracle_path_tested':False,'automatic_retry':False})
        save(out/'SHA256.json',{str(p.relative_to(out)):sha(p) for p in sorted(out.rglob('*')) if p.is_file()})
        print(json.dumps(json.loads((out/'RESULT.json').read_text()),indent=2),flush=True)
    if not passed:raise SystemExit(2)

if __name__=='__main__':main()
