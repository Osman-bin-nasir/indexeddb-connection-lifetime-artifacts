"""Inspect preserved failures without importing acquisition code or changing evidence.

Only this investigation's output is created. No guest is booted, filesystem is
replayed, trial is retried, or original record is rewritten. qemu-img check is
called without repair options. Supply a fresh --output path for another audit.
"""
import argparse
import collections
import datetime
import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parents[2]
REPO = CAMPAIGN.parent
ATTEMPTS = CAMPAIGN / 'scientific/attempts'
IDS = [
    'scientific-trace_category_timelines-00003',
    'scientific-trace_category_timelines-00004',
    'scientific-trace_category_timelines-00014',
    'scientific-trace_category_timelines-00020',
    'scientific-fault_scope_comparison-00020',
]


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read(path):
    return json.loads(path.read_text())


def verify(mapping, root):
    checks = []
    for relative, expected in mapping.items():
        path = root / relative
        actual = sha(path) if path.is_file() else None
        checks.append({'path': str(path.relative_to(REPO)),
                       'expected_sha256': expected, 'actual_sha256': actual,
                       'matches': actual == expected})
    return checks


def command(argv):
    result = subprocess.run(argv, cwd=REPO, capture_output=True, text=True, check=False)
    return {'command': argv, 'returncode': result.returncode,
            'stdout': result.stdout, 'stderr': result.stderr}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=HERE / 'INVESTIGATION_RESULTS.json')
    args = parser.parse_args()
    if args.output.exists():
        raise RuntimeError('Refusing to overwrite an investigation output')
    lock = read(CAMPAIGN / 'operator/FINAL_INPUT_LOCK.json')
    protocol = REPO / 'confirmatory/PREREGISTRATION.md'
    git_root = Path(command(['git', 'rev-parse', '--show-toplevel'])['stdout'].strip())
    tagged = subprocess.run(['git', 'show', lock['protocol_tag'] + ':' +
                             str(protocol.relative_to(git_root))], cwd=REPO,
                            capture_output=True, check=True).stdout
    expected_protocol = read(ATTEMPTS / IDS[0] / 'REGISTERED_ENDPOINT.json')['protocol_sha256']
    relevant = {p: h for p, h in lock['input_hashes'].items()
                if p.startswith(('operator/backend_v1/engine/repairs/010/',
                                 'operator/backend_v1/engine/repairs/011/'))
                or p in ['operator/backend_v1/backend.py',
                         'operator/backend_v1/backend_runtime.py',
                         'operator/backend_dispatch_v2.py',
                         'operator/backend_dispatch_v3.py',
                         'operator/registered_endpoint_v1.py']}
    pinned = verify(relevant, CAMPAIGN)
    disposition_path = CAMPAIGN / 'operator/validator_correction_v1/DISPOSITION_354_PREMEASUREMENT_FAILURE_001.json'
    disposition = read(disposition_path)
    rows = []
    preserved_before = {}
    for ident in IDS:
        directory = ATTEMPTS / ident
        for path in directory.rglob('*'):
            if path.is_file():
                preserved_before[str(path.relative_to(REPO))] = sha(path)
        assignment = read(directory / 'assignment.json')
        design = read(REPO / 'confirmatory/design' / (assignment['experiment'] + '.json'))
        frozen = next(a for a in design['assignments'] if a['trial_id'] == ident)
        row = {'trial_id': ident, 'assignment': assignment,
               'assignment_matches_frozen': assignment == frozen,
               'original_endpoint_remains': 'unknown',
               'can_recover_eligible_endpoint_from_preserved_evidence': False,
               'fresh_prospective_assignment_required_for_new_eligible_observation': True,
               'original_assignment_consumed_no_retry_or_replacement': True}
        if ident == IDS[1]:
            row.update(measurement_started=False, recorded_reason=disposition['reason'],
                       disposition=disposition,
                       preserved_manifest_checks=verify(disposition['evidence_hashes'], CAMPAIGN),
                       resolution_reason='No VM or scientific measurement launched; no missing observation exists to recover.')
            rows.append(row)
            continue
        result = read(directory / 'RESULT.json')
        events = [json.loads(line) for line in (directory / 'events.jsonl').read_text().splitlines()]
        kinds = collections.Counter(e['kind'] for e in events)
        guests = [e['guest'] for e in events if e['kind'] == 'GUEST_RECORD']
        qmp = [{'host_ns': e['host_monotonic_ns'], 'vm_pid': e.get('vm_pid'),
                'command': e['data'].get('execute')} for e in events
               if e['kind'] == 'QMP' and e.get('direction') == 'request']
        row.update(result=result, independent_verification=read(directory / 'INDEPENDENT_VERIFICATION.json'),
                   event_kinds=dict(kinds), qmp_commands=qmp,
                   oracle_present=(directory / 'ORACLE.json').is_file(),
                   preserved_manifest_checks={n: verify(read(directory / n), directory)
                                              for n in ['SHA256.json', 'OPERATOR_SHA256.json']})
        repair = '011' if assignment['experiment'] == 'trace_category_timelines' else '010'
        recorded_sources = read(directory / 'ENGINE_START.json')['candidate_repair_source_hashes']
        row['executed_source_pin_checks'] = verify(recorded_sources, CAMPAIGN / 'operator/backend_v1/engine/repairs' / repair)
        row['qcow2_checks'] = []
        for path in directory.rglob('*.qcow2'):
            row['qcow2_checks'].append(command(['qemu-img', 'check', str(path)]))
        if assignment['experiment'] == 'trace_category_timelines':
            nonjson = [e for e in events if e['kind'] == 'WORKER_NON_JSON']
            raw = ''.join(e['text'] for e in nonjson)
            marker = 'BlockingIOError: [Errno 11] write could not complete without blocking'
            at = raw.find(marker)
            row.update(measurement_started=True, assigned_fault_executed=kinds['FAULT_DISPATCH'] > 0,
                       system_reset_requested=any(e['command'] == 'system_reset' for e in qmp),
                       trace_complete_records=sum(g.get('kind') == 'TRACE_COMPLETE' for g in guests),
                       trace_stop_response_records=sum(g.get('command') == 'trace-stop' for g in guests),
                       valid_trace_data_records=sum(g.get('kind') == 'TRACE_DATA' for g in guests),
                       nonjson_records=len(nonjson), trace_emit_blocking_error_recorded=at >= 0,
                       first_trace_write_error_excerpt=raw[max(0, at - 600):at + len(marker)],
                       controller_trace_stop_timeout_seconds=0.4,
                       guest_tracing_complete_timeout_seconds=5,
                       resolution_reason='Guest trace writes failed and the required trace-stop response was absent; the assigned QMP reset and oracle never ran. Cleanup shut down the VM. Reinterpreting trace fragments cannot reconstruct an unperformed fault/recovery.')
        else:
            initial = next(e for e in events if e['kind'] == 'VM_START')
            fault = next(e for e in events if e['kind'] == 'FAULT_DISPATCH')
            classification = next(e for e in events if e['kind'] == 'SIGKILL_CLASSIFICATION')
            console = (directory / 'forensic_projection/journal-helper/console.txt').read_text(errors='replace')
            view = read(directory / 'LIVE_SNAPSHOT.json')
            row.update(measurement_started=True, assigned_fault_executed=True,
                       fault_dispatch_overshoot_ms=fault['overshoot_ms'],
                       sigkill_original_boot_unchanged=classification['unchanged_boot_id'],
                       snapshot_original_qemu_pid=view['original_qemu_pid'],
                       original_vm_quit_recorded=any(e['command'] == 'quit' and e['vm_pid'] == initial['pid'] for e in qmp),
                       same_guest_oracle_recorded=kinds['SIGKILL_ORACLE_SAME_GUEST'] > 0,
                       saved_ram_vm_state_files=[str(p.relative_to(directory)) for p in directory.rglob('*')
                                                 if p.is_file() and p.suffix in ['.vmstate', '.ram', '.mem']],
                       kernel_error_lines=[line for line in console.splitlines() if 'checksum invalid' in line],
                       original_extractor_stderr=(directory / 'forensic_projection/original-noload.stderr').read_text(),
                       backing_chain=command(['qemu-img', 'info', '--output=json', '--backing-chain', str(directory / 'overlay.qcow2')]),
                       resolution_reason='The immutable no-replay ext4 view had an inode checksum error. The pinned extractor refused substitution, and the original guest was quit before its same-guest oracle. Preserved disks cannot restore that live kernel/RAM/boot identity. Later replay or boot may support separately labelled forensic diagnosis, but cannot supply this registered SIGKILL endpoint.')
        rows.append(row)
    counts = collections.Counter()
    for directory in ATTEMPTS.iterdir():
        if not directory.is_dir():
            continue
        counts['reserved_assignments'] += 1
        result_path = directory / 'RESULT.json'
        if result_path.is_file():
            result = read(result_path)
            counts['results_present'] += 1
            counts['recorded_technical_eligible'] += int(result['technical_eligible'])
            counts['raw_' + result['endpoint']] += 1
        else:
            counts['no_result'] += 1
    preserved_after = {p: sha(REPO / p) for p in preserved_before}
    report = {'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'scope': 'Read-only investigation of five original failures; no acquisition, retry, replay, or reclassification.',
              'protocol_tag': lock['protocol_tag'], 'scientific_assigned': lock['scientific_assigned'],
              'protocol_current_sha256': sha(protocol),
              'protocol_matches_recorded_hash': sha(protocol) == expected_protocol,
              'protocol_matches_repository_tag': tagged == protocol.read_bytes(),
              'pinned_relevant_scientific_inputs': pinned,
              'recorded_campaign_counts_not_a_new_whole_campaign_certification': dict(counts),
              'original_attempt_file_hashes_before': preserved_before,
              'original_attempts_unchanged_after_investigation': preserved_before == preserved_after,
              'eligible_endpoints_salvaged': 0, 'new_assignments_run': 0, 'attempts': rows}
    with args.output.open('x') as target:
        target.write(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'output': str(args.output), 'unchanged': report['original_attempts_unchanged_after_investigation'],
                      'protocol_matches_tag': report['protocol_matches_repository_tag'],
                      'pinned_sources_match': all(x['matches'] for x in pinned),
                      'counts': dict(counts), 'eligible_endpoints_salvaged': 0}, indent=2))


if __name__ == '__main__':
    main()
