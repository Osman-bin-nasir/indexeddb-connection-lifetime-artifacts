"""Queue exactly one pinned support program behind one independently passed bounded qualification job."""
import datetime,hashlib,json,subprocess,time
from pathlib import Path
HERE=Path(__file__).parent;ROOT=HERE.parents[1]
def main():
 plan=json.loads((HERE/'QUEUE_SUPPORT_PLAN_001.json').read_text());start=datetime.datetime.now(datetime.timezone.utc).isoformat()
 with (HERE/'QUEUE_SUPPORT_CONSUMED_001.json').open('x') as f:json.dump({'utc':start,'maximum_support_attempts':1,'scientific_started':0},f,indent=2)
 result={'utc_start':start,'support_launched':False,'scientific_started':0,'automatic_retry':False};deadline=time.monotonic()+3600
 try:
  while time.monotonic()<deadline:
   p=ROOT/plan['prerequisite_stop']
   if p.exists():
    stop=json.loads(p.read_text())
    if not stop['passed']:raise RuntimeError('Prerequisite stopped, support not consumed')
    for name,expected in plan['source_hashes'].items():
     if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=expected:raise RuntimeError('Prospective queued support source changed '+name)
    result['support_launched']=True
    with (HERE/'SUPPORT_CONSOLE_001.txt').open('xb') as log:r=subprocess.run(['python3',str(HERE/'engineering_once.py')],stdout=log,stderr=subprocess.STDOUT)
    result['returncode']=r.returncode
    if r.returncode:raise RuntimeError('Once-only support failed; no retry')
    break
   time.sleep(10)
  else:raise RuntimeError('Prerequisite wait expired, support not consumed')
 except BaseException as e:result['error']=repr(e);raise
 finally:
  result['utc_stop']=datetime.datetime.now(datetime.timezone.utc).isoformat()
  with (HERE/'QUEUE_SUPPORT_STOP_001.json').open('x') as f:json.dump(result,f,indent=2);f.write('\n')
if __name__=='__main__':main()
