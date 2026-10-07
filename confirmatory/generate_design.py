#!/usr/bin/env python3
"""Generate prospective Mac-only assignments; never acquire or synthesize outcomes."""
import csv
import hashlib
import itertools
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SEED = 'indexeddb-connection-lifetime-mac-20261003-v2'
BASE = dict(architecture='aarch64', accelerator='hvf', browser='packaged_pinned',
            backend_policy='force_sqlite', durability='relaxed', fault='qmp_reset',
            timing_anchor='host_ack', close_ms=0, fault_after_ack_ms=None,
            fault_after_close_ms=None, held=False, workload='single_256_bytes',
            filesystem='ext4_commit30', sysctls='record_unchanged', uptime='ordinary',
            instrumentation='ordinary', mapper='none')
KEYS = [
    dict(key='immediate_close_late_deadline', fault_after_ack_ms=2500),
    dict(key='delayed_close_short_interval', close_ms=1000, fault_after_ack_ms=2750),
    dict(key='held_five_seconds', held=True, close_ms=None, fault_after_ack_ms=5000),
    dict(key='held_fifteen_seconds', held=True, close_ms=None, fault_after_ack_ms=15000),
    dict(key='held_thirty_seconds', held=True, close_ms=None, fault_after_ack_ms=30000),
    dict(key='strict_short_deadline', durability='strict', fault_after_ack_ms=500),
]
FOUR_KEYS = KEYS[:4]
FAMILIES = []

def family(name, cells, tier, blocks=10, optional=False, unit='fresh trial'):
    conditions = [dict(BASE, **cell) for cell in cells]
    assert conditions and len({canonical(c) for c in conditions}) == len(conditions)
    FAMILIES.append(dict(name=name, cells=conditions, tier=tier, repetitions=blocks,
                         optional=optional, unit=unit))

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'))

def rank(*items):
    return hashlib.sha256('|'.join(map(str, (SEED, *items))).encode()).hexdigest()

family('close_aligned_recovery_grid', [
    dict(close_ms=c, timing_anchor='observed_close_estimate', fault_after_close_ms=g)
    for c, g in itertools.product([0, 1000], range(1600, 2401, 100))], 1)
family('held_connection_recovery_sweep', [
    dict(held=True, close_ms=None, fault_after_ack_ms=t)
    for t in [5000, 7500, 10000, 12500, 15000]] + [
    dict(held=False, close_ms=0, fault_after_ack_ms=t) for t in [5000, 15000]], 1)
family('six_key_conditions', KEYS, 1)
family('target_byte_diagnostics', [dict(k, instrumentation='write_capture') for k in FOUR_KEYS], 1)
family('trace_category_timelines', [dict(k, instrumentation='trace_categories') for k in FOUR_KEYS], 1, blocks=5)
family('fault_scope_comparison', [dict(k, fault=f)
    for f, k in itertools.product(['qmp_reset', 'sysrq_reboot', 'browser_sigkill'], FOUR_KEYS)], 2)
family('block_state_recovery', [dict(k, mapper=m, filesystem='ext4_commit5_data_volume', fault='block_capture')
    for m, k in itertools.product(['linear_control', 'dm_log_writes', 'dm_flakey_drop_writes'], FOUR_KEYS)], 2,
    unit='independent block-state capture; replay prefixes are dependent')
profiles = [
    ('ext4_custom_reference', 'ext4_commit30_data_volume', 'fixed_sixty_seconds'),
    ('ext4_defaults_fixed', 'ext4_default_data_volume', 'fixed_sixty_seconds'),
    ('ext4_defaults_random', 'ext4_default_data_volume', 'random_45_to_180_seconds'),
    ('xfs_fixed', 'xfs_default_data_volume', 'fixed_sixty_seconds'),
]
family('environment_sensitivity', [dict(k, environment_profile=p, filesystem=fs, uptime=u)
    for (p, fs, u), k in itertools.product(profiles, FOUR_KEYS)], 2)
family('application_and_background_activity', [dict(k, workload=w)
    for w, k in itertools.product(['single_256_bytes', 'background_fsync',
                                   'ten_records_one_transaction', 'four_connections'], FOUR_KEYS)], 2)
family('durability_cost', [dict(durability=d, workload=w, held=h,
    connection_policy='retained' if h else 'close_reopen_per_transaction',
    close_ms=None if h else 0, fault='none', fault_after_ack_ms=None)
    for d, w, h in itertools.product(['strict', 'relaxed'],
        ['single_256_bytes', 'single_64k_bytes', 'ten_records_one_transaction'], [False, True])], 3,
    optional=True, unit='fresh profile/overlay; 100 measured transactions nested within trial')


