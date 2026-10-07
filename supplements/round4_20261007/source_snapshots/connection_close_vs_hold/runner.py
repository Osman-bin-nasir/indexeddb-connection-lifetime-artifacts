"""Experiment C1: connection-lifecycle discriminator for the SQLite relaxed recovery step.

Two conditions, one workload, one tracing pipeline, one assigned delay (2.25 s):

  C1-control  the frozen frontend closes the original IDBDatabase after the ACK
              (``connection=closed``), exactly as in paper3v2_mechanism_b1;
  C1-test     the frozen frontend retains the original IDBDatabase and never calls
              ``close()`` (``connection=held``), so no DatabaseConnection can be
              released after the ACK.

If the +2.01 s WAL fdatasync is scheduled by the connection-destruction grace
period, C1-control recovers and C1-test does not. Reuses the paper3v2 harness
skeleton, workload, oracle and guest unchanged (strict sentinel -> one relaxed
target -> QMP system_reset -> recovery), plus the same host-controlled prewrite
gate and an identical tracing pipeline in both conditions. Traced trials are a
separate population and are never pooled with paper3v2, paper3v2_mechanism
(Experiment A) or paper3v2_mechanism_b1.

Per trial the pipeline attaches, before the gate is released and therefore before the
target write:
  * a PID-scoped strace over the browser process tree resolving fsync, fdatasync,
    sync_file_range, msync (and, new in C1, unlink/unlinkat/ftruncate/truncate) to
    file descriptors and paths;
  * an eBPF process-level stream over the write and sync families (path-agnostic);
  * a ~50 ms guest cachestat(2) + /proc/vmstat + /proc/diskstats sampler;
  * the prescribed uprobe stage over the nine Candidate-1 functions, attempted on
    every trial and recorded even when the guest build exposes none of them.

The gate is released only after the gating channels are verified alive, so a tracing
failure invalidates the trial (and is never counted as a loss). All guest event times
are reconstructed from the guest's own clocks and expressed relative to the target
ACK; no host clock converts a guest time.
"""
import asyncio
import datetime
import json
import shlex
import time
from dataclasses import replace
from pathlib import Path
from urllib.parse import parse_qs, parse_qsl, urlencode, urlsplit, urlunsplit

from controller.browser import BrowserController
from controller.config import ControllerConfig
from controller.experiment import (AcknowledgementServer, ExperimentRunner,
                                   ReceivedMessage, write_exclusive_json)
from controller.logger import EventLogger
from controller.metadata import collect_trial_metadata
from controller.targeted import (create_fresh_overlay, dynamic_config,
                                 verify_baseline_payload)
from paper2.boot_recovery_fix_01.runner import apply_boot_source_fix, normal_recovery
from paper2.diagnostic2.readiness import (LoggedGuestClient, crosscheck_identity,
                                          verify_health)
from paper2.harness import instrumented_reset, targeted_url

from . import tracing
from .oracle import GOOD, classify
from .qmp import QMPClient
from .spec import (CONDITIONS, CONTROL, EXPERIMENT, IDENTITY, PROJECT, ROOT, SLOTS,
                   TEST, TRACE_TIMEOUT_S, indexeddb_dir, profile, sha,
                   tracing_pipeline_sha256)
from .tracing import (UPROBES, ack_realtime_and_events, capture, descendant_pids,
                      ebpf_command, instantiate, observer_command, reduce_trace,
                      scp_to_guest, ssh, strace_command, terminate_capture,
                      uprobe_command, uprobe_list_command, uprobe_program,
                      uprobe_resolution, write_ledger)

SQLITE_SIGNATURE = '53514c69746520666f726d6174203300'
RESOLVED = {'SENTINEL_SURVIVED_TARGET_SURVIVED', 'SENTINEL_SURVIVED_TARGET_LOST',
            'SENTINEL_LOST', 'CHECKSUM_FAILURE', 'UNEXPECTED_STATE'}
OBSERVER_REMOTE = '/tmp/paper3v2c1-observer.py'
PROGRAM_REMOTE = '/tmp/paper3v2c1-trace.bt'
UPROBE_REMOTE = '/tmp/paper3v2c1-uprobe.bt'
# The workload mechanism that keeps the original connection alive in C1-test.
HOLD_MECHANISM = {'C1-control': 'connection_closed_after_ack',
                  'C1-test': 'held_open_flag'}

# Shared state for the tracer attachment, set before the Runner is constructed.
CURRENT: dict = {}


def save(path, value):
    write_exclusive_json(path, value)


def config():
    c = ControllerConfig.load(ROOT / 'config.yaml')
    return replace(c, paths=replace(c.paths, project_root=PROJECT))


def append(path, value):
    with path.open('a') as stream:
        stream.write(json.dumps(value, separators=(',', ':')) + '\n')


def check_freeze():
    freeze = json.loads((ROOT / 'support' / 'experiment-freeze.json').read_text())
    assert freeze['experiment_id'] == EXPERIMENT
    assert {slot['condition'] for slot in SLOTS} == set(CONDITIONS)
    assert sha(ROOT / 'support' / 'order.json') == freeze['order_sha256']
    for name, digest in freeze['source_hashes'].items():
        assert sha(PROJECT / name) == digest, name
    assert tracing_pipeline_sha256() == freeze['tracing_pipeline_sha256'], 'Tracing pipeline changed'
    c = config()
    assert sha(c.vm.disk_image) == freeze['baseline_sha256']
    assert sha(PROJECT / 'vm/browser-storage.qcow2') == freeze['backing_sha256']
    return c


