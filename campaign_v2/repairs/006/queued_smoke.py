"""Bounded once-only wait, then one prospectively documented excluded smoke."""
import datetime,json,os,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];ADMIN=Path(__file__).parent
sys.path.insert(0,str(ROOT))
from provision_vm import save,sha,disk_check

def main():
 if (ADMIN/'QUEUED_SMOKE_CONSUMED.json').exists():raise RuntimeError('Queued support supervisor consumed')
 save(ADMIN/'QUEUED_SMOKE_CONSUMED.json',{'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'maximum_qualification_attempts':1,'scientific_acquisition':False})
 until=time.monotonic()+3600
 while True:
  for n,h in json.loads((ADMIN/'EXECUTION_SOURCE_HASHES.json').read_text()).items():
   if sha(ADMIN/n)!=h:raise RuntimeError('Prospective smoke source changed')
  disk_check(3*1024**3)
  stop=ROOT/'extensions/workloads/STOP_V3.json'
  if stop.exists():
   outcome=json.loads(stop.read_text());status=json.loads((stop.parent/'STATUS_V3.json').read_text())
   if outcome['failure'] or status['independently_passed']!=12:raise RuntimeError('Preceding workload batch did not qualify; no fresh SIGKILL attempt')
   break
  if time.monotonic()>until:raise RuntimeError('Bounded wait elapsed; no qualification started')
  time.sleep(30)
 with __import__('socket').socket() as s:s.bind(('127.0.0.1',2233))
 save(ADMIN/'QUEUED_SMOKE_GATE.json',{'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'workload_independent_passes':12,'command':[sys.executable,str(ADMIN/'full_path_smoke.py')],'scientific_started':0})
 completed=subprocess.run([sys.executable,str(ADMIN/'full_path_smoke.py')],cwd=ROOT.parent)
 save(ADMIN/'QUEUED_SMOKE_STOP.json',{'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'returncode':completed.returncode,'scientific_started':0,'no_retry':True})
 raise SystemExit(completed.returncode)
if __name__=='__main__':main()
