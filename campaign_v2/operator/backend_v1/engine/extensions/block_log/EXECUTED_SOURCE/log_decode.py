"""Read-only log-writes v1 decoder, pinned against josefbacik/log-writes header. No inferred unrecorded entry."""
from backend_runtime import RUN_ROLE, ENGINE, ATTEMPT_RELATIVE, attempt_root, validate_reserved, validate_assignment, deploy_worker
import hashlib, struct
from pathlib import Path
MAGIC = 29963231459240050
FLAGS = {'flush': 1, 'fua': 2, 'discard': 4, 'mark': 8, 'metadata': 16}

def decode(path):
    p = Path(path)
    rows = []
    with p.open('rb') as f:
        head = f.read(28)
        if len(head) != 28:
            raise RuntimeError('Incomplete log superblock')
        magic, version, total, sector = struct.unpack('<QQQI', head)
        if magic != MAGIC or version != 1 or sector not in [512, 4096]:
            raise RuntimeError('Unsupported/unrecorded log header')
        if total > 10000000:
            raise RuntimeError('Implausible entry count')
        f.seek(sector)
        for n in range(total):
            start = f.tell()
            header = f.read(sector)
            if len(header) != sector:
                raise RuntimeError('Truncated log entry header')
            location, count, flags, length = struct.unpack('<QQQQ', header[:32])
            if flags & ~31 or length > sector - 32:
                raise RuntimeError('Unsupported flags/private bytes')
            private = header[32:32 + length]
            size = count * sector
            if size > 1024 ** 3:
                raise RuntimeError('Unbounded entry size')
            data_offset = f.tell()
            data = f.read(size) if not flags & 4 else b''
            if not flags & 4 and len(data) != size:
                raise RuntimeError('Incomplete entry bytes')
            rows.append({'ordinal': n, 'header_offset': start, 'data_offset': data_offset, 'sector': location, 'sectors': count, 'bytes': size, 'flags': flags, 'flag_names': [k for k, v in FLAGS.items() if flags & v], 'private_hex': private.hex(), 'mark': private.rstrip(b'\x00').decode('ascii') if flags & 8 else None, 'data_sha256': hashlib.sha256(data).hexdigest() if not flags & 4 else None})
    return {'magic': hex(magic), 'version': version, 'sector_size': sector, 'declared_entries': total, 'fully_decoded_entries': len(rows), 'last_fully_recorded_entry': len(rows) - 1, 'entries': rows, 'unrecorded_bytes_not_inferred': True, 'consumed_log_bytes': f.tell() if False else rows[-1]['data_offset'] + (0 if rows[-1]['flags'] & 4 else rows[-1]['bytes']) if rows else sector}

def replay_prefix(log, blank, destination, until):
    """Fresh derivative from exactly verified blank baseline. Discard entries block rather than silently substitute semantics."""
    import shutil
    p = Path(destination)
    if p.exists():
        raise RuntimeError('Replay destination exists')
    meta = decode(log)
    if until < 0 or until >= len(meta['entries']):
        raise RuntimeError('Unrecorded boundary')
    with Path(blank).open('rb') as f:
        while (chunk := f.read(1024 ** 2)):
            if chunk != bytes(len(chunk)):
                raise RuntimeError('Baseline is not a verified zero/blank image')
    import subprocess
    subprocess.run(['qemu-img', 'create', '-f', 'raw', str(p), str(Path(blank).stat().st_size)], check=True, capture_output=True)
    with Path(log).open('rb') as source, p.open('r+b') as out:
        for e in meta['entries'][:until + 1]:
            if e['flags'] & 4:
                raise RuntimeError('Discard entry requires separately validated discard semantics')
            if not e['bytes']:
                continue
            source.seek(e['data_offset'])
            data = source.read(e['bytes'])
            offset = e['sector'] * meta['sector_size']
            if offset + len(data) > p.stat().st_size:
                raise RuntimeError('Replay write exceeds baseline')
            if hashlib.sha256(data).hexdigest() != e['data_sha256']:
                raise RuntimeError('Log bytes changed during replay')
            out.seek(offset)
            out.write(data)
        out.flush()
    return {'prefix_last_entry': until, 'dependent_prefix': True, 'scientific_trial_count': 0, 'unrecorded_bytes_not_inferred': True}
