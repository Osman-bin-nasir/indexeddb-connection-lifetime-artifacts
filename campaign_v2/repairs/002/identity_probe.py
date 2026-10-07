"""One read-only support probe, never a qualification or scientific assignment."""
import datetime
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from provision_vm import sha, save, disk_check
from qualification import VM, Events, BASE, remote, verify_frozen_base

def main():
    verify_frozen_base(); disk_check(3 * 1024**3)
    out = ROOT / 'support/identity_diagnostics/support-identity-forensics-20261004-00001'
    out.mkdir(parents=True, exist_ok=False)
    source = ROOT / 'qualification/attempts/qualification-amendment-001-close_aligned_recovery_grid-00001/overlay.qcow2'
    before = sha(source)
    save(out / 'START.json', {'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(), 'role':'engineering_support',
        'scientific_denominator':False, 'qualification_assignment':None, 'target_write':False,
        'fault':False, 'recovery_oracle':False, 'source_sha256':before, 'source_script_sha256':sha(Path(__file__))})
    events = Events(out / 'events.jsonl'); vm = None
    try:
        disk = out / 'helper.qcow2'
        subprocess.run(['qemu-img','create','-f','qcow2','-F','qcow2','-b',str(BASE),str(disk)], check=True, capture_output=True)
        vm = VM(disk, out / 'helper-boot', 2233, 'support-identity-20261004-00001', events, memory=1024)
        vm.attach_evidence_after_boot(source)
        script = """sudo python3 - <<'PY'
import base64,json,pathlib,subprocess
root=pathlib.Path('/mnt/idbv2-support');root.mkdir(exist_ok=True)
subprocess.run(['mount','-t','ext4','-o','ro,noload','/dev/vdc1',str(root)],check=True)
try:
 p=root/'opt/idbv2/attempt.json'
 result={'exists':p.exists(),'mount':json.loads(subprocess.check_output(['findmnt','-J',str(root)],text=True))}
 if p.exists():
  raw=p.read_bytes();st=p.stat();result.update(bytes=len(raw),content_base64=base64.b64encode(raw).decode(),inode=st.st_ino,mtime_ns=st.st_mtime_ns)
  try:result['parsed_identity']=json.loads(raw)
  except Exception as e:result['parse_error']=repr(e)
 print(json.dumps(result))
finally:subprocess.run(['umount',str(root)],check=True)
PY"""
        response = remote(vm.port, script, check=False)
        (out / 'response.stdout').write_bytes(response.stdout)
        (out / 'response.stderr').write_bytes(response.stderr)
        save(out / 'READ_RESPONSE.json', {'returncode':response.returncode,'stdout_bytes':len(response.stdout),'stderr_bytes':len(response.stderr)})
        if response.returncode:raise RuntimeError('Support read failed; preserved response')
        result = json.loads(response.stdout)
        save(out / 'OBSERVATION.json', result)
        print(json.dumps(result, indent=2), flush=True)
    finally:
        if vm:vm.quit()
        events.file.close()
        after = sha(source)
        save(out / 'STOP.json', {'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source_sha256_before':before,
            'source_sha256_after':after,'source_unchanged':before==after,'scientific_started':0,'qualification_started':0,'automatic_retry':False})
        save(out / 'SHA256.json', {str(p.relative_to(out)):sha(p) for p in sorted(out.rglob('*')) if p.is_file()})
        if before != after:raise RuntimeError('Evidence source hash changed')

if __name__ == '__main__':main()
