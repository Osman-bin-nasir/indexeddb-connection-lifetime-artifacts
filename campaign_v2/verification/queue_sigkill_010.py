"""Wait for the timeline job to end with an independent pass, then consume the bounded SIGKILL plan once."""
import datetime,json,subprocess,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];HERE=ROOT/'repairs/010'
def main():
 consumed=HERE/'QUEUED_JOB_010_CONSUMED.json'
 with consumed.open('x') as f:json.dump({'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scientific_started':0,'automatic_retry':False},f)
 end=time.monotonic()+3600
 while time.monotonic()<end:
  p=ROOT/'extensions/timelines/TIMELINE_QUALIFICATION_001_STOP.json'
  if p.exists():
   if not json.loads(p.read_text())['passed']:
    result={'started':False,'reason':'Timeline job failed; no next VM launch','scientific_started':0}
   else:
    r=subprocess.run(['python3',str(ROOT/'verification/run_qualification_job.py'),'--plan',str(HERE/'QUALIFICATION_PLAN_010.json')]);result={'started':True,'returncode':r.returncode,'scientific_started':0}
   (HERE/'QUEUED_JOB_010_STOP.json').write_text(json.dumps(result,indent=2)+'\n');return
  time.sleep(10)
 (HERE/'QUEUED_JOB_010_STOP.json').write_text(json.dumps({'started':False,'reason':'Prerequisite wait expired','scientific_started':0},indent=2)+'\n')
if __name__=='__main__':main()
