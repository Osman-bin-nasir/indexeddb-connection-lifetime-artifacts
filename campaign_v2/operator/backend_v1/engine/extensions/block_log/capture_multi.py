"""Quiesced multi-disk external snapshots. Diagnostic continuation writes only to throwaway overlays."""
from backend_runtime import RUN_ROLE, ENGINE, ATTEMPT_RELATIVE, attempt_root, validate_reserved, validate_assignment, deploy_worker
import time
from pathlib import Path
from provision_vm import save, sha

def capture(vm, images, out, events):
    if vm.qmp.execute('query-status')['return']['status'] != 'paused':
        raise RuntimeError('Multi-disk capture requires assigned pause')
    blocks = vm.qmp.execute('query-block')['return']
    selected = []
    actions = []
    for label, source in images.items():
        source = Path(source)
        matches = [b for b in blocks if b.get('inserted', {}).get('file') == str(source)]
        if len(matches) != 1 or not matches[0].get('device'):
            raise RuntimeError('Cannot identify one writable block backend ' + label)
        b = matches[0]
        target = Path(out) / ('throwaway-after-boundary-' + label + '.qcow2')
        if target.exists():
            raise RuntimeError('Snapshot target already exists')
        selected.append((label, source, b, target))
        actions.append({'type': 'blockdev-snapshot-sync', 'data': {'device': b['device'], 'snapshot-file': str(target), 'format': 'qcow2', 'mode': 'absolute-paths'}})
    before = time.monotonic_ns()
    result = vm.qmp.execute('transaction', {'actions': actions})
    after = time.monotonic_ns()
    changed = vm.qmp.execute('query-block')['return']
    nodes = vm.qmp.execute('query-named-block-nodes')['return']
    views = {}
    for label, source, b, target in selected:
        active = [x for x in changed if x['device'] == b['device']]
        old = [x for x in nodes if x.get('node-name') == b['inserted']['node-name']]
        if len(active) != 1 or active[0]['inserted']['file'] != str(target) or len(old) != 1 or (old[0].get('ro') is not True):
            raise RuntimeError('Source not frozen/read-only after transaction ' + label)
        source.chmod(292)
        views[label] = {'source': str(source), 'sha256': sha(source), 'source_node_read_only': True, 'throwaway_after_boundary': str(target), 'query_block_after': active[0], 'original_node_after': old[0]}
    receipt = {'views': views, 'transaction': result, 'snapshot_start_host_ns': before, 'snapshot_return_host_ns': after, 'guest_paused_through_snapshot': True, 'oracle_started': False, 'diagnostic_continuation_on_throwaways_only': True, 'original_boot_id': vm.boot, 'original_qemu_pid': vm.proc.pid, 'boundary_uncertainty_disclosed': True}
    save(Path(out) / 'MULTI_DISK_CAPTURE.json', receipt)
    events('IMMUTABLE_MULTI_DISK_CAPTURE', capture=receipt)
    return receipt
