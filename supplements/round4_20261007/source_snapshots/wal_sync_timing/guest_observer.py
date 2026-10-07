"""Guest-only, read-only file page-cache, global dirty-page and block-device sampler.

Uses Linux cachestat(2) for per-file dirty/writeback page counts and reads
/proc/diskstats plus /sys/block/<dev>/stat for block-device write and flush
counters. No sync, flush, fsync, fdatasync, fadvise, or cache-eviction operation
occurs; nothing is written except this process's stdout.

One JSON object per sample on stdout, at ~50 ms intervals:

  guest_monotonic_ns, guest_realtime_ns, guest_uptime_s, sample_index
  vmstat   : nr_dirty, nr_writeback, nr_dirty_threshold, nr_dirty_background_threshold
  files    : {path: {inode,size,mtime_ns,cached,dirty,writeback,evicted,recently_evicted}}
  blockdev : {name: {reads,writes,sectors_written,flushes,fields_raw}}
"""
import argparse
import ctypes
import json
import os
import pathlib
import time

SYS_CACHESTAT_AARCH64 = 451


class Range(ctypes.Structure):
    _fields_ = [('off', ctypes.c_uint64), ('length', ctypes.c_uint64)]


class Stat(ctypes.Structure):
    _fields_ = [('cached', ctypes.c_uint64), ('dirty', ctypes.c_uint64),
                ('writeback', ctypes.c_uint64), ('evicted', ctypes.c_uint64),
                ('recently_evicted', ctypes.c_uint64)]


libc = ctypes.CDLL(None, use_errno=True)


def cachestat(path):
    fd = os.open(path, os.O_RDONLY | os.O_CLOEXEC)
    try:
        query, value = Range(0, 0), Stat()
        ret = libc.syscall(SYS_CACHESTAT_AARCH64, fd, ctypes.byref(query), ctypes.byref(value), 0)
        if ret != 0:
            code = ctypes.get_errno()
            raise OSError(code, os.strerror(code), str(path))
        return {name: int(getattr(value, name)) for name, _ in value._fields_}
    finally:
        os.close(fd)


def vmstat():
    wanted = {'nr_dirty', 'nr_writeback', 'nr_dirty_threshold', 'nr_dirty_background_threshold'}
    return {parts[0]: int(parts[1]) for line in pathlib.Path('/proc/vmstat').read_text().splitlines()
            if (parts := line.split()) and parts[0] in wanted}


def device_lines():
    rows = {}
    for line in pathlib.Path('/proc/diskstats').read_text().splitlines():
        parts = line.split()
        if len(parts) < 14:
            continue
        name = parts[2]
        if not name.startswith('vd') and not name.startswith('sd') and not name.startswith('nvme'):
            continue
        values = [int(value) for value in parts[3:]]
        rows[name] = {
            'reads': values[0] if len(values) > 0 else None,
            'sectors_read': values[2] if len(values) > 2 else None,
            'writes': values[4] if len(values) > 4 else None,
            'sectors_written': values[6] if len(values) > 6 else None,
            'discards': values[11] if len(values) > 11 else None,
            # flush requests completed / ms flushing are the last two kernel fields
            'flushes': values[-2] if len(values) >= 2 else None,
            'fields_raw': values,
        }
    return rows


def sample(directory):
    files = {}
    if directory is not None:
        for path in sorted(directory.rglob('*')):
            if not path.is_file():
                continue
            try:
                st = path.stat()
                files[str(path)] = dict(inode=st.st_ino, size=st.st_size,
                                        mtime_ns=st.st_mtime_ns, **cachestat(path))
            except (OSError, FileNotFoundError) as error:
                files[str(path)] = {'error': repr(error)}
    return dict(guest_monotonic_ns=time.monotonic_ns(), guest_realtime_ns=time.time_ns(),
                guest_uptime_s=float(pathlib.Path('/proc/uptime').read_text().split()[0]),
                vmstat=vmstat(), files=files, blockdev=device_lines())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--directory', type=pathlib.Path)
    parser.add_argument('--duration-s', type=float)
    parser.add_argument('--interval-ms', type=float, default=50)
    parser.add_argument('--self-test-file', type=pathlib.Path)
    args = parser.parse_args()
    if args.self_test_file is not None:
        print(json.dumps({'cachestat': cachestat(args.self_test_file), 'vmstat': vmstat(),
                          'blockdev': device_lines(), 'guest_monotonic_ns': time.monotonic_ns()}))
        return
    assert args.directory is not None and args.duration_s is not None
    assert args.duration_s > 0 and 0 < args.interval_ms <= 100
    start = time.monotonic()
    sequence = 0
    while True:
        now = time.monotonic()
        if now - start > args.duration_s:
            break
        row = sample(args.directory)
        row['sample_index'] = sequence
        print(json.dumps(row, separators=(',', ':')), flush=True)
        sequence += 1
        deadline = start + sequence * args.interval_ms / 1000
        if deadline > now:
            time.sleep(deadline - time.monotonic())


if __name__ == '__main__':
    main()
