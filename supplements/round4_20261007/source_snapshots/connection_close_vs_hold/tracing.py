"""Frozen Experiment C1 tracing pipeline: transport, parsers, ledger, reduction.

Byte-for-byte the paper3v2_mechanism_b1 pipeline for the strace/eBPF/cachestat
channels, plus two additions that are identical in both C1 conditions:

  * a file-lifecycle strace channel (`unlink`, `unlinkat`, `ftruncate`,
    `truncate`) so the WAL descriptor's close/delete/truncate is observed
    directly rather than inferred;
  * a uprobe stage over the nine prescribed Candidate-1 functions of the
    connection-close path, attempted on every trial and recorded whether or not
    the guest Chromium build exposes those symbols.

All guest events are reconstructed from the guest's own clocks. The reset-anchored
comparison is expressed relative to the target ACK using two within-guest anchors:
the page's `browserRealtimeMs` (CLOCK_REALTIME, present on every event payload) and
the guest-agent `uptime` RPC's `guest_monotonic_ns` (CLOCK_MONOTONIC, the same clock
bpftrace `nsecs` and cachestat sampling use). No host clock is used to convert a
guest time, and no host/guest cross-clock alignment is performed.
"""
from __future__ import annotations

import asyncio
import datetime
import json
import re
import shlex
import statistics
import time
from pathlib import Path

from .spec import PROJECT, ROOT, TRACE_TIMEOUT_S

SSH_PORT = 2222
SSH_KEY = PROJECT / 'vm' / 'research_vm_ed25519'
WAL_NAME = re.compile(r'(?:-wal$|sqlite-wal)')
INDEXEDDB_DIR = '/IndexedDB/'
# Tolerance for joining a strace row to its eBPF twin on the shared guest timeline.
# Both are syscall-entry probes, so a genuine duplicate lands within microseconds; this
# only has to absorb the residual realtime->monotonic offset fit.
EBPF_JOIN_TOLERANCE_S = 0.05

SYNC_NAME = 'fsync|fdatasync|sync_file_range|msync'
# File-lifecycle family added for Experiment C1: the close/delete/truncate half of
# the SQLite WAL shutdown, which the sync-only set cannot see.
FILE_NAME = 'unlink|unlinkat|ftruncate|truncate'
SYNC_CALLS = frozenset(SYNC_NAME.split('|'))
FILE_CALLS = frozenset(FILE_NAME.split('|'))
CALL_NAME = '(?:' + SYNC_NAME + '|' + FILE_NAME + ')'
PID_PREFIX = r'(?:\[pid\s+(?P<pid>\d+)\]\s+)?'
# A call completed on its own line: `[pid N] TS fdatasync(3</p>) = 0 <0.0007>`
SYNC_LINE = re.compile(
    PID_PREFIX + r'(?P<ts>\d+\.\d+)\s+(?P<call>(?:' + CALL_NAME + r'))\((?P<args>.*?)\)\s+=\s+'
    r'(?P<ret>-?\d+)(?P<rest>.*)$')
# A call whose trace text was interrupted: `[pid N] TS fdatasync(3</p>) <unfinished ...>`
UNFINISHED_LINE = re.compile(
    PID_PREFIX + r'(?P<ts>\d+\.\d+)\s+(?P<call>(?:' + CALL_NAME + r'))\((?P<args>.*?)\s+<unfinished \.\.\.>$')
# The continuation: `[pid N] TS <... fdatasync resumed>) = 0 <0.0007>`
RESUMED_LINE = re.compile(
    PID_PREFIX + r'(?:(?P<completed_ts>\d+\.\d+)\s+)?<\.\.\.\s+'
    r'(?P<call>(?:' + CALL_NAME + r'))\s+resumed>(?P<args>.*?)\)\s+=\s+(?P<ret>-?\d+)(?P<rest>.*)$')
FD_PATH = re.compile(r'(?P<fd>\d+)<(?P<path>[^>]*)>')
QUOTED = re.compile(r'"(?P<path>[^"]*)"')
# Uprobe stage: the nine prescribed Candidate-1 symbols, attempted every trial.
UPROBES = ('DatabaseConnection::Release', 'DatabaseConnection::MaybeSelfDestruct',
           'BackingStoreImpl::DestroyConnection', 'DatabaseConnection::GetCleanupTask',
           'DatabaseConnection::CloseDatabase', 'sql::Database::CloseInternal',
           'sqlite3WalClose', 'sqlite3WalCheckpoint', 'unixSync')


def guest_ssh_command(command: str) -> list[str]:
    return ['ssh', '-i', str(SSH_KEY), '-p', str(SSH_PORT), '-o', 'BatchMode=yes',
            '-o', 'StrictHostKeyChecking=accept-new', '-o', 'ConnectTimeout=5',
            'research@127.0.0.1', command]


