"""Recompute excluded qualification status from unchanged raw records and inventories."""
import datetime
import json
from pathlib import Path
import shutil

from provision_vm import ROOT,sha
from qualification import assignments


def recompute():
    frozen=ROOT.parent/'confirmatory'
    manifest=json.loads((frozen/'design/MANIFEST.json').read_text())
    families=[];details=[];errors=[]
    for family in manifest['experiments']:
        if family['optional']:continue
        planned=[a for a in assignments() if a['experiment']==family['name']]
        count={'family':family['name'],'scientific_assigned':family['assignments'],'scientific_started':0,
               'qualification_assigned':len(planned),'started':0,'finished_attempts':0,'passed':0,
               'failed':0,'interrupted_or_missing_result':0,'endpoint_unknown':0,'integrity_failure':0,
               'technically_invalid':0,'unstarted':0,'status':'held_after_failed_common_forensics_qualification'}
        for assignment in planned:
            out=ROOT/'qualification/attempts'/assignment['trial_id']
            if not out.exists():count['unstarted']+=1;continue
            count['started']+=1
            if not (out/'RESULT.json').exists():
                count['interrupted_or_missing_result']+=1;continue
            result=json.loads((out/'RESULT.json').read_text());count['finished_attempts']+=1
            count['passed' if result['qualification_passed'] else 'failed']+=1
            count['technically_invalid']+=not result['qualification_passed']
            count['endpoint_unknown']+=result['endpoint']=='unknown'
            count['integrity_failure']+=result['endpoint']=='integrity_failure'
            raw=[json.loads(line) for line in (out/'events.jsonl').read_text().splitlines()]
            inventory=json.loads((out/'SHA256.json').read_text())
            mismatches=[name for name,digest in inventory.items() if sha(out/name)!=digest]
            if mismatches:errors.append({'trial_id':assignment['trial_id'],'hash_mismatches':mismatches})
            if json.loads((out/'assignment.json').read_text())!=assignment:errors.append({'trial_id':assignment['trial_id'],'assignment_mismatch':True})
            page=[x for x in raw if x['kind']=='GUEST_RECORD' and x['guest'].get('kind')=='PAGE_EVENT']
            ack=next((x for x in page if x['guest']['event']['kind']=='ACK'),None)
            close=next((x for x in page if x['guest']['event']['kind']=='CLOSE_RETURNED'),None)
            fault=next((x for x in raw if x['kind']=='FAULT_DISPATCH'),None)
            identity=next((x for x in raw if x['kind']=='FAULT_IDENTITY'),None)
            schedule=next((x for x in raw if x['kind']=='SCHEDULED_FAULT'),None)
            qmp_reset=[x for x in raw if x['kind']=='QMP' and x.get('data',{}).get('event')=='RESET']
            mapping=schedule['mapping'] if schedule else None
            timing={}
            if ack and fault:
                timing['ack_receipt_to_dispatch_ms']=(fault['fault']['dispatch_ns']-ack['receipt_ns'])/1e6
                timing['dispatch_overshoot_ms']=(fault['fault']['dispatch_ns']-fault['deadline_ns'])/1e6
                timing['qmp_write_minus_dispatch_ms']=(fault['fault']['qmp_written_ns']-fault['fault']['dispatch_ns'])/1e6
            if close and ack:timing['page_close_delay_ms']=close['guest']['event']['page_ms']-ack['guest']['event']['ack_ms']
            if mapping and fault:
                timing['mapped_close_to_dispatch_ms']=(fault['fault']['dispatch_ns']-mapping['estimate_ns'])/1e6
                timing['mapped_close_uncertainty_ms']=mapping['uncertainty_ns']/1e6
            start=json.loads((out/'START.json').read_text())
            source=ROOT/'qualification/source_snapshots'/start['source_hashes']['qualification.py']
            source_verified=all((source/name).exists() and sha(source/name)==digest for name,digest in start['source_hashes'].items())
            if not source_verified:errors.append({'trial_id':assignment['trial_id'],'executed_source_not_verified':True})
            view=json.loads((out/'IMMUTABLE_VIEW.json').read_text()) if (out/'IMMUTABLE_VIEW.json').exists() else None
            details.append({'trial_id':assignment['trial_id'],'condition':assignment,'result':result,
                'timing':timing,'qmp_reset_events':qmp_reset,'boot_id_evidence':identity,
                'raw_inventory_verified':not mismatches,'executed_source_verified':source_verified,
                'immutable_view':view,'immutable_view_hash_verified':bool(view and sha(out/'overlay.qcow2')==view['sha256']),
                'oracle_record_present':(out/'ORACLE.json').exists(),'forensic_extract_present':(out/'forensic-extraction.json').exists(),
                'reader_launched':any(x['kind']=='GUEST_RECORD' and x['guest'].get('kind')=='WORKER_READY' and identity and x['host_monotonic_ns']>identity['host_monotonic_ns'] for x in raw),
                'scientific_endpoint_available':False})
        families.append(count)
    return {'checked_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'status':'STEP_2_BLOCKED_FAILED_EXCLUDED_QUALIFICATION','families':families,'attempts':details,
        'scientific_assigned':930,'scientific_started':0,'qualification_assigned':95,
        'qualification_started':sum(f['started'] for f in families),
        'qualification_passed':sum(f['passed'] for f in families),'qualification_failed':sum(f['failed'] for f in families),
        'qualification_unstarted':sum(f['unstarted'] for f in families),'optional_cost_active':False,
        'errors':errors,'disk_free_bytes':shutil.disk_usage(ROOT).free,'disk_floor_bytes':6*1024**3,
        'corrected_full_campaign_hours':None,'corrected_full_campaign_disk_bytes':None,
        'resource_estimate_status':'Unavailable: one failed cell does not measure the remaining families',
        'technical_hash_lock_complete':False,'operator_package_ready':False,
        'amendment_001_status':'draft_only_not_authorized_not_executed',
        'count_semantics':'Finished attempts overlap failed/technically invalid/unknown. They are not interpretable binary endpoints.'}


if __name__=='__main__':
    result=recompute()
    (ROOT/'STEP2_VERIFICATION.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in {'families','attempts'}},indent=2))
    if result['errors']:raise SystemExit(1)
