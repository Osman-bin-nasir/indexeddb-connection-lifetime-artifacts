"""Independent read-only full-path smoke audit. Never acquires observations."""
import datetime
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
ROOT=Path(__file__).resolve().parents[2]
ADMIN=Path(__file__).parent
ID='qualification-smoke-technical-002-close_aligned_recovery_grid-00001'
def read(p):return json.loads(p.read_text())
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
    out=ROOT/'qualification/attempts'/ID
    result=read(out/'RESULT.json');spec=read(out/'payload_contract.json');assignment=read(out/'assignment.json')
    raw=[json.loads(l) for l in (out/'events.jsonl').read_text().splitlines()]
    one=lambda kind:next(x for x in raw if x['kind']==kind)
    page=[x for x in raw if x['kind']=='GUEST_RECORD' and x['guest'].get('kind')=='PAGE_EVENT']
    pe=lambda kind:next(x for x in page if x['guest']['event']['kind']==kind)
    ack=pe('ACK');close=pe('CLOSE_RETURNED');sentinel=pe('SENTINEL_INDEPENDENT_READBACK')
    fault=one('FAULT_DISPATCH');schedule=one('SCHEDULED_FAULT');identity=one('FAULT_IDENTITY')
    checks={'assignment_matches_local_prospective_record':assignment==read(ADMIN/'FULL_PATH_SMOKE_ASSIGNMENT.json'),
        'raw_hashes_match':all(sha(out/n)==h for n,h in read(out/'SHA256.json').items()),
        'local_prospective_input_hashes_match':all(sha(ADMIN/n)==h for n,h in read(ADMIN/'SMOKE_EXECUTION_HASHES.json').items()),
        'executed_candidate_hashes_match':all(sha(ADMIN/n)==h for n,h in read(out/'START.json')['candidate_repair_source_hashes'].items()),
        'excluded':result['role']=='qualification' and not result['scientific_denominator'] and result['scientific_assignments_started']==0,
        'strict_sentinel':sentinel['guest']['event']['durability_observed']=='strict' and sentinel['guest']['event']['readback']['endpoint']=='lost',
        'relaxed_ack':ack['guest']['event']['durability_observed']=='relaxed',
        'boot_id_change':identity['old_boot_id']!=identity['new_boot_id']}
    reset=[x['data'] for x in raw if x['kind']=='QMP' and x.get('data',{}).get('event')=='RESET']
    checks['reset_classification']=any(x.get('data',{}).get('guest') is False and x['data'].get('reason')=='host-qmp-system-reset' for x in reset)
    timing={'overshoot_ms':(fault['fault']['dispatch_ns']-fault['deadline_ns'])/1e6,
        'ack_receipt_to_dispatch_ms':(fault['fault']['dispatch_ns']-ack['receipt_ns'])/1e6,
        'mapped_close_to_dispatch_ms':(fault['fault']['dispatch_ns']-schedule['mapping']['estimate_ns'])/1e6,
        'clock_mapping_uncertainty_ms':schedule['mapping']['uncertainty_ns']/1e6,
        'page_close_delay_ms':close['guest']['event']['page_ms']-ack['guest']['event']['ack_ms']}
    checks['timing_gate']=0<=timing['overshoot_ms']<=25
    observations={};anchors={};anchor=None
    for x in raw:
        if x['kind']=='VM_START':anchor=x['host_monotonic_ns']
        if x['kind']=='FAULT_DISPATCH':anchor=x['fault']['dispatch_ns']
        if x['kind']=='HEALTHY_OBSERVATION':
            b=x['observation']['identity']['boot_id'];observations.setdefault(b,[]).append(x['observation']['host_ns']);anchors.setdefault(b,anchor)
    readiness={b:{'n':len(t),'span_s':(t[-1]-t[0])/1e9,'ready_after_anchor_s':(t[-1]-anchors[b])/1e9} for b,t in observations.items()}
    checks['all_readiness_gates']=len(readiness)==4 and all(v['n']>=3 and v['span_s']>=5 and v['ready_after_anchor_s']<=180 for v in readiness.values())
    start_identity=read(out/'identity-before-worker.stdout');recovery_identity=read(out/'identity-before-recovery.stdout')
    checks['identity_reads_match']=start_identity==recovery_identity and start_identity['trial_id']==ID
    setup=read(out/'identity-setup.stdout')
    checks['identity_sync_receipt']=setup['file_fsync_completed'] and setup['directory_fsync_completed'] and setup['identity']==start_identity
    view=read(out/'IMMUTABLE_VIEW.json')
    checks['immutable_view_matches']=sha(out/'overlay.qcow2')==view['sha256']
    checks['all_images_match']=all(sha(out/n)==h for n,h in result['image_sha256'].items())
    attach=one('EVIDENCE_ATTACHED_AFTER_HELPER_BOOT')
    checks['read_only_attachment']=attach['read_only'] and attach['helper_root']=='/dev/vda1' and attach['serial']=='idbv2-evidence'
    extract=read(out/'forensics/inventory.json')
    checks['read_only_extract']=extract['block_read_only'] and not extract['replay_performed'] and not extract['oracle_started'] and extract['mount_options_requested']=='ro,noload' and 'ro' in extract['actual_mount']['filesystems'][0]['options'].split(',')
    checks['extract_hashes_match']=all(sha(out/'forensics/files'/x['relative_path'])==x['sha256'] for x in extract['files'])
    oracle=read(out/'ORACLE.json')['guest'];sort=lambda a:sorted(a,key=lambda x:x['id'])
    checks['independent_raw_oracle_matches']=oracle['endpoint']=='recovered' and oracle['sentinel_valid'] and oracle['direct']==spec['targets'] and sort(oracle['indexed'])==sort(spec['targets']) and sort(oracle['all'])==sort([spec['sentinel']]+spec['targets'])
    records=spec['targets']+[spec['sentinel']]
    checks['record_checksums_valid']=all(hashlib.sha256((json.dumps(x['metadata'],sort_keys=True,separators=(',',':'),ensure_ascii=True)+'\n'+x['payload']).encode('ascii')).hexdigest()==x['checksum'] and len(x['payload'])==x['metadata']['payload_bytes'] for x in records)
    previous={}
    for old in ['qualification-close_aligned_recovery_grid-00001','qualification-amendment-001-close_aligned_recovery_grid-00001']:
        p=ROOT/'qualification/attempts'/old;r=read(p/'RESULT.json')
        previous[old]={'hashes_match':all(sha(p/n)==h for n,h in read(p/'SHA256.json').items()),'endpoint':r['endpoint'],'passed':r['qualification_passed']}
    checks['previous_failures_intact']=all(v['hashes_match'] and v['endpoint']=='unknown' and not v['passed'] for v in previous.values())
    frozen=ROOT.parent/'confirmatory';checks['frozen_30_files_match']=all(sha(frozen/n.strip())==h for h,n in [l.split(maxsplit=1) for l in (frozen/'SHA256SUMS').read_text().splitlines()])
    checks['tag_commit_unchanged']=subprocess.check_output(['git','rev-parse','prereg-connection-lifetime-mac-v2^{}'],text=True).strip()=='5a749734a0a63f3e1c662bb91dd829e6f288dc5c'
    report={'verified_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'checks':checks,'independent_smoke_pass':result['qualification_passed'] and all(checks.values()),'result':result,'timing_ms':timing,'readiness':readiness,'immutable_view':view,'previous_failures':previous,'scientific_assigned':930,'scientific_started':0,'osf_uploaded_this_turn':False,'campaign_ready':False,'disk_free_bytes':shutil.disk_usage(ROOT).free}
    (ADMIN/'SMOKE_VERIFICATION.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'independent_smoke_pass':report['independent_smoke_pass'],'checks':checks,'timing_ms':timing},indent=2))
    if not report['independent_smoke_pass']:raise SystemExit(1)
if __name__=='__main__':main()
