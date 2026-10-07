"""Registered 32-KiB write/fsync workload, emits actual schedule and syscall evidence."""
import json, os, pathlib, sys, time

def main():
    config = json.loads(sys.stdin.readline())
    if config.get('role') not in ('qualification', 'scientific', 'scientific'):
        raise RuntimeError('Qualification-only workload')
    profile = pathlib.Path(config['profile'])
    if not str(profile).startswith('/var/lib/idbv2/') or not profile.is_dir():
        raise RuntimeError('Unexpected profile')
    path = profile.parent / 'background-fsync.bin'
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 384)
    block = bytes(range(256)) * 128
    if len(block) != 32768:
        raise RuntimeError('Wrong background write size')
    boot = pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    sequence = 0

    def emit(kind, **value):
        nonlocal sequence
        sequence += 1
        print(json.dumps({'kind': kind, 'sequence': sequence, 'guest_monotonic_ns': time.monotonic_ns(), 'boot_id': boot, **value}), flush=True)
    try:
        st = os.fstat(fd)
        if st.st_dev != profile.stat().st_dev:
            raise RuntimeError('Background file not on browser filesystem')
        emit('BACKGROUND_READY', path=str(path), inode=st.st_ino, device=st.st_dev, profile_device=profile.stat().st_dev, period_ns=100000000, bytes_per_operation=len(block))
        anchor = time.monotonic_ns()
        i = 0
        while True:
            deadline = anchor + i * 100000000
            remaining = (deadline - time.monotonic_ns()) / 1000000000.0
            if remaining > 0:
                time.sleep(remaining)
            started = time.monotonic_ns()
            offset = os.lseek(fd, 0, os.SEEK_CUR)
            emit('BACKGROUND_OPERATION_BEGIN', operation=i, scheduled_ns=deadline, started_ns=started, offset=offset, requested_bytes=len(block))
            written = os.write(fd, block)
            write_return = time.monotonic_ns()
            if written != len(block):
                raise RuntimeError('Short background write')
            fsync_start = time.monotonic_ns()
            os.fsync(fd)
            fsync_end = time.monotonic_ns()
            emit('BACKGROUND_OPERATION_COMPLETE', operation=i, scheduled_ns=deadline, started_ns=started, offset=offset, returned_bytes=written, write_return_ns=write_return, fsync_start_ns=fsync_start, fsync_return_ns=fsync_end, fsync_returned=True)
            i += 1
    finally:
        os.close(fd)
if __name__ == '__main__':
    main()
