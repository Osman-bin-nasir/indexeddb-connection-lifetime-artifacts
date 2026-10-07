"""Frozen paper3v2_mechanism_b1 population: 16 traced main slots.

Experiment B1 traces the SQLite relaxed step found in paper3v2:
    SQLite relaxed 2.00 s, traced   8 trials
    SQLite relaxed 2.25 s, traced   8 trials
Traced trials are a separate population and are never pooled with any untraced
paper3v2 or paper3v2_mechanism cell.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent.parent
TRACING_HELPERS = ('guest_observer.py', 'trace_b1.bt', 'tracing.py')
IDENTITY = json.loads((ROOT / 'support' / 'identity.json').read_text())
EXPERIMENT = IDENTITY['experiment_id']
ORDER = json.loads((ROOT / 'support' / 'order.json').read_text())
SEED = ORDER['seed']
SLOTS = tuple(ORDER['slots'])
MAIN = tuple(s for s in SLOTS if s['role'] == 'main')
SANITY = tuple(s for s in SLOTS if s['role'] == 'sanity')
PROFILE_ROOT = '/var/lib/browser-storage-research/profiles/chromium'
FRONTEND_DIR = PROJECT / 'paper2' / 'backend_sync_trace_01' / 'frontend'
TRACE_TIMEOUT_S = 20

assert len(SLOTS) == 16 and len(MAIN) == 16 and len(SANITY) == 0
assert len({s['trial_id'] for s in SLOTS}) == 16
assert all(s['role'] == 'main' for s in SLOTS)
assert all(s['backend'] == 'sqlite' and s['mode'] == 'relaxed' and s['action'] == 'reset'
           and not s['held'] and not s['probe'] for s in SLOTS)
assert all(s['traced'] is True for s in SLOTS)
assert all(s['ordinal'] == index for index, s in enumerate(SLOTS, 1))

CELLS = {}
for slot in SLOTS:
    CELLS[slot['delay_s']] = CELLS.get(slot['delay_s'], 0) + 1
assert CELLS == {2.0: 8, 2.25: 8}


def profile(slot):
    return f"{PROFILE_ROOT}/review-backend-{slot['backend']}-v1"


def indexeddb_dir(slot):
    return f"{profile(slot)}/Default/IndexedDB"


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def tracing_pipeline_sha256():
    """One digest over the strace/eBPF/cachestat pipeline source that runs per trial."""
    digest = hashlib.sha256()
    for name in TRACING_HELPERS:
        digest.update(f'{name} {sha(ROOT / name)}\n'.encode())
    return digest.hexdigest()
