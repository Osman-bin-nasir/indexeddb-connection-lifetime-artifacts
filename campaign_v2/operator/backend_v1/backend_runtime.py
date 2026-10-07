"""Explicit operator provenance and verified helper deployment. No acquisition on import."""
import hashlib,json,shlex
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
ENGINE=Path(__file__).parent/'engine'
RUN_ROLE=None
ATTEMPT_RELATIVE=None

def configure(role):
 global RUN_ROLE,ATTEMPT_RELATIVE
 if role not in ['qualification','scientific']:raise RuntimeError('Unknown execution role')
 if RUN_ROLE is not None:raise RuntimeError('One attempt per backend process')
 RUN_ROLE=role;ATTEMPT_RELATIVE='qualification/attempts' if role=='qualification' else 'scientific/attempts'
def attempt_root():
 if RUN_ROLE is None:raise RuntimeError('Explicit role not configured')
 return ROOT/ATTEMPT_RELATIVE
def validate_reserved(out,a):
 out=Path(out);expected=attempt_root()/a['trial_id']
 if out.resolve()!=expected.resolve() or not out.is_dir():raise RuntimeError('Wrong reserved attempt directory')
 start=json.loads((out/'START.json').read_text())
 if a['role']!=RUN_ROLE or start['role']!=RUN_ROLE or start['scientific_denominator']!=(RUN_ROLE=='scientific') or start.get('engine_reserved') is not True:raise RuntimeError('Invalid operator reservation provenance')
 if (out/'ENGINE_START.json').exists() or (out/'RESULT.json').exists():raise RuntimeError('Consumed engine attempt, never retry')
def validate_assignment(out,a):
 if json.loads((Path(out)/'assignment.json').read_text())!=a:raise RuntimeError('Reserved immutable assignment differs')
def deploy_worker(remote,port,events):
 p=ENGINE/'guest_worker.py';data=p.read_bytes();expected=hashlib.sha256(data).hexdigest();path='/opt/idbv2/operator/guest_worker.py'
 # This additional source is written before prepare/write. Original pinned worker,
 # JS, browser, base image and earlier attempts remain untouched.
 response=remote(port,'sudo mkdir -p /opt/idbv2/operator && sudo tee '+shlex.quote(path)+' >/dev/null',input=data)
 actual=remote(port,'sha256sum '+shlex.quote(path)).stdout.decode().split()[0]
 if actual!=expected:raise RuntimeError('Additional worker transfer hash mismatch')
 events('OPERATOR_WORKER_DEPLOYED',path=path,sha256=actual,role=RUN_ROLE,original_worker_unchanged=True,before_target=True)