class GateServer(AcknowledgementServer):
    """ACK/recovery/diagnostic wire server that also holds the run page at /control."""

    def __init__(self, host, port, trace):
        super().__init__(host, port)
        self.trace = trace
        self.waiting = asyncio.Event()
        self.gate = asyncio.Event()
        self.browser_events = []
        self.trial_id = CURRENT['slot']['trial_id']

    async def _handle(self, reader, writer):
        status, body = 204, b''
        try:
            blob = await asyncio.wait_for(reader.readuntil(b'\r\n\r\n'), 10)
            lines = blob.decode('iso-8859-1').split('\r\n')
            method, target, _ = lines[0].split(' ', 2)
            headers = {k.lower().strip(): v.strip() for line in lines[1:] if ':' in line
                       for k, v in [line.split(':', 1)]}
            parsed = urlsplit(target)
            if method == 'GET' and parsed.path == '/control':
                tid = parse_qs(parsed.query).get('trialId', [None])[0]
                self.trace('CONTROL_REQUEST', trial_id=tid)
                if tid != self.trial_id:
                    status = 404
                else:
                    CURRENT['gate_state'] = 'waiting'
                    self.waiting.set()
                    await asyncio.wait_for(self.gate.wait(), 120)
                    status, body = 200, b'{}'
            elif method == 'POST':
                size = int(headers.get('content-length', '0'))
                assert 0 < size < 10000000
                payload = json.loads(await asyncio.wait_for(reader.readexactly(size), 10))
                ns = time.monotonic_ns()
                self.trace('HTTP_PAYLOAD', received_ns=ns, route=parsed.path, payload=payload)
                if parsed.path == '/api/v1/ack':
                    assert payload.get('trialId') == self.trial_id
                    await self.acks.put(ReceivedMessage(ns, payload))
                elif parsed.path == '/api/v1/recovery':
                    await self.recoveries.put(ReceivedMessage(ns, payload))
                elif parsed.path in ('/diagnostic/event', '/diagnostic/agent-event'):
                    # The page's own event stream, including TARGET_WRITE_STARTED and its
                    # browserRealtimeMs/browserWallClockIso stamps.
                    self.browser_events.append(dict(route=parsed.path, host_received_ns=ns,
                                                    payload=payload))
                else:
                    status = 404
            elif method != 'OPTIONS':
                status = 405
        except Exception as error:
            self.trace('HTTP_ERROR', error=repr(error))
            status = 400
        reason = {200: 'OK', 204: 'No Content', 400: 'Bad Request',
                  404: 'Not Found', 405: 'Method Not Allowed'}[status]
        writer.write((f'HTTP/1.1 {status} {reason}\r\nAccess-Control-Allow-Origin: *\r\n'
                      'Access-Control-Allow-Headers: content-type\r\n'
                      'Access-Control-Allow-Methods: GET, POST, OPTIONS\r\n'
                      'Cache-Control: no-store\r\n'
                      f'Content-Length: {len(body)}\r\nConnection: close\r\n\r\n').encode() + body)
        try:
            await writer.drain()
        except Exception as error:
            self.trace('HTTP_RESPONSE_ERROR', error=repr(error))
        writer.close()


async def arm_uprobe_stage(main_pid: int, td):
    """Attempt the prescribed uprobe set and record, per trial, what attached.

    bpftrace has no optional-attach syntax, so the nine symbols are first resolved
    against the running Chromium executable's own probe listing. Symbols that do
    not resolve are recorded, not silently dropped, and the stage never gates the
    trial: it is a capability record, identical in both conditions.
    """
    binary = await tracing.browser_executable(main_pid)
    listing = await ssh(uprobe_list_command(binary), timeout=120)
    resolution = uprobe_resolution(listing, binary)
    (td / 'uprobe-listing.txt').write_text(listing)
    status = dict(resolution)
    status['prescribed'] = list(UPROBES)
    status['armed'] = bool(resolution['resolvable'])
    status['listing_line_count'] = len([line for line in listing.splitlines() if line.strip()])
    if not status['armed']:
        status['reason'] = ('none of the nine prescribed symbols is resolvable in the guest'
                            ' Chromium executable (bpftrace resolves uprobe names from the'
                            ' executable symbol table)')
        (td / 'uprobe-program.bt').write_text(uprobe_program(
            (ROOT / 'trace_c1_uprobe.bt').read_text(), resolution))
        return status, None
    program = uprobe_program((ROOT / 'trace_c1_uprobe.bt').read_text(), resolution)
    (td / 'uprobe-program.bt').write_text(program)
    await scp_to_guest(td / 'uprobe-program.bt', UPROBE_REMOTE)
    status['reason'] = 'armed'
    capture_item = await capture(uprobe_command(UPROBE_REMOTE), td / 'uprobe.txt',
                                 td / 'uprobe.stderr.txt')
    return status, capture_item


async def arm_tracers():
    """Start the identical strace + eBPF + cachestat pipeline and verify it is alive."""
    slot, td = CURRENT['slot'], CURRENT['td']
    prof = profile(slot)
    main_pid = await tracing.browser_main_pid(prof)
    pids = descendant_pids(await ssh('ps -eo pid=,ppid='), main_pid)
    program = instantiate((ROOT / 'trace_b1.bt').read_text(), pids)
    (td / 'trace-program.bt').write_text(program)
    await scp_to_guest(td / 'trace-program.bt', PROGRAM_REMOTE)
    await scp_to_guest(ROOT / 'guest_observer.py', OBSERVER_REMOTE)
    CURRENT['trace_start_host_ns'] = time.monotonic_ns()
    CURRENT['pids'] = pids
    captures = {
        # strace writes its trace to stderr; the stdout file is kept empty but present.
        'strace': await capture(strace_command(pids), td / 'strace.stdout.txt', td / 'strace.stderr.txt'),
        'bpftrace': await capture(ebpf_command(PROGRAM_REMOTE), td / 'bpftrace.txt',
                                  td / 'bpftrace.stderr.txt'),
        'observer': await capture(observer_command(indexeddb_dir(slot), TRACE_TIMEOUT_S),
                                  td / 'cachestat.jsonl', td / 'cachestat.stderr.txt',
                                  parse_json=True),
    }
    uprobe_status, uprobe_capture = await arm_uprobe_stage(main_pid, td)
    CURRENT['uprobe_status'] = uprobe_status
    if uprobe_capture is not None:
        captures['uprobe'] = uprobe_capture
    CURRENT['captures'] = captures
    CURRENT['trace_text_paths'] = {'strace': td / 'strace.stderr.txt', 'bpftrace': td / 'bpftrace.txt',
                                   'uprobe': td / 'uprobe.txt'}
    await asyncio.sleep(2)
    gating = ('strace', 'bpftrace', 'observer')
    alive = {name: item[0].returncode is None for name, item in captures.items()}
    activation = {
        'browser_main_pid': main_pid, 'pids': pids, 'tracers_alive': alive,
        'strace_alive': alive['strace'], 'bpftrace_alive': alive['bpftrace'],
        'observer_alive': alive['observer'], 'checked_host_ns': time.monotonic_ns(),
        'strace_command': strace_command(pids), 'ebpf_command': ebpf_command(PROGRAM_REMOTE),
        'observer_command': observer_command(indexeddb_dir(slot), TRACE_TIMEOUT_S),
        'tracing_pipeline_sha256': tracing_pipeline_sha256(),
        'gating_channels': list(gating), 'uprobe_stage': {k: uprobe_status.get(k) for k in
                                                          ('armed', 'binary', 'listing_entries',
                                                           'resolvable', 'unresolved', 'reason')},
    }
    activation['passed'] = all(alive[name] for name in gating)
    CURRENT['activation'] = activation
    CURRENT['activation_passed'] = activation['passed']
    return activation


