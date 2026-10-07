"""Separate guest workload stream, preserving incomplete operations after the reset."""
from backend_runtime import RUN_ROLE, ENGINE, ATTEMPT_RELATIVE, attempt_root, validate_reserved, validate_assignment, deploy_worker
import json, shlex, subprocess, threading, time
from pathlib import Path

class Background:

    def __init__(self, ssh, port, profile, out, events):
        self.events = events
        self.values = []
        self.condition = threading.Condition()
        self.stderr = (out / 'background.stderr').open('xb')
        source = Path(__file__).with_name('guest_background.py').read_text()
        self.proc = subprocess.Popen(ssh(port) + ['python3 -u -c ' + shlex.quote(source)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.stderr)
        self.thread = threading.Thread(target=self.read, daemon=True)
        self.thread.start()
        self.proc.stdin.write((json.dumps({'role': 'qualification', 'profile': profile}) + '\n').encode())
        self.proc.stdin.flush()
        end = time.monotonic() + 10
        try:
            with self.condition:
                while not any((x['background']['kind'] == 'BACKGROUND_OPERATION_COMPLETE' for x in self.values)):
                    if self.proc.poll() is not None and (not self.thread.is_alive()):
                        raise RuntimeError('Background workload failed before first fsync')
                    if time.monotonic() > end:
                        raise RuntimeError('Background workload did not qualify startup')
                    self.condition.wait(0.05)
        except Exception:
            self.close()
            raise

    def read(self):
        for line in self.proc.stdout:
            received = time.monotonic_ns()
            try:
                x = json.loads(line)
            except json.JSONDecodeError:
                self.events('BACKGROUND_NON_JSON', raw=line.decode(errors='replace'))
                continue
            r = self.events('BACKGROUND_RECORD', background=x, receipt_ns=received)
            with self.condition:
                self.values.append(r)
                self.condition.notify_all()
        with self.condition:
            self.condition.notify_all()

    def close(self):
        if self.proc.poll() is None:
            self.proc.terminate()
            self.proc.wait(timeout=5)
        self.thread.join(timeout=5)
        self.stderr.close()