async def ssh(command: str, *, timeout: float = 30, input_bytes: bytes | None = None) -> str:
    process = await asyncio.create_subprocess_exec(
        *guest_ssh_command(command),
        stdin=asyncio.subprocess.PIPE if input_bytes is not None else asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    stdout, stderr = await asyncio.wait_for(process.communicate(input_bytes), timeout)
    if process.returncode:
        raise RuntimeError(f'Guest command failed ({process.returncode}): {command}: {stderr.decode()}')
    return stdout.decode()


async def scp_to_guest(local: Path, remote: str) -> None:
    process = await asyncio.create_subprocess_exec(
        'scp', '-q', '-i', str(SSH_KEY), '-P', str(SSH_PORT), '-o', 'BatchMode=yes',
        '-o', 'StrictHostKeyChecking=accept-new', str(local), f'research@127.0.0.1:{remote}',
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    _, stderr = await asyncio.wait_for(process.communicate(), 30)
    if process.returncode:
        raise RuntimeError('Guest copy failed: ' + stderr.decode())


async def capture(command: str, stdout_path: Path, stderr_path: Path, *, parse_json: bool = False):
    """Run a guest command over SSH, copying both streams verbatim to disk.

    When `parse_json`, each stdout line is also indexed with the host time at
    which the copy received it. `rows` is that index; `last_received_ns` advances
    on every stdout chunk (used as the approximate host stamp for line-oriented
    trace text where a per-line receipt time is not available)."""
    proc = await asyncio.create_subprocess_exec(*guest_ssh_command(command),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    rows: list[dict] = []
    state = {'last_received_ns': None, 'count': 0, 'parse_errors': 0}

    async def pump(reader, path: Path, index: bool):
        pending = b''
        with path.open('xb', buffering=0) as stream:
            while chunk := await reader.read(65536):
                state['last_received_ns'] = time.monotonic_ns()
                stream.write(chunk)
                if not index:
                    continue
                pending += chunk
                while b'\n' in pending:
                    line, pending = pending.split(b'\n', 1)
                    if not line.strip():
                        continue
                    received_ns = time.monotonic_ns()
                    try:
                        row = json.loads(line)
                        if not isinstance(row, dict):
                            raise ValueError('not an object')
                        row['host_received_ns'] = received_ns
                        rows.append(row)
                        state['count'] += 1
                    except Exception:
                        state['parse_errors'] += 1
            if index and pending.strip():
                state['parse_errors'] += 1

    tasks = [asyncio.create_task(pump(proc.stdout, stdout_path, parse_json)),
             asyncio.create_task(pump(proc.stderr, stderr_path, False))]
    state['rows'] = rows
    return proc, tasks, state


async def finish_capture(proc, tasks, *, timeout: float = TRACE_TIMEOUT_S + 25) -> int | None:
    try:
        code = await asyncio.wait_for(proc.wait(), timeout)
    except (asyncio.TimeoutError, TimeoutError):
        proc.kill()
        code = await proc.wait()
    await asyncio.gather(*tasks, return_exceptions=True)
    return code


async def terminate_capture(proc, tasks, *, timeout: float = 20) -> int | None:
    if proc.returncode is None:
        proc.terminate()
    try:
        code = await asyncio.wait_for(proc.wait(), timeout)
    except (asyncio.TimeoutError, TimeoutError):
        proc.kill()
        code = await proc.wait()
    await asyncio.gather(*tasks, return_exceptions=True)
    return code


async def browser_main_pid(profile: str) -> int:
    script = ('import json,pathlib\nprofile = ' + repr(profile) + '\n'
              "found = []\n"
              "for item in pathlib.Path('/proc').iterdir():\n"
              "    if not item.name.isdigit(): continue\n"
              "    try: command = (item / 'cmdline').read_bytes().replace(b'\\0', b' ').decode(errors='replace')\n"
              "    except OSError: continue\n"
              "    if '--user-data-dir=' + profile in command and '--type=' not in command:\n"
              "        found.append(int(item.name))\n"
              "print(json.dumps(found))")
    found = json.loads(await ssh('python3 -c ' + shlex.quote(script)))
    assert len(found) == 1, f'Expected one Chromium main process, found {found}'
    return found[0]


async def browser_executable(pid: int) -> str:
    """Resolve the exact executable of an already-running browser main process.

    The uprobe stage must name the same binary the workload runs, so the path is
    read from `/proc/<main_pid>/exe` rather than guessed.
    """
    return (await ssh(f'readlink -f /proc/{pid}/exe')).strip()


def descendant_pids(ps_text: str, root: int) -> list[int]:
    pairs = [tuple(map(int, line.split()[:2])) for line in ps_text.splitlines() if len(line.split()) >= 2]
    result = {int(root)}
    while True:
        new = result | {pid for pid, parent in pairs if parent in result}
        if new == result:
            return sorted(result)
        result = new


def instantiate(program_template: str, pids: list[int]) -> str:
    return program_template.replace('@@PREDICATE@@', ' || '.join(f'pid == {pid}' for pid in pids))


def strace_command(pids: list[int]) -> str:
    pid_args = ' '.join(f'-p {pid}' for pid in pids)
    # `-s 256` (was `-s 0` in B1) so the path argument of `unlink`/`unlinkat`/
    # `truncate` is printed; the sync family carries no string arguments, so the
    # sync channel is unaffected.
    return ('sudo -n timeout -s INT ' + str(TRACE_TIMEOUT_S) + 's strace -f -ttt -T -yy -s 256 '
            '-e trace=fsync,fdatasync,sync_file_range,msync,unlink,unlinkat,ftruncate,truncate '
            + pid_args)


def ebpf_command(remote_program: str) -> str:
    return f'sudo -n timeout -s INT {TRACE_TIMEOUT_S}s bpftrace {remote_program}'


def observer_command(directory: str, duration_s: float, interval_ms: float = 50) -> str:
    return (f'python3 -u /tmp/paper3v2c1-observer.py --directory {shlex.quote(directory)} '
            f'--duration-s {duration_s} --interval-ms {interval_ms}')


def is_wal(path: str) -> bool:
    """The IndexedDB backing-store WAL only.

    A bare `-wal` suffix also matches unrelated Chromium databases (for example
    `Default/DIPS-wal`), so the file must also live under the profile's `IndexedDB`
    directory to be treated as the target descriptor.
    """
    return INDEXEDDB_DIR in path and bool(WAL_NAME.search(path.rsplit('/', 1)[-1]))


def _sync_event(line, call, ts, args, ret, rest, *, resumed=False, completed_ts=None):
    """One strace call. `guest_realtime_s` is the syscall *entry* time (the stamp
    strace prints at entry), so a one-line call and a resumed call are commensurable.

    `family` splits the sync channel from the Experiment C1 file-lifecycle channel.
    `path_arg` is the quoted pathname of `unlink`/`unlinkat`/`truncate`; `fd_path` is
    the `-yy` descriptor path of `ftruncate` (and of the sync family).
    """
    fd_match = FD_PATH.match(args)
    quoted = QUOTED.search(args)
    duration_match = re.search(r'<(\d+\.\d+)>', rest)
    return {
        'source': 'strace', 'syscall': call,
        'family': 'sync' if call in SYNC_CALLS else 'file',
        'guest_realtime_s': float(ts),
        'guest_realtime_completed_s': float(completed_ts) if completed_ts else None,
        'pid': None, 'fd': int(fd_match.group('fd')) if fd_match else None,
        'fd_path': fd_match.group('path') if fd_match else None,
        'path_arg': quoted.group('path') if quoted else None,
        'return_value': int(ret), 'completed': int(ret) == 0,
        'duration_s': float(duration_match.group(1)) if duration_match else None,
        'resumed': resumed, 'raw': line.rstrip(),
    }


def parse_strace(text: str) -> dict:
    """Parse fsync/fdatasync/sync_file_range/msync lines from `strace -ttt -T -yy -f`.

    With `-f` strace interleaves threads, so a call's text is frequently split into an
    entry line ending in `<unfinished ...>` and a later `<... call resumed>` line. Both
    forms are reconstructed: a resumed completion inherits the entry line's timestamp,
    descriptor and resolved path, so an interleaved WAL sync is not lost.
    """
    events, unfinished, resumed, unmatched = [], 0, 0, 0
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
            event = _sync_event(line, call, ts, args, continuation.group('ret'),
                                continuation.group('rest'), resumed=True,
                                completed_ts=continuation.group('completed_ts'))
            event['pid'] = pid or None
            events.append(event)
            continue
        match = SYNC_LINE.match(line)
        if not match:
            unmatched += 1
            continue
        event = _sync_event(line, match.group('call'), match.group('ts'), match.group('args'),
                            match.group('ret'), match.group('rest'))
        event['pid'] = int(match.group('pid')) if match.group('pid') else None
        events.append(event)
    return {'events': events, 'unfinished_lines': unfinished, 'resumed_lines': resumed,
            'unmatched_lines': unmatched}


def parse_uprobe(text: str) -> dict:
    """Parse one row per firing from the C1 uprobe stage.

    Emitted shape (space separated): U NSECS PID TID SYMBOL COMM. A program that
    could not attach emits nothing; the reason is recorded separately in
    ``uprobe_status`` by the trial runner.
    """
    events, unmatched = [], 0
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 6 or parts[0] != 'U':
            if line.strip():
                unmatched += 1
            continue
        events.append({'source': 'uprobe', 'kind': 'U', 'symbol': parts[4],
                       'guest_monotonic_ns': int(parts[1]), 'pid': int(parts[2]),
                       'tid': int(parts[3]), 'comm': ' '.join(parts[5:]),
                       'raw': line.rstrip()})
    return {'events': events, 'unmatched_lines': unmatched}


def uprobe_command(remote_program: str) -> str:
    return f'sudo -n timeout -s INT {TRACE_TIMEOUT_S}s bpftrace {remote_program}'


def uprobe_list_command(binary: str) -> str:
    return f"sudo -n bpftrace -l 'uprobe:{binary}:*' 2>&1"


def uprobe_resolution(listing: str, binary: str) -> dict:
    """Which of the nine prescribed symbols bpftrace can attach to on this build.

    bpftrace resolves uprobe names from the executable's symbol table, and its
    probe syntax cannot carry a `::` C++ name, so a symbol is only usable when a
    plain (C) name appears in the listing. Nothing is guessed: a symbol absent
    from the listing is recorded as unresolved with the listing line count.
    """
    available = set()
    for line in listing.splitlines():
        line = line.strip()
        if not line.startswith('uprobe:'):
            continue
        tail = line.rsplit(':', 1)[-1].strip()
        if tail:
            available.add(tail)
    resolvable, unresolved = [], []
    for symbol in UPROBES:
        (resolvable if symbol in available else unresolved).append(symbol)
    return {'binary': binary, 'listing_entries': len(available),
            'resolvable': resolvable, 'unresolved': unresolved,
            'resolvable_probe_lines': [f'uprobe:{binary}:{name}' for name in resolvable]}


def uprobe_program(template: str, resolution: dict) -> str:
    """Instantiate the uprobe template with only the resolvable probe lines."""
    lines = resolution['resolvable_probe_lines']
    body = ',\n'.join(lines)
    return template.replace('@@PROBES@@', body if body else '// no resolvable probe')


def parse_bpftrace(text: str) -> dict:
    """Parse one row per event from `trace_b1.bt`.

    Emitted shape (space separated): KIND NSECS PID TID PROBE FD COMM [COUNT],
    with `FD` printed as `-1` for msync. `comm` is the last non-count token, so a
    process name containing a space does not shift the count.

    Kinds: W = write/pwrite64 (count = bytes), V = writev/pwritev (count = iovec
    length, not bytes), S = fsync/fdatasync, R = sync_file_range, M = msync.
    """
    events, unmatched = [], 0
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 7 or parts[0] not in ('W', 'V', 'S', 'R', 'M'):
            if line.strip():
                unmatched += 1
            continue
        kind = parts[0]
        probe = parts[4]
        if kind in ('W', 'V') and len(parts) > 7:
            count = int(parts[-1])
            comm = ' '.join(parts[6:-1])
        else:
            count = None
            comm = ' '.join(parts[6:])
        events.append({
            'source': 'ebpf', 'kind': kind, 'probe': probe,
            'syscall': probe.split('sys_enter_')[-1] if 'sys_enter_' in probe else probe,
            'guest_monotonic_ns': int(parts[1]),
            'pid': int(parts[2]), 'tid': int(parts[3]),
            'fd': None if parts[5] == '-1' else int(parts[5]),
            'comm': comm,
            'count': count,
            'raw': line.rstrip(),
        })
    return {'events': events, 'unmatched_lines': unmatched}


def _wal_presence(rows: list[dict]) -> list[dict]:
    """Per-sample WAL file lifecycle: present/absent, size, dirty and writeback pages.

    The cachestat sampler re-enumerates the IndexedDB directory every ~50 ms, so a
    WAL file that SQLite deletes (or truncates to zero) on connection close simply
    stops appearing (or reports size 0), which is visible without any symbol.
    """
    out = []
    for row in rows:
        states = row.get('files') or {}
        wal = {path: state for path, state in states.items() if is_wal(path)}
        if not wal:
            out.append({'guest_monotonic_ns': row.get('guest_monotonic_ns'),
                        'guest_realtime_ns': row.get('guest_realtime_ns'),
                        'guest_uptime_s': row.get('guest_uptime_s'),
                        'sample_index': row.get('sample_index'),
                        'host_received_ns': row.get('host_received_ns'),
                        'present': False, 'paths': [], 'size': None,
                        'dirty': None, 'writeback': None, 'inode': None})
            continue
        for path, state in sorted(wal.items()):
            out.append({'guest_monotonic_ns': row.get('guest_monotonic_ns'),
                        'guest_realtime_ns': row.get('guest_realtime_ns'),
                        'guest_uptime_s': row.get('guest_uptime_s'),
                        'sample_index': row.get('sample_index'),
                        'host_received_ns': row.get('host_received_ns'),
                        'present': True, 'paths': [path],
                        'size': state.get('size'), 'dirty': state.get('dirty'),
                        'writeback': state.get('writeback'), 'inode': state.get('inode')})
    return out


def _wal_lifecycle_events(presence: list[dict], ack_monotonic_ns) -> list[dict]:
    """Transitions of the WAL file itself: disappeared, reappeared, or emptied.

    ``close_type`` flags the transitions that a sqlite3WalClose would produce
    (the file going away, or a PASSIVE checkpoint truncating it to zero).
    ``wal_appeared`` is NOT close evidence: the file also materialises when the
    first write of a fresh connection creates it, so it is recorded but never
    counted as a connection-close effect.
    """
    events = []
    previous = None
    close_type = {'wal_disappeared': True, 'wal_truncated_to_zero': True,
                  'wal_appeared': False}
    for row in presence:
        if previous is not None:
            name = None
            if previous['present'] and not row['present']:
                name = 'wal_disappeared'
            elif not previous['present'] and row['present']:
                name = 'wal_appeared'
            elif (previous['present'] and row['present'] and previous['size'] not in (None, 0)
                  and row['size'] == 0):
                name = 'wal_truncated_to_zero'
            if name:
                events.append({'event': name, 'close_type': close_type[name],
                               **{k: row[k] for k in
                                  ('guest_monotonic_ns', 'guest_realtime_ns', 'guest_uptime_s',
                                   'sample_index', 'host_received_ns')}})
        previous = row
    for event in events:
        event['guest_time_rel_ack_s'] = relative_s(event.get('guest_monotonic_ns'),
                                                   ack_monotonic_ns=ack_monotonic_ns, clock='monotonic')
    return events


def _clean_signature(rows: list[dict]) -> list[dict]:
    """dirty|writeback > 0 in the previous sample and == 0 in the current sample."""
    out, previous = [], {}
    for row in rows:
        for path, state in (row.get('files') or {}).items():
            if not isinstance(state, dict) or 'dirty' not in state or 'writeback' not in state:
                continue
            old = previous.get(path)
            if old and old['dirty'] + old['writeback'] > 0 and state['dirty'] == state['writeback'] == 0:
                out.append({'file': path, 'guest_monotonic_ns': row.get('guest_monotonic_ns'),
                            'guest_realtime_ns': row.get('guest_realtime_ns'),
                            'guest_uptime_s': row.get('guest_uptime_s'),
                            'sample_index': row.get('sample_index'),
                            'host_received_ns': row.get('host_received_ns'),
                            'inode': state.get('inode'), 'size': state.get('size')})
            previous[path] = state
    return out


def _blockdev_events(rows: list[dict]) -> list[dict]:
    events, previous = [], {}
    for row in rows:
        devices = row.get('blockdev') or {}
        name = next((n for n in ('vda', 'sda') if n in devices), None) or \
            next((n for n in sorted(devices) if not n[-1].isdigit()), None)
        if name is None:
            continue
        current = devices[name]
        old = previous.get(name)
        if old is not None:
            writes = (current.get('writes') or 0) - (old.get('writes') or 0)
            sectors = (current.get('sectors_written') or 0) - (old.get('sectors_written') or 0)
            flushes = (current.get('flushes') or 0) - (old.get('flushes') or 0)
            if writes > 0 or sectors > 0 or flushes > 0:
                events.append({'device': name, 'writes_delta': writes, 'sectors_written_delta': sectors,
                               'flushes_delta': flushes,
                               'guest_monotonic_ns': row.get('guest_monotonic_ns'),
                               'guest_realtime_ns': row.get('guest_realtime_ns'),
                               'guest_uptime_s': row.get('guest_uptime_s'),
                               'sample_index': row.get('sample_index'),
                               'host_received_ns': row.get('host_received_ns')})
        previous[name] = current
    return events


def realtime_to_monotonic_offset_ns(samples: list[dict]) -> int | None:
    """CLOCK_REALTIME - CLOCK_MONOTONIC, taken from the sampler's own paired readings.

    Every cachestat sample records both guest clocks at the same instant, so the median
    difference places the strace (CLOCK_REALTIME, `-ttt`) channel and the eBPF/cachestat
    (CLOCK_MONOTONIC) channel on one guest timeline for a direct cross-channel join.
    """
    offsets = [row['guest_realtime_ns'] - row['guest_monotonic_ns'] for row in samples
               if isinstance(row.get('guest_realtime_ns'), int)
               and isinstance(row.get('guest_monotonic_ns'), int)]
    return int(statistics.median(offsets)) if offsets else None


def relative_s(value, ack_monotonic_ns=None, ack_realtime_s=None, *, clock: str):
    if value is None:
        return None
    if clock == 'monotonic' and ack_monotonic_ns is not None:
        return (value - ack_monotonic_ns) / 1e9
    if clock == 'realtime' and ack_realtime_s is not None:
        return value - ack_realtime_s
    return None


def reduce_trace(*, browser_events: list[dict], samples: list[dict], gate_host_ns: int | None,
                 ack_monotonic_ns: int | None, ack_realtime_ms: float | None,
                 ack_uptime_s, command_ns: int, strace_text: str, bpftrace_text: str,
                 uprobe_text: str = '', uprobe_status: dict | None = None,
                 reset_rel_ack_s: float | None = None) -> dict:
    strace = parse_strace(strace_text)
    ebpf = parse_bpftrace(bpftrace_text)
    uprobe = parse_uprobe(uprobe_text)
    ack_realtime_s = (ack_realtime_ms / 1000.0) if ack_realtime_ms is not None else None
    offset_ns = realtime_to_monotonic_offset_ns(samples)

    wal_paths = sorted({e['fd_path'] for e in strace['events']
                        if e['fd_path'] and is_wal(e['fd_path'])})
    wal_paths += sorted({p for row in samples for p in (row.get('files') or {}) if is_wal(p)})
    wal_paths = sorted(set(wal_paths))
    wal_fds = sorted({e['fd'] for e in strace['events'] if e['fd'] is not None
                      and e['fd_path'] and is_wal(e['fd_path'])})

    # strace's `[pid N]` is the *thread* id, so it joins to the eBPF stream's tid first.
    comm_by_tid, comm_by_pid = {}, {}
    for event in ebpf['events']:
        comm_by_tid.setdefault(event['tid'], event['comm'])
        comm_by_pid.setdefault(event['pid'], event['comm'])
    fd_paths = {}
    for event in strace['events']:
        if event['fd'] is not None and event['fd_path']:
            fd_paths[str(event['fd'])] = event['fd_path']

    strace_rows = []
    for event in strace['events']:
        byte_count = None
        if event['syscall'] == 'sync_file_range':
            fields = [field.strip() for field in event['raw'].split('(', 1)[-1].split(',')]
            if len(fields) >= 3:
                try:
                    byte_count = int(fields[2], 0)
                except ValueError:
                    byte_count = None
        mono_ns = (int(round(event['guest_realtime_s'] * 1e9)) - offset_ns
                   if offset_ns is not None else None)
        on_wal = bool((event['fd_path'] and is_wal(event['fd_path']))
                      or (event['path_arg'] and is_wal(event['path_arg'])))
        strace_rows.append({
            'source': 'strace', 'syscall': event['syscall'], 'family': event['family'],
            'pid': event['pid'],
            'comm': comm_by_tid.get(event['pid']) or comm_by_pid.get(event['pid']),
            'issuing_process': comm_by_tid.get(event['pid']) or comm_by_pid.get(event['pid']),
            'fd': event['fd'], 'fd_path': event['fd_path'], 'path_arg': event['path_arg'],
            'on_wal_descriptor': on_wal,
            'bytes': byte_count, 'resumed': event['resumed'],
            'duration_s': event['duration_s'], 'return_value': event['return_value'],
            'completed': event['completed'],
            'guest_realtime_s': event['guest_realtime_s'],
            'guest_realtime_completed_s': event['guest_realtime_completed_s'],
            'guest_monotonic_ns_est': mono_ns,
            'clock_basis': 'guest_monotonic' if mono_ns is not None else 'guest_realtime',
            'guest_time_rel_ack_s': (
                relative_s(mono_ns, ack_monotonic_ns=ack_monotonic_ns, clock='monotonic')
                if mono_ns is not None else
                relative_s(event['guest_realtime_s'], ack_realtime_s=ack_realtime_s, clock='realtime')),
        })
    sync_rows = [row for row in strace_rows if row['family'] == 'sync']
    file_rows = [row for row in strace_rows if row['family'] == 'file']
    wal_file_rows = [row for row in file_rows if row['on_wal_descriptor']]

    ebpf_rows = []
    for event in ebpf['events']:
        ebpf_rows.append({
            'source': 'ebpf', 'syscall': event['syscall'], 'kind': event['kind'],
            'pid': event['pid'], 'tid': event['tid'], 'comm': event['comm'],
            'fd': event['fd'], 'on_wal_descriptor': event['fd'] in wal_fds,
            'bytes': event['count'] if event['kind'] == 'W' else None,
            'iovec_length': event['count'] if event['kind'] == 'V' else None,
            'guest_monotonic_ns': event['guest_monotonic_ns'],
            'guest_time_rel_ack_s': relative_s(event['guest_monotonic_ns'],
                                               ack_monotonic_ns=ack_monotonic_ns, clock='monotonic'),
            'host_received_ns': None,
        })

    transitions = _clean_signature(samples)
    for transition in transitions:
        transition['source'] = 'cachestat'
        transition['guest_time_rel_ack_s'] = relative_s(
            transition.get('guest_monotonic_ns'), ack_monotonic_ns=ack_monotonic_ns, clock='monotonic')
        transition['wal'] = is_wal(transition['file'])

    blockdev = _blockdev_events(samples)
    for event in blockdev:
        event['source'] = 'blockdev'
        event['guest_time_rel_ack_s'] = relative_s(
            event.get('guest_monotonic_ns'), ack_monotonic_ns=ack_monotonic_ns, clock='monotonic')

    starts = [e for e in browser_events if e.get('payload', {}).get('kind') == 'TARGET_WRITE_STARTED']
    write_start_ms = starts[0]['payload'].get('browserRealtimeMs') if starts else None

    wal_sync = [row for row in sync_rows if row['on_wal_descriptor']]
    # Mechanical cross-channel join, not an inference: an eBPF sync on a WAL descriptor is
    # a duplicate of a strace row when they name the same syscall and descriptor and land
    # within EBPF_JOIN_TOLERANCE_S on the shared guest timeline. Anything left is reported.
    strace_times = [(row['syscall'], row['fd'], row['guest_time_rel_ack_s']) for row in wal_sync
                    if row['guest_time_rel_ack_s'] is not None]
    ebpf_only = []
    for row in ebpf_rows:
        if not row['on_wal_descriptor'] or row['guest_time_rel_ack_s'] is None:
            continue
        if row['kind'] in ('W', 'V'):
            continue
        if not any(syscall == row['syscall'] and fd == row['fd']
                   and abs(rel - row['guest_time_rel_ack_s']) <= EBPF_JOIN_TOLERANCE_S
                   for syscall, fd, rel in strace_times):
            ebpf_only.append(row)

    wal_transitions = [t for t in transitions if t['wal']]
    spacing = [round(b['guest_time_rel_ack_s'] - a['guest_time_rel_ack_s'], 6)
               for a, b in zip(wal_transitions, wal_transitions[1:])
               if a['guest_time_rel_ack_s'] is not None and b['guest_time_rel_ack_s'] is not None]
    intervals = [row['guest_monotonic_ns'] for row in samples if isinstance(row.get('guest_monotonic_ns'), int)]
    deltas = [(b - a) / 1e6 for a, b in zip(intervals, intervals[1:]) if b > a]

    # ---- Experiment C1: the (ACK, reset] window and what happened inside it ----
    wal_presence = _wal_presence(samples)
    for row in wal_presence:
        row['guest_time_rel_ack_s'] = relative_s(row.get('guest_monotonic_ns'),
                                                 ack_monotonic_ns=ack_monotonic_ns, clock='monotonic')
    wal_lifecycle = _wal_lifecycle_events(wal_presence, ack_monotonic_ns)

    uprobe_rows = []
    for event in uprobe['events']:
        uprobe_rows.append({'source': 'uprobe', 'symbol': event['symbol'],
                            'pid': event['pid'], 'tid': event['tid'], 'comm': event['comm'],
                            'guest_monotonic_ns': event['guest_monotonic_ns'],
                            'guest_time_rel_ack_s': relative_s(event['guest_monotonic_ns'],
                                                               ack_monotonic_ns=ack_monotonic_ns,
                                                               clock='monotonic')})

    def _in_window(value):
        if value is None:
            return False
        if value < 0:
            return False
        return reset_rel_ack_s is None or value <= reset_rel_ack_s

    effect = {
        'window_s': reset_rel_ack_s,
        'window_bounded': reset_rel_ack_s is not None,
        'wal_fd_syncs_in_window': [r for r in wal_sync if _in_window(r['guest_time_rel_ack_s'])],
        'wal_file_events_in_window': [r for r in wal_file_rows
                                      if _in_window(r['guest_time_rel_ack_s'])],
        'wal_lifecycle_events_in_window': [e for e in wal_lifecycle
                                           if e.get('close_type')
                                           and _in_window(e['guest_time_rel_ack_s'])],
        'wal_appeared_in_window': [e for e in wal_lifecycle
                                   if e['event'] == 'wal_appeared'
                                   and _in_window(e['guest_time_rel_ack_s'])],
        'wal_dirty_to_clean_in_window': [t for t in wal_transitions
                                         if _in_window(t['guest_time_rel_ack_s'])],
    }
    effect['observed'] = bool(effect['wal_fd_syncs_in_window']
                              or effect['wal_file_events_in_window']
                              or effect['wal_lifecycle_events_in_window']
                              or effect['wal_dirty_to_clean_in_window'])

    return {
        'ack_guest_realtime_ms': ack_realtime_ms,
        'ack_guest_monotonic_ns': ack_monotonic_ns,
        'ack_guest_uptime_s': ack_uptime_s,
        'gate_released_host_ns': gate_host_ns,
        'target_write_start_guest_realtime_ms': write_start_ms,
        'target_write_start_to_ack_ms': (ack_realtime_ms - write_start_ms)
        if (write_start_ms is not None and ack_realtime_ms is not None) else None,
        'wal_paths': wal_paths,
        'wal_descriptors': wal_fds,
        'traced_fd_paths': fd_paths,
        'wal_fd_paths': {str(fd): fd_paths[str(fd)] for fd in wal_fds if str(fd) in fd_paths},
        'clock_anchors': {
            'strace_clock': 'CLOCK_REALTIME (-ttt), relative to page browserRealtimeMs at ACK',
            'ebpf_clock': 'CLOCK_MONOTONIC (bpftrace nsecs), relative to guest-agent uptime RPC monotonic at ACK',
            'cachestat_clock': 'CLOCK_MONOTONIC + /proc/uptime, relative to guest-agent uptime RPC monotonic at ACK',
            'blockdev_clock': 'CLOCK_MONOTONIC + /proc/uptime, relative to guest-agent uptime RPC monotonic at ACK',
            'note': 'within-guest anchoring only; no host clock used to convert a guest time',
            'ack_realtime_vs_monotonic_offset_note': 'page Date.now() and the uptime RPC are separate guest samples; '
                                                     'their residual offset is bounded by the ACK-to-RPC round trip',
        },
        'strace_events_total': len(strace['events']),
        'strace_unmatched_lines': strace['unmatched_lines'],
        'strace_unfinished_lines': strace['unfinished_lines'],
        'strace_resumed_lines': strace.get('resumed_lines'),
        'strace_clock_basis': ('guest_monotonic via the sampler\'s realtime-monotonic offset'
                               if offset_ns is not None else
                               'guest_realtime (no sampler offset available)'),
        'realtime_to_monotonic_offset_ns': offset_ns,
        'ebpf_events_total': len(ebpf['events']),
        'ebpf_unmatched_lines': ebpf['unmatched_lines'],
        'wal_sync_events': wal_sync,
        'strace_file_events': file_rows,
        'wal_file_events': wal_file_rows,
        'wal_file_lifecycle': wal_presence,
        'wal_lifecycle_events': wal_lifecycle,
        'connection_close_effect': effect,
        'uprobe_status': uprobe_status or {},
        'uprobe_events': uprobe_rows,
        'uprobe_tids_seen': sorted({row['tid'] for row in uprobe_rows}),
        'uprobe_symbols_seen': sorted({row['symbol'] for row in uprobe_rows}),
        'uprobe_unmatched_lines': uprobe['unmatched_lines'],
        'ebpf_events_on_wal_fd_not_in_strace': ebpf_only,
        'wal_dirty_to_clean_transitions': wal_transitions,
        'wal_dirty_to_clean_spacing_s': spacing,
        'blockdev_flush_events': [e for e in blockdev if e['flushes_delta'] > 0],
        'blockdev_write_events': [e for e in blockdev if e['writes_delta'] > 0 or e['sectors_written_delta'] > 0],
        'clean_before_reset': bool(wal_transitions),
        'earliest_clean_rel_ack_s': min((t['guest_time_rel_ack_s'] for t in wal_transitions
                                         if t['guest_time_rel_ack_s'] is not None), default=None),
        'sampling': {'cachestat_samples': len(samples), 'sampled_files': len(samples[0].get('files', {}))
                     if samples else 0, 'median_interval_ms': statistics.median(deltas) if deltas else None},
    }


def write_ledger(path: Path, reduction: dict, strace_text: str, bpftrace_text: str) -> int:
    """One row per observed event, with source, guest and host timestamps, fd/file and state."""
    rows = []
    for row in reduction['wal_sync_events']:
        rows.append({'source': 'strace', 'syscall': row['syscall'], 'pid': row['pid'],
                     'fd': row['fd'], 'path': row['fd_path'], 'state': 'completed' if row['completed'] else 'errored',
                     'guest_realtime_s': row['guest_realtime_s'],
                     'guest_time_rel_ack_s': row['guest_time_rel_ack_s'],
                     'host_timestamp_ns': None, 'host_timestamp_kind': 'not_per_line',
                     'observed': {'return_value': row['return_value'], 'duration_s': row['duration_s']}})
    for row in reduction['ebpf_events_on_wal_fd_not_in_strace']:
        rows.append({'source': 'ebpf', 'syscall': row['syscall'], 'pid': row['pid'], 'fd': row['fd'],
                     'path': next((p for p in reduction['wal_paths']
                                   if p.rsplit('/', 1)[-1].endswith('-wal')), None),
                     'state': 'ebpf_only_on_wal_fd', 'guest_monotonic_ns': row['guest_monotonic_ns'],
                     'guest_time_rel_ack_s': row['guest_time_rel_ack_s'],
                     'host_timestamp_ns': row['host_received_ns'], 'host_timestamp_kind': 'chunk_receipt',
                     'observed': {'comm': row['comm'], 'bytes': row['bytes']}})
    for row in reduction['wal_dirty_to_clean_transitions']:
        rows.append({'source': 'cachestat', 'event': 'dirty_to_clean', 'file': row['file'],
                     'fd': None, 'state': 'clean', 'guest_monotonic_ns': row['guest_monotonic_ns'],
                     'guest_realtime_ns': row['guest_realtime_ns'], 'guest_uptime_s': row['guest_uptime_s'],
                     'guest_time_rel_ack_s': row['guest_time_rel_ack_s'],
                     'host_timestamp_ns': row['host_received_ns'], 'host_timestamp_kind': 'per_line'})
    for row in reduction['blockdev_flush_events']:
        rows.append({'source': 'blockdev', 'device': row['device'], 'fd': None, 'file': None,
                     'state': 'flush', 'guest_monotonic_ns': row['guest_monotonic_ns'],
                     'guest_realtime_ns': row['guest_realtime_ns'], 'guest_uptime_s': row['guest_uptime_s'],
                     'guest_time_rel_ack_s': row['guest_time_rel_ack_s'],
                     'host_timestamp_ns': row['host_received_ns'], 'host_timestamp_kind': 'per_line',
                     'observed': {'flushes_delta': row['flushes_delta'], 'writes_delta': row['writes_delta']}})
    # Experiment C1 additions: the WAL file-lifecycle channel and the uprobe stage.
    for row in reduction.get('strace_file_events', []):
        rows.append({'source': 'strace', 'syscall': row['syscall'], 'family': 'file',
                     'pid': row['pid'], 'tid': row['pid'], 'fd': row['fd'],
                     'path': row['path_arg'] or row['fd_path'],
                     'on_wal': row['on_wal_descriptor'],
                     'state': 'completed' if row['completed'] else 'errored',
                     'guest_realtime_s': row['guest_realtime_s'],
                     'guest_time_rel_ack_s': row['guest_time_rel_ack_s'],
                     'host_timestamp_ns': None, 'host_timestamp_kind': 'not_per_line',
                     'observed': {'return_value': row['return_value'],
                                  'issuing_process': row['issuing_process']}})
    for row in reduction.get('wal_lifecycle_events', []):
        rows.append({'source': 'cachestat', 'event': row['event'], 'fd': None,
                     'file': next(iter(reduction.get('wal_paths', []) or [None]), None),
                     'state': row['event'], 'guest_monotonic_ns': row['guest_monotonic_ns'],
                     'guest_realtime_ns': row['guest_realtime_ns'], 'guest_uptime_s': row['guest_uptime_s'],
                     'guest_time_rel_ack_s': row['guest_time_rel_ack_s'],
                     'host_timestamp_ns': row['host_received_ns'], 'host_timestamp_kind': 'per_line'})
    for row in reduction.get('uprobe_events', []):
        rows.append({'source': 'uprobe', 'symbol': row['symbol'], 'pid': row['pid'],
                     'tid': row['tid'], 'fd': None, 'file': None, 'state': 'fired',
                     'guest_monotonic_ns': row['guest_monotonic_ns'],
                     'guest_time_rel_ack_s': row['guest_time_rel_ack_s'],
                     'host_timestamp_ns': None, 'host_timestamp_kind': 'not_per_line',
                     'observed': {'comm': row['comm']}})
    rows.sort(key=lambda row: (row.get('guest_time_rel_ack_s') is None,
                               row.get('guest_time_rel_ack_s') if row.get('guest_time_rel_ack_s') is not None else 0))
    with path.open('x') as stream:
        for row in rows:
            stream.write(json.dumps(row, separators=(',', ':')) + '\n')
    return len(rows)


def ack_realtime_and_events(ack_payload: dict) -> tuple[float | None, list[dict]]:
    """The page's own CLOCK_REALTIME stamp for the ACK, plus its diagnostic event list.

    Preferred source is the ACK payload's own `browserWallClockIso` (`new Date()` at
    ACK construction). The page's `browserRealtimeMs` from the ACK diagnostic identity
    is used only if that stamp is absent or unparseable.
    """
    events = (ack_payload.get('diagnosticIdentity') or {}).get('events') or []
    stamp = ack_payload.get('browserWallClockIso')
    if isinstance(stamp, str):
        try:
            parsed = datetime.datetime.fromisoformat(stamp.replace('Z', '+00:00'))
            # Epoch milliseconds, the same unit as `browserRealtimeMs`.
            return parsed.timestamp() * 1000.0, events
        except ValueError:
            pass
    for event in reversed(events):
        if event.get('kind') == 'ACK_RESPONSE_RETURNED' and isinstance(event.get('browserRealtimeMs'), (int, float)):
            return float(event['browserRealtimeMs']), events
    for event in reversed(events):
        if isinstance(event.get('browserRealtimeMs'), (int, float)):
            return float(event['browserRealtimeMs']), events
    return None, events
