"""Headed guest measurement worker. Controller selects a registered qualification ID."""
from __future__ import annotations
import asyncio
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
import subprocess
import threading
import time
import uuid
from playwright.async_api import async_playwright
ROOT = Path('/opt/idbv2/worker')
EXE = Path('/opt/idbv2/browsers/chromium-1243/chrome-linux-arm64/chrome')
EXPECTED_EXE = '839efe5fd8b6a773dd81b2e10afdc15f3c0a17316fb82b5908c0533306c4ed9e'
sequence = 0
session = str(uuid.uuid4())

def emit(kind, **value):
    global sequence
    sequence += 1
    print(json.dumps({'sequence': sequence, 'kind': kind, 'guest_monotonic_ns': time.monotonic_ns(), 'guest_boot_ns': time.clock_gettime_ns(time.CLOCK_BOOTTIME), 'session': session, **value}), flush=True)

class LocalPage(BaseHTTPRequestHandler):

    def do_GET(self):
        if self.path == '/transaction.js':
            data = (ROOT / 'transaction.js').read_bytes()
            content_type = 'text/javascript'
        elif self.path == '/':
            data = b'<!doctype html><meta charset="utf-8"><title>v2 registered transaction</title><script src="/transaction.js"></script>'
            content_type = 'text/html'
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass

def backend_files(profile):
    result = []
    root = Path(profile) / 'Default/IndexedDB'
    for path in sorted(root.rglob('*')):
        if not path.is_file():
            continue
        with path.open('rb') as f:
            header = f.read(32)
        st = path.stat()
        result.append({'path': str(path.relative_to(profile)), 'bytes': st.st_size, 'inode': st.st_ino, 'device': st.st_dev, 'header_hex': header.hex(), 'sqlite_header': header.startswith(b'SQLite format 3\x00')})
    return result

async def main():
    config = json.loads(await asyncio.to_thread(sys.stdin.readline))
    if config['role'] not in ('qualification', 'scientific', 'scientific'):
        raise RuntimeError('This build-phase worker refuses scientific acquisition')
    profile = config['profile']
    if not str(profile).startswith('/var/lib/idbv2/'):
        raise RuntimeError('Dedicated v2 profile required')
    if hashlib.file_digest(EXE.open('rb'), 'sha256').hexdigest() != EXPECTED_EXE:
        raise RuntimeError('Wrong packaged Chromium executable')
    server = ThreadingHTTPServer(('127.0.0.1', 9090), LocalPage)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    async with async_playwright() as pw:
        args = ['--enable-features=IdbSqliteBackingStore', '--disable-background-networking', '--disable-component-update', '--disable-domain-reliability', '--disable-sync', '--no-first-run', '--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE localhost']
        context = await pw.chromium.launch_persistent_context(profile, executable_path=str(EXE), headless=False, viewport={'width': 1440, 'height': 1000}, args=args)
        page = context.pages[0]
        page.on('close', lambda: emit('PAGE_CLOSE'))
        page.on('crash', lambda: emit('PAGE_CRASH'))
        page.on('pageerror', lambda e: emit('PAGE_ERROR', error=str(e)))

        async def binding(source, event):
            emit('PAGE_EVENT', event=event)
        await page.expose_binding('recordEvent', binding)
        await page.goto('http://localhost:9090/', wait_until='load')

        async def telemetry():
            while True:
                state = await page.evaluate('window.v2.connectionState()')
                emit('CONNECTION_TELEMETRY', state=state)
                await asyncio.sleep(0.1)
        telemetry_task = asyncio.create_task(telemetry())
        emit('WORKER_READY', boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(), profile=profile, viewport={'width': 1440, 'height': 1000}, args=args, browser_version=subprocess.check_output([str(EXE), '--version'], text=True).strip())
        while True:
            line = await asyncio.to_thread(sys.stdin.readline)
            if not line:
                break
            item = json.loads(line)
            cmd = item['command']
            try:
                if cmd == 'clock':
                    before = time.monotonic_ns()
                    value = await page.evaluate('window.v2.clock()')
                    after = time.monotonic_ns()
                    value.update(guest_before_ns=before, guest_after_ns=after)
                elif cmd == 'prepare':
                    value = await page.evaluate('s=>window.v2.prepare(s)', config)
                    files = backend_files(profile)
                    if not any((f['sqlite_header'] for f in files)):
                        raise RuntimeError('SQLite backend not independently confirmed from file headers')
                    value = {'precondition_oracle': value, 'backend_files': files}
                elif cmd == 'write':
                    planned = config.get('planned_uptime_ms')
                    if planned is not None:
                        requested = int(planned) * 1000000
                        queued = time.clock_gettime_ns(time.CLOCK_BOOTTIME)
                        if queued >= requested:
                            raise RuntimeError('Scheduled target launch missed before queueing')
                        await asyncio.sleep((requested - queued) / 1000000000.0)
                        actual = time.clock_gettime_ns(time.CLOCK_BOOTTIME)
                        if actual < requested:
                            raise RuntimeError('Early scheduled target launch')
                        emit('SCHEDULED_TARGET_LAUNCH', planned_uptime_ms=planned, queue_uptime_ns=queued, actual_launch_uptime_ns=actual, interpretation='worker dispatch of target-write evaluation; actual transaction request and ACK retained separately')
                    value = await page.evaluate('s=>window.v2.write(s)', config)
                elif cmd == 'connection-state':
                    value = await page.evaluate('window.v2.connectionState()')
                elif cmd == 'oracle':
                    value = await page.evaluate('s=>window.v2.oracle(s)', config)
                elif cmd == 'trace-categories':
                    cdp = await context.new_cdp_session(page)
                    value = await cdp.send('Tracing.getCategories')
                elif cmd == 'exit':
                    await context.close()
                    emit('WORKER_EXIT', request_id=item['request_id'])
                    break
                else:
                    raise ValueError('Unknown command')
                emit('RESPONSE', request_id=item['request_id'], command=cmd, value=value, ok=True)
            except Exception as e:
                emit('RESPONSE', request_id=item['request_id'], command=cmd, ok=False, error=repr(e))
        telemetry_task.cancel()
        server.shutdown()
if __name__ == '__main__':
    asyncio.run(main())
