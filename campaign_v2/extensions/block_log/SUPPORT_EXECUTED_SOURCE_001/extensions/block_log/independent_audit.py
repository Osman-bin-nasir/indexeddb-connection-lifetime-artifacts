"""Independent audit of finished mapped capture attempts. No recovery/loss inferred from interrupted records."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];ADMIN=Path(__file__).parent
def read(p):return json.loads(p.read_text())
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def audit(a):
 out=ROOT/'qualification/attempts'/a['trial_id'];result=read(out/'RESULT.json');start=read(out/'START.json');events=[json.loads(l) for l in (out/'events.jsonl').read_text().splitlines()];one=lambda k:next(x for x in events if x['kind']==k)
 checks={'assignment_exact':read(out/'assignment.json')==a,'excluded':result['role']=='qualification' and result['scientific_denominator'] is False and result['scientific_assignments_started']==0,'raw_inventory_matches':all(sha(out/n)==h for n,h in read(out/'SHA256.json').items()),'all_images_match':all(sha(out/n)==h for n,h in result['image_sha256'].items()),'source_snapshot_matches':all(sha(ADMIN/'EXECUTED_SOURCE'/n)==h for n,h in start['candidate_repair_source_hashes'].items())}
 lock=read(ADMIN/'REPAIRED_BASE_LOCK.json');checks['base_matches']=lock==start['base_lock'] and sha(Path(lock['derived_base_path']))==lock['derived_base_sha256']
 pages=[x for x in events if x['kind']=='GUEST_RECORD' and x['guest'].get('kind')=='PAGE_EVENT'];pe=lambda kind:next(x for x in pages if x['guest']['event']['kind']==kind)
 ack=pe('ACK');sentinel=pe('SENTINEL_INDEPENDENT_READBACK');fault=one('FAULT_DISPATCH');identity=one('FAULT_IDENTITY');spec=read(out/'payload_contract.json');oracle_record=read(out/'ORACLE.json');oracle=oracle_record['guest']
 over=(fault['fault']['dispatch_ns']-fault['deadline_ns'])/1e6;checks['timing_gate']=0<=over<=25 and fault['deadline_ns']==ack['receipt_ns']+a['fault_after_ack_ms']*1_000_000
 checks['strict_precondition']=sentinel['guest']['event']['durability_observed']=='strict' and sentinel['guest']['event']['readback']['sentinel_valid'] and sentinel['guest']['event']['readback']['endpoint']=='lost';checks['ack_relaxed']=ack['guest']['event']['durability_observed']==a['durability']=='relaxed'
 if a['held']:
  held=one('HELD_EVIDENCE')['last_telemetry'];checks['held']=held['receipt_ns']<=fault['fault']['dispatch_ns'] and held['guest']['state']['original_present'] and not held['guest']['state']['original_closed']
 else:checks['close']=pe('CLOSE_RETURNED')['guest']['event']['assigned_close_ms']==a['close_ms']
 checks['fresh_recovery_guest']=identity['old_boot_id']!=identity['new_boot_id'] and identity['volatile_state_discarded'] and identity['qemu_changed'] and identity['classification']=='block_capture_fresh_derivative'
 capture=read(out/'MULTI_DISK_CAPTURE.json');checks['immutable_multi_capture']=capture['guest_paused_through_snapshot'] and not capture['oracle_started'] and capture['snapshot_return_host_ns']<oracle_record['host_send_ns'] and all(x['source_node_read_only'] and sha(Path(x['source']))==x['sha256'] for x in capture['views'].values())
 continuation=one('DIAGNOSTIC_CONTINUATION');checks['diagnostic_continuation_only_throwaways']=capture['diagnostic_continuation_on_throwaways_only'] and continuation['captured_images_unchanged'] and continuation['oracle_on_original_guest'] is False
 view=read(out/'IMMUTABLE_VIEW.json');checks['view_boundary_disclosed']=view['captured_ns']==capture['snapshot_return_host_ns'] and view['guest_volatile_state_discarded'] and view['boundary_uncertainty_disclosed'] and not view['capture_after_guest_boot_activity'] and all(sha(out/n)==h for n,h in view['sha256'].items())
 for phase,recover in [('data-mount',False),('recovery-data-mount',True)]:
  entry=read(out/(phase+'.json'))['mount']['filesystems'][0];checks[phase]=entry['fstype']=='ext4' and entry['source']==('/dev/vdc' if recover else '/dev/mapper/idbv2-browser') and 'commit=' not in entry['options'] and 'discard' not in entry['options']
 setup=read(out/'identity-setup.stdout');before=read(out/'identity-before-worker.stdout');after=read(out/'identity-before-recovery.stdout');checks['identity_before_after']=setup['file_fsync_completed'] and setup['directory_fsync_completed'] and setup['identity']==before==after and before['trial_id']==a['trial_id']
 if a['mapper']=='dm_flakey_drop_writes':
  interval=read(out/'FLAKEY_INTERVAL_START.json');bracket=interval['host_bracket'];tr=interval['transition'];checks['flakey_transition_after_ack_before_capture']=bracket['host_send_ns']>=ack['receipt_ns'] and bracket['host_receive_ns']<fault['fault']['dispatch_ns'] and tr['start_guest_ns']<=tr['end_guest_ns'] and 'drop_writes' in tr['table'] and interval['no_extra_target_probe_or_fsync']
 projection=read(out/'FORENSIC_VIEW_PROVENANCE.json');inventory=read(out/'forensic_projection/forensics/inventory.json');checks['explicit_projection_original_unchanged']=projection['view_kind']=='journal_replay_derivative' and sha(Path(projection['original_source']))==projection['original_sha256'] and projection['journal_replay_performed_on_separate_derivative'] and projection['post_replay_extract_read_only']
 checks['extracts_match']=all(sha(out/'forensic_projection/forensics/files'/x['relative_path'])==x['sha256'] for x in inventory['files']);checks['raw_journal_match']=sha(out/'forensic_projection/original-journal.bin')==projection['raw_journal_sha256']
 boundary=read(out/'BLOCK_TRACE_BOUNDARY.json');trace=(out/'block-trace.raw').read_text();checks['trace_drained_no_reported_loss']=trace.rstrip().endswith('END') and boundary['returncode']==0 and not boundary['diagnostics'] and sha(out/'block-trace.raw')==boundary['raw_sha256']
 from block_windows import windows
 expected=windows(trace,one('SCHEDULED_FAULT')['clock_samples'],fault);checks['timing_windows_recomputed']=expected==read(out/'BLOCK_EVENT_WINDOWS.json') and bool(expected['events'])
 checks['sqlite_backend_confirmed']=any(x['kind']=='GUEST_RECORD' and x['guest'].get('command')=='prepare' and any(y['sqlite_header'] for y in x['guest']['value']['backend_files']) for x in events)
 target=spec['targets'];sort=lambda xs:sorted(xs,key=lambda x:x['id'])
 valid=oracle['direct']==target and sort(oracle['indexed'])==sort(target) and sort(oracle['all'])==sort(target+[spec['sentinel']]) if oracle['endpoint']=='recovered' else all(x is None for x in oracle['direct']) and len(oracle['direct'])==len(target) and not oracle['indexed'] and oracle['all']==[spec['sentinel']] if oracle['endpoint']=='lost' else False
 checks['oracle_correct']=valid and oracle['sentinel_valid'] and result['endpoint']==oracle['endpoint']
 checks['contract_checksums']=all(hashlib.sha256((json.dumps(x['metadata'],sort_keys=True,separators=(',',':'),ensure_ascii=True)+'\n'+x['payload']).encode('ascii')).hexdigest()==x['checksum'] for x in target+[spec['sentinel']])
 ready={};anchors={};anchor=None
 for x in events:
  if x['kind']=='VM_START':anchor=x['host_monotonic_ns']
  if x['kind']=='HEALTHY_OBSERVATION':
   boot=x['observation']['identity']['boot_id'];ready.setdefault(boot,[]).append(x['observation']['host_ns']);anchors.setdefault(boot,anchor)
 checks['readiness_all_seven_boots']=len(ready)==7 and all(len(t)>=3 and t[-1]-t[0]>=5e9 and t[-1]-anchors[b]<=180e9 for b,t in ready.items())
 from log_decode import decode
 log=read(out/'REGISTERED_LOG_PREFIXES.json');decoded=decode(out/'log-prefixes/original-log.raw');checks['log_prefixes_registered']=log['all_prefixes_interpretable'] and [x['name'] for x in log['prefixes']]==['immediately_before_ack_marker','at_ack_marker','last_fully_recorded_before_boundary'] and log['entries_fully_decoded']==decoded['fully_decoded_entries'] and log['declared_entries']==decoded['declared_entries'] and log['prefixes_not_trials'] and sha(out/'log-prefixes/original-log.raw')==log['raw_log_sha256']
 mark=read(out/'ACK_MARKER.json');checks['ack_marker_after_receipt_before_boundary']=mark['host_bracket']['host_send_ns']>=ack['receipt_ns'] and mark['host_bracket']['host_receive_ns']<fault['fault']['dispatch_ns'] and mark['marker_uncertainty_disclosed']
 for row in log['prefixes']:
  po=read(out/row['oracle_path'])['guest'];pv=po['direct']==target and sort(po['indexed'])==sort(target) and sort(po['all'])==sort(target+[spec['sentinel']]) if po['endpoint']=='recovered' else all(x is None for x in po['direct']) and len(po['direct'])==len(target) and not po['indexed'] and po['all']==[spec['sentinel']] if po['endpoint']=='lost' else False
  checks['prefix_'+row['name']]=pv and po['sentinel_valid'] and row['endpoint']==po['endpoint'] and row['dependent_within_capture'] and row['scientific_trial_count']==0 and sha((out/row['oracle_path']).parent/'replayed-data.raw')==row['replayed_raw_sha256']
 return {'trial_id':a['trial_id'],'independent_pass':result['qualification_passed'] and all(checks.values()),'checks':checks,'endpoint':result['endpoint'],'scientific_denominator':False,'wall_seconds':result['wall_seconds'],'dispatch_overshoot_ms':over}
