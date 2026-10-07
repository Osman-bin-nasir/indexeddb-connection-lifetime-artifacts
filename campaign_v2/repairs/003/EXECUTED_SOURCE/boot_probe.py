"""Read-only support forensics for the post-reset mount failure."""
import datetime,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from qualification import VM,Events,BASE,remote,verify_frozen_base
from provision_vm import sha,save,disk_check

def main():
    verify_frozen_base();disk_check(3*1024**3)
    out=ROOT/'support/boot_diagnostics/support-boot-forensics-20261004-00001';out.mkdir(parents=True,exist_ok=False)
    source=ROOT/'qualification/attempts/qualification-close_aligned_recovery_grid-00015/overlay.qcow2';before=sha(source)
    save(out/'START.json',{'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'role':'engineering_support','scientific_denominator':False,'qualification_assignment':None,'source_sha256':before,'source_script_sha256':sha(Path(__file__)),'browser':False,'fault':False})
    events=Events(out/'events.jsonl');vm=None
    try:
        disk=out/'helper.qcow2';subprocess.run(['qemu-img','create','-f','qcow2','-F','qcow2','-b',str(BASE),str(disk)],check=True,capture_output=True)
        vm=VM(disk,out/'boot',2233,'support-boot-forensics-20261004-00001',events,memory=1024);vm.attach_evidence_after_boot(source)
        script="""sudo python3 - <<'PY'
import json,pathlib,subprocess
root=pathlib.Path('/mnt/idbv2-support');root.mkdir(exist_ok=True)
subprocess.run(['mount','-t','ext4','-o','ro,noload','/dev/vdc1',str(root)],check=True)
def cmd(args):
 r=subprocess.run(args,capture_output=True,text=True);return {'returncode':r.returncode,'stdout':r.stdout,'stderr':r.stderr}
try:
 result={'fstab':(root/'etc/fstab').read_text(),'block_inventory':cmd(['lsblk','-J','-o','NAME,FSTYPE,LABEL,UUID,PARTUUID,RO','/dev/vdc']),
 'actual_mount':cmd(['findmnt','-J',str(root)]),'blkid':cmd(['blkid'])}
 journal=root/'var/log/journal'
 result['journal_directory_exists']=journal.exists()
 if journal.exists():
  result['boot_list']=cmd(['journalctl','--directory='+str(journal),'--list-boots','--no-pager'])
  result['last_boot_mount_and_udev']=cmd(['journalctl','--directory='+str(journal),'-b','0','--no-pager','-o','short-monotonic','-u','boot.mount','-u','systemd-udevd.service','-u','systemd-fsck@dev-disk-by\\x2dlabel-BOOT.service'])
 print(json.dumps(result))
finally:subprocess.run(['umount',str(root)],check=True)
PY"""
        r=remote(vm.port,script,check=False,timeout=60)
        (out/'response.stdout').write_bytes(r.stdout);(out/'response.stderr').write_bytes(r.stderr)
        save(out/'RESPONSE.json',{'returncode':r.returncode})
        if r.returncode:raise RuntimeError('Read-only probe failed; response retained')
        value=json.loads(r.stdout);save(out/'OBSERVATION.json',value)
        print(json.dumps(value,indent=2),flush=True)
    finally:
        if vm:vm.quit()
        events.file.close();after=sha(source)
        save(out/'STOP.json',{'source_unchanged':before==after,'source_sha256_before':before,'source_sha256_after':after,'scientific_started':0,'qualification_started':0})
        save(out/'SHA256.json',{str(p.relative_to(out)):sha(p) for p in sorted(out.rglob('*')) if p.is_file()})
        if before!=after:raise RuntimeError('Evidence hash changed')
if __name__=='__main__':main()
