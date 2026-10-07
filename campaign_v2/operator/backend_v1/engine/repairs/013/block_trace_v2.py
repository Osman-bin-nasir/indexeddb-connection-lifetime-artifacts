"""Stream pinned BPF file identities to host. Reset boundary and possible undelivered tail remain disclosed."""
from backend_runtime import RUN_ROLE, ENGINE, ATTEMPT_RELATIVE, attempt_root, validate_reserved, validate_assignment, deploy_worker
import json, queue, shlex, subprocess, threading, time
from pathlib import Path
from provision_vm import save, sha

class BlockTrace:

    def __init__(self, host, vm, out, events):
        self.host = host
        self.vm = vm
        self.out = Path(out)
        self.events = events
        self.proc = None
        self.stderr = None
        self.thread = None
        self.pid = None
        script = Path(__file__).parent / 'block_trace_v2.bt'
        host.remote(vm.port, 'cat > /tmp/idbv2-file-identity.bt', input=script.read_bytes())
        actual = host.remote(vm.port, 'sha256sum /tmp/idbv2-file-identity.bt').stdout.decode().split()[0]
        if actual != sha(script):
            raise RuntimeError('Block trace source transfer mismatch')
        value = json.loads(host.remote(vm.port, 'python3 -c \'import os,json; s=os.stat("/var/lib/idbv2"); print(json.dumps({"major":os.major(s.st_dev),"minor":os.minor(s.st_dev)}))\'').stdout)
        dev = value['major'] << 20 | value['minor']
        save(self.out / 'BLOCK_TRACE_CONFIG.json', {'device': value, 'kernel_dev_t': dev, 'bpftrace_source_sha256': actual, 'ring_pages': 1024, 'no_guest_capture_log': True, 'tail_undelivered_at_reset_may_be_unknown': True, 'no_absence_inference': True})
        command = 'sudo bash -c ' + shlex.quote('echo $$ > /tmp/idbv2-bpf.pid; exec env BPFTRACE_PERF_RB_PAGES=1024 bpftrace -q /tmp/idbv2-file-identity.bt ' + str(dev))
        self.stderr = (self.out / 'block-trace.stderr').open('xb')
        self.proc = subprocess.Popen(host.ssh(vm.port) + [command], stdout=subprocess.PIPE, stderr=self.stderr)
        q = queue.Queue()
        log = (self.out / 'block-trace.raw').open('xb')

        def read():
            for line in self.proc.stdout:
                log.write(line)
                log.flush()
                q.put(line)
            log.close()
            q.put(None)
        self.thread = threading.Thread(target=read, daemon=True)
        self.thread.start()
        end = time.monotonic() + 30
        while time.monotonic() < end:
            item = q.get(timeout=max(0.1, end - time.monotonic()))
            if item == b'READY\n':
                break
            if item is None:
                raise RuntimeError('Block trace ended before READY')
        else:
            raise RuntimeError('Block trace readiness timeout')
        self.pid = int(host.remote(vm.port, 'cat /tmp/idbv2-bpf.pid').stdout)
        events('BLOCK_TRACE_READY', pid=self.pid, script_sha256=actual, device=value)

    def close(self, reset=False):
        if self.proc is None:
            return
        if self.proc.poll() is None:
            if not reset and self.pid:
                self.host.remote(self.vm.port, 'sudo kill -INT ' + str(self.pid), check=False)
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.terminate()
                self.proc.wait(timeout=10)
        self.thread.join(timeout=10)
        self.stderr.close()
        stderr = (self.out / 'block-trace.stderr').read_text()
        diagnostics = [l for l in stderr.splitlines() if not (reset and (l.startswith('Connection to 127.0.0.1 closed') or 'Connection reset by peer' in l or 'Broken pipe' in l))]
        save(self.out / 'BLOCK_TRACE_BOUNDARY.json', {'host_monotonic_ns': time.monotonic_ns(), 'reset_boundary': reset, 'returncode': self.proc.returncode, 'diagnostics': diagnostics, 'possible_undelivered_tail': 'unknown after abrupt reset' if reset else 'END observed if graceful', 'no_absence_inference': True, 'raw_sha256': sha(self.out / 'block-trace.raw')})
        self.proc = None
