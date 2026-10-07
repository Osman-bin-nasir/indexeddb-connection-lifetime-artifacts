"""Once-only excluded mapped block-state cells. No source build or physical-power fault."""
from backend_runtime import RUN_ROLE, ENGINE, ATTEMPT_RELATIVE, attempt_root, validate_reserved, validate_assignment, deploy_worker
import datetime, hashlib, json, shlex, shutil, subprocess, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[5]
HERE = Path(__file__).parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ENGINE / 'extensions/environment'))
import qualification_environment as host
sys.path.insert(0, str(ENGINE / 'repairs/009'))
import qualification_fault_scope as original
sys.path.insert(0, str(HERE))
from provision_vm import gate, disk_check, sha, save
from identity_io import write_identity, read_identity
from projection_data import extract
from forensic_formats import inspect
from block_trace_v2 import BlockTrace
from capture_multi import capture
from block_windows import windows
BASE = ROOT / 'repairs/003/mount-pinned-base.qcow2'
ATTEMPTS = attempt_root()
assignments = host.assignments
verify_frozen_base = host.verify_frozen_base

def mapper_command(vm, out, phase, config, events):
    before = time.monotonic_ns()
    r = host.remote(vm.port, 'sudo python3 -c ' + shlex.quote((HERE / 'guest_mapper_candidate.py').read_text()), input=json.dumps({'role': RUN_ROLE, **config}).encode(), timeout=90, check=False)
    after = time.monotonic_ns()
    (out / (phase + '.stdout')).write_bytes(r.stdout)
    (out / (phase + '.stderr')).write_bytes(r.stderr)
    save(out / (phase + '.response.json'), {'returncode': r.returncode, 'host_send_ns': before, 'host_receive_ns': after, 'configuration': config})
    if r.returncode:
        raise RuntimeError('Mapped command failed ' + phase)
    rows = [json.loads(l) for l in r.stdout.splitlines()]
    events('MAPPER_ACTION', phase=phase, host_send_ns=before, host_receive_ns=after, records=rows)
    return rows

def mount_data(vm, out, phase, recovery=False):
    command = 'sudo mount -t ext4 ' + ('/dev/vdc' if recovery else '/dev/mapper/idbv2-browser') + ' /var/lib/idbv2'
    r = host.remote(vm.port, command + ' && sudo chown research:research /var/lib/idbv2 && findmnt -J /var/lib/idbv2')
    (out / (phase + '.stdout')).write_bytes(r.stdout)
    (out / (phase + '.stderr')).write_bytes(r.stderr)
    value = json.loads(r.stdout)
    entry = value['filesystems'][0]
    if entry['fstype'] != 'ext4' or 'commit=' in entry['options'] or 'discard' in entry['options']:
        raise RuntimeError('Mapped volume is not ext4 default mount')
    save(out / (phase + '.json'), {'mount': value, 'recovery_derivative': recovery, 'no_sysctl_changes': True})
    return value

