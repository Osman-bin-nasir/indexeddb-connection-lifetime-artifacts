"""Wait for the bounded environment batch to finish, then run at most one excluded support test."""
import datetime,json,subprocess,time
from pathlib import Path
HERE=Path(__file__).parent;ROOT=HERE.parents[1]
def main():
 deadline=time.monotonic()+3*60*60
 while time.monotonic()<deadline:
  p=ROOT/'extensions/environment/QUALIFICATION_BATCH_STOP_002.json'
  if p.exists():
   v=json.loads(p.read_text())
   if not v['passed']:
    (HERE/'QUEUED_SUPPORT_STOP_001.json').write_text(json.dumps({'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'support_started':False,'reason':'Environment prerequisite stopped without pass','automatic_retry':False,'scientific_started':0},indent=2)+'\n');return
   result=subprocess.run(['python3',str(HERE/'engineering_once.py')])
   (HERE/'QUEUED_SUPPORT_STOP_001.json').write_text(json.dumps({'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'support_started':True,'returncode':result.returncode,'automatic_retry':False,'scientific_started':0},indent=2)+'\n');return
  time.sleep(30)
 (HERE/'QUEUED_SUPPORT_STOP_001.json').write_text(json.dumps({'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'support_started':False,'reason':'Prerequisite wait expired','automatic_retry':False,'scientific_started':0},indent=2)+'\n')
if __name__=='__main__':main()
