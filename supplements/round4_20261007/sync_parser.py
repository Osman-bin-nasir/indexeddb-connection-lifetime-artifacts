import re
WAL_NAME = re.compile('(?:-wal$|sqlite-wal)')
INDEXEDDB_DIR = '/IndexedDB/'
SYNC_NAME = 'fsync|fdatasync|sync_file_range|msync'
PID_PREFIX = '(?:\\[pid\\s+(?P<pid>\\d+)\\]\\s+)?'
SYNC_LINE = re.compile(PID_PREFIX + '(?P<ts>\\d+\\.\\d+)\\s+(?P<call>(?:' + SYNC_NAME + '))\\((?P<args>.*?)\\)\\s+=\\s+(?P<ret>-?\\d+)(?P<rest>.*)$')
UNFINISHED_LINE = re.compile(PID_PREFIX + '(?P<ts>\\d+\\.\\d+)\\s+(?P<call>(?:' + SYNC_NAME + '))\\((?P<args>.*?)\\s+<unfinished \\.\\.\\.>$')
RESUMED_LINE = re.compile(PID_PREFIX + '(?:(?P<completed_ts>\\d+\\.\\d+)\\s+)?<\\.\\.\\.\\s+(?P<call>(?:' + SYNC_NAME + '))\\s+resumed>(?P<args>.*?)\\)\\s+=\\s+(?P<ret>-?\\d+)(?P<rest>.*)$')
FD_PATH = re.compile('(?P<fd>\\d+)<(?P<path>[^>]*)>')

def is_wal(path: str) -> bool:
    """The IndexedDB backing-store WAL only.

    A bare `-wal` suffix also matches unrelated Chromium databases (for example
    `Default/DIPS-wal`), so the file must also live under the profile's `IndexedDB`
    directory to be treated as the target descriptor.
    """
    return INDEXEDDB_DIR in path and bool(WAL_NAME.search(path.rsplit('/', 1)[-1]))

def _sync_event(line, call, ts, args, ret, rest, *, resumed=False, completed_ts=None):
    """One strace sync call. `guest_realtime_s` is the syscall *entry* time (the stamp
    strace prints at entry), so a one-line call and a resumed call are commensurable."""
    fd_match = FD_PATH.match(args)
    duration_match = re.search('<(\\d+\\.\\d+)>', rest)
    return {'source': 'strace', 'syscall': call, 'guest_realtime_s': float(ts), 'guest_realtime_completed_s': float(completed_ts) if completed_ts else None, 'pid': None, 'fd': int(fd_match.group('fd')) if fd_match else None, 'fd_path': fd_match.group('path') if fd_match else None, 'return_value': int(ret), 'completed': int(ret) == 0, 'duration_s': float(duration_match.group(1)) if duration_match else None, 'resumed': resumed, 'raw': line.rstrip()}

def parse_strace(text: str) -> dict:
    """Parse fsync/fdatasync/sync_file_range/msync lines from `strace -ttt -T -yy -f`.

    With `-f` strace interleaves threads, so a call's text is frequently split into an
    entry line ending in `<unfinished ...>` and a later `<... call resumed>` line. Both
    forms are reconstructed: a resumed completion inherits the entry line's timestamp,
    descriptor and resolved path, so an interleaved WAL sync is not lost.
    """
    events, unfinished, resumed, unmatched = ([], 0, 0, 0)
    pending: dict[int, tuple] = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        entry = UNFINISHED_LINE.match(line)
        if entry:
            unfinished += 1
            pid = int(entry.group('pid')) if entry.group('pid') else 0
            pending[pid] = (entry.group('call'), entry.group('ts'), entry.group('args'))
            continue
        continuation = RESUMED_LINE.match(line)
        if continuation:
            resumed += 1
            pid = int(continuation.group('pid')) if continuation.group('pid') else 0
            started = pending.pop(pid, None)
            if started is None:
                unmatched += 1
                continue
            call, ts, args = started
            event = _sync_event(line, call, ts, args, continuation.group('ret'), continuation.group('rest'), resumed=True, completed_ts=continuation.group('completed_ts'))
            event['pid'] = pid or None
            events.append(event)
            continue
        match = SYNC_LINE.match(line)
        if not match:
            unmatched += 1
            continue
        event = _sync_event(line, match.group('call'), match.group('ts'), match.group('args'), match.group('ret'), match.group('rest'))
        event['pid'] = int(match.group('pid')) if match.group('pid') else None
        events.append(event)
    return {'events': events, 'unfinished_lines': unfinished, 'resumed_lines': resumed, 'unmatched_lines': unmatched}
