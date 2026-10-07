"""Neutral ext4/log-writes witness. No browser, IndexedDB target or scientific fault."""
import json, os, subprocess, time
from pathlib import Path
import guest_mapper_candidate as mapper
mapper.create('dm_log_writes')
mapper.run(['mkfs.ext4', '-F', '/dev/mapper/idbv2-browser'])
mapper.run(['mount', '-t', 'ext4', '/dev/mapper/idbv2-browser', '/var/lib/idbv2'])
mapper.mark('neutral-before-files')
root = Path('/var/lib/idbv2')
for name, content, mark in [('before-ack.bin', b'neutral-before-ack-exact-bytes', 'registered-ack'), ('after-ack.bin', b'neutral-after-ack-exact-bytes', 'neutral-end')]:
    with (root / name).open('xb') as f:
        f.write(content)
        f.flush()
        os.fsync(f.fileno())
    fd = os.open(root, os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    mapper.mark(mark)
    print(json.dumps({'kind': 'NEUTRAL_FILE', 'name': name, 'hex': content.hex(), 'guest_ns': time.monotonic_ns(), 'mark': mark}), flush=True)
print(json.dumps({'kind': 'NEUTRAL_FS_SETUP_PASS', 'no_browser_or_target': True}), flush=True)