def run_one(a):
    gate()
    lock = verify_frozen_base()
    disk_check(3 * 1024 ** 3)
    if a['role'] != RUN_ROLE:
        raise RuntimeError('Scientific acquisition refused')
    out = ATTEMPTS / a['trial_id']
    validate_reserved(out, assignment if 'assignment' in locals() else a)
    start = time.monotonic_ns()
    free = shutil.disk_usage(ROOT).free
    spec = host.contract(a)
    validate_assignment(out, assignment if 'assignment' in locals() else a)
    save(out / 'payload_contract.json', spec)
    save(out / 'ENGINE_START.json', {'role': RUN_ROLE, 'scientific_denominator': RUN_ROLE == 'scientific', 'started_ns': start, 'base_lock': lock, 'candidate_repair_source_hashes': {p.name: sha(p) for p in HERE.glob('*.py')}, 'disk_free_before': free})
    events = host.Events(out / 'events.jsonl')
    vm = worker = trace = None
    passed = False
    endpoint = 'unknown'
    reasons = []
    old_args = host.vm_args
    active_data = active_log = None
    try:
        if a['experiment'] != 'block_state_recovery' or a['fault'] != 'block_capture' or a['mapper'] not in ['linear_control', 'dm_flakey_drop_writes'] or (a['filesystem'] != 'ext4_commit5_data_volume') or (a['instrumentation'] != 'ordinary') or (a['workload'] != 'single_256_bytes'):
            raise RuntimeError('Unsupported exact registered mapped cell')
        disk = out / 'root.qcow2'
        data = out / 'data.qcow2'
        log = out / 'log.qcow2'
        active_data = data
        active_log = log
        subprocess.run(['qemu-img', 'create', '-f', 'qcow2', '-F', 'qcow2', '-b', str(BASE), str(disk)], capture_output=True, check=True)
        for p in [data, log]:
            subprocess.run(['qemu-img', 'create', '-f', 'qcow2', str(p), '1G'], capture_output=True, check=True)
        save(out / 'INITIAL_VOLUME_HASHES.json', {'data_sha256': sha(data), 'log_sha256': sha(log), 'size_bytes': 1024 ** 3})

        def args(*v, **kw):
            result = old_args(*v, **kw)
            memory = kw.get('memory', v[4] if len(v) > 4 else 6144)
            if memory == 6144:
                for name, p, slot in [('data', active_data, 2), ('log', active_log, 4)]:
                    if p is not None:
                        result += ['-device', f'pcie-root-port,id={name}-port,slot={slot},chassis={slot}', '-drive', f'file={p},if=none,id={name}-drive,format=qcow2,cache=none', '-device', f'virtio-blk-pci,drive={name}-drive,serial=idbv2-{name},bus={name}-port']
            return result
        host.vm_args = args
        host.DATA = None
        vm = host.VM(disk, out / 'boot', 2233, 'block-qual-' + str(time.monotonic_ns()), events)
        trace = BlockTrace(host, vm, out, events)
        mapper_command(vm, out, 'mapper-create', {'command': 'create', 'mapper': a['mapper']}, events)
        r = host.remote(vm.port, 'sudo mkfs.ext4 -F /dev/mapper/idbv2-browser', timeout=120, check=False)
        (out / 'mkfs.stdout').write_bytes(r.stdout)
        (out / 'mkfs.stderr').write_bytes(r.stderr)
        save(out / 'MKFS_RESPONSE.json', {'returncode': r.returncode, 'argv': ['mkfs.ext4', '-F', '/dev/mapper/idbv2-browser'], 'defaults': True})
        if r.returncode:
            raise RuntimeError('Matched ext4 format failed')
        mount_data(vm, out, 'data-mount')
        profile = '/var/lib/idbv2/' + a['trial_id'] + '/profile'
        host.remote(vm.port, 'mkdir -p ' + shlex.quote(profile))
        identity = {'trial_id': a['trial_id'], 'profile': profile, 'base_sha256': lock['derived_base_sha256'], 'overlay': str(disk), 'data_overlay': str(data), 'mapper': a['mapper'], 'role': RUN_ROLE}
        write_identity(host.remote, vm.port, identity, out)
        events('ATTEMPT_IDENTITY', identity=identity, query_block=vm.qmp.execute('query-block'))
        r = host.remote(vm.port, 'findmnt -J /; cat /proc/sys/vm/dirty_writeback_centisecs /proc/sys/vm/dirty_expire_centisecs /proc/sys/vm/dirty_ratio /proc/sys/vm/dirty_background_ratio; uname -a')
        (out / 'guest-filesystem-sysctls.txt').write_bytes(r.stdout)
        source = host.remote(vm.port, 'sha256sum /opt/idbv2/worker/guest_worker.py').stdout.decode().split()[0]
        if source != lock['worker_files']['guest_worker.py']:
            raise RuntimeError('Pinned worker changed')
        worker = original.Worker(vm, spec, out, events)
        prep = worker.command('prepare')
        save(out / 'PREPARE.json', prep)
        samples = [worker.command('clock') for _ in range(9)]
        worker.command('write')
        ack = worker.page_event('ACK')
        if ack['guest']['event']['durability_observed'] != 'relaxed':
            raise RuntimeError('Wrong durability hint')
        deadline = ack['receipt_ns'] + a['fault_after_ack_ms'] * 1000000
        events('SCHEDULED_FAULT', deadline_ns=deadline, ack=ack, clock_samples=samples)
        if a['mapper'] == 'dm_flakey_drop_writes':
            rows = mapper_command(vm, out, 'mapper-drop-after-ack', {'command': 'transition'}, events)
            tr = next((x for x in rows if x['kind'] == 'FLAKEY_TRANSITION'))
            save(out / 'FLAKEY_INTERVAL_START.json', {'transition': tr, 'ack_receipt_ns': ack['receipt_ns'], 'host_bracket': json.loads((out / 'mapper-drop-after-ack.response.json').read_text()), 'neutral_transition_independently_validated': 'support-neutral-block-mapper-dm_flakey_drop_writes-20261004-00002', 'no_extra_target_probe_or_fsync': True})
        if a['close_ms'] is not None:
            worker.page_event('CLOSE_RETURNED')
        host.wait_deadline(deadline)
        fault = vm.qmp.execute('stop')
        over = (fault['dispatch_ns'] - deadline) / 1000000.0
        events('FAULT_DISPATCH', fault=fault, deadline_ns=deadline, overshoot_ms=over, classification='block_capture_quiesce')
        if not 0 <= over <= 25:
            reasons.append('dispatch_timing_ineligible')
        status = vm.qmp.execute('query-status')
        if status['return']['status'] != 'paused':
            raise RuntimeError('Assigned block boundary not paused')
        if a['held']:
            prior = [x for x in worker.items if x['guest'].get('kind') == 'CONNECTION_TELEMETRY' and x['receipt_ns'] <= fault['dispatch_ns']]
            held = prior[-1] if prior else None
            events('HELD_EVIDENCE', last_telemetry=held)
            if not held or held['guest']['state']['original_closed'] or (not held['guest']['state']['original_present']):
                reasons.append('held_connection_not_confirmed')
        old_boot = vm.boot
        old_pid = vm.proc.pid
        captured_views = capture(vm, {'root': disk, 'data': data, 'log': log}, out, events)
        vm.qmp.execute('cont')
        trace.close(reset=False)
        trace = None
        trace_raw = (out / 'block-trace.raw').read_text()
        boundary = json.loads((out / 'BLOCK_TRACE_BOUNDARY.json').read_text())
        if not trace_raw.rstrip().endswith('END') or boundary['diagnostics'] or boundary['returncode'] != 0:
            raise RuntimeError('Block trace drain/loss/completeness gate failed')
        fault_record = next((x for x in events.values if x['kind'] == 'FAULT_DISPATCH'))
        save(out / 'BLOCK_EVENT_WINDOWS.json', windows(trace_raw, samples, fault_record))
        events('DIAGNOSTIC_CONTINUATION', purpose='observer buffer drain only', captured_images_unchanged=all((sha(Path(x['source'])) == x['sha256'] for x in captured_views['views'].values())), oracle_on_original_guest=False)
        vm.qmp.execute('stop')
        vm.quit()
        worker.close()
        worker = vm = None
        captured = captured_views['snapshot_return_host_ns']
        for p in [disk, data, log]:
            p.chmod(292)
        hashes = {p.name: sha(p) for p in [disk, data, log]}
        save(out / 'IMMUTABLE_VIEW.json', {'captured_ns': captured, 'sha256': hashes, 'old_boot_id': old_boot, 'old_qemu_pid': old_pid, 'guest_volatile_state_discarded': True, 'pause': fault, 'pause_reply': status, 'fault_to_capture_ms': (captured - fault['dispatch_ns']) / 1000000.0, 'capture_after_guest_boot_activity': False, 'instantaneous_crash_state': False, 'oracle_started': False, 'boundary_uncertainty_disclosed': True})
        projection = extract(host, data, profile, out / 'forensic_projection', events, original_expected_sha256=hashes[data.name])
        save(out / 'FORENSIC_VIEW_PROVENANCE.json', projection)
        inventory = json.loads((out / 'forensic_projection/forensics/inventory.json').read_text())
        save(out / 'FORENSIC_FORMATS.json', {'files': [{'path': x['relative_path'], **inspect(out / 'forensic_projection/forensics/files' / x['relative_path'])} for x in inventory['files']], 'source_sha256': hashes[data.name], 'view_kind': 'journal_replay_derivative', 'callback_attribution': 'not established'})
        root_recovery = out / 'root-recovery.qcow2'
        data_recovery = out / 'data-recovery.qcow2'
        for original_disk, dest in [(disk, root_recovery), (data, data_recovery)]:
            subprocess.run(['qemu-img', 'create', '-f', 'qcow2', '-F', 'qcow2', '-b', str(original_disk), str(dest)], capture_output=True, check=True)
        active_data = data_recovery
        active_log = None
        vm = host.VM(root_recovery, out / 'recovery-boot', 2233, 'block-reader-' + str(time.monotonic_ns()), events)
        mount_data(vm, out, 'recovery-data-mount', recovery=True)
        events('FAULT_IDENTITY', old_boot_id=old_boot, new_boot_id=vm.boot, classification='block_capture_fresh_derivative', volatile_state_discarded=old_boot != vm.boot, qemu_changed=old_pid != vm.proc.pid)
        read_identity(host.remote, vm.port, identity, out, 'identity-before-recovery')
        worker = original.Worker(vm, spec, out, events, recovery=True)
        oracle = worker.command('oracle')
        save(out / 'ORACLE.json', oracle)
        endpoint = oracle['guest']['endpoint']
        if endpoint not in ['recovered', 'lost']:
            reasons.append('endpoint_not_interpretable')
        if any((sha(out / n) != h for n, h in hashes.items())):
            raise RuntimeError('Immutable original block capture changed')
        passed = not reasons
    except BaseException as e:
        reasons.append(str(e))
        events('QUALIFICATION_ERROR', error=repr(e))
    finally:
        if trace:
            try:
                trace.close(reset=False)
            except Exception as e:
                events('TRACE_CLEANUP_ERROR', error=repr(e))
        if worker:
            try:
                worker.close()
            except Exception as e:
                events('WORKER_CLEANUP_ERROR', error=repr(e))
        if vm:
            try:
                vm.quit()
            except Exception as e:
                events('VM_CLEANUP_ERROR', error=repr(e))
        host.vm_args = old_args
        host.DATA = None
        end = time.monotonic_ns()
        result = {'trial_id': a['trial_id'], 'role': RUN_ROLE, 'scientific_denominator': RUN_ROLE == 'scientific', 'technical_eligible': passed, 'endpoint': endpoint, 'reasons': reasons, 'wall_seconds': (end - start) / 1000000000.0, 'allocated_bytes': sum((p.stat().st_blocks * 512 for p in out.rglob('*') if p.is_file() if p.name != 'backend-console.txt')), 'logical_bytes': sum((p.stat().st_size for p in out.rglob('*') if p.is_file() if p.name != 'backend-console.txt')), 'free_before': free, 'free_after': shutil.disk_usage(ROOT).free, 'image_sha256': {str(p.relative_to(out)): sha(p) for p in out.rglob('*.qcow2')}, 'retry_permitted': False, 'scientific_assignments_started': int(RUN_ROLE == 'scientific'), 'technical_hash_lock_complete': False}
        save(out / 'RESULT.json', result)
        events('QUALIFICATION_FINISHED', result=result)
        events.file.close()
        save(out / 'SHA256.json', {str(p.relative_to(out)): sha(p) for p in out.rglob('*') if p.is_file() if p.name != 'backend-console.txt'})
        print(json.dumps(result, indent=2), flush=True)
    return passed
