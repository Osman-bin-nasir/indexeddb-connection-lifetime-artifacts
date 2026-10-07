"""Loopback-only host socket regression, no guest or experiment assignment."""
from backend_runtime import RUN_ROLE, ENGINE, ATTEMPT_RELATIVE, attempt_root, validate_reserved, validate_assignment, deploy_worker
import datetime, json, socket, pathlib

def bind_result(port, reuse):
    with socket.socket() as probe:
        if reuse:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind(('127.0.0.1', port))
            return {'bound': True, 'errno': None}
        except OSError as e:
            return {'bound': False, 'errno': e.errno, 'error': str(e)}

def main():
    out = pathlib.Path(__file__).resolve().parents[2] / 'support/host_port/support-port-reuse-20261004-00001'
    out.mkdir(parents=True, exist_ok=False)
    server = socket.socket()
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('127.0.0.1', 0))
    port = server.getsockname()[1]
    server.listen(1)
    live = bind_result(port, True)
    client = socket.socket()
    client.connect(('127.0.0.1', port))
    accepted, _ = server.accept()
    accepted.shutdown(socket.SHUT_WR)
    assert client.recv(1) == b''
    client.close()
    accepted.close()
    server.close()
    plain = bind_result(port, False)
    reuse = bind_result(port, True)
    report = {'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'role': 'engineering_support', 'port': port, 'live_listener_reuse_probe': live, 'closed_listener_plain_probe': plain, 'closed_listener_reuse_probe': reuse, 'passed': not live['bound'] and reuse['bound'], 'scientific_started': 0, 'qualification_started': 0, 'loopback_only': True}
    (out / 'VERIFICATION.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    if not report['passed']:
        raise SystemExit(2)
if __name__ == '__main__':
    main()
