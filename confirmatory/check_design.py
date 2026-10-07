#!/usr/bin/env python3
"""Verify exact revision-2 matrices, blocks, seeds, retention and operational gates."""
import hashlib
import json
from collections import Counter
from pathlib import Path
from generate_design import FAMILIES, FOUR_KEYS, render

P = Path(__file__).resolve().parent
manifest = json.loads((P / 'design/MANIFEST.json').read_text())
expected = render()
counts = {
 'close_aligned_recovery_grid': (18, 10, 180, 1),
 'held_connection_recovery_sweep': (7, 10, 70, 1),
 'six_key_conditions': (6, 10, 60, 1),
 'target_byte_diagnostics': (4, 10, 40, 1),
 'trace_category_timelines': (4, 5, 20, 1),
 'fault_scope_comparison': (12, 10, 120, 2),
 'block_state_recovery': (12, 10, 120, 2),
 'environment_sensitivity': (16, 10, 160, 2),
 'application_and_background_activity': (16, 10, 160, 2),
 'durability_cost': (12, 10, 120, 3),
}
assert set(counts) == set(expected) == {e['name'] for e in manifest['experiments']}
assert {p.stem for p in (P / 'design').glob('*.json')} == set(counts) | {'MANIFEST'}
ids = set()
all_rows = []
for spec, entry in zip(FAMILIES, manifest['experiments'], strict=True):
 path = P / entry['path']
 assert hashlib.sha256(path.read_bytes()).hexdigest() == entry['sha256']
 plan = json.loads(path.read_text())
 assert plan == expected[spec['name']]
 assert (entry['cells'], entry['repetitions'], entry['assignments'], entry['tier']) == counts[spec['name']]
 assert entry['qualification_assignments'] == entry['cells']
 for role, nblocks in [('assignments', spec['repetitions']), ('qualification_assignments', 1)]:
  rows = plan[role]
  assert len(rows) == len(spec['cells']) * nblocks
  assert set(Counter(r['condition_id'] for r in rows).values()) == {nblocks}
  for block in range(1, nblocks + 1):
   selected = [r for r in rows if r['block'] == block]
   assert len(selected) == len(spec['cells']) == len({r['condition_id'] for r in selected})
  for r in rows:
   assert r['trial_id'] not in ids
   ids.add(r['trial_id'])
   assert (r['architecture'], r['accelerator'], r['browser'], r['sysctls']) == ('aarch64', 'hvf', 'packaged_pinned', 'record_unchanged')
   assert not any(k in r for k in ['recovered', 'outcome', 'observed_uptime', 'result'])
   assert r['close_ms'] is None if r['held'] else r['close_ms'] is not None
   assert r['planned_uptime_ms'] is None if r['uptime'] == 'ordinary' else 45000 <= r['planned_uptime_ms'] <= 180000
   if r['uptime'] == 'fixed_sixty_seconds': assert r['planned_uptime_ms'] == 60000
  all_rows.extend(rows)
 rows = plan['assignments']
 name = spec['name']
 if name == 'close_aligned_recovery_grid':
  assert {(r['close_ms'], r['fault_after_close_ms']) for r in rows} == {(c, g) for c in [0, 1000] for g in range(1600, 2401, 100)}
  assert all(r['timing_anchor'] == 'observed_close_estimate' and r['fault_after_ack_ms'] is None for r in rows)
 if name == 'held_connection_recovery_sweep':
  assert {(r['held'], r['fault_after_ack_ms']) for r in rows} == {(True, t) for t in [5000, 7500, 10000, 12500, 15000]} | {(False, t) for t in [5000, 15000]}
 if name == 'fault_scope_comparison': assert {r['fault'] for r in rows} == {'qmp_reset', 'sysrq_reboot', 'browser_sigkill'}
 if name == 'block_state_recovery': assert {r['mapper'] for r in rows} == {'linear_control', 'dm_log_writes', 'dm_flakey_drop_writes'}
 if name == 'environment_sensitivity': assert {r['environment_profile'] for r in rows} == {'ext4_custom_reference', 'ext4_defaults_fixed', 'ext4_defaults_random', 'xfs_fixed'}
 if name == 'application_and_background_activity': assert {r['workload'] for r in rows} == {'single_256_bytes', 'background_fsync', 'ten_records_one_transaction', 'four_connections'}
 if name in ['target_byte_diagnostics', 'trace_category_timelines', 'fault_scope_comparison', 'block_state_recovery', 'environment_sensitivity', 'application_and_background_activity']:
  assert {r['key'] for r in rows} == {k['key'] for k in FOUR_KEYS}
for label, optional, science, qualification, retained in [('required', False, 930, 95, 51), ('optional', True, 120, 12, 6)]:
 assert manifest[label + '_scientific_assignments'] == science
 assert manifest[label + '_qualification_assignments'] == qualification
 selected = [r for r in all_rows if r['optional'] == optional]
 assert sum(r['keep_full_overlay_seeded'] for r in selected) == retained
 assert 0.03 <= retained / len(selected) <= 0.05
assert sum(e['assignments'] for e in manifest['experiments'] if e['tier'] == 1) == 370
assert sum(e['assignments'] for e in manifest['experiments'] if e['tier'] == 2) == 560
assert sum(e['qualification_assignments'] for e in manifest['experiments'] if not e['optional']) == 95
assert not (P / 'raw').exists()
gate = json.loads((P / 'GATE.json').read_text())
assert gate['status'] == 'AWAITING_OSF_URL_AND_REPOSITORY_TAG'
assert gate['acquisition_started'] is False and gate['execution_allowed'] is False
assert gate['paper_writing_allowed'] is False and gate['scientific_acquisition_by_current_agent_allowed'] is False
report = dict(status='PASS', required_scientific_assignments=930, excluded_required_qualification_attempts=95,
 optional_cost_assignments=120, optional_cost_qualification_attempts=12,
 tier_1_assignments=370, tier_2_assignments=560, active_families=10,
 required_seeded_full_overlays=51, optional_seeded_full_overlays=6,
 balanced_complete_blocks=True, grid_cells=18, timeline_block_exception=5,
 assignments_are_not_observations=True, new_acquisition_attempts=0)
(P / 'DESIGN_VALIDATION.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
