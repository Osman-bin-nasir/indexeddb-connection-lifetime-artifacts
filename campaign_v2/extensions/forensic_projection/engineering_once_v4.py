"""Exactly one fresh excluded forensic support attempt; never reclassifies its source attempt."""
import datetime,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).parent
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'repairs/009'))
import qualification_fault_scope as host
from provision_vm import save,sha,gate,disk_check
from projection_v4 import extract

def main():
 gate();host.verify_frozen_base();disk_check(3*1024**3)
 plan=json.loads((HERE/'SUPPORT_PLAN_004.json').read_text())
 for n,h in plan['source_hashes'].items():
  if sha(ROOT/n)!=h:raise RuntimeError('Prospective source changed '+n)
 source=Path(plan['source_image']);expected=plan['source_sha256']
 if sha(source)!=expected:raise RuntimeError('Preserved source hash changed')
 out=ROOT/'support/forensic_projection'/plan['support_id'];out.mkdir(parents=True,exist_ok=False)
 save(out/'START.json',{'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'role':'support_only','scientific_denominator':False,'no_new_target_or_fault':True,'qualification_cells_passed':0,'plan':plan})
 events=host.Events(out/'events.jsonl');passed=False;error=None
 try:
  receipt=extract(host,source,plan['profile'],out/'projection',events,original_expected_sha256=expected)
  passed=receipt['files']>0 and sha(source)==expected
  save(out/'SUPPORT_VERIFICATION.json',{'passed':passed,'qualification_cells_passed':0,'scientific_started':0,'source_attempt_reclassified':False,'receipt':receipt})
 except BaseException as e:error=repr(e);events('SUPPORT_ERROR',error=error)
 finally:
  events.file.close();save(out/'STOP.json',{'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'passed':passed,'error':error,'automatic_retry':False,'scientific_started':0,'qualification_cells_passed':0})
  save(out/'SHA256.json',{str(p.relative_to(out)):sha(p) for p in sorted(out.rglob('*')) if p.is_file()})
 if not passed:raise SystemExit(2)
if __name__=='__main__':main()
