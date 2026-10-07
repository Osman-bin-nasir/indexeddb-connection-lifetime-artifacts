"""Administrative status only, never acquisition or outcome reclassification."""
import datetime,hashlib,json,os,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];ADMIN=ROOT/'repairs/004'
sys.path.insert(0,str(ROOT))
from qualification import assignments

def read(p):return json.loads(p.read_text())
def atomic(p,v):
 temp=p.with_suffix(p.suffix+'.tmp');temp.write_text(json.dumps(v,indent=2)+'\n');os.replace(temp,p)
def update():
 originals=assignments();map_original={a['trial_id']:a for a in originals};rows=[]
 for p in sorted((ROOT/'qualification/attempts').iterdir()):
  if not (p/'START.json').exists():continue
  a=read(p/'assignment.json');r=read(p/'RESULT.json') if (p/'RESULT.json').exists() else None
  rows.append({'trial_id':p.name,'family':a['experiment'],'condition_id':a['condition_id'],'original_qualification_id':a.get('original_qualification_id',a['trial_id']),'role':a['role'],'scientific_denominator':False,'complete':r is not None,'controller_passed':r['qualification_passed'] if r else None,'endpoint':r['endpoint'] if r else 'unknown','reasons':r['reasons'] if r else ['unfinished'],'wall_seconds':r['wall_seconds'] if r else None})
 smoke=read(ADMIN/'SMOKE_VERIFICATION.json') if (ADMIN/'SMOKE_VERIFICATION.json').exists() else None
 batch=read(ADMIN/'QUALIFICATION_BATCH_STATUS.json') if (ADMIN/'QUALIFICATION_BATCH_STATUS.json').exists() else None
 verified=[]
 if smoke and smoke['independent_pass']:verified.append(smoke['trial_id'])
 if batch:verified.extend(r['trial_id'] for r in batch['attempts'] if r['independent_pass'])
 byid={r['trial_id']:r for r in rows};cells={(byid[t]['family'],byid[t]['condition_id']) for t in verified}
 manifest=read(ROOT.parent/'confirmatory/design/MANIFEST.json');families=[]
 for item in manifest['experiments']:
  if item['optional']:continue
  design=read(ROOT.parent/'confirmatory'/item['path']);name=design['qualification_assignments'][0]['experiment']
  q=[a for a in originals if a['experiment']==name]
  families.append({'family':name,'scientific_assigned':len(design['assignments']),'scientific_started':0,'required_qualification_cells':len(q),'independently_qualified_current_inputs':sum((name,a['condition_id']) in cells for a in q),'still_unqualified':sum((name,a['condition_id']) not in cells for a in q)})
 now=datetime.datetime.now(datetime.timezone.utc);ist=now.astimezone(datetime.timezone(datetime.timedelta(hours=5,minutes=30)))
 frozen=ROOT.parent/'confirmatory';check=all(hashlib.sha256((frozen/n.strip()).read_bytes()).hexdigest()==h for h,n in [l.split(maxsplit=1) for l in (frozen/'SHA256SUMS').read_text().splitlines()])
 value={'updated_utc':now.isoformat(),'updated_ist':ist.isoformat(),'status':batch['status'] if batch else 'FRESH_REPAIR_QUALIFICATION_IN_PROGRESS','scientific_assigned':930,'scientific_started':0,'scientific_completed':0,'frozen_30_files_match':check,'tag_commit':subprocess.check_output(['git','rev-parse','prereg-connection-lifetime-mac-v2^{}'],text=True).strip(),'current_technical_inputs':'Technical Amendment 004 using the separately derived Amendment 003 base','required_cells':95,'independently_qualified_current_inputs':len(cells),'still_unqualified_current_inputs':95-len(cells),'unimplemented_cells':56,'total_historical_excluded_attempts_started':len(rows),'total_historical_excluded_attempts_finished':sum(r['complete'] for r in rows),'total_historical_controller_passed':sum(r['controller_passed'] is True for r in rows),'total_historical_failed_unknown':sum(r['complete'] and r['controller_passed'] is False for r in rows),'old_passes_not_carried_to_current_inputs':True,'attempts':rows,'families':families,'latest_smoke':smoke,'latest_batch':batch,'operator_runner_qualified':False,'final_hash_lock_complete':False,'campaign_ready':False,'campaign_completion_eta':None,'disk_free_gib':shutil.disk_usage(ROOT).free/1024**3,'disk_floor_gib':6,'operation_headroom_gib':3,'no_evidence_deleted':True,'verified_offload':False,'drive_deferred_by_author':True,'new_osf_posting':False,'monitor':{'id':'indexeddb-campaign-repair-and-verification','interval_minutes':30,'active':True}}
 atomic(ROOT/'STEP2_VERIFICATION.json',value)
 (ROOT/'STEP2_STATUS.md').write_text(f"# Step 2 repair and excluded qualification\n\nUpdated {ist.strftime('%Y-%m-%d %H:%M:%S')} IST. Scientific started **0 / 930**. Frozen design/tag unchanged: {check}.\n\nCurrent-input independently qualified cells: {len(cells)} / 95. Historical excluded attempts: {len(rows)} started, {value['total_historical_controller_passed']} controller passes, {value['total_historical_failed_unknown']} failed/unknown, {sum(not r['complete'] for r in rows)} unfinished. Prior failed records and endpoints remain unchanged. Old-base passes are not carried forward to qualify the repaired inputs.\n\nAmendment 003 fixed auxiliary boot mount selectors on a separate base. Its new qualification stopped when cached lsblk returned an empty PARTUUID. Amendment 004 reads the GPT table directly, retaining exact partition/filesystem/mount checks. Its smoke and batch status are in repairs/004. {value['status']}. No automatic retry.\n\nThe monitor runs every 30 minutes. 56 required cells still need execution paths and qualification. The full operator runner, final technical lock and full resource forecast remain pending. No scientific ETA or launch is claimed.\n\nDisk free {value['disk_free_gib']:.2f} GiB, floor 6 GiB plus 3 GiB operation headroom. Drive deferred by author. Evidence retained locally; no deletion or verified offload. No new OSF upload before smoke verification, as requested.\n")
 (ROOT/'NEXT_STEPS.txt').write_text('Monitor repairs/004/FULL_PATH_SMOKE_STOP.json and QUALIFICATION_BATCH_STATUS.json. Stop on failure, unknown endpoint, integrity error or disk risk. Do not reuse consumed IDs. Preserve historical evidence. After independently verified smoke, run the bounded once-only fresh 38-cell qualification plan on repaired inputs. Implement and qualify the other 56 registered cells. Complete final hash lock and resumable operator runner including integrity/archive dry-run and measured resource plan. Start the fixed 930 assignments only after all gates pass. Monitor automation runs every 30 minutes. Drive is deferred; do not delete evidence or cross disk floor. OSF amendment posting must disclose actual smoke-first chronology.\n')
 print(json.dumps({k:value[k] for k in ['updated_ist','status','scientific_started','independently_qualified_current_inputs','total_historical_excluded_attempts_started','total_historical_failed_unknown','disk_free_gib']}))
if __name__=='__main__':update()
