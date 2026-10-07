"""Isolated v2 provisioning. This module never runs a scientific assignment."""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import socket
import subprocess
import time

ROOT = Path(__file__).resolve().parent
VM = ROOT / 'provision/vm'
PRIVATE = ROOT / 'provision/private'
EVIDENCE = ROOT / 'provision/evidence'
RUNTIME = ROOT / 'provision/runtime'
BASE = ROOT / 'provision/downloads/ubuntu-24.04-server-cloudimg-arm64.img'
DISK = VM / 'provisioned.qcow2'
KEY = PRIVATE / 'v2_guest_ed25519'
SSH_PORT = 2232
QMP_DIR = Path('/tmp/idbv2-provision')
QMP = QMP_DIR / 'qmp.sock'
FROZEN_BASE_SHA = '1d6bffe64b848468ac97f821d369a4846d983de1800ccf6b5ec8853e85cefc55'


def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def save(path, data):
    with Path(path).open('x') as f:
        json.dump(data, f, indent=2)
        f.write('\n')


def run(args, **kw):
    return subprocess.run(args, check=True, **kw)


def disk_check(headroom=4 * 1024**3):
    free = shutil.disk_usage(ROOT).free
    if free - headroom < 6 * 1024**3:
        raise RuntimeError('DISK_STOP: projected headroom crosses the 6 GiB floor')
    return free


def gate():
    receipt = json.loads((ROOT / 'OSF_PACKAGE_VERIFICATION.json').read_text())
    if not receipt['download_round_trip_verified'] or not receipt['step_2_authorized_by_author']:
        raise RuntimeError('External-registration package gate has not been verified')
    if sha(ROOT.parent / 'confirmatory/PREREGISTRATION.md') != receipt['protocol_sha256']:
        raise RuntimeError('Frozen registration changed')
    if platform.system() != 'Darwin' or platform.machine() != 'arm64':
        raise RuntimeError('Registered Mac/ARM64 host required')


def ssh_args():
    return ['ssh', '-i', str(KEY), '-p', str(SSH_PORT),
            '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=accept-new',
            '-o', f'UserKnownHostsFile={PRIVATE / "known_hosts"}',
            '-o', 'ConnectTimeout=3', 'research@127.0.0.1']


def create():
    gate()
    disk_check()
    evidence = json.loads((EVIDENCE / 'BASE_IMAGE_VERIFICATION.json').read_text())
    if sha(BASE) != FROZEN_BASE_SHA or not evidence['signature_valid']:
        raise RuntimeError('Base image has not passed signed-checksum verification')
    for p in (VM, PRIVATE, EVIDENCE, RUNTIME, QMP_DIR):
        p.mkdir(parents=True, exist_ok=True)
    PRIVATE.chmod(0o700)
    QMP_DIR.chmod(0o700)
    if DISK.exists() or (VM / 'seed.iso').exists():
        raise RuntimeError('Refusing to overwrite provisioning disk/seed')
    if not KEY.exists():
        run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-C', 'idbv2-local-guest', '-f', str(KEY)])
    seed = PRIVATE / 'seed'
    seed.mkdir(exist_ok=False)
    pub = KEY.with_suffix('.pub').read_text().strip()
    (seed / 'user-data').write_text(
        '#cloud-config\nhostname: idbv2-qualification\nmanage_etc_hosts: true\n'
        'package_update: false\npackage_upgrade: false\nusers:\n'
        '  - name: research\n    groups: [adm, sudo]\n    sudo: ALL=(ALL) NOPASSWD:ALL\n'
        '    shell: /bin/bash\n    lock_passwd: true\n    ssh_authorized_keys:\n'
        f'      - {pub}\n')
    (seed / 'meta-data').write_text('instance-id: idbv2-provision-v1\nlocal-hostname: idbv2-qualification\n')
    run(['hdiutil', 'makehybrid', '-quiet', '-o', str(VM / 'seed.iso'), '-iso', '-joliet',
         '-default-volume-name', 'cidata', str(seed)])
    run(['qemu-img', 'create', '-f', 'qcow2', '-F', 'qcow2', '-b', str(BASE), str(DISK), '16G'])
    save(EVIDENCE / 'CREATE.json', {'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
         'role': 'provision_only', 'base_sha256': sha(BASE), 'seed_sha256': sha(VM / 'seed.iso'),
         'disk_initial_sha256': sha(DISK), 'original_pilot_vm_used': False,
         'disk_free_bytes': shutil.disk_usage(ROOT).free})


