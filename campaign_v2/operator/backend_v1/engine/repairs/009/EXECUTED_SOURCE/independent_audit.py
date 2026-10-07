"""Audit finished batch attempts only. Never reads live records as final outcomes."""
from backend_runtime import RUN_ROLE, ENGINE, ATTEMPT_RELATIVE, attempt_root, validate_reserved, validate_assignment, deploy_worker
import hashlib, json, datetime
from pathlib import Path
ROOT = Path(__file__).resolve().parents[5]
ADMIN = Path(__file__).parent

def read(p):
    return json.loads(p.read_text())

def sha(p):
    with p.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def audit(a):
    out = ROOT / ATTEMPT_RELATIVE / a['trial_id']
    result = read(out / 'RESULT.json')
    events = [json.loads(l) for l in (out / 'events.jsonl').read_text().splitlines()]
    one = lambda k: next((x for x in events if x['kind'] == k))
    checks = {'assignment_matches_frozen': read(out / 'assignment.json') == a, 'raw_inventory_matches': all((sha(out / n) == h for n, h in read(out / 'SHA256.json').items())), 'all_images_match': all((sha(out / n) == h for n, h in result['image_sha256'].items())), 'excluded': result['role'] == RUN_ROLE and result['scientific_denominator'] == (RUN_ROLE == 'scientific') and (result['scientific_assignments_started'] == int(RUN_ROLE == 'scientific'))}
    checks['source_matches_batch_snapshot'] = all((sha(ADMIN / 'EXECUTED_SOURCE' / n) == h for n, h in read(out / 'ENGINE_START.json')['candidate_repair_source_hashes'].items()))
    from boot_mounts import validate_inventory
    mount_records = [x for x in events if x['kind'] == 'AUXILIARY_MOUNT_IDENTITY']
    for x in mount_records:
        validate_inventory(x['identity'])
    lock = read(ADMIN / 'REPAIRED_BASE_LOCK.json')
    checks['all_mount_identities'] = len(mount_records) == 4 and all((x['identity']['fstab'] == lock['fstab'] for x in mount_records))
    checks['repaired_base_matches'] = sha(Path(lock['derived_base_path'])) == lock['derived_base_sha256'] and read(out / 'ENGINE_START.json')['base_lock'] == lock
    p = [x for x in events if x['kind'] == 'GUEST_RECORD' and x['guest'].get('kind') == 'PAGE_EVENT']
    pe = lambda k: next((x for x in p if x['guest']['event']['kind'] == k))
    ack = pe('ACK')
    sentinel = pe('SENTINEL_INDEPENDENT_READBACK')
    fault = one('FAULT_DISPATCH')
    identity = one('FAULT_IDENTITY')
    overshoot = (fault['fault']['dispatch_ns'] - fault['deadline_ns']) / 1000000.0
    checks['dispatch_eligible'] = 0 <= overshoot <= 25
    checks['ack_hint_matches'] = ack['guest']['event']['durability_observed'] == a['durability']
    checks['sentinel_precondition'] = sentinel['guest']['event']['durability_observed'] == 'strict' and sentinel['guest']['event']['readback']['endpoint'] == 'lost' and sentinel['guest']['event']['readback']['sentinel_valid']
    checks['fault_boot_identity'] = identity['old_boot_id'] == identity['new_boot_id'] if a['fault'] == 'browser_sigkill' else identity['old_boot_id'] != identity['new_boot_id']
    checks['fault_identity_label'] = identity['classification'] == a['fault']
    agents = [x for x in events if x['kind'] == 'FAULT_AGENT_RECORD']
    agent = lambda k: next((x for x in agents if x['fault_agent']['kind'] == k))
    request = agent('FAULT_REQUEST_ACCEPTED')
    checks['guest_dispatch_received'] = request['fault_agent']['fault'] == a['fault'] and request['receipt_ns'] >= fault['fault']['dispatch_ns']
    if a['fault'] == 'browser_sigkill':
        classification = one('SIGKILL_CLASSIFICATION')
        tree = agent('SIGKILL_SELECTED_TREE')['fault_agent']['tree']
        dispatch = agent('SIGKILL_DISPATCH_RESULT')['fault_agent']
        exits = agent('SIGKILL_EXIT_EVIDENCE')['fault_agent']
        checks['selected_browser_tree'] = len(tree['processes']) > 0 and tree['root_pid'] in {p['pid'] for p in tree['processes']} and all((p['start_ticks'] > 0 for p in tree['processes']))
        checks['sigkill_signals'] = len(dispatch['signals']) == len(tree['groups']) and all((s['signal'] == 9 and s['error'] is None for s in dispatch['signals']))
        checks['selected_process_exit'] = exits['all_selected_exited'] and (not exits['profile_browser_survivors']) and all((p['original_identity_exited'] for p in exits['selected'])) and ({p['pid'] for p in exits['selected']} == {p['pid'] for p in tree['processes']})
        checks['unchanged_boot_evidence'] = classification['unchanged_boot_id'] and all((x['fault_agent']['boot_id'] == identity['old_boot_id'] for x in agents))
    else:
        classification = one('SYSRQ_CLASSIFICATION')
        req = agent('SYSRQ_REBOOT_REQUEST')['fault_agent']
        console = (out / 'boot/console.txt').read_bytes()
        checks['sysrq_trigger'] = req['trigger'] == '/proc/sysrq-trigger' and req['value'] == 'b' and (req['boot_id'] == identity['old_boot_id'])
        checks['sysrq_independent_serial'] = classification['boot_id_changed'] and any(('Resetting' in line for line in classification['serial_lines'])) and (b'sysrq: Resetting' in console)
    if a['held']:
        held = one('HELD_EVIDENCE')['last_telemetry']
        checks['held_state_confirmed'] = held['receipt_ns'] <= fault['fault']['dispatch_ns'] and held['guest']['state']['original_present'] and (not held['guest']['state']['original_closed'])
    else:
        checks['close_record_exists'] = pe('CLOSE_RETURNED')['guest']['event']['assigned_close_ms'] == a['close_ms']
    setup = read(out / 'identity-setup.stdout')
    before = read(out / 'identity-before-worker.stdout')
    after = read(out / 'identity-before-recovery.stdout')
    checks['identity_sync_and_readback'] = setup['file_fsync_completed'] and setup['directory_fsync_completed'] and (setup['identity'] == before == after) and (before['trial_id'] == a['trial_id'])
    view = read(out / 'IMMUTABLE_VIEW.json')
    oracle_record = read(out / 'ORACLE.json')
    oracle = oracle_record['guest']
    spec = read(out / 'payload_contract.json')
    checks['immutable_before_reader'] = view['captured_ns'] < oracle_record['host_send_ns'] and (not view['oracle_started']) and (sha(out / 'overlay.qcow2') == view['sha256'])
    extracts = read(out / 'forensics/inventory.json')
    checks['extracts_match'] = all((sha(out / 'forensics/files' / x['relative_path']) == x['sha256'] for x in extracts['files']))
    checks['extract_read_only'] = extracts['block_read_only'] and (not extracts['replay_performed']) and (extracts['mount_options_requested'] == 'ro,noload')
    checks['sqlite_backend_confirmed'] = any((x['kind'] == 'GUEST_RECORD' and x['guest'].get('command') == 'prepare' and any((f['sqlite_header'] for f in x['guest']['value']['backend_files'])) for x in events))
    target = spec['targets']
    sort = lambda values: sorted(values, key=lambda x: x['id'])
    if oracle['endpoint'] == 'recovered':
        valid = oracle['direct'] == target and sort(oracle['indexed']) == sort(target) and (sort(oracle['all']) == sort(target + [spec['sentinel']]))
    elif oracle['endpoint'] == 'lost':
        valid = all((x is None for x in oracle['direct'])) and len(oracle['direct']) == len(target) and (not oracle['indexed']) and (oracle['all'] == [spec['sentinel']])
    else:
        valid = False
    checks['oracle_matches_raw_content'] = valid and oracle['sentinel_valid'] and (result['endpoint'] == oracle['endpoint'])
    checks['contract_checksums'] = all((hashlib.sha256((json.dumps(x['metadata'], sort_keys=True, separators=(',', ':'), ensure_ascii=True) + '\n' + x['payload']).encode('ascii')).hexdigest() == x['checksum'] for x in target + [spec['sentinel']]))
    epochs = []
    active = None
    for x in events:
        if x['kind'] == 'VM_START':
            active = {'anchor': x['host_monotonic_ns'], 'observations': []}
            epochs.append(active)
        if x['kind'] == 'RECOVERY_SAME_GUEST_START':
            active = {'anchor': x['host_monotonic_ns'], 'observations': []}
            epochs.append(active)
        if x['kind'] == 'FAULT_DISPATCH':
            active = {'anchor': x['fault']['dispatch_ns'], 'observations': []}
            epochs.append(active)
        if x['kind'] == 'HEALTHY_OBSERVATION':
            active['observations'].append(x['observation'])
    checks['readiness_all_four_windows'] = len(epochs) == 4 and all((len(e['observations']) >= 3 and len({o['identity']['boot_id'] for o in e['observations']}) == 1 and (e['observations'][-1]['host_ns'] - e['observations'][0]['host_ns'] >= 5000000000.0) and (e['observations'][-1]['host_ns'] - e['anchor'] <= 180000000000.0) for e in epochs))
    if a['fault'] == 'browser_sigkill':
        same = one('SIGKILL_ORACLE_SAME_GUEST')
        initial = one('VM_START')
        snapshot = read(out / 'LIVE_SNAPSHOT.json')
        commands = [x for x in events if x['kind'] == 'QMP' and x.get('vm_pid') == initial['pid'] and (x.get('direction') == 'request') and (x['host_monotonic_ns'] < oracle_record['host_send_ns'])]
        checks['original_guest_retained_through_oracle'] = same['qemu_pid'] == initial['pid'] == snapshot['original_qemu_pid'] and same['boot_id'] == identity['old_boot_id'] and snapshot['guest_volatile_state_retained'] and (not snapshot['guest_shutdown_before_oracle']) and (not any((x['data']['execute'] in ['quit', 'system_reset'] for x in commands)))
        checks['live_snapshot_immutable'] = snapshot['disk_node_read_only'] and sha(out / 'overlay.qcow2') == snapshot['sha256'] == same['original_disk_sha256'] and (out / 'active-after-snapshot.qcow2').exists()
    return {'trial_id': a['trial_id'], 'independent_pass': result['technical_eligible'] and all(checks.values()), 'checks': checks, 'endpoint': result['endpoint'], 'scientific_denominator': RUN_ROLE == 'scientific', 'wall_seconds': result['wall_seconds'], 'dispatch_overshoot_ms': overshoot}

def main():
    plan = read(ADMIN / 'QUALIFICATION_BATCH_PLAN.json')
    status = read(ADMIN / 'QUALIFICATION_BATCH_STATUS.json')
    done = set(status['completed_trial_ids'])
    rows = []
    for a in plan['assignments']:
        if a['trial_id'] in done:
            try:
                rows.append(audit(a))
            except Exception as e:
                rows.append({'trial_id': a['trial_id'], 'independent_pass': False, 'audit_error': repr(e)})
    report = {'checked_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'status_snapshot': status, 'finished_attempts_audited': len(rows), 'independently_passed': sum((x['independent_pass'] for x in rows)), 'attempts': rows, 'scientific_started': 0, 'campaign_ready': False}
    (ADMIN / 'BATCH_INDEPENDENT_VERIFICATION.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k not in {'attempts', 'status_snapshot'}}, indent=2))
    if any((not x['independent_pass'] for x in rows)):
        raise SystemExit(1)
if __name__ == '__main__':
    main()
