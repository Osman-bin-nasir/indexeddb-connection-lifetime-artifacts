"""Read-only original errno74 observation and explicit journal-replay projection, without target/fault/oracle."""
import datetime,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).parent
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'extensions/environment'))
import qualification_environment as host
sys.path.insert(0,str(HERE))
from projection_data import extract
from provision_vm import gate,disk_check,sha,save

def main():
 gate();host.verify_frozen_base();disk_check(3*1024**3);plan=json.loads((HERE/'SUPPORT_PLAN_013.json').read_text())
 for n,h in plan['source_hashes'].items():
  if sha(ROOT/n)!=h:raise RuntimeError('Prospective source changed '+n)
 source=Path(plan['source_image'])
 if sha(source)!=plan['source_sha256']:raise RuntimeError('Preserved source changed')
 if subprocess.run(['pgrep','-f','qemu-system-aarch64'],capture_output=True).returncode==0:raise RuntimeError('Another VM active')
 out=ROOT/'support/block_projection'/plan['support_id'];out.mkdir(parents=True,exist_ok=False);save(out/'START.json',{'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'role':'support_only','no_oracle_target_or_fault':True,'no_endpoint_reclassification':True,'plan':plan});events=host.Events(out/'events.jsonl');passed=False;error=None
 try:
  receipt=extract(host,source,plan['profile'],out/'projection',events,original_expected_sha256=plan['source_sha256']);checks={'original_hash_unchanged':sha(source)==plan['source_sha256'],'original_unavailable_preserved':receipt['raw_no_replay_available'] is False,'explicit_replay_only_derivative':receipt['journal_replay_performed_on_separate_derivative'],'derived_extract_read_only':receipt['post_replay_extract_read_only'],'derived_files_observed':receipt['files']>0};passed=all(checks.values());save(out/'SUPPORT_VERIFICATION.json',{'passed':passed,'checks':checks,'receipt':receipt,'original_endpoint_unchanged':'unknown','scientific_started':0,'qualification_cells_passed':0})
 except BaseException as e:error=repr(e);events('SUPPORT_ERROR',error=error)
 finally:
  events.file.close();save(out/'STOP.json',{'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'passed':passed,'error':error,'no_oracle':True,'no_endpoint_reclassification':True,'scientific_started':0,'qualification_cells_passed':0});save(out/'SHA256.json',{str(p.relative_to(out)):sha(p) for p in out.rglob('*') if p.is_file()})
 if not passed:raise SystemExit(2)
if __name__=='__main__':main()
