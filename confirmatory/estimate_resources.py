#!/usr/bin/env python3
"""Planning scenarios from recorded pilot resource measurements, not new experiments."""
import json
from pathlib import Path

P = Path(__file__).resolve().parent
manifest = json.loads((P / 'design/MANIFEST.json').read_text())
pilot = json.loads((P / 'PILOT_RESOURCE_BASELINE.json').read_text())
# Explicit provisional seconds, including extra work absent from pilot event spans.
# These are assumptions pending one technical qualification per registered cell.
seconds = {
 'close_aligned_recovery_grid': (60, 90),
 'held_connection_recovery_sweep': (60, 90),
 'six_key_conditions': (60, 90),
 'target_byte_diagnostics': (120, 240),
 'trace_category_timelines': (90, 180),
 'fault_scope_comparison': (60, 120),
 'block_state_recovery': (180, 300),
 'environment_sensitivity': (120, 210),
 'application_and_background_activity': (60, 120),
 'durability_cost': (90, 180),
}
rows = []
for e in manifest['experiments']:
 lo, hi = seconds[e['name']]
 n = e['assignments'] + e['qualification_assignments']
 rows.append(dict(family=e['name'], scientific=e['assignments'], qualification=e['qualification_assignments'],
                  attempts=n, optional=e['optional'], seconds_per_attempt_scenario=[lo, hi],
                  hours_including_qualification=[n * lo / 3600, n * hi / 3600]))
required = [r for r in rows if not r['optional']]
optional = [r for r in rows if r['optional']]
sums = lambda entries: [sum(r['hours_including_qualification'][i] for r in entries) for i in range(2)]
overlay = pilot['storage_reference']['pilot_overlay_mean_MiB']
raw = pilot['storage_reference']['pilot_raw_mean_MiB']
report = dict(status='PROVISIONAL_SCENARIOS_NOT_QUALIFIED', scientific_observations=0,
              pilot_event_span_summary=pilot['summary'], assumptions_seconds_per_attempt=seconds,
              families=rows, mandatory_attempt_hours=sums(required), optional_attempt_hours=sums(optional),
              additional_provision_archive_verify_hours=[2, 6],
              mandatory_total_hours=[sums(required)[0] + 2, sums(required)[1] + 6],
              disk=dict(planning_free_GiB=35, measured_revision_free_GiB=pilot['filesystem_free_GiB_at_revision'],
                        hard_stop_GiB=6, offload_destination='Google Drive, author-managed folder IndexedDB-Mac-Confirmatory-v2 (folder URL pending)',
                        pilot_overlay_mean_MiB=overlay, pilot_raw_mean_MiB=raw,
                        all_mandatory_overlays_uncompressed_GiB=1025 * overlay / 1024,
                        largest_family_198_overlays_GiB=198 * overlay / 1024,
                        largest_family_at_pilot_max_61_75_MiB_GiB=198 * 61.75 / 1024,
                        all_mandatory_raw_at_pilot_mean_GiB=1025 * raw / 1024,
                        retained_seeded_51_overlays_before_zstd_GiB=51 * overlay / 1024,
                        anomaly_overlay_count='UNKNOWN; all anomalies retained; stop if capacity exhausted',
                        forensic_capture_budget_MiB_per_attempt=[1, 8],
                        forensic_capture_total_GiB=[1025 / 1024, 1025 * 8 / 1024],
                        new_base_tools_reservation_GiB=[3, 6], archive_scratch_reservation_GiB=2,
                        zstd_ratio_measured=False,
                        retained_seeded_overlays_zstd_scenarios_GiB={str(r):51 * overlay / 1024 * r for r in [0.1, 0.25, 1.0]},
                        largest_family_conservative_peak_GiB=6 + 198 * 61.75 / 1024 + 198 * (8 + raw) / 1024 + 2,
                        zstd_scenarios_are_not_pilot_measurements=True))
(P / 'RESOURCE_ESTIMATES.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({k:v for k,v in report.items() if k not in ['families','assumptions_seconds_per_attempt','disk']},indent=2))
print(json.dumps(report['disk'],indent=2))
