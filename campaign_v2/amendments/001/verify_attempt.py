"""Read-only audit of the single amendment attempt. Never launches a VM."""
import datetime
import hashlib
import json
from pathlib import Path
import shutil

ADMIN = Path(__file__).resolve().parent
ROOT = ADMIN.parents[1]
ID = 'qualification-amendment-001-close_aligned_recovery_grid-00001'
OLD = 'qualification-close_aligned_recovery_grid-00001'

def sha(p):
    with p.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def read(p):
    return json.loads(p.read_text())

def main():
    out = ROOT / 'qualification/attempts' / ID
    old = ROOT / 'qualification/attempts' / OLD
    approval = read(ADMIN / 'AUTHOR_APPROVAL_RECEIPT.json')
    original = {str(p.relative_to(old)): sha(p) for p in sorted(old.rglob('*')) if p.is_file()}
    checks = {'original_all_files_unchanged': original == approval['original_preserved_inventory'],
              'original_endpoint_unknown': read(old / 'RESULT.json')['endpoint'] == 'unknown',
              'original_remains_failed': not read(old / 'RESULT.json')['qualification_passed'],
              'new_assignment_matches_posted': read(out / 'assignment.json') == read(ADMIN / 'ASSIGNMENT.json')}
    result = read(out / 'RESULT.json')
    inventory = read(out / 'SHA256.json')
    checks['raw_hashes_match'] = all(sha(out / name) == digest for name, digest in inventory.items())
    checks['image_hashes_match'] = all(sha(out / name) == digest for name, digest in result['image_sha256'].items())
    inputs = read(ADMIN / 'EXECUTION_INPUTS.json')
    checks['prospective_execution_source_matches'] = all(sha(ROOT / n) == h and sha(ADMIN / 'EXECUTED_SOURCE' / n) == h for n,h in inputs['source_sha256'].items())
    start = read(out / 'START.json')
    checks['start_source_matches_snapshot'] = all(sha(ADMIN / 'EXECUTED_SOURCE' / n) == h for n,h in start['source_hashes'].items())
    checks['excluded_from_science'] = result['role'] == 'qualification' and result['scientific_denominator'] is False and result['scientific_assignments_started'] == 0
    raw = [json.loads(l) for l in (out / 'events.jsonl').read_text().splitlines()]
    find = lambda kind: next((x for x in raw if x['kind'] == kind), None)
    page = [x for x in raw if x['kind'] == 'GUEST_RECORD' and x['guest'].get('kind') == 'PAGE_EVENT']
    pe = lambda kind: next((x for x in page if x['guest']['event']['kind'] == kind), None)
    ack, close, sentinel = pe('ACK'), pe('CLOSE_RETURNED'), pe('SENTINEL_INDEPENDENT_READBACK')
    fault, schedule, identity, attach = [find(k) for k in ['FAULT_DISPATCH','SCHEDULED_FAULT','FAULT_IDENTITY','EVIDENCE_ATTACHED_AFTER_HELPER_BOOT']]
    timing = {}
    if ack and fault:
        timing['ack_receipt_to_dispatch_ms'] = (fault['fault']['dispatch_ns'] - ack['receipt_ns']) / 1e6
        timing['dispatch_overshoot_ms'] = (fault['fault']['dispatch_ns'] - fault['deadline_ns']) / 1e6
        checks['dispatch_in_frozen_gate'] = 0 <= timing['dispatch_overshoot_ms'] <= 25
    if close and ack:
        timing['page_close_delay_ms'] = close['guest']['event']['page_ms'] - ack['guest']['event']['ack_ms']
    if schedule and schedule['mapping'] and fault:
        timing['mapped_close_to_dispatch_ms'] = (fault['fault']['dispatch_ns'] - schedule['mapping']['estimate_ns']) / 1e6
        timing['mapped_close_uncertainty_ms'] = schedule['mapping']['uncertainty_ns'] / 1e6
    resets = [x for x in raw if x['kind'] == 'QMP' and x.get('data',{}).get('event') == 'RESET']
    checks['qmp_reset_classification'] = any(x['data'].get('data',{}).get('reason') == 'host-qmp-system-reset' and x['data']['data'].get('guest') is False for x in resets)
    checks['boot_identity_changed'] = bool(identity and identity['old_boot_id'] != identity['new_boot_id'])
    checks['strict_sentinel_and_absent_target_precondition'] = bool(sentinel and sentinel['guest']['event']['durability_observed'] == 'strict' and sentinel['guest']['event']['readback']['endpoint'] == 'lost' and sentinel['guest']['event']['readback']['sentinel_valid'])
    checks['relaxed_ack'] = bool(ack and ack['guest']['event']['durability_observed'] == 'relaxed')
    view = read(out / 'IMMUTABLE_VIEW.json') if (out / 'IMMUTABLE_VIEW.json').exists() else None
    checks['immutable_evidence_hash_matches'] = bool(view and sha(out / 'overlay.qcow2') == view['sha256'])
    checks['helper_root_and_read_only_attachment'] = bool(attach and attach['helper_root'] == '/dev/vda1' and attach['read_only'] and attach['serial'] == 'idbv2-evidence')
    checks['helper_boot_excludes_evidence'] = all(not any('overlay.qcow2' in a for a in x['command']) for x in raw if x['kind'] == 'VM_START' and x['role'] == 'forensic_helper')
    extract = read(out / 'forensics/inventory.json') if (out / 'forensics/inventory.json').exists() else None
    checks['forensic_members_match'] = bool(extract and all(sha(out / 'forensics/files' / x['relative_path']) == x['sha256'] for x in extract['files']))
    checks['forensic_read_only_no_replay'] = bool(extract and extract['block_read_only'] and not extract['replay_performed'] and not extract['oracle_started'] and extract['mount_options_requested'] == 'ro,noload')
    oracle = read(out / 'ORACLE.json')['guest'] if (out / 'ORACLE.json').exists() else None
    spec = read(out / 'payload_contract.json')
    if oracle:
        direct = oracle.get('direct',[]); indexed = oracle.get('indexed',[]); all_values = oracle.get('all',[])
        if oracle['endpoint'] == 'recovered':
            valid = direct == spec['targets'] and sorted(indexed,key=lambda x:x['id']) == sorted(spec['targets'],key=lambda x:x['id']) and sorted(all_values,key=lambda x:x['id']) == sorted([spec['sentinel']]+spec['targets'],key=lambda x:x['id'])
        elif oracle['endpoint'] == 'lost':
            valid = all(x is None for x in direct) and not indexed and all_values == [spec['sentinel']]
        else: valid = False
        checks['oracle_raw_content_matches_endpoint'] = valid and oracle.get('sentinel_valid') is True and oracle['endpoint'] == result['endpoint']
    else: checks['oracle_raw_content_matches_endpoint'] = False
    passed = result['qualification_passed'] and all(checks.values())
    summary = {'verified_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'trial_id':ID,'runner_result':result,
               'checks':checks,'independent_qualification_pass':passed,'timing_diagnostics_ms':timing,
               'qmp_reset_records':resets,'boot_identity':identity,'immutable_view':view,'oracle':oracle,
               'scientific_assigned':930,'scientific_started':0,'registered_qualification_started':1,
               'registered_qualification_failed':1,'registered_qualification_unstarted':94,
               'amendment_qualification_started':1,'further_execution_authorized':False,
               'disk_free_bytes':shutil.disk_usage(ROOT).free,
               'full_campaign_forecast':'pending remaining cell qualification; cannot extrapolate one condition'}
    (ADMIN / 'VERIFICATION.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({'independent_qualification_pass':passed,'checks':checks,'timing':timing},indent=2))

if __name__ == '__main__': main()