def assignments(spec, qualification=False):
    result = []
    role = 'qualification' if qualification else 'scientific'
    for block in range(1, 2 if qualification else spec['repetitions'] + 1):
        cells = sorted(spec['cells'], key=lambda c: (rank(role, spec['name'], block, canonical(c)), canonical(c)))
        for cell in cells:
            ordinal = len(result) + 1
            result.append(dict(experiment=spec['name'], role=role,
                trial_id=f"{role}-{spec['name']}-{ordinal:05d}", ordinal=ordinal, block=block,
                condition_id=hashlib.sha256(canonical(cell).encode()).hexdigest()[:16],
                optional=spec['optional'], tier=spec['tier'],
                planned_uptime_ms=(45000 + int(rank('uptime', role, spec['name'], block, canonical(cell))[:16], 16) % 135001)
                if cell['uptime'] == 'random_45_to_180_seconds' else 60000
                if cell['uptime'] == 'fixed_sixty_seconds' else None, **cell))
    return result


def render():
    plans = {s['name']: dict(s, seed=SEED, status='ASSIGNMENTS_ONLY_NOT_ACQUIRED',
                            assignments=assignments(s), qualification_assignments=assignments(s, True)) for s in FAMILIES}
    # Selection is fixed before outcomes. Mandatory and optional plans have separate 5% samples.
    for optional in [False, True]:
        rows = [r for s in FAMILIES if s['optional'] == optional
                for role in ['assignments', 'qualification_assignments'] for r in plans[s['name']][role]]
        selected = {r['trial_id'] for r in sorted(rows, key=lambda r: (rank('overlay-retention', r['trial_id']), r['trial_id']))[:len(rows) // 20]}
        for row in rows:
            row['keep_full_overlay_seeded'] = row['trial_id'] in selected
    return plans


def main():
    dest = ROOT / 'design'
    dest.mkdir(exist_ok=True)
    plans = render()
    # Obsolete active assignments remain recoverable from the superseded Git revision.
    for path in dest.glob('*.json'):
        if path.stem not in plans and path.name != 'MANIFEST.json':
            path.unlink()
    manifest = dict(seed=SEED, randomization='SHA-256 rank within randomized complete blocks; distinct roles',
                    status='ASSIGNMENTS_ONLY_NOT_ACQUIRED', acquisition_started=False,
                    family_execution_order=list(plans), scientific_execution_order='family order, then ordinal; never reuse attempted slots',
                    retained_overlay_sampling='SHA-256 rank; floor(5%); separate mandatory/optional pools including qualification',
                    experiments=[])
    for spec in FAMILIES:
        path = dest / (spec['name'] + '.json')
        path.write_text(json.dumps(plans[spec['name']], indent=2) + '\n')
        manifest['experiments'].append(dict(name=spec['name'], tier=spec['tier'], cells=len(spec['cells']),
            repetitions=spec['repetitions'], assignments=len(plans[spec['name']]['assignments']),
            qualification_assignments=len(plans[spec['name']]['qualification_assignments']), optional=spec['optional'],
            unit=spec['unit'], path=str(path.relative_to(ROOT)), sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    for label, optional in [('required', False), ('optional', True)]:
        entries = [e for e in manifest['experiments'] if e['optional'] == optional]
        manifest[label + '_scientific_assignments'] = sum(e['assignments'] for e in entries)
        manifest[label + '_qualification_assignments'] = sum(e['qualification_assignments'] for e in entries)
        rows = [r for e in entries for role in ['assignments', 'qualification_assignments'] for r in plans[e['name']][role]]
        manifest[label + '_seeded_full_overlays'] = sum(r['keep_full_overlay_seeded'] for r in rows)
    assert (manifest['required_scientific_assignments'], manifest['required_qualification_assignments']) == (930, 95)
    assert (manifest['optional_scientific_assignments'], manifest['optional_qualification_assignments']) == (120, 12)
    (dest / 'MANIFEST.json').write_text(json.dumps(manifest, indent=2) + '\n')
    with (dest / 'DESIGN_COUNTS.csv').open('w', newline='') as stream:
        fields = ['name', 'tier', 'cells', 'repetitions', 'assignments', 'qualification_assignments', 'optional', 'unit']
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction='ignore', lineterminator='\n')
        writer.writeheader()
        writer.writerows(manifest['experiments'])
    print(json.dumps({k: v for k, v in manifest.items() if k != 'experiments'}, indent=2))

if __name__ == '__main__':
    main()
