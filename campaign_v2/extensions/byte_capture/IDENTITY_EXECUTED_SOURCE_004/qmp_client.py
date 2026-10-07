"""QMP transport with timestamped requests, replies and asynchronous events."""
import json
import socket
import threading
import time


class QMP:
    def __init__(self, path, log):
        self.log = log
        self.sock = socket.socket(socket.AF_UNIX)
        self.sock.settimeout(10)
        self.sock.connect(str(path))
        self.file = self.sock.makefile('rb')
        self.lock = threading.Lock()
        self.next_id = 0
        self.record('greeting', json.loads(self.file.readline()))
        self.execute('qmp_capabilities')

    def record(self, direction, data):
        value = {'host_monotonic_ns': time.monotonic_ns(), 'direction': direction, 'data': data}
        self.log(value)
        return value

    def execute(self, command, arguments=None):
        with self.lock:
            self.next_id += 1
            data = {'execute': command, 'id': self.next_id}
            if arguments is not None:
                data['arguments'] = arguments
            before = time.monotonic_ns()
            self.record('request', data)
            self.sock.sendall(json.dumps(data).encode()+b'\r\n')
            written = time.monotonic_ns()
            while True:
                line = self.file.readline()
                if not line:
                    if command == 'quit':
                        return {'dispatch_ns': before, 'qmp_written_ns': written, 'eof': True}
                    raise RuntimeError('QMP EOF')
                reply = json.loads(line)
                self.record('receive', reply)
                if reply.get('id') == self.next_id:
                    if 'error' in reply:
                        raise RuntimeError(f'QMP {command}: {reply["error"]}')
                    return {'dispatch_ns': before, 'qmp_written_ns': written, 'return': reply.get('return')}

    def close(self):
        self.file.close()
        self.sock.close()
