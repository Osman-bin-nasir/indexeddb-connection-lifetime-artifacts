"""Audit finished batch attempts only. Never reads live records as final outcomes."""
import hashlib,json,datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
ADMIN=Path(__file__).parent
def read(p):return json.loads(p.read_text())
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def audit(a):
    out=ROOT/'qualification/attempts'/a['trial_id'];result=read(out/'RESULT.json')
    events=[json.loads(l) for l in (out/'events.jsonl').read_text().splitlines()]
    one=lambda k:next(x for x in events if x['kind']==k)
    checks={'assignment_matches_frozen':read(out/'assignment.json')==a,
        'raw_inventory_matches':all(sha(out/n)==h for n,h in read(out/'SHA256.json').items()),
        'all_images_match':all(sha(out/n)==h for n,h in result['image_sha256'].items()),
        'excluded':result['role']=='qualification' and result['scientific_denominator'] is False and result['scientific_assignments_started']==0}
    checks['source_matches_batch_snapshot']=all(sha(ADMIN/'EXECUTED_SOURCE'/n)==h for n,h in read(out/'START.json')['candidate_repair_source_hashes'].items())
    from boot_mounts import validate_inventory
    mount_records=[x for x in events if x['kind']=='AUXILIARY_MOUNT_IDENTITY']
    for x in mount_records:validate_inventory(x['identity'])
    lock=read(ADMIN/'REPAIRED_BASE_LOCK.json')
    volume=read(out/'VOLUME_READY.json');expected=lock['fstab']+volume['fstab_added']
    checks['all_mount_identities']=len(mount_records)==4 and [x['identity']['fstab'] for x in mount_records]==[lock['fstab'],expected,lock['fstab'],expected]
    checks['repaired_base_matches']=sha(Path(lock['derived_base_path']))==lock['derived_base_sha256'] and read(out/'START.json')['base_lock']==lock
    p=[x for x in events if x['kind']=='GUEST_RECORD' and x['guest'].get('kind')=='PAGE_EVENT'];pe=lambda k:next(x for x in p if x['guest']['event']['kind']==k)
    ack=pe('ACK');sentinel=pe('SENTINEL_INDEPENDENT_READBACK');fault=one('FAULT_DISPATCH');identity=one('FAULT_IDENTITY')
    overshoot=(fault['fault']['dispatch_ns']-fault['deadline_ns'])/1e6
    checks['dispatch_eligible']=0<=overshoot<=25
    checks['ack_hint_matches']=ack['guest']['event']['durability_observed']==a['durability']
    checks['sentinel_precondition']=sentinel['guest']['event']['durability_observed']=='strict' and sentinel['guest']['event']['readback']['endpoint']=='lost' and sentinel['guest']['event']['readback']['sentinel_valid']
    checks['boot_changed']=identity['old_boot_id']!=identity['new_boot_id']
    checks['reset_classified']=any(x['kind']=='QMP' and x.get('data',{}).get('event')=='RESET' and x['data'].get('data',{}).get('guest') is False and x['data']['data'].get('reason')=='host-qmp-system-reset' for x in events)
    if a['held']:
        held=one('HELD_EVIDENCE')['last_telemetry']
        checks['held_state_confirmed']=held['receipt_ns']<=fault['fault']['dispatch_ns'] and held['guest']['state']['original_present'] and not held['guest']['state']['original_closed']
    else:checks['close_record_exists']=pe('CLOSE_RETURNED')['guest']['event']['assigned_close_ms']==a['close_ms']
    setup=read(out/'identity-setup.stdout');before=read(out/'identity-before-worker.stdout');after=read(out/'identity-before-recovery.stdout')
    checks['identity_sync_and_readback']=setup['file_fsync_completed'] and setup['directory_fsync_completed'] and setup['identity']==before==after and before['trial_id']==a['trial_id']
    view=read(out/'IMMUTABLE_VIEW.json');oracle_record=read(out/'ORACLE.json');oracle=oracle_record['guest'];spec=read(out/'payload_contract.json')
    checks['immutable_before_reader']=view['captured_ns']<oracle_record['host_send_ns'] and not view['oracle_started'] and sha(out/'overlay.qcow2')==view['sha256'] and sha(out/'data.qcow2')==view['data_sha256']
    extracts=read(out/'forensics/inventory.json');checks['extracts_match']=all(sha(out/'forensics/files'/x['relative_path'])==x['sha256'] for x in extracts['files'])
    checks['extract_read_only']=extracts['block_read_only'] and not extracts['replay_performed'] and extracts['mount_options_requested']==('ro,noload' if volume['fstype']=='ext4' else 'ro,norecovery,nouuid')
    checks['sqlite_backend_confirmed']=any(x['kind']=='GUEST_RECORD' and x['guest'].get('command')=='prepare' and any(f['sqlite_header'] for f in x['guest']['value']['backend_files']) for x in events)
    target=spec['targets'];sort=lambda values:sorted(values,key=lambda x:x['id'])
    if oracle['endpoint']=='recovered':valid=oracle['direct']==target and sort(oracle['indexed'])==sort(target) and sort(oracle['all'])==sort(target+[spec['sentinel']])
    elif oracle['endpoint']=='lost':valid=all(x is None for x in oracle['direct']) and len(oracle['direct'])==len(target) and not oracle['indexed'] and oracle['all']==[spec['sentinel']]
    else:valid=False
    checks['oracle_matches_raw_content']=valid and oracle['sentinel_valid'] and result['endpoint']==oracle['endpoint']
    if a['workload']=='ten_records_one_transaction':checks['ten_record_ack']=len(target)==10 and ack['guest']['event']['records']==10
    if a['workload']=='four_connections':
        extra=one('FOUR_CONNECTION_EVIDENCE');checks['three_extra_connections_held']=ack['guest']['event']['additional_connections']==3 and extra['last_telemetry']['guest']['state']['additional_connections']==3 and not extra['unexpected_extra_close']
    if a['workload']=='background_fsync':
        bg=[x for x in events if x['kind']=='BACKGROUND_RECORD'];ready=next(x['background'] for x in bg if x['background']['kind']=='BACKGROUND_READY');ops=[x['background'] for x in bg if x['background']['kind']=='BACKGROUND_OPERATION_COMPLETE' and x['receipt_ns']<=fault['fault']['dispatch_ns']]
        checks['background_same_filesystem']=ready['device']==ready['profile_device'] and ready['path']==str(Path(before['profile']).parent/'background-fsync.bin')
        checks['background_registered_operations']=ready['period_ns']==100_000_000 and ready['bytes_per_operation']==32768 and len(ops)>0 and all(o['returned_bytes']==32768 and o['fsync_returned'] and o['fsync_return_ns']>=o['fsync_start_ns'] for o in ops)
    expected_profiles={'ext4_commit30_data_volume':('ext4_commit30','ext4',['-o','commit=30,discard']),'ext4_default_data_volume':('ext4_defaults','ext4',[]),'xfs_default_data_volume':('xfs_defaults','xfs',[])}
    profile,fs,opts=expected_profiles[a['filesystem']]
    observations=[x for x in events if x['kind']=='DATA_VOLUME_OBSERVATION']
    checks['registered_data_mount']=volume['filesystem_requested']==profile and volume['fstype']==fs and volume['mount_arguments']==['mount','-t',fs,*opts,'/dev/vdc','/var/lib/idbv2'] and volume['data_size_bytes']==1024**3 and volume['root_device']=='/dev/vda1' and volume['data_serial']=='idbv2-data' and [x['stage'] for x in observations]==['pre-worker','post-reset','recovery'] and all(x['root_source']=='/dev/vda1' and x['actual_mount']['source']=='/dev/vdc' and x['actual_mount']['fstype']==fs and x['serial']=='idbv2-data' and x['sysctls_unchanged'] for x in observations)
    checks['custom_data_mount_options']=profile!='ext4_commit30' or all({'commit=30','discard'}<=set(x['actual_mount']['options'].split(',')) for x in observations)
    launches=[x for x in events if x['kind']=='GUEST_RECORD' and x['guest'].get('kind')=='SCHEDULED_TARGET_LAUNCH']
    launch=launches[0]['guest'] if len(launches)==1 else {}
    planned=a['planned_uptime_ms']*1_000_000
    checks['scheduled_uptime']=len(launches)==1 and launch['planned_uptime_ms']==a['planned_uptime_ms'] and launch['queue_uptime_ns']<planned<=launch['actual_launch_uptime_ns']<=ack['guest']['guest_boot_ns']
    checks['worker_source_matches']=one('ENVIRONMENT_WORKER_SOURCE')['sha256']==read(out/'START.json')['candidate_repair_source_hashes']['guest_worker_env.py']
    checks['forensic_data_volume']=extracts['device']=='/dev/vdc' and extracts['profile']==before['profile'] and extracts['filesystem_identity'].find('TYPE="'+fs+'"')>=0
    checks['original_data_before_oracle']=view['data_path']==str(out/'data.qcow2') and read(out/'FORENSIC_FORMATS.json')['source_sha256']==view['data_sha256']
    checks['contract_checksums']=all(hashlib.sha256((json.dumps(x['metadata'],sort_keys=True,separators=(',',':'),ensure_ascii=True)+'\n'+x['payload']).encode('ascii')).hexdigest()==x['checksum'] for x in target+[spec['sentinel']])
    ready={};anchors={};anchor=None
    for x in events:
        if x['kind']=='VM_START':anchor=x['host_monotonic_ns']
        if x['kind']=='FAULT_DISPATCH':anchor=x['fault']['dispatch_ns']
        if x['kind']=='HEALTHY_OBSERVATION':
            b=x['observation']['identity']['boot_id'];ready.setdefault(b,[]).append(x['observation']['host_ns']);anchors.setdefault(b,anchor)
    checks['readiness_all_four_boots']=len(ready)==4 and all(len(t)>=3 and t[-1]-t[0]>=5e9 and t[-1]-anchors[b]<=180e9 for b,t in ready.items())
    return {'trial_id':a['trial_id'],'independent_pass':result['qualification_passed'] and all(checks.values()),'checks':checks,'endpoint':result['endpoint'],'scientific_denominator':False,'wall_seconds':result['wall_seconds'],'dispatch_overshoot_ms':overshoot,'planned_launch_uptime_ms':a['planned_uptime_ms'],'actual_launch_uptime_ms':launch.get('actual_launch_uptime_ns',0)/1e6,'actual_ack_uptime_ms':ack['guest']['guest_boot_ns']/1e6}
def main():
    plan=read(ADMIN/'QUALIFICATION_BATCH_PLAN.json');status=read(ADMIN/'QUALIFICATION_BATCH_STATUS.json');done=set(status['completed_trial_ids']);rows=[]
    for a in plan['assignments']:
        if a['trial_id'] in done:
            try:rows.append(audit(a))
            except Exception as e:rows.append({'trial_id':a['trial_id'],'independent_pass':False,'audit_error':repr(e)})
    report={'checked_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status_snapshot':status,'finished_attempts_audited':len(rows),'independently_passed':sum(x['independent_pass'] for x in rows),'attempts':rows,'scientific_started':0,'campaign_ready':False}
    (ADMIN/'BATCH_INDEPENDENT_VERIFICATION.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in {'attempts','status_snapshot'}},indent=2))
    if any(not x['independent_pass'] for x in rows):raise SystemExit(1)
if __name__=='__main__':main()