def start():
    gate()
    disk_check()
    if (RUNTIME / 'qemu.pid').exists():
        pid = int((RUNTIME / 'qemu.pid').read_text())
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            pass
        else:
            raise RuntimeError('Provisioning QEMU already running')
    with socket.socket() as s:
        s.bind(('127.0.0.1', SSH_PORT))
    if QMP.exists():
        raise RuntimeError('Existing QMP socket: inspect stale runtime before restart')
    args = ['qemu-system-aarch64', '-name', 'idbv2-provision-v1', '-machine', 'virt,accel=hvf',
            '-cpu', 'host', '-smp', '4', '-m', '6144',
            '-bios', '/opt/homebrew/share/qemu/edk2-aarch64-code.fd',
            '-drive', f'file={DISK},if=virtio,format=qcow2,cache=none',
            '-drive', f'file={VM / "seed.iso"},if=virtio,format=raw,readonly=on',
            '-device', 'virtio-net-pci,netdev=net0',
            '-netdev', f'user,id=net0,hostfwd=tcp:127.0.0.1:{SSH_PORT}-:22',
            '-qmp', f'unix:{QMP},server=on,wait=off', '-nographic']
    now = time.monotonic_ns()
    with (EVIDENCE / f'console-{now}.txt').open('xb') as console:
        proc = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=console,
                                stderr=subprocess.STDOUT, start_new_session=True)
    (RUNTIME / 'qemu.pid').write_text(str(proc.pid))
    save(EVIDENCE / f'BOOT-{now}.json', {'host_monotonic_ns': now, 'role': 'provision_only',
         'command': args, 'pid': proc.pid, 'scientific_assignment': None,
         'qualification_assignment': None, 'readiness_is_not_cell_qualification': True})
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f'QEMU exited {proc.returncode}')
        result = subprocess.run(ssh_args() + ['echo READY'], capture_output=True, timeout=10)
        if result.returncode == 0 and result.stdout.strip() == b'READY':
            save(EVIDENCE / f'SSH_READY-{now}.json', {'role': 'provision_only',
                 'host_monotonic_ns': time.monotonic_ns(), 'elapsed_s': (time.monotonic_ns()-now)/1e9})
            print('Provisioning guest SSH ready; no registered cell has been attempted', flush=True)
            return
        time.sleep(1)
    raise TimeoutError('Provisioning SSH not reachable within 180 seconds')


def install():
    gate()
    disk_check()
    now = time.monotonic_ns()
    script = ROOT / 'guest_packages.sh'
    with (EVIDENCE / f'packages-{now}.txt').open('xb') as log:
        result = subprocess.run(ssh_args() + ['bash -s'], input=script.read_bytes(),
                                stdout=log, stderr=subprocess.STDOUT, timeout=1800)
    save(EVIDENCE / f'PACKAGE_INSTALL-{now}.json', {'role': 'provision_only',
         'script_sha256': sha(script), 'returncode': result.returncode,
         'scientific_assignments_started': 0, 'qualification_assignments_started': 0})
    if result.returncode:
        raise RuntimeError('Package provisioning failed; see preserved package log')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('command', choices=['create', 'start', 'install', 'disk-check'])
    choice = ap.parse_args().command
    if choice == 'disk-check':
        print(json.dumps({'free_bytes': disk_check(0), 'floor_bytes': 6*1024**3}))
    else:
        {'create': create, 'start': start, 'install': install}[choice]()


if __name__ == '__main__':
    main()
