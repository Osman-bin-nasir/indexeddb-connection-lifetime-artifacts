"""One bounded qualification continuation after an independently passing completed prerequisite."""
import argparse,datetime,json,subprocess,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--prerequisite',required=True,type=Path);ap.add_argument('--plan',required=True,type=Path);ap.add_argument('--receipt-prefix',required=True,type=Path);args=ap.parse_args()
 with Path(str(args.receipt_prefix)+'_CONSUMED.json').open('x') as f:json.dump({'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scientific_started':0,'automatic_retry':False},f)
 deadline=time.monotonic()+3600
 while time.monotonic()<deadline:
  if args.prerequisite.exists():
   value=json.loads(args.prerequisite.read_text())
   if not value['passed']:result={'started':False,'reason':'Prerequisite stopped without independent pass','scientific_started':0}
   else:
    r=subprocess.run(['python3',str(ROOT/'verification/run_qualification_job.py'),'--plan',str(args.plan)]);result={'started':True,'returncode':r.returncode,'scientific_started':0}
   Path(str(args.receipt_prefix)+'_STOP.json').write_text(json.dumps(result,indent=2)+'\n');return
  time.sleep(10)
 Path(str(args.receipt_prefix)+'_STOP.json').write_text(json.dumps({'started':False,'reason':'Prerequisite wait expired','scientific_started':0},indent=2)+'\n')
if __name__=='__main__':main()
