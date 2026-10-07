"""Classify observed block events with conservative clock and pause brackets, never exact callback attribution."""
from backend_runtime import RUN_ROLE, ENGINE, ATTEMPT_RELATIVE, attempt_root, validate_reserved, validate_assignment, deploy_worker

def windows(raw, samples, fault):
    bounds = [(x['host_send_ns'] - x['guest']['guest_after_ns'], x['host_receive_ns'] - x['guest']['guest_before_ns']) for x in samples]
    lo = max((x[0] for x in bounds))
    hi = min((x[1] for x in bounds))
    if lo > hi:
        raise RuntimeError('Contradictory host/guest clock brackets')
    events = []
    for line in raw.splitlines():
        if not line.startswith('BLOCK '):
            continue
        p = line.split()
        if len(p) != 8:
            raise RuntimeError('Malformed block event')
        ns = int(p[1])
        earliest = ns + lo
        latest = ns + hi
        classification = 'before_boundary' if latest < fault['fault']['dispatch_ns'] else 'after_quiesce_reply' if earliest > fault['host_monotonic_ns'] else 'within_boundary_uncertainty'
        events.append({'guest_ns': ns, 'tid': int(p[2]), 'layer': p[3], 'kernel_dev_t': int(p[4]), 'sector': int(p[5]), 'sectors': int(p[6]), 'rwbs': p[7], 'host_earliest_ns': earliest, 'host_latest_ns': latest, 'boundary_classification': classification})
    return {'offset_bracket_ns': [lo, hi], 'pause_bracket_host_ns': [fault['fault']['dispatch_ns'], fault['host_monotonic_ns']], 'events': events, 'capture_completed_by_graceful_drain_after_immutable_snapshot': True, 'diagnostic_continuation_excluded_from_captured_block_state': True, 'loss_absence_requires_clear_diagnostics_and_end': True, 'callback_attribution': 'not established'}
