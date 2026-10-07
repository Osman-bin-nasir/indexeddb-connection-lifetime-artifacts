"""Reconstruct registered dependent log-writes prefixes on fresh derivatives. Original capture is never modified."""
from backend_runtime import RUN_ROLE, ENGINE, ATTEMPT_RELATIVE, attempt_root, validate_reserved, validate_assignment, deploy_worker
import json, shlex, subprocess, time
from pathlib import Path
from provision_vm import save, sha
from log_decode import decode
from forensic_formats import inspect

def apply(log, meta, destination, last):
    if Path(destination).exists():
        raise RuntimeError('Existing replay destination, no overwrite')
    subprocess.run(['qemu-img', 'create', '-f', 'raw', str(destination), '1G'], check=True, capture_output=True)
    with Path(log).open('rb') as source, Path(destination).open('r+b') as out:
        for e in meta['entries'][:last + 1]:
            if not e['bytes']:
                continue
            offset = e['sector'] * meta['sector_size']
            if offset + e['bytes'] > 1024 ** 3:
                raise RuntimeError('Out-of-volume log entry')
            if e['flags'] & 4:
                out.seek(offset)
                remaining = e['bytes']
                while remaining:
                    size = min(1024 ** 2, remaining)
                    if out.read(size) != bytes(size):
                        raise RuntimeError('Nonzero discard extent requires additional qualification')
                    remaining -= size
                continue
            source.seek(e['data_offset'])
            data = source.read(e['bytes'])
            if len(data) != e['bytes']:
                raise RuntimeError('Truncated log payload')
            out.seek(offset)
            out.write(data)
        out.flush()

def prefixes(host, worker_host, root, log, profile, spec, identity, out, events, *, root_sha256):
    folder = Path(out) / 'log-prefixes'
    folder.mkdir(exist_ok=False)
    raw = folder / 'original-log.raw'
    before = sha(log)
    subprocess.run(['qemu-img', 'convert', '-f', 'qcow2', '-O', 'raw', str(log), str(raw)], check=True, capture_output=True)
    raw.chmod(292)
    meta = decode(raw)
    save(folder / 'LOG_DECODE.json', meta)
    ack = [e['ordinal'] for e in meta['entries'] if e['mark'] == 'registered-ack']
    if len(ack) != 1 or ack[0] < 1 or meta['last_fully_recorded_entry'] < ack[0]:
        raise RuntimeError('ACK/boundary prefix unrecorded')
    boundaries = [('immediately_before_ack_marker', ack[0] - 1), ('at_ack_marker', ack[0]), ('last_fully_recorded_before_boundary', meta['last_fully_recorded_entry'])]
    rows = []
    old_args = host.vm_args
    for name, last in boundaries:
        place = folder / name
        place.mkdir()
        image = place / 'replayed-data.raw'
        apply(raw, meta, image, last)
        image.chmod(292)
        image_sha = sha(image)
        vm = worker = None
        data = place / 'data-recovery.qcow2'
        boot = place / 'root-recovery.qcow2'
        subprocess.run(['qemu-img', 'create', '-f', 'qcow2', '-F', 'raw', '-b', str(image), str(data)], capture_output=True, check=True)
        subprocess.run(['qemu-img', 'create', '-f', 'qcow2', '-F', 'qcow2', '-b', str(root), str(boot)], capture_output=True, check=True)

        def args(*a, **kw):
            argv = old_args(*a, **kw)
            memory = kw.get('memory', a[4] if len(a) > 4 else 6144)
            if memory == 6144:
                argv += ['-device', 'pcie-root-port,id=prefix-port,slot=2,chassis=2', '-drive', f'file={data},if=none,id=prefix-drive,format=qcow2,cache=none', '-device', 'virtio-blk-pci,drive=prefix-drive,serial=idbv2-data,bus=prefix-port']
            return argv
        try:
            host.vm_args = args
            vm = host.VM(boot, place / 'boot', 2233, 'prefix-' + str(time.monotonic_ns()), events)
            r = host.remote(vm.port, 'sudo mount -t ext4 /dev/vdc /var/lib/idbv2', check=False)
            (place / 'mount.stdout').write_bytes(r.stdout)
            (place / 'mount.stderr').write_bytes(r.stderr)
            save(place / 'MOUNT_RESPONSE.json', {'returncode': r.returncode})
            if r.returncode:
                raise RuntimeError('Registered prefix filesystem unavailable')
            actual = json.loads(host.remote(vm.port, 'cat /opt/idbv2/attempt.json').stdout)
            if actual != identity:
                raise RuntimeError('Wrong prefix root/attempt identity')
            worker = worker_host.Worker(vm, spec, place, events, recovery=True)
            oracle = worker.command('oracle')
            save(place / 'ORACLE.json', oracle)
            endpoint = oracle['guest']['endpoint']
            if endpoint not in ['recovered', 'lost']:
                raise RuntimeError('Registered prefix oracle unknown/integrity failure')
            rows.append({'name': name, 'last_entry': last, 'endpoint': endpoint, 'oracle_path': str((place / 'ORACLE.json').relative_to(out)), 'replayed_raw_sha256': image_sha, 'dependent_within_capture': True, 'scientific_trial_count': 0, 'prefix_includes_ack_marker': last >= ack[0], 'not_acknowledged_loss_if_pre_ack': name == 'immediately_before_ack_marker'})
        finally:
            if worker:
                worker.close()
            if vm:
                vm.quit()
            host.vm_args = old_args
        if sha(image) != image_sha or sha(root) != root_sha256 or sha(log) != before:
            raise RuntimeError('Immutable replay source changed')
    return {'raw_log_sha256': sha(raw), 'original_log_qcow2_sha256': before, 'all_prefixes_interpretable': len(rows) == 3, 'prefixes': rows, 'entries_fully_decoded': meta['fully_decoded_entries'], 'declared_entries': meta['declared_entries'], 'prefixes_not_trials': True, 'last_fully_recorded_prefix_uses_captured_log_header': True, 'host_ack_marker_chronology_and_uncertainty_disclosed': True, 'unrecorded_prefixes_not_inferred': True}