class TracedBrowser:
    """Holds the run page at /control until the tracing pipeline is verified alive."""

    def __init__(self, underlying, owner):
        self.underlying, self.owner = underlying, owner

    def __getattr__(self, name):
        return getattr(self.underlying, name)

    async def launch_trial(self, **kwargs):
        launch = await self.underlying.launch_trial(**kwargs)
        if dict(parse_qs(urlsplit(kwargs['url']).query)).get('action') != ['run']:
            return launch
        td = CURRENT['td']
        await asyncio.wait_for(self.owner.ack_server.waiting.wait(), 30)
        activation = await arm_tracers()
        save(td / 'trace-activation.json', activation)
        if not activation['passed']:
            raise RuntimeError('Tracing pipeline failed before target write: ' + repr(activation))
        released_ns = time.monotonic_ns()
        CURRENT['gate_release_host_ns'] = released_ns
        CURRENT['gate_state'] = 'released_after_tracer_activation'
        self.owner.ack_server.gate.set()
        save(td / 'prewrite-gate-release.json',
             {'host_ns': released_ns, 'gate_state': CURRENT['gate_state'],
              'method': 'HTTP control gate released only after strace/eBPF/cachestat activation'
                        ' was verified'})
        return launch


class Runner(ExperimentRunner):
    def __init__(self, c, trace):
        super().__init__(c)
        self.trace = trace
        self.guest = LoggedGuestClient('127.0.0.1', c.vm.guest_agent_forward_port, c.vm.vm_id, trace)
        self.browser = TracedBrowser(BrowserController(self.guest, c.paths.browser_profile_root_guest), self)
        self.ack_server = GateServer(c.experiment.ack_bind_host, c.experiment.ack_port, trace)

    def _new_qmp_client(self):
        q = QMPClient(host=self.config.vm.qmp_host, port=self.config.vm.qmp_port)
        q.trace = self.trace
        return q

    async def rpc(self, command):
        sent = time.monotonic_ns()
        value = await asyncio.to_thread(self.guest._request, 'POST', '/diagnostic', {'command': command})
        received = time.monotonic_ns()
        self.trace('RPC', command=command, sent_ns=sent, received_ns=received, response=value)
        return dict(sent_ns=sent, received_ns=received, response=value)

    async def close_verified(self):
        before = time.monotonic_ns()
        value = await asyncio.wait_for(asyncio.to_thread(self.guest._request, 'POST', '/close', {}), 30)
        assert value['exit_evidence']['pids_after'] == []
        self.trace('BROWSER_CLOSE_VERIFIED', host_call_ns=before, response=value)
        return dict(host_call_ns=before, host_exit_observed_ns=time.monotonic_ns(), **value)

    async def powerdown(self):
        pidpath = self.config.vm.qmp_socket.parent / f'{self.config.vm.vm_id}.pid'
        pid = self.adapter.verify_qemu_process(pidpath)
        shutdown_task = asyncio.create_task(self.qmp.wait_for_event('SHUTDOWN', 180))
        called = time.monotonic_ns()
        await self.qmp.execute('system_powerdown')
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            p = await asyncio.create_subprocess_exec(
                'ps', '-p', str(pid), '-o', 'state=',
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            out, _ = await p.communicate()
            if p.returncode or not out.strip() or out.strip().startswith(b'Z'):
                shutdown_ns, shutdown_event = await shutdown_task
                assert shutdown_event.get('data', {}).get('reason') == 'guest-shutdown'
                assert shutdown_event.get('data', {}).get('guest') is True, 'Unverified orderly guest shutdown'
                result = dict(pid=pid, powerdown_call_ns=called, shutdown_observed_ns=shutdown_ns,
                              shutdown_event=shutdown_event, exit_observed_ns=time.monotonic_ns())
                self.trace('QEMU_ORDERLY_EXIT', **result)
                pidpath.unlink(missing_ok=True)
                await self.qmp.close()
                self.qmp = None
                return result
            await asyncio.sleep(.25)
        raise TimeoutError('Orderly guest/QEMU shutdown did not complete')


async def provision(r, td, manifest):
    opts = ['-i', str(PROJECT / 'vm/research_vm_ed25519'), '-p', '2222',
            '-o', 'StrictHostKeyChecking=accept-new', '-o', 'ConnectTimeout=10', 'research@127.0.0.1']
    installer = ("import sys,pathlib,subprocess,json; data=json.load(sys.stdin); "
                 "pathlib.Path('/opt/browser-storage-research/readiness-identity.json').write_text(json.dumps(data['manifest'])); "
                 "pathlib.Path('/opt/browser-storage-research/paper2-readiness-agent.py').write_text(data['source']); "
                 "subprocess.run(['sudo','mkdir','-p','/etc/systemd/system/browser-storage-research-agent.service.d'],check=True); "
                 "subprocess.run(['sudo','tee','/etc/systemd/system/browser-storage-research-agent.service.d/diagnostic.conf'],"
                 "input=b'[Service]\\nExecStart=\\nExecStart=/usr/bin/xvfb-run -a /opt/browser-storage-research/.venv/bin/python "
                 "/opt/browser-storage-research/paper2-readiness-agent.py --host 0.0.0.0 --port 8788\\n',check=True); "
                 "subprocess.run(['sudo','systemctl','daemon-reload'],check=True); "
                 "subprocess.run(['sudo','systemctl','restart','browser-storage-research-agent.service'],check=True); "
                 "subprocess.run(['sync'],check=True)")
    process = await asyncio.create_subprocess_exec(
        'ssh', *opts, 'python3 -c ' + shlex.quote(installer),
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    stdout, stderr = await asyncio.wait_for(
        process.communicate(json.dumps(dict(source=(ROOT / 'guest_agent.py').read_text(),
                                            manifest=manifest)).encode()), 40)
    save(td / 'provision.json', dict(returncode=process.returncode, stdout=stdout.decode(),
                                     stderr=stderr.decode(), agent_sha256=sha(ROOT / 'guest_agent.py')))
    if process.returncode:
        raise RuntimeError('Diagnostic agent provisioning failed')
    info = await r.guest.wait_ready(30)
    assert info.agent_source_sha256 == sha(ROOT / 'guest_agent.py'), 'Diagnostic agent source mismatch'
    return info


def url(c, slot, tid, exp, action):
    fault = 'qemu-reset' if slot['action'] == 'reset' else 'none'
    u = targeted_url(c, requested_delay_ns=slot['requested_delay_ns'], action=action,
                     experiment_id=exp, trial_id=tid, mode=slot['mode'], fault_model=fault)
    p = urlsplit(u)
    q = dict(parse_qsl(p.query))
    q['connection'] = 'held' if slot['held'] and action == 'run' else 'closed'
    return urlunsplit(p._replace(query=urlencode(q)))


async def schedule_reset(r, ack_received_ns, delay_s, out):
    """ACK-anchored dispatch; the assigned delay is an earliest-dispatch deadline and
    preparation overrun is measured, never used to abort a trial. A raw guest uptime
    sample is taken immediately before the reset command is dispatched."""
    if delay_s < 0:
        raise ValueError('Negative delay')
    target = ack_received_ns + int(delay_s * 1_000_000_000)
    if delay_s > 0:
        from controller.timing import wait_after
        await wait_after(ack_received_ns, int(delay_s * 1_000_000_000))
    uptime = await r.rpc('uptime')
    out['guest_uptime_s_at_reset'] = uptime['response'].get('uptime_seconds')
    out['guest_monotonic_ns_at_reset'] = uptime['response'].get('guest_monotonic_ns')
    out['reset_uptime_sample_received_ns'] = uptime['received_ns']
    called = time.monotonic_ns()
    return dict(action_command_ns=called, ack_to_command_ns=called - ack_received_ns,
                requested_deadline_ns=target,
                deadline_overshoot_ns=max(0, called - target),
                zero_delay_policy=('ASAP after verified post-ACK close and identity checks'
                                   if delay_s == 0 else None))


async def initialize_sentinel(r, c, slot, td, trace):
    """Create and verify the same strict sentinel in a fresh backend profile, then
    record the on-disk backend identity before the relaxed target runs."""
    timing = {}
    for action in ('baseline-init', 'baseline-verify'):
        baseline_tid = f"{slot['trial_id']}-{action}"
        baseline_url = targeted_url(c, requested_delay_ns=0, action=action, experiment_id=EXPERIMENT,
                                    trial_id=baseline_tid, mode='strict', fault_model='none')
        launch = await r.browser.launch_trial(browser='chromium', trial_id=baseline_tid,
                                              profile_id=f"review-backend-{slot['backend']}-v1",
                                              url=baseline_url)
        assert launch.version == '153.0.8010.12' and launch.profile == profile(slot)
        expected_flag = '--enable-features=IdbSqliteBackingStore'
        args = launch.launch_settings['args']
        assert (expected_flag in args) == (slot['backend'] == 'sqlite'), args
        message = await r.ack_server.wait_for_recovery(baseline_tid, 120)
        timing[f'{action}_received_ns'] = message.received_ns
        timing[f'{action}_browser_monotonic_ms'] = message.payload.get('browserMonotonicMs')
        verification = verify_baseline_payload(message.payload, action)
        save(td / f'{action}-verification.json', verification)
        save(td / f'{action}-payload.json', message.payload)
        if not verification['passed']:
            raise RuntimeError(f'{action} failed: {verification}')
        close = await r.close_verified()
        save(td / f'{action}-browser-close.json', close)
        trace('BASELINE_ACTION_VERIFIED', action=action, profile=launch.profile, flags=args)
    sync = await ssh('sync', timeout=30)
    save(td / 'sentinel-sync.json', {'stdout': sync, 'scope': 'fresh trial overlay only'})
    root = indexeddb_dir(slot)
    inventory_script = ('import pathlib,json; p=pathlib.Path(' + repr(root) + '); '
                        'print(json.dumps([{"path":str(f.relative_to(p)),"header_hex":f.open("rb").read(16).hex()} '
                        'for f in p.rglob("*") if f.is_file()]))')
    inventory = json.loads(await ssh('python3 -c ' + shlex.quote(inventory_script), timeout=30))
    save(td / 'backend-inventory-before-target.json', inventory)
    leveldb_present = any('.indexeddb.leveldb/' in row['path'] for row in inventory)
    sqlite_signature = any(row['header_hex'].startswith(SQLITE_SIGNATURE) for row in inventory)
    observed = 'leveldb' if leveldb_present else ('sqlite' if sqlite_signature else 'unknown')
    matched = ((slot['backend'] == 'leveldb' and leveldb_present)
               or (slot['backend'] == 'sqlite' and not leveldb_present and sqlite_signature))
    check = dict(expected=slot['backend'], observed=observed, matched=matched,
                 leveldb_files=leveldb_present, sqlite_signature=sqlite_signature,
                 files=len(inventory), sqlite_signature_expected=SQLITE_SIGNATURE)
    save(td / 'on-disk-format-check.json', check)
    trace('ON_DISK_FORMAT_CHECK', **check)
    save(td / 'sentinel-timing.json', timing)
    return dict(check=check, timing=timing)


def initial_boot_integrity(action):
    if action in ('browser', 'live'):
        return {'status': 'N/A', 'details': {'reason': 'no guest reboot'}}
    return {'status': 'unknown', 'details': {'reason': 'readiness not yet established'}}


async def finalize_trace(td, out):
    """Stop the pipeline, rebuild the guest-relative event ledger, and record it.

    This runs even when the trial failed before the reset, so a partial ledger is
    always preserved. A missing/failed activation or a failed reduction marks the
    trial's tracing pipeline as failed; it never turns a trial into a loss.
    """
    captures = CURRENT.get('captures') or {}
    exit_codes = {}
    for name, item in captures.items():
        exit_codes[name] = await terminate_capture(item[0], item[1])
    if captures:
        save(td / 'trace-capture-exit.json', exit_codes)

    out['trace_start_host_ns'] = CURRENT.get('trace_start_host_ns')
    out['trace_end_host_ns'] = time.monotonic_ns()
    out['prewrite_gate_state'] = CURRENT.get('gate_state', 'not_reached')
    out['tracing_pipeline_sha256'] = tracing_pipeline_sha256()
    out['traced_process_tree'] = CURRENT.get('pids')
    out['trace_activation'] = CURRENT.get('activation')

    observer_state = (captures.get('observer') or (None, None, {}))[2]
    samples = observer_state.get('rows', []) or []
    out['cachestat_sample_count'] = len(samples)
    out['cachestat_parse_errors'] = observer_state.get('parse_errors')
    out['strace_received_lines'] = (captures.get('strace') or (None, None, {}))[2].get('count')
    out['bpftrace_received_lines'] = (captures.get('bpftrace') or (None, None, {}))[2].get('count')

    def read_text(path):
        path = Path(path) if path else None
        return path.read_text(errors='replace') if path is not None and path.is_file() else ''

    # The (ACK, reset] window is guest-clock based: both anchors are guest uptime
    # samples taken by the guest agent on the ACK and immediately before the reset.
    ack_uptime_s = out.get('guest_uptime_s_at_ack')
    reset_uptime_s = out.get('guest_uptime_s_at_reset')
    reset_rel_ack_s = (reset_uptime_s - ack_uptime_s
                       if isinstance(ack_uptime_s, (int, float))
                       and isinstance(reset_uptime_s, (int, float)) else None)

    reduction_ok = False
    try:
        paths = CURRENT.get('trace_text_paths') or {}
        strace_text = read_text(paths.get('strace'))
        bpftrace_text = read_text(paths.get('bpftrace'))
        uprobe_text = read_text(paths.get('uprobe'))
        reduction = reduce_trace(
            browser_events=CURRENT.get('browser_events') or [], samples=samples,
            gate_host_ns=CURRENT.get('gate_release_host_ns'),
            ack_monotonic_ns=CURRENT.get('ack_monotonic_ns'),
            ack_realtime_ms=CURRENT.get('ack_realtime_ms'),
            ack_uptime_s=CURRENT.get('ack_uptime_s'),
            command_ns=out.get('action_command_ns') or 0,
            strace_text=strace_text, bpftrace_text=bpftrace_text,
            uprobe_text=uprobe_text, uprobe_status=CURRENT.get('uprobe_status'),
            reset_rel_ack_s=reset_rel_ack_s)
        ledger = td / 'trace-ledger.jsonl'
        reduction['ledger_rows'] = write_ledger(ledger, reduction, strace_text, bpftrace_text)
        reduction['ledger_path'] = str(ledger)
        # Dedicated uprobe firing ledger (one row per firing; empty when the stage
        # could not attach on this build).
        uprobe_ledger = td / 'uprobe-ledger.jsonl'
        with uprobe_ledger.open('x') as stream:
            for row in reduction['uprobe_events']:
                stream.write(json.dumps({'source': 'uprobe', 'symbol': row['symbol'],
                                         'pid': row['pid'], 'tid': row['tid'],
                                         'comm': row['comm'],
                                         'guest_monotonic_ns': row['guest_monotonic_ns'],
                                         'guest_time_rel_ack_s': row['guest_time_rel_ack_s'],
                                         'host_timestamp_ns': None}, separators=(',', ':')) + '\n')
        out['uprobe_firing_ledger_path'] = str(uprobe_ledger)
        out['uprobe_firing_rows'] = len(reduction['uprobe_events'])
        out['uprobe_tids_seen'] = reduction['uprobe_tids_seen']
        out['uprobe_symbols_seen'] = reduction['uprobe_symbols_seen']
        out['uprobe_status'] = reduction['uprobe_status']
        out['connection_close_effect'] = reduction['connection_close_effect']
        out['reset_rel_ack_s_guest_uptime'] = reset_rel_ack_s
        reduction['trace_start_host_ns'] = out['trace_start_host_ns']
        reduction['trace_end_host_ns'] = out['trace_end_host_ns']
        reduction['prewrite_gate_state'] = out['prewrite_gate_state']
        reduction['capture_exit_codes'] = exit_codes
        save(td / 'trace-reduction.json', reduction)
        out['trace_ledger_path'] = str(ledger)
        out['cachestat_sample_count'] = reduction['sampling']['cachestat_samples']
        out['traced_fd_paths'] = reduction['traced_fd_paths']
        out['trace_summary'] = {
            'strace_events_total': reduction['strace_events_total'],
            'strace_unmatched_lines': reduction['strace_unmatched_lines'],
            'strace_unfinished_lines': reduction['strace_unfinished_lines'],
            'ebpf_events_total': reduction['ebpf_events_total'],
            'ebpf_unmatched_lines': reduction['ebpf_unmatched_lines'],
            'wal_paths': reduction['wal_paths'],
            'wal_descriptors': reduction['wal_descriptors'],
            'wal_sync_events': len(reduction['wal_sync_events']),
            'wal_dirty_to_clean_transitions': len(reduction['wal_dirty_to_clean_transitions']),
            'wal_dirty_to_clean_spacing_s': reduction['wal_dirty_to_clean_spacing_s'],
            'blockdev_flush_events': len(reduction['blockdev_flush_events']),
            'ebpf_events_on_wal_fd_not_in_strace': len(reduction['ebpf_events_on_wal_fd_not_in_strace']),
            'clean_before_reset': reduction['clean_before_reset'],
            'earliest_clean_rel_ack_s': reduction['earliest_clean_rel_ack_s'],
            'median_cachestat_interval_ms': reduction['sampling']['median_interval_ms'],
            'strace_file_events': len(reduction['strace_file_events']),
            'wal_file_events': len(reduction['wal_file_events']),
            'wal_lifecycle_events': len(reduction['wal_lifecycle_events']),
            'uprobe_events': len(reduction['uprobe_events']),
            'uprobe_armed': bool(reduction['uprobe_status'].get('armed')),
            'connection_close_effect_observed': reduction['connection_close_effect']['observed'],
        }
        reduction_ok = True
    except Exception as error:
        out['errors'].append('TRACE_REDUCTION: ' + repr(error))

    out['trace_pipeline_ok'] = bool(CURRENT.get('activation_passed')) and reduction_ok
    if not out['trace_pipeline_ok']:
        out['errors'].append('TRACE_PIPELINE_FAILED: activation_passed=%s reduction_ok=%s'
                             % (bool(CURRENT.get('activation_passed')), reduction_ok))


async def trial(c, slot):
    """One frozen traced reset trial on a fresh overlay. Never replaced."""
    assert slot in SLOTS and slot['action'] == 'reset' and not slot['probe']
    assert slot['held'] == (slot['condition'] == TEST), 'held must follow the condition'
    assert slot['traced'] is True
    tid = slot['trial_id']
    exp = EXPERIMENT
    td = ROOT / 'raw' / exp / tid
    td.mkdir(parents=True, exist_ok=False)
    overlay = ROOT / 'overlays' / exp / f'{tid}.qcow2'
    overlay.parent.mkdir(parents=True, exist_ok=True)
    CURRENT.clear()
    CURRENT.update(slot=slot, td=td, gate_state='not_reached', activation_passed=False)
    # `slot` already carries `traced` and `delay_s`, so they are picked up through
    # `**slot` rather than passed as conflicting keywords.
    out = dict(experiment_id=exp, dataset_role='paper3v2_mechanism_c1',
               **slot, classification='HARNESS_ERROR', resolved=False,
               primary_endpoint_eligible=False, technical_valid=False, timing_valid=False,
               trace_pipeline_ok=False, errors=[], boot_integrity=initial_boot_integrity('reset'),
               started_ns=time.monotonic_ns())

    def trace(kind, **kw):
        append(td / 'events.jsonl', dict(kind=kind, host_ns=time.monotonic_ns(),
                                         wall=datetime.datetime.now(datetime.timezone.utc).isoformat(), **kw))

    CURRENT['trace'] = trace
    save(td / 'trial.json', out)
    (td / 'config.yaml').write_bytes((ROOT / 'config.yaml').read_bytes())
    save(td / 'overlay.json', create_fresh_overlay(c.vm.disk_image, overlay))
    r = Runner(dynamic_config(c, overlay), trace)
    CURRENT['browser_events'] = r.ack_server.browser_events
    manifest = dict(experiment_id=exp, trial_id=tid, overlay_path=str(overlay),
                    profile=profile(slot), origin='http://127.0.0.1:5173', nonce=IDENTITY['nonce'])
    expected = dict(guest_id=c.vm.vm_id, agent_source_sha256=sha(ROOT / 'guest_agent.py'),
                    readiness_identity=manifest)
    save(td / 'expected-identity.json', expected)
    logger = EventLogger(td / 'controller-events.jsonl', experiment_id=exp, trial_id=tid,
                         browser='chromium', mode=slot['mode'], workload='target-transaction',
                         requested_delay_ns=slot['requested_delay_ns'], fault_model='qemu-reset')
    console = c.vm.qmp_socket.parent / f'{c.vm.vm_id}.log'
    offset = console.stat().st_size if console.exists() else 0
    stage = 'PREPARE'
    recovery_readiness_failed = False
    try:
        async with r:
            r.qmp = await r._ensure_vm(logger)
            info = await r.guest.wait_ready(180)
            assert info.agent_source_sha256 == sha(PROJECT / 'controller/guest_agent.py'), 'Initial baseline agent changed'
            info = await provision(r, td, manifest)
            before_health = await r.guest.health_payload()
            verify_health(before_health, expected)
            save(td / 'health-before.json', before_health)
            await apply_boot_source_fix(td)
            boot_uptime = await r.rpc('uptime')
            out['guest_uptime_s_at_boot_complete'] = boot_uptime['response'].get('uptime_seconds')
            out['guest_monotonic_ns_at_boot_complete'] = boot_uptime['response'].get('guest_monotonic_ns')
            trace('BOOT_COMPLETE', guest_uptime_s=out['guest_uptime_s_at_boot_complete'],
                  uptime_received_ns=boot_uptime['received_ns'])
            stage = 'SENTINEL_SETUP'
            sentinel = await initialize_sentinel(r, c, slot, td, trace)
            out['on_disk_format'] = sentinel['check']
            out['sentinel_timing'] = sentinel['timing']
            out['sentinel_baseline_init_received_ns'] = sentinel['timing'].get('baseline-init_received_ns')
            out['sentinel_baseline_verify_received_ns'] = sentinel['timing'].get('baseline-verify_received_ns')
            if not sentinel['check']['matched']:
                out['errors'].append('On-disk format mismatch: ' + json.dumps(sentinel['check']))
            stage = 'TARGET_LAUNCH'
            # The gate holds the run page here; TracedBrowser attaches the pipeline and
            # only then releases it, so the target write happens under tracing.
            launch = await r.browser.launch_trial(browser='chromium', trial_id=tid,
                                                  profile_id=f"review-backend-{slot['backend']}-v1",
                                                  url=url(c, slot, tid, exp, 'run'))
            assert launch.version == '153.0.8010.12' and launch.profile == profile(slot)
            target_flag = '--enable-features=IdbSqliteBackingStore'
            target_args = launch.launch_settings['args']
            out['launch_flag_observed'] = target_flag in target_args
            out['launch_flag_matched'] = (target_flag in target_args) == (slot['backend'] == 'sqlite')
            assert out['launch_flag_matched'], target_args
            meta = collect_trial_metadata(r.config, r.adapter, info, browser='chromium',
                                          browser_version=launch.version, workload='target-transaction',
                                          durability_mode=slot['mode'],
                                          requested_delay_ns=slot['requested_delay_ns'],
                                          fault_model='qemu-reset',
                                          browser_launch_settings=launch.launch_settings)
            meta.update(dataset_role='paper3v2_mechanism_c1',
                        protocol='targeted-single-transaction-v1', role=slot['role'],
                        traced=True, delay_s=slot['delay_s'], condition=slot['condition'],
                        connection_lifecycle=('closed_after_ack' if slot['condition'] == CONTROL
                                              else 'held_open_after_ack'))
            save(td / 'metadata.json', meta)
            stage = 'ACK'
            ack = await r.ack_server.wait_for_ack(tid, 1, 120)
            save(td / 'ack.json', ack.payload)
            ack_received_ns = ack.received_ns
            ack_realtime_ms, ack_events = ack_realtime_and_events(ack.payload)
            uptime_rpc = await r.rpc('uptime')
            save(td / 'uptime-at-ack.json', uptime_rpc)
            CURRENT['ack_monotonic_ns'] = uptime_rpc['response'].get('guest_monotonic_ns')
            CURRENT['ack_realtime_ms'] = ack_realtime_ms
            CURRENT['ack_uptime_s'] = uptime_rpc['response'].get('uptime_seconds')
            CURRENT['ack_host_ns'] = ack_received_ns
            out['guest_uptime_s_at_ack'] = uptime_rpc['response'].get('uptime_seconds')
            out['guest_monotonic_ns_at_ack'] = uptime_rpc['response'].get('guest_monotonic_ns')
            out['ack_anchor_guest_realtime_ms'] = ack_realtime_ms
            out['ack_anchor_guest_monotonic_ns'] = CURRENT['ack_monotonic_ns']
            out['uptime_sample_lag_ns'] = uptime_rpc['received_ns'] - ack_received_ns
            write_start = next((e for e in ack_events if e.get('kind') == 'TARGET_WRITE_STARTED'), None)
            out['target_write_start_browser_monotonic_ms'] = (write_start or {}).get('browserMonotonicMs')
            out['target_write_start_observed'] = write_start is not None
            out['browser_event_count_at_ack'] = len(ack_events)
            out['target_ack_browser_monotonic_ms'] = ack.payload.get('browserMonotonicMs')
            out['target_indexeddb_complete_monotonic_ms'] = ack.payload.get('indexedDbCompleteMonotonicMs')
            write_start_host_ns = next((e['host_received_ns'] for e in r.ack_server.browser_events
                                        if e['payload'].get('kind') == 'TARGET_WRITE_STARTED'), None)
            out['target_write_start_host_ns'] = write_start_host_ns
            sentinel_init_ns = out.get('sentinel_baseline_init_received_ns')
            sentinel_verify_ns = out.get('sentinel_baseline_verify_received_ns')
            if sentinel_init_ns and write_start_host_ns:
                out['sentinel_to_target_write_start_ms'] = (write_start_host_ns - sentinel_init_ns) / 1e6
            if sentinel_verify_ns and write_start_host_ns:
                out['sentinel_verify_to_target_write_start_ms'] = (write_start_host_ns - sentinel_verify_ns) / 1e6
            if sentinel_init_ns:
                out['sentinel_to_target_ack_ms'] = (ack_received_ns - sentinel_init_ns) / 1e6
            ws_ms = out.get('target_write_start_browser_monotonic_ms')
            ack_ms = out.get('target_ack_browser_monotonic_ms')
            if isinstance(ws_ms, (int, float)) and isinstance(ack_ms, (int, float)):
                out['target_write_start_to_ack_page_ms'] = ack_ms - ws_ms
            from paper2.oracle import verify_targeted_ack
            av = verify_targeted_ack(experiment_id=exp, trial_id=tid, mode=slot['mode'], payload_bytes=256,
                                     payload=ack.payload, fault_model='qemu-reset',
                                     requested_delay_ns=slot['requested_delay_ns'])
            save(td / 'ack-verification.json', av)
            assert av['valid'], av
            out['ack_received_ns'] = ack_received_ns
            out['ack_validation_finished_ns'] = time.monotonic_ns()
            ready_rpc = await r.rpc('ready')
            base = ready_rpc['response']
            out['close_verified_ns'] = ready_rpc['received_ns']
            page_kinds = [e.get('kind') for e in base['after']['events']]
            out['connection_hold_mechanism'] = HOLD_MECHANISM[slot['condition']]
            out['page_event_kinds_at_ready'] = page_kinds
            out['connection_held_at_ready_before'] = base['before'].get('connectionHeld')
            out['connection_held_at_ready_after'] = base['after'].get('connectionHeld')
            out['connection_close_call_observed'] = 'ORIGINAL_CONNECTION_CLOSE_CALL' in page_kinds
            out['connection_retained_event_observed'] = 'ORIGINAL_CONNECTION_RETAINED' in page_kinds
            assert any(kind == 'WORKLOAD_RETURNED' for kind in page_kinds), 'Workload completion not observed'
            if slot['condition'] == TEST:
                # C1-test: the workload must retain the original IDBDatabase and never
                # call close(), so no DatabaseConnection can be released after the ACK.
                assert base['before'].get('connectionHeld') is True, 'Connection not held at ready'
                assert base['after'].get('connectionHeld') is True, 'Connection was not held after the ACK'
                assert 'ORIGINAL_CONNECTION_RETAINED' in page_kinds, 'Hold not signalled by the page'
                assert 'ORIGINAL_CONNECTION_CLOSE_CALL' not in page_kinds, 'Close was called despite hold'
            else:
                # C1-control: identical to the paper3v2_mechanism_b1 close boundary.
                assert (base['before'].get('connectionHeld') is False
                        and base['after'].get('connectionHeld') is False), 'Verified close boundary failed'
                assert 'ORIGINAL_CONNECTION_CLOSE_CALL' in page_kinds, 'Close call not observed'
            save(td / 'identity-before.json', base)
            initial = (await r.rpc('identity'))['response']
            save(td / 'guest-before.json', initial)
            assert initial['boot_id'] == before_health['boot_id']
            assert initial['agent_session'] == before_health['agent_session']
            assert initial['readiness_identity'] == manifest
            out['pre_boot_id'] = initial['boot_id']
            block = await r.qmp.execute('query-block')
            save(td / 'qmp-block-before.json', block)
            assert any(str(overlay) == b.get('inserted', {}).get('file') for b in block), 'Attached overlay mismatch'
            r._verify_reset_target()
            stage = 'ACTION'
            out.update(await schedule_reset(r, ack_received_ns, slot['delay_s'], out))
            called = out['action_command_ns']
            event_task = asyncio.create_task(r.qmp.wait_for_event('RESET', 30))
            write, response = await instrumented_reset(r.qmp)
            reset, event = await event_task
            out.update(qmp_write_ns=write, qmp_response_ns=response, action_observed_ns=reset,
                       ack_to_command_ns=called - ack_received_ns,
                       command_to_reset_event_ns=reset - called,
                       ack_to_reset_event_ns=reset - ack_received_ns,
                       reset_deadline_overshoot_ns=reset - out['requested_deadline_ns'],
                       reset_event=event)
            trace('RESET_OBSERVED', command='system_reset', ack_received_ns=ack_received_ns,
                  action_command_ns=called, qmp_write_ns=write, reset_observed_ns=reset)
            if event.get('data', {}).get('reason') != 'host-qmp-system-reset':
                raise RuntimeError('Unexpected reset reason')
            if not ack_received_ns <= called <= write <= reset:
                raise RuntimeError('Invalid reset timing order')
            out['timing_valid'] = write >= out['requested_deadline_ns']
            stage = 'RECOVERY_READINESS'
            try:
                normal = await normal_recovery(r, td, before_health, expected, manifest, trace, reset)
                readiness = normal['readiness']
            except TimeoutError:
                recovery_readiness_failed = True
                raise
            out['readiness'] = readiness
            out['boot_integrity'] = normal['boot_integrity']
            out['post_boot_id'] = readiness['post_boot_id']
            out['boot_id_changed'] = readiness['post_boot_id'] != initial['boot_id']
            stage = 'RECOVERY_ORACLE'
            after_guest = (await r.rpc('identity'))['response']
            save(td / 'guest-after-action.json', after_guest)
            crosscheck_identity(after_guest, readiness, manifest)
            if after_guest['boot_id'] == initial['boot_id']:
                raise RuntimeError('Boot ID unchanged')
            confirmation = await r.guest.health_payload()
            verify_health(confirmation, expected)
            save(td / 'health-confirmation.json', confirmation)
            block = await r.qmp.execute('query-block')
            save(td / 'qmp-block-after.json', block)
            assert any(str(overlay) == b.get('inserted', {}).get('file') for b in block), 'Recovery overlay mismatch'
            relaunch = await r.browser.launch_trial(browser='chromium', trial_id=tid,
                                                    profile_id=f"review-backend-{slot['backend']}-v1",
                                                    url=url(c, slot, tid, exp, 'recover'))
            assert relaunch.version == '153.0.8010.12' and relaunch.profile == profile(slot)
            page_ready = await r.rpc('page-ready')
            save(td / 'recovery-page-ready.json', page_ready)
            post = await asyncio.wait_for(r.rpc('read'), 120)
            save(td / 'post-response.json', post)
            endpoint = classify(post['response']['value'], exp, tid, slot['mode'])
            out.update(endpoint)
            save(td / 'post-verification.json', endpoint)
            if endpoint['classification'] not in GOOD:
                out['errors'].append('Endpoint ' + endpoint['classification'])
            stage = 'CLEANUP'
            save(td / 'terminal-browser-close.json', await r.close_verified())
            save(td / 'terminal-guest-shutdown.json', await r.powerdown())
    except Exception as error:
        out['errors'].append(f'{stage}: {type(error).__name__}: {error}')
        if recovery_readiness_failed:
            out.update(classification='RECOVERY_ERROR')
        elif stage != 'CLEANUP':
            out.update(classification='HARNESS_ERROR')
        trace('TRIAL_ERROR', stage=stage, error=repr(error))
    finally:
        pidpath = c.vm.qmp_socket.parent / f'{c.vm.vm_id}.pid'
        try:
            pid = r.adapter.verify_qemu_process(pidpath)
        except RuntimeError:
            pid = None
        if pid:
            try:
                q = r._new_qmp_client()
                await q.connect()
                await q.verify_identity(c.vm.vm_id)
                r.adapter.verify_qemu_process(pidpath)
                trace('EMERGENCY_CLEANUP_QUIT', pid=pid, reason='trial or cleanup failure; not clean control')
                await q.execute('quit')
                await q.close()
            except Exception as error:
                out['errors'].append('Emergency cleanup failed: ' + repr(error))
        if console.exists():
            with console.open('rb') as f:
                f.seek(offset)
                (td / 'qemu-console.log').write_bytes(f.read())
        # Trace finalization happens before the validity flags so a pipeline failure
        # is recorded as a technical error rather than silently dropped.
        await finalize_trace(td, out)
        # ---- C1 connection-lifecycle invariant ----
        # An armed uprobe firing is the only direct evidence of a
        # `DatabaseConnection::Release`; when the guest build exposes no symbols it
        # is recorded as unknown and the symbol-free close/checkpoint fingerprint is
        # recorded separately (never conflated).
        effect = out.get('connection_close_effect') or {}
        armed = bool((out.get('uprobe_status') or {}).get('armed'))
        release_tids = [row for row in (out.get('uprobe_status') or {}).get('resolvable', [])
                        if row == 'DatabaseConnection::Release']
        if armed and 'DatabaseConnection::Release' in (out.get('uprobe_symbols_seen') or []):
            in_window = [row for row in (CURRENT.get('uprobe_events') or [])
                         if row['symbol'] == 'DatabaseConnection::Release'
                         and row['guest_time_rel_ack_s'] is not None
                         and 0 <= row['guest_time_rel_ack_s'] <= (out.get('reset_rel_ack_s_guest_uptime') or 0)]
            out['release_fired_before_reset'] = bool(in_window)
            out['release_fired_before_reset_source'] = 'uprobe_DatabaseConnection_Release'
        elif armed:
            out['release_fired_before_reset'] = False
            out['release_fired_before_reset_source'] = ('uprobe_armed_but_DatabaseConnection_Release_not_resolvable'
                                                        if not release_tids else 'uprobe_no_firing')
        else:
            out['release_fired_before_reset'] = None
            out['release_fired_before_reset_source'] = 'uprobe_stage_unavailable_on_this_build'
        out['connection_close_effect_before_reset'] = bool(effect.get('observed'))
        if slot['condition'] == TEST and effect.get('observed'):
            out['errors'].append(
                'CONNECTION_CLOSE_EFFECT_IN_TEST_WINDOW: a WAL-descriptor sync, WAL file'
                ' event, WAL lifecycle transition or WAL dirty->clean transition was'
                ' observed inside the (ACK, reset] window despite the held connection: '
                + json.dumps({'wal_fd_syncs_in_window': len(effect.get('wal_fd_syncs_in_window') or []),
                              'wal_file_events_in_window': len(effect.get('wal_file_events_in_window') or []),
                              'wal_lifecycle_events_in_window': len(effect.get('wal_lifecycle_events_in_window') or []),
                              'wal_dirty_to_clean_in_window': len(effect.get('wal_dirty_to_clean_in_window') or [])}))
        out['finished_ns'] = time.monotonic_ns()
        out['wall_seconds'] = (out['finished_ns'] - out['started_ns']) / 1e9
        out['resolved'] = out['classification'] in RESOLVED
        out['on_disk_format_matched'] = bool(out.get('on_disk_format', {}).get('matched'))
        out['technical_valid'] = bool(not out['errors']
                                      and out['trace_pipeline_ok']
                                      and out['on_disk_format_matched']
                                      and out.get('boot_id_changed') is True
                                      and out.get('timing_valid') is True)
        out['primary_endpoint_eligible'] = bool(out['technical_valid'] and out['classification'] in GOOD)
        out['target_survived'] = out['classification'] == 'SENTINEL_SURVIVED_TARGET_SURVIVED'
        out['sentinel_survived'] = out['classification'] in GOOD
        # ---- canonical B1 fields (raw values; no cross-clock alignment) ----
        def _ms(ns):
            return None if ns is None else ns / 1e6

        cls = out['classification']
        out['role'] = slot['role']
        out['condition'] = slot['condition']
        out['assigned_condition'] = slot['condition']
        out['held'] = bool(slot['held'])
        out['durability'] = slot['mode']
        out['assigned_delay_s'] = slot['delay_s']
        out.setdefault('on_disk_observed', (out.get('on_disk_format') or {}).get('observed'))
        out.setdefault('launch_flag_matched', None)
        out['sentinel_result'] = ('SURVIVED' if cls in ('SENTINEL_SURVIVED_TARGET_SURVIVED',
                                                       'SENTINEL_SURVIVED_TARGET_LOST')
                                  else 'LOST' if cls == 'SENTINEL_LOST' else None)
        out['target_result'] = ('SURVIVED' if cls == 'SENTINEL_SURVIVED_TARGET_SURVIVED'
                                else 'LOST' if cls == 'SENTINEL_SURVIVED_TARGET_LOST' else None)
        out['ack_to_qmp_command_ms'] = _ms(out.get('ack_to_command_ns'))
        out['ack_to_reset_event_ms'] = _ms(out.get('ack_to_reset_event_ns'))
        init_ns = out.get('sentinel_baseline_init_received_ns')
        verify_ns = out.get('sentinel_baseline_verify_received_ns')
        out['baseline_init_to_baseline_verify_ms'] = (_ms(verify_ns - init_ns)
                                                      if init_ns is not None and verify_ns is not None else None)
        out['baseline_verify_to_target_write_start_ms'] = out.get('sentinel_verify_to_target_write_start_ms')
        out['baseline_init_to_target_write_start_ms'] = out.get('sentinel_to_target_write_start_ms')
        out['ack_to_qmp_command_dispatch_overshoot_ms'] = _ms(out.get('deadline_overshoot_ns'))
        out['technical_errors'] = list(out['errors'])
        # Disk bounding: every raw artifact is retained, but a slot's overlay is dropped
        # once the trial is classified. This cannot change trial semantics. A prune
        # failure is recorded without retroactively invalidating an otherwise valid trial.
        if out['resolved']:
            try:
                overlay.unlink(missing_ok=True)
                out['overlay_retained'] = False
            except OSError as prune_error:
                out['overlay_retained'] = True
                out['overlay_prune_error'] = repr(prune_error)
        else:
            out['overlay_retained'] = True
        save(td / 'result.json', out)
    return out


if __name__ == '__main__':
    raise SystemExit('Experiment C1 is driven in bounded chunks: '
                     '.venv/bin/python -m paper2.paper3v2_mechanism_c1.resume --max-seconds N')
