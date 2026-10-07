"""Frozen paper3v2_mechanism_c1 population: 16 traced main slots.

Experiment C1 is the connection-lifecycle discriminator for the SQLite relaxed
recovery step found in paper3v2 and traced by paper3v2_mechanism_b1:

    C1-control  (connection close allowed after ACK)   8 trials, 2.25 s
    C1-test     (connection close prevented after ACK) 8 trials, 2.25 s

Both conditions share the identical workload, the identical 2.25 s assigned
delay and the identical tracing pipeline; the only difference is the frozen
frontend's `connection=held` parameter. Traced trials are a separate population
and are never pooled with any untraced paper3v2 or paper3v2_mechanism cell, nor
with paper3v2_mechanism_b1.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent.parent
# `runner.py` is the file that selects the condition's workload (the
# `connection=held` URL parameter), so the pipeline digest covers it together
# with the three guest-side helpers.
TRACING_HELPERS = ('guest_observer.py', 'trace_b1.bt', 'trace_c1_uprobe.bt',
                   'tracing.py', 'runner.py')
WORKLOAD_FILE = 'runner.py'
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
ASSIGNED_DELAY_S = 2.25
CONTROL = 'C1-control'
TEST = 'C1-test'
CONDITIONS = (CONTROL, TEST)
CONDITION_TAG = {CONTROL: 'control', TEST: 'test'}

assert len(SLOTS) == 16 and len(MAIN) == 16 and len(SANITY) == 0
assert len({s['trial_id'] for s in SLOTS}) == 16
assert all(s['role'] == 'main' for s in SLOTS)
assert all(s['backend'] == 'sqlite' and s['mode'] == 'relaxed' and s['action'] == 'reset'
           and not s['probe'] for s in SLOTS)
assert all(s['traced'] is True for s in SLOTS)
assert all(s['delay_s'] == ASSIGNED_DELAY_S for s in SLOTS)
assert all(s['held'] == (s['condition'] == TEST) for s in SLOTS)
assert all(s['condition'] in CONDITIONS for s in SLOTS)
assert all(s['ordinal'] == index for index, s in enumerate(SLOTS, 1))

CELLS = {}
for slot in SLOTS:
    CELLS[slot['condition']] = CELLS.get(slot['condition'], 0) + 1
assert CELLS == {CONTROL: 8, TEST: 8}, CELLS


def condition(slot):
    return slot['condition']


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
    """One digest over the strace/eBPF/cachestat/uprobe pipeline that runs per trial.

    Includes `runner.py` because it is the modified workload file (it selects the
    condition's `connection=held` URL parameter).
    """
    digest = hashlib.sha256()
    for name in TRACING_HELPERS:
        digest.update(f'{name} {sha(ROOT / name)}\n'.encode())
    return digest.hexdigest()
