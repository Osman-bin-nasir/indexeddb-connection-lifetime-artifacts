"""Bounded once-only supervisor, waits for independently qualified workloads."""
import datetime,json,subprocess,sys,time,socket
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];ADMIN=Path(__file__).parent
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ADMIN))
from provision_vm import save,sha,disk_check,gate
from qualification_fault_scope import assignments,verify_frozen_base

def stamp():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def preflight():
 for n,h in json.loads((ADMIN/'EXECUTION_SOURCE_HASHES.json').read_text()).items():
  if sha(ADMIN/n)!=h:raise RuntimeError('Prospective source changed: '+n)
 gate();verify_frozen_base();disk_check(3*1024**3)
 for line in (ROOT.parent/'confirmatory/SHA256SUMS').read_text().splitlines():
  h,n=line.split(maxsplit=1)
  if sha(ROOT.parent/'confirmatory'/n.strip())!=h:raise RuntimeError('Frozen design changed')
 tag=subprocess.check_output(['git','rev-parse','prereg-connection-lifetime-mac-v2^{}'],cwd=ROOT,text=True).strip()
 if tag!='5a749734a0a63f3e1c662bb91dd829e6f288dc5c':raise RuntimeError('Frozen tag changed')
 a=json.loads((ADMIN/'FULL_PATH_SMOKE_ASSIGNMENT.json').read_text())
 compare={k:v for k,v in a.items() if k not in ['original_qualification_id','technical_amendment_id','scientific_denominator']};compare['trial_id']=a['original_qualification_id']
 original=next(x for x in assignments() if x['trial_id']==compare['trial_id'])
 if compare!=original:raise RuntimeError('Registered condition changed')
 if (ROOT/'qualification/attempts'/a['trial_id']).exists():raise RuntimeError('Attempt consumed')
 return a

def main():
 a=preflight()
 if '--preflight' in sys.argv:print(json.dumps({'preflight':'passed','trial_id':a['trial_id'],'scientific_started':0,'queued_until_workload_pass':True}));return
 save(ADMIN/'QUEUED_SMOKE_CONSUMED.json',{'utc':stamp(),'maximum_qualification_attempts':1,'scientific_acquisition':False,'wait_limit_seconds':3600})
 until=time.monotonic()+3600
 try:
  while True:
   preflight();stop=ROOT/'repairs/007/QUALIFICATION_BATCH_STOP.json'
   if stop.exists():
    end=json.loads(stop.read_text());status=json.loads((stop.parent/'QUALIFICATION_BATCH_STATUS.json').read_text())
    if end['failure'] or status['independently_passed']!=11:raise RuntimeError('Workload batch did not qualify; no SIGKILL attempt')
    smoke=json.loads((stop.parent/'SMOKE_VERIFICATION.json').read_text())
    if not smoke['independent_pass']:raise RuntimeError('Workload smoke not qualified')
    break
   if time.monotonic()>until:raise RuntimeError('Bounded wait elapsed; no attempt started')
   time.sleep(30)
  for port in [2233,2234]:
   with socket.socket() as s:s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);s.bind(('127.0.0.1',port))
  save(ADMIN/'QUEUED_SMOKE_GATE.json',{'utc':stamp(),'workload_required_nonquiet_cells_qualified':12,'trial_id':a['trial_id'],'scientific_started':0})
  completed=subprocess.run([sys.executable,str(ADMIN/'full_path_smoke.py')],cwd=ROOT.parent)
  save(ADMIN/'QUEUED_SMOKE_STOP.json',{'utc':stamp(),'returncode':completed.returncode,'scientific_started':0,'automatic_retry':False})
  raise SystemExit(completed.returncode)
 except Exception as e:
  save(ADMIN/'QUEUED_SMOKE_STOP.json',{'utc':stamp(),'error':repr(e),'scientific_started':0,'automatic_retry':False});raise
if __name__=='__main__':main()
