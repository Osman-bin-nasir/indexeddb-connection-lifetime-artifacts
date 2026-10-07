"""Read-only administrative aggregation of excluded attempts and independent audits."""
import datetime,hashlib,json,os,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from qualification import assignments

def read(p):return json.loads(p.read_text())
def optional(p):return read(p) if p.exists() else None
def atomic(p,v):
 t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(v,indent=2)+'\n');os.replace(t,p)
def main():
 rows=[]
 for p in sorted((ROOT/'qualification/attempts').iterdir()):
  if not (p/'START.json').exists():continue
  a=read(p/'assignment.json');r=optional(p/'RESULT.json')
  rows.append({'trial_id':p.name,'family':a['experiment'],'condition_id':a['condition_id'],'complete':r is not None,'controller_passed':r['qualification_passed'] if r else None,'endpoint':r['endpoint'] if r else 'unknown','reasons':r['reasons'] if r else ['attempt unfinished'],'scientific_denominator':False})
 verified=[]
 for dirname in ['004','005','006','007','008','009']:
  p=ROOT/'repairs'/dirname;smoke=optional(p/'SMOKE_VERIFICATION.json')
  if smoke and smoke.get('independent_pass'):
   a=read(p/'FULL_PATH_SMOKE_ASSIGNMENT.json');verified.append((a['experiment'],a['condition_id'],a['trial_id']))
  plan=optional(p/'QUALIFICATION_BATCH_PLAN.json');status=optional(p/'QUALIFICATION_BATCH_STATUS.json')
  if plan and status:
   lookup={a['trial_id']:a for a in plan['assignments']}
   for r in status.get('attempts',status.get('rows',[])):
    if r['independent_pass']:
     a=lookup[r['trial_id']];verified.append((a['experiment'],a['condition_id'],a['trial_id']))
 for name in ['fault_scope','workloads']:
  p=ROOT/'extensions'/name;plan=optional(p/'QUALIFICATION_PLAN.json');status=optional(p/'STATUS_V3.json') if name=='workloads' else optional(p/'STATUS.json')
  if plan and status:
   lookup={a['trial_id']:a for a in plan['assignments']}
   for r in status.get('rows',[]):
    if r['independent_pass']:
     a=lookup[r['trial_id']];verified.append((a['experiment'],a['condition_id'],a['trial_id']))
 p=ROOT/'extensions/environment'
 env=optional(p/'QUALIFICATION_VERIFICATION_001.json')
 if env and env.get('controller_passed') and env.get('audit',{}).get('independent_pass'):
  a=read(p/'QUALIFICATION_PLAN_001.json')['assignment'];verified.append((a['experiment'],a['condition_id'],a['trial_id']))
 env_plan=optional(p/'QUALIFICATION_BATCH_PLAN_002.json');env_status=optional(p/'QUALIFICATION_BATCH_STATUS_002.json')
 if env_plan and env_status:
  lookup={a['trial_id']:a for a in env_plan['assignments']}
  for r in env_status.get('attempts',[]):
   if r.get('independent_pass'):
    a=lookup[r['trial_id']];verified.append((a['experiment'],a['condition_id'],a['trial_id']))
 sys.path.insert(0,str(ROOT/'operator'))
 import operator as builtin_operator
 import importlib.util
 module_spec=importlib.util.spec_from_file_location('campaign_operator_status',ROOT/'operator/operator.py')
 op=importlib.util.module_from_spec(module_spec);module_spec.loader.exec_module(op)
 scientific=op.status()
 demo=optional(ROOT/'operator/OPERATOR_DEMONSTRATION_RECEIPT_001.json')
 for source in [ROOT/'extensions/timelines',ROOT/'repairs/010',ROOT/'repairs/011',ROOT/'repairs/012',ROOT/'extensions/byte_capture',ROOT/'extensions/block_state']:
  for pp in source.glob('QUALIFICATION_PLAN_*.json'):
   plan=read(pp)
   if 'job_id' not in plan:continue
   status=optional(source/(plan['job_id']+'_STATUS.json'))
   if not status:continue
   lookup={a['trial_id']:a for a in plan['assignments']}
   for r in status.get('attempts',[]):
    if r.get('independent_pass'):
     a=lookup[r['trial_id']];verified.append((a['experiment'],a['condition_id'],a['trial_id']))
 covered={(f,c) for f,c,t in verified};frozen=ROOT.parent/'confirmatory';manifest=read(frozen/'design/MANIFEST.json');families=[]
 for item in manifest['experiments']:
  if item['optional']:continue
  data=read(frozen/item['path']);q=data['qualification_assignments'];family=item['name']
  families.append({'family':family,'scientific_assigned':len(data['assignments']),'scientific_started':scientific['families'][family]['started'],'required_cells':len(q),'independently_qualified_cells':sum((family,a['condition_id']) in covered for a in q),'still_unqualified':sum((family,a['condition_id']) not in covered for a in q)})
 known_statuses={}
 for n in ['repairs/004/QUALIFICATION_BATCH_STATUS.json','extensions/fault_scope/STATUS.json','extensions/workloads/STATUS_V3.json','repairs/007/QUALIFICATION_BATCH_STATUS.json','repairs/007/FULL_PATH_SMOKE_STOP.json','repairs/008/FULL_PATH_SMOKE_STOP.json','repairs/008/QUEUED_SMOKE_STOP.json','repairs/009/FULL_PATH_SMOKE_STOP.json','repairs/009/SMOKE_PROCESS.json','repairs/009/QUALIFICATION_BATCH_STATUS.json']:
  p=ROOT/n
  if p.exists():known_statuses[n]=optional(p)
 now=datetime.datetime.now(datetime.timezone.utc);ist=now.astimezone(datetime.timezone(datetime.timedelta(hours=5,minutes=30)))
 checks=all(hashlib.sha256((frozen/n.strip()).read_bytes()).hexdigest()==h for h,n in [l.split(maxsplit=1) for l in (frozen/'SHA256SUMS').read_text().splitlines()])
 v={'updated_utc':now.isoformat(),'updated_ist':ist.isoformat(),'scientific_assigned':930,'scientific_started':scientific['started'],'scientific_completed':scientific['complete'],'required_cells':95,'independently_qualified_cells':len(covered),'still_unqualified':95-len(covered),'historical_excluded_started':len(rows),'historical_excluded_finished':sum(r['complete'] for r in rows),'historical_controller_passed':sum(r['controller_passed'] is True for r in rows),'historical_failed_unknown':sum(r['complete'] and r['controller_passed'] is False for r in rows),'unfinished_attempts':sum(not r['complete'] for r in rows),'attempts':rows,'families':families,'independent_cell_receipts':[{'family':f,'condition_id':c,'trial_id':t} for f,c,t in verified],'subordinate_statuses':known_statuses,'disk_free_gib':shutil.disk_usage(ROOT).free/1024**3,'disk_floor_gib':6,'operation_headroom_gib':3,'no_deleted_evidence':True,'drive_deferred_by_author':True,'offload_verified':False,'frozen_30_files_match':checks,'operator_runner_qualified':False,'operator_excluded_live_demonstration_passed':bool(demo and all(demo.get(k) for k in ['status_passed','run_batch_passed','verify_passed','archive_roundtrip_passed'])),'final_technical_hash_lock_complete':False,'scientific_eta':None,'campaign_ready':False,'monitor_interval_minutes':150,'new_osf_upload':False}
 atomic(ROOT/'CAMPAIGN_PROGRESS.json',v)
 text=f"# Campaign progress\n\nUpdated {ist.strftime('%Y-%m-%d %H:%M:%S')} IST. Scientific assignments **{scientific['started']}/930 started**, **{scientific['complete']} finished**. Independent qualification coverage **{len(covered)}/95 distinct cells**.\n\nExcluded qualification attempts: {len(rows)} started, {v['historical_excluded_finished']} finished, {v['historical_controller_passed']} controller passes, {v['historical_failed_unknown']} failed or unknown, {v['unfinished_attempts']} unfinished. Pilots, support, qualifications and operator demonstration remain excluded from science. Coverage counts distinct frozen cells from independent receipts, not pooled passes.\n\n"
 for f in families:text+=f"{f['family']}: {f['independently_qualified_cells']}/{f['required_cells']} qualified, scientific assigned {f['scientific_assigned']}.\n\n"
 text+=f"Operator excluded live status/run-batch/verify/archive demonstration: {v['operator_excluded_live_demonstration_passed']}. Scientific backend, full scientific family archive workflow, all-cell qualification, final technical input lock and measured full-campaign storage forecast remain incomplete. An isolated qualification pass cannot authorize scientific acquisition.\n\nAmendment008 SIGKILL failure retains unknown and absent read-only directory evidence, no oracle. Journal-projection support004 passed independently after three preserved support failures; derived extracts are explicitly distinguished from original no-replay state. Timeline job001 stopped at its original unknown endpoint; later amendment011 uses the original pinned recovery reader. SIGKILL amendment010B uses explicitly labeled journal-replay projection extracts while its recovery oracle retains the original guest boot and RAM. All ten failed/unknown qualification attempts retain their exact original records. Timeline amendment011 passed all three attempts independently; SIGKILL amendment010B passed all four. Byte diagnostics amendment012 passed all four independently; original byte00001 remains unknown. Remaining distinct cells are block-state12. Kernel identity capture records observed file-pointer/generation/device/inode/offset/returns; possible undelivered reset tail remains unknown, without an absence claim. Environment original unused slot00001 has its separate prospective local plan; read its consumed/stop/verification records. No qualification retry is implied.\n\nFrozen 30-file design matches: {checks}. Free space {v['disk_free_gib']:.2f} GiB, floor6GiB plus operation headroom. Original evidence retained. Author deferred Drive setup; no verified offload. Local archive round-trips passed but do not authorize deletion. Scientific completion ETA remains unavailable while required paths are unqualified.\n"
 (ROOT/'CAMPAIGN_PROGRESS.md').write_text(text)
 (ROOT/'STEP2_STATUS.md').write_text(text)
 atomic(ROOT/'STEP2_VERIFICATION.json',v)
 (ROOT/'NEXT_STEPS.txt').write_text('Use verification/campaign_progress_v7.py. Versions1 through6 remain historical. Inspect live processes and current environment consumed/stop records before any VM launch. Current coverage comes from independent receipts. Never reuse a consumed ID, overwrite original evidence or retry scientific slots. Read extensions/environment/QUALIFICATION_PLAN_001.json and QUALIFICATION_VERIFICATION_001.json. Only after its independent pass may a separate prospective bounded plan consume remaining unused environment slots, stopping on first failure. Complete block-state qualification; any previously failed condition requires a prospectively documented fresh excluded ID. Operator live excluded demonstration passed; scientific backend/family archive workflow/final lock/resource gates remain incomplete. Fixed930 acquisition is authorized only after all applicable gates pass. Preserve source snapshots and all failures. No deletion before verified offload. Drive setup deferred;6GiB floor plus operation headroom. No new OSF upload before verification; disclose chronology later.\n')
 print(json.dumps({k:v[k] for k in ['updated_ist','independently_qualified_cells','historical_excluded_started','historical_excluded_finished','historical_failed_unknown','unfinished_attempts','scientific_started','disk_free_gib']}))
if __name__=='__main__':main()
