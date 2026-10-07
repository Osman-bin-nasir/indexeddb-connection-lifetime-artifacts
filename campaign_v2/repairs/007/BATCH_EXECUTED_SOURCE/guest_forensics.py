"""Read-only filesystem extracts from a QEMU-read-only attachment, never recovery."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time


def command(args):
    return subprocess.check_output(args, text=True)


def main():
    config = json.loads(sys.stdin.read())
    disk = config['device']
    if not disk.startswith('/dev/vd') or disk in {'/dev/vda','/dev/vdb'}:
        raise RuntimeError('Refusing helper root/seed device')
    if command(['blockdev','--getro',disk]).strip() != '1':
        raise RuntimeError('Evidence attachment is not block read-only')
    root = Path('/mnt/idbv2-evidence')
    root.mkdir(exist_ok=True)
    volume = disk if config['data_volume'] else disk+'1'
    fs = config.get('fstype','ext4')
    options = 'ro,noload' if fs == 'ext4' else 'ro,norecovery,nouuid'
    subprocess.run(['mount','-t',fs,'-o',options,volume,str(root)],check=True)
    try:
        out = Path(config['output'])
        out.mkdir(parents=True,exist_ok=False)
        profile_relative = config['profile'].lstrip('/') if not config['data_volume'] else config['profile_relative']
        profile = root/profile_relative
        data = profile/'Default/IndexedDB'
        if not data.is_dir():
            raise RuntimeError('Evidence view missing expected IndexedDB directory')
        files = []
        for source in sorted(data.rglob('*')):
            if not source.is_file():
                continue
            dest = out/'files'/source.relative_to(data)
            dest.parent.mkdir(parents=True,exist_ok=True)
            st = source.stat()
            raw = source.read_bytes()
            dest.write_bytes(raw)
            files.append({'relative_path':str(source.relative_to(data)), 'bytes':len(raw),
                          'sha256':hashlib.sha256(raw).hexdigest(),'inode':st.st_ino,'device':st.st_dev,
                          'mode':st.st_mode,'mtime_ns':st.st_mtime_ns,'header_hex':raw[:100].hex()})
        result = {'role':'immutable_pre_oracle_filesystem_extract', 'guest_monotonic_ns':time.monotonic_ns(),
                  'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                  'device':disk, 'block_read_only':True,'mount_options_requested':options,
                  'actual_mount':json.loads(command(['findmnt','-J',str(root)])),
                  'filesystem_identity':command(['blkid',volume]).strip(),
                  'profile':config['profile'],'files':files,
                  'replay_performed':False,'oracle_started':False,
                  'instantaneous_crash_state':False,'callback_attribution':'not established'}
        (out/'inventory.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result),flush=True)
    finally:
        subprocess.run(['umount',str(root)],check=True)


if __name__ == '__main__':
    main()
