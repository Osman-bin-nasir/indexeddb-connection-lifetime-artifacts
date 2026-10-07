"""Exact scientific executable pins, derived from the unchanged final lock.

Qualification sources and audits remain preserved. No observed hash, fallback
path, or qualification-worker alias is an accepted scientific executable pin.
"""
import hashlib
import json
from pathlib import Path

VERSION = 'scientific-worker-pin-audit-v1.0.0'
CAMPAIGN = Path(__file__).resolve().parents[2]
FINAL_LOCK_SHA256 = '6b41534b91721debdfb664cf0296e22c32ac5debc22f345df75ef41914f00798'
WORKER_SOURCE = 'operator/backend_v1/engine/guest_worker.py'
TRACE_SOURCE = 'operator/backend_v1/engine/repairs/011/guest_worker_trace.py'
WORKER_PATH = '/opt/idbv2/operator/guest_worker.py'
TRACE_PATH = '/opt/idbv2/trace-worker.py'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def frozen_pins():
    lock_path = CAMPAIGN / 'operator/FINAL_INPUT_LOCK.json'
    if sha(lock_path) != FINAL_LOCK_SHA256:
        raise RuntimeError('Original final scientific input lock changed')
    lock = json.loads(lock_path.read_text())
    pins = {}
    for name in [WORKER_SOURCE, TRACE_SOURCE]:
        expected = lock['input_hashes'][name]
        source = CAMPAIGN / name
        if source.is_symlink() or sha(source) != expected:
            raise RuntimeError('Frozen scientific executable source changed: ' + name)
        pins[name] = expected
    return pins


def expected_events(family):
    pins = frozen_pins()
    worker = (WORKER_PATH, pins[WORKER_SOURCE])
    if family == 'target_byte_diagnostics':
        return [(False, *worker), (True, *worker)]
    if family == 'trace_category_timelines':
        return [(False, TRACE_PATH, pins[TRACE_SOURCE]), (True, *worker)]
    raise RuntimeError('Worker-pin correction does not cover family ' + family)


def verify_worker_events(events, family):
    expected = expected_events(family)
    actual = [item for item in events if item.get('kind') == 'WORKER_EXECUTABLE_SOURCE']
    if len(actual) != 2:
        return False
    return all(item.get('recovery') is recovery
               and item.get('path') == path
               and item.get('sha256') == digest
               for item, (recovery, path, digest) in zip(actual, expected))
