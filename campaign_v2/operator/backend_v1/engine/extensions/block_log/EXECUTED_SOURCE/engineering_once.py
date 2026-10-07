"""One neutral log-writes/ext4 prefix engineering test. No scientific/qualification assignment or endpoint."""
from backend_runtime import RUN_ROLE, ENGINE, ATTEMPT_RELATIVE, attempt_root, validate_reserved, validate_assignment, deploy_worker
import datetime, json, shlex, subprocess, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[5]
HERE = Path(__file__).parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ENGINE / 'extensions/environment'))
import qualification_environment as host
sys.path.insert(0, str(HERE))
from provision_vm import gate, disk_check, save, sha
from capture_multi import capture
from log_decode import decode
from log_prefixes import apply

def main():
    gate()
    host.verify_frozen_base()
    disk_check(3 * 1024 ** 3)
    plan = json.loads((HERE / 'SUPPORT_PLAN_001.json').read_text())
    for n, h in plan['source_hashes'].items():
        if sha(ROOT / n) != h:
            raise RuntimeError('Declared support source changed ' + n)
    if subprocess.run(['pgrep', '-f', 'qemu-system-aarch64'], capture_output=True).returncode == 0:
        raise RuntimeError('Another VM active; no support consumed')
    out = ROOT / 'support/block_log' / plan['support_id']
    out.mkdir(parents=True, exist_ok=False)
    save(out / 'START.json', {'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'role': 'support_only', 'scientific_denominator': False, 'no_browser_target_or_assigned_fault': True, 'plan': plan})
    events = host.Events(out / 'events.jsonl')
    vm = None
    error = None
    passed = False
    oldargs = host.vm_args
    active_data = active_log = None
    try:
        root = out / 'root.qcow2'
        data = out / 'data.qcow2'
        log = out / 'log.qcow2'
        active_data = data
        active_log = log
        subprocess.run(['qemu-img', 'create', '-f', 'qcow2', '-F', 'qcow2', '-b', str(host.BASE), str(root)], check=True, capture_output=True)
        for p in [data, log]:
            subprocess.run(['qemu-img', 'create', '-f', 'qcow2', str(p), '1G'], check=True, capture_output=True)
        save(out / 'BLANK_INPUT_HASHES.json', {'data_sha256': sha(data), 'log_sha256': sha(log), 'size_bytes': 1024 ** 3, 'zero_baseline_by_fresh_qemu_create': True})

        def args(*a, **kw):
            argv = oldargs(*a, **kw)
            for name, p, slot in [('data', active_data, 2), ('log', active_log, 4)]:
                if p is not None:
                    argv += ['-device', f'pcie-root-port,id={name}-port,slot={slot},chassis={slot}', '-drive', f'file={p},if=none,id={name}-drive,format=qcow2,cache=none', '-device', f'virtio-blk-pci,drive={name}-drive,serial=idbv2-{name},bus={name}-port']
            return argv
        host.vm_args = args
        vm = host.VM(root, out / 'boot', 2235, 'log-fs-support-' + str(time.monotonic_ns()), events, memory=1024)
        for name in ['guest_mapper_candidate.py', 'guest_neutral_filesystem.py']:
            host.remote(vm.port, 'cat > /tmp/' + name, input=(HERE / name).read_bytes())
        r = host.remote(vm.port, 'sudo python3 /tmp/guest_neutral_filesystem.py', timeout=120, check=False)
        (out / 'neutral.stdout').write_bytes(r.stdout)
        (out / 'neutral.stderr').write_bytes(r.stderr)
        save(out / 'NEUTRAL_RESPONSE.json', {'returncode': r.returncode})
        if r.returncode:
            raise RuntimeError('Neutral mapped ext4 path failed')
        vm.qmp.execute('stop')
        receipt = capture(vm, {'root': root, 'data': data, 'log': log}, out, events)
        vm.quit()
        vm = None
        raw = out / 'original-log.raw'
        subprocess.run(['qemu-img', 'convert', '-f', 'qcow2', '-O', 'raw', str(log), str(raw)], check=True, capture_output=True)
        raw.chmod(292)
        meta = decode(raw)
        save(out / 'LOG_DECODE.json', meta)
        marks = {e['mark']: e['ordinal'] for e in meta['entries'] if e['mark']}
        if not all((m in marks for m in ['registered-ack', 'neutral-end'])):
            raise RuntimeError('Neutral required markers unrecorded')
        bounds = [('immediately_before_ack_marker', marks['registered-ack'] - 1), ('at_ack_marker', marks['registered-ack']), ('last_fully_recorded_before_boundary', meta['last_fully_recorded_entry'])]
        observations = []
        active_log = None
        for name, last in bounds:
            place = out / name
            place.mkdir()
            replayed = place / 'replayed-data.raw'
            apply(raw, meta, replayed, last)
            replayed.chmod(292)
            initial = sha(replayed)
            clone = place / 'data-recovery.qcow2'
            subprocess.run(['qemu-img', 'create', '-f', 'qcow2', '-F', 'raw', '-b', str(replayed), str(clone)], check=True, capture_output=True)
            boot = place / 'root.qcow2'
            subprocess.run(['qemu-img', 'create', '-f', 'qcow2', '-F', 'qcow2', '-b', str(host.BASE), str(boot)], check=True, capture_output=True)
            active_data = clone
            vm = host.VM(boot, place / 'boot', 2235, 'log-prefix-support-' + str(time.monotonic_ns()), events, memory=1024)
            code = "import pathlib,subprocess,json\nsubprocess.run(['mount','-t','ext4','/dev/vdc','/var/lib/idbv2'],check=True)\np=pathlib.Path('/var/lib/idbv2');print(json.dumps({n:(p/n).read_bytes().hex() if (p/n).exists() else None for n in ['before-ack.bin','after-ack.bin']}))\n"
            r = host.remote(vm.port, 'sudo python3 -c ' + shlex.quote(code), check=False)
            (place / 'read.stdout').write_bytes(r.stdout)
            (place / 'read.stderr').write_bytes(r.stderr)
            save(place / 'READ_RESPONSE.json', {'returncode': r.returncode})
            if r.returncode:
                raise RuntimeError('Neutral prefix filesystem unavailable')
            observed = json.loads(r.stdout)
            expected = {'before-ack.bin': b'neutral-before-ack-exact-bytes'.hex(), 'after-ack.bin': b'neutral-after-ack-exact-bytes'.hex() if name == 'last_fully_recorded_before_boundary' else None}
            checks = {'neutral_bytes_match': observed == expected, 'source_hash_unchanged': sha(replayed) == initial}
            observations.append({'name': name, 'last_entry': last, 'checks': checks, 'observed': observed, 'replayed_source_sha256': initial})
            vm.quit()
            vm = None
            if not all(checks.values()):
                raise RuntimeError('Neutral prefix byte witness mismatch')
        passed = len(observations) == 3 and all((sha(Path(v['source'])) == v['sha256'] for v in receipt['views'].values()))
        save(out / 'SUPPORT_VERIFICATION.json', {'passed': passed, 'prefixes': observations, 'originals_unchanged': passed, 'registered_browser_prefixes_still_pending': True, 'scientific_started': 0, 'qualification_cells_passed': 0})
    except BaseException as e:
        error = repr(e)
        events('SUPPORT_ERROR', error=error)
    finally:
        if vm:
            vm.quit()
        host.vm_args = oldargs
        events.file.close()
        save(out / 'STOP.json', {'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'passed': passed, 'error': error, 'scientific_started': 0, 'qualification_cells_passed': 0, 'automatic_retry': False})
        save(out / 'SHA256.json', {str(p.relative_to(out)): sha(p) for p in out.rglob('*') if p.is_file()})
    if not passed:
        raise SystemExit(2)
if __name__ == '__main__':
    main()
