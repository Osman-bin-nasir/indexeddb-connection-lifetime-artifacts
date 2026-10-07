"""Candidate identity I/O repair. Not a qualified campaign input."""
from backend_runtime import RUN_ROLE, ENGINE, ATTEMPT_RELATIVE, attempt_root, validate_reserved, validate_assignment, deploy_worker
import json
import shlex
from pathlib import Path
GUEST_WRITE = "import json,os,pathlib,sys\nraw=sys.stdin.buffer.read()\nidentity=json.loads(raw)\nif not isinstance(identity,dict):raise ValueError('Identity must be an object')\npath=pathlib.Path('/opt/idbv2/attempt.json')\nfd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o644)\ntry:\n with os.fdopen(fd,'wb') as f:\n  f.write(raw);f.flush();os.fsync(f.fileno())\n directory=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)\n try:os.fsync(directory)\n finally:os.close(directory)\n print(json.dumps({'identity':json.loads(path.read_bytes()),'file_fsync_completed':True,'directory_fsync_completed':True}))\nexcept Exception:\n # Preserve partial setup evidence. Do not retry or overwrite.\n raise\n"

def retain_response(out, phase, response):
    out = Path(out)
    for suffix, raw in [('stdout', response.stdout), ('stderr', response.stderr)]:
        with (out / (phase + '.' + suffix)).open('xb') as f:
            f.write(raw)
    with (out / (phase + '.response.json')).open('x') as f:
        json.dump({'returncode': response.returncode, 'stdout_bytes': len(response.stdout), 'stderr_bytes': len(response.stderr)}, f, indent=2)
    if response.returncode:
        raise RuntimeError(phase + ': command failed; response retained')

def read_identity(remote, port, expected, out, phase):
    response = remote(port, 'cat /opt/idbv2/attempt.json', check=False)
    retain_response(out, phase, response)
    try:
        observed = json.loads(response.stdout)
    except (ValueError, UnicodeDecodeError) as e:
        raise RuntimeError(phase + ': unreadable identity JSON; response retained') from e
    if observed != expected:
        raise RuntimeError(phase + ': identity mismatch; response retained')
    return observed

def write_identity(remote, port, identity, out):
    response = remote(port, 'sudo python3 -c ' + shlex.quote(GUEST_WRITE), input=json.dumps(identity).encode(), check=False)
    retain_response(out, 'identity-setup', response)
    value = json.loads(response.stdout)
    if value.get('identity') != identity or value.get('file_fsync_completed') is not True or value.get('directory_fsync_completed') is not True:
        raise RuntimeError('Identity setup receipt invalid; response retained')
    return read_identity(remote, port, identity, out, 'identity-before-worker')
