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
 for dirname in ['004','005','006','007','008']:
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
 covered={(f,c) for f,c,t in verified};frozen=ROOT.parent/'confirmatory';manifest=read(frozen/'design/MANIFEST.json');families=[]
 for item in manifest['experiments']:
  if item['optional']:continue
  data=read(frozen/item['path']);q=data['qualification_assignments'];family=item['name']
  families.append({'family':family,'scientific_assigned':len(data['assignments']),'scientific_started':0,'required_cells':len(q),'independently_qualified_cells':sum((family,a['condition_id']) in covered for a in q),'still_unqualified':sum((family,a['condition_id']) not in covered for a in q)})
 known_statuses={}
 for n in ['repairs/004/QUALIFICATION_BATCH_STATUS.json','extensions/fault_scope/STATUS.json','extensions/workloads/STATUS_V3.json','repairs/007/QUALIFICATION_BATCH_STATUS.json','repairs/007/FULL_PATH_SMOKE_STOP.json','repairs/008/FULL_PATH_SMOKE_STOP.json','repairs/008/QUEUED_SMOKE_STOP.json']:
  p=ROOT/n
  if p.exists():known_statuses[n]=optional(p)
 now=datetime.datetime.now(datetime.timezone.utc);ist=now.astimezone(datetime.timezone(datetime.timedelta(hours=5,minutes=30)))
 checks=all(hashlib.sha256((frozen/n.strip()).read_bytes()).hexdigest()==h for h,n in [l.split(maxsplit=1) for l in (frozen/'SHA256SUMS').read_text().splitlines()])
 v={'updated_utc':now.isoformat(),'updated_ist':ist.isoformat(),'scientific_assigned':930,'scientific_started':0,'scientific_completed':0,'required_cells':95,'independently_qualified_cells':len(covered),'still_unqualified':95-len(covered),'historical_excluded_started':len(rows),'historical_excluded_finished':sum(r['complete'] for r in rows),'historical_controller_passed':sum(r['controller_passed'] is True for r in rows),'historical_failed_unknown':sum(r['complete'] and r['controller_passed'] is False for r in rows),'unfinished_attempts':sum(not r['complete'] for r in rows),'attempts':rows,'families':families,'independent_cell_receipts':[{'family':f,'condition_id':c,'trial_id':t} for f,c,t in verified],'subordinate_statuses':known_statuses,'disk_free_gib':shutil.disk_usage(ROOT).free/1024**3,'disk_floor_gib':6,'operation_headroom_gib':3,'no_deleted_evidence':True,'drive_deferred_by_author':True,'offload_verified':False,'frozen_30_files_match':checks,'operator_runner_qualified':False,'final_technical_hash_lock_complete':False,'scientific_eta':None,'campaign_ready':False,'monitor_interval_minutes':30,'new_osf_upload':False}
 atomic(ROOT/'CAMPAIGN_PROGRESS.json',v)
 text=f"# Campaign progress\n\nUpdated {ist.strftime('%Y-%m-%d %H:%M:%S')} IST. Scientific started **0/930**. Current-input qualification coverage: **{len(covered)}/95 cells**. Frozen files match: {checks}.\n\nExcluded attempts: {len(rows)} started, {v['historical_excluded_finished']} finished, {v['historical_controller_passed']} controller passes, {v['historical_failed_unknown']} failed/unknown, {v['unfinished_attempts']} unfinished. Prior failed endpoints and raw records remain unchanged. Support diagnostics and pilots are excluded. Current cell coverage comes from independent receipts, not the pooled attempt pass count.\n\nThe ordinary repaired-base smoke and 38-cell batch passed independently, covering 39 cells. Non-QMP fault-scope qualification is unqualified: one process-selector failure and one subsequent forensic read failure remain unknown. The corrected same-guest SIGKILL snapshot path passed a neutral RAM/boot/image engineering smoke, but its fresh Amendment008 full qualification failed: the read-only extractor could not find the expected IndexedDB directory. This is different from the preceding errno74 error. No oracle ran; unknown is preserved. No retry or non-QMP continuation is running. A workload background-fsync qualification reached reset then failed a host bind preflight before helper startup, with no oracle. The host port correction passed a loopback regression and a fresh Amendment007 full-path qualification passed all23 independent checks. Its eleven unused workload slots subsequently passed independently, so all16 workload cells including four quiet controls are qualified. This does not qualify the SIGKILL path.\n\nRemaining required tooling includes environment/data-volume/uptime, block-state/prefix recovery, byte capture and timelines. Source files built or unit-tested are not claimed live-qualified. Draft operator status/integrity/archive/run-batch shells and a guarded data-volume helper are built; their live end-to-end demonstration, complete scientific backend/family archive workflow, final input lock and measured full-campaign resource forecast remain pending. No scientific ETA is asserted.\n\nDisk free {v['disk_free_gib']:.2f} GiB. Floor 6 GiB plus operation headroom. Drive deferred by author; no verified offload or deletion. No new OSF upload; amendments remain local with actual smoke-first chronology. The monitor continues every 30 minutes.\n"
 batch=known_statuses.get('repairs/007/QUALIFICATION_BATCH_STATUS.json')
 if batch:text+=f"\nWorkload continuation: {batch['status']}; assigned {batch['assigned_excluded']}, finished {batch['finished']}, independent passes {batch['independently_passed']}, failures {batch['failed']}, current {batch['current']}, remaining {batch['remaining']}.\n"
 (ROOT/'CAMPAIGN_PROGRESS.md').write_text(text)
 (ROOT/'STEP2_STATUS.md').write_text(text)
 atomic(ROOT/'STEP2_VERIFICATION.json',v)
 (ROOT/'NEXT_STEPS.txt').write_text('Read CAMPAIGN_PROGRESS.json plus current source-specific smoke/batch status before acting. Preserve every consumed ID/raw failure. Amendment007 smoke and eleven-slot workload continuation have independently passed. Amendment008 same-guest SIGKILL failed forensic directory access and is stopped; preserve unknown. Diagnose using new excluded support IDs and immutable evidence; any further qualification needs a prospective fresh-ID amendment. SIGKILL must retain the original guest through its oracle; the Amendment 006 implementation is support-tested only and remains unqualified, with no unavailable forensic extract substituted. A new qualification needs a prospectively documented fresh ID and source lock. Implement and qualify environment volumes/uptime, block-state and prefixes, byte capture, timelines and remaining non-QMP faults. Complete operator status/preflight/run-batch/verify/archive/disk-check, integrity and archive dry-run, final input lock and corrected measured resource plan. Start fixed 930 scientific assignments only when all actual gates pass. No retries or evidence deletion before verified offload; Drive is deferred, floor6GiB+headroom enforced. Monitor every30minutes.\n')
 print(json.dumps({k:v[k] for k in ['updated_ist','independently_qualified_cells','historical_excluded_started','historical_excluded_finished','historical_failed_unknown','unfinished_attempts','scientific_started','disk_free_gib']}))
if __name__=='__main__':main()
