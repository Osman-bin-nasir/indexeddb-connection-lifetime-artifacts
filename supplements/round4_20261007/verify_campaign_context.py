import json,hashlib,statistics
from pathlib import Path
from collections import Counter,defaultdict
import argparse
parser=argparse.ArgumentParser(description='Read-only verification of campaign acquisition receipts, acquisition mounts and trace windows. Requires the extracted v1.0.0 full compact evidence release; never writes source evidence.')
parser.add_argument('--release-root',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args();ROOT=args.release_root.resolve();OUT=args.out.resolve()
if OUT==ROOT or ROOT in OUT.parents:parser.error('--out must be outside the release evidence folder')
OUT.mkdir(parents=True,exist_ok=True)
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
inputs={};rows=[];trace=[];counts=Counter();groups=defaultdict(Counter)
def tracked(p):inputs[str(p.relative_to(ROOT))]=sha(p);return p
for td in sorted((ROOT/'campaign_v2/scientific/attempts').glob('scientific-*')):
    a=read(tracked(td/'assignment.json'));start=read(tracked(td/'START.json'))
    assert a['role']=='scientific' and start['role']=='scientific'
    result=read(tracked(td/'RESULT.json')) if (td/'RESULT.json').exists() else None
    finish=read(tracked(td/'OPERATOR_INTEGRATION_RESULT.json')) if (td/'OPERATOR_INTEGRATION_RESULT.json').exists() else None
    mount=None
    if a['experiment']=='block_state_recovery':
        mount=read(tracked(td/'data-mount.json'))['mount']['filesystems'][0]
        assert mount['target']=='/var/lib/idbv2' and mount['source']=='/dev/mapper/idbv2-browser' and mount['fstype']=='ext4' and 'commit=30' not in mount['options']
    elif a['experiment']=='environment_sensitivity':
        v=[json.loads(x) for x in tracked(td/'volume-setup.stdout').read_text().splitlines() if x.strip()]
        setup=next(x for x in v if x.get('kind')=='DATA_VOLUME_READY');mount=setup['actual_mount']['filesystems'][0]
        assert mount['source']=='/dev/vdc' and mount['target']=='/var/lib/idbv2'
        if a['environment_profile']=='ext4_custom_reference':assert mount['fstype']=='ext4' and 'commit=30' in mount['options'] and 'discard' in mount['options']
        elif a['environment_profile']=='xfs_fixed':assert mount['fstype']=='xfs'
        else:assert mount['fstype']=='ext4' and 'commit=30' not in mount['options'] and 'discard' not in mount['options']
    elif (td/'guest-filesystem-sysctls.txt').exists():
        mount=json.JSONDecoder().raw_decode(tracked(td/'guest-filesystem-sysctls.txt').read_text())[0]['filesystems'][0]
        assert mount['source']=='/dev/vda1' and mount['fstype']=='ext4' and 'commit=30' in mount['options'] and 'discard' in mount['options']
    else:assert a['experiment']=='trace_category_timelines' and result is None
    counts[a['experiment']]+=1
    if mount:groups[a['experiment']][(mount['source'],mount['fstype'],mount['options'])]+=1
    rows.append(dict(trial_id=a['trial_id'],family=a['experiment'],start_utc=start['utc'],finished_utc=finish.get('utc') if finish else None,mount=mount,endpoint=result.get('endpoint') if result else 'no_result',eligible=result.get('technical_eligible') if result else False))
    if (td/'TRACE_END.json').exists():
        end=read(tracked(td/'TRACE_END.json')); events=[json.loads(x) for x in tracked(td/'events.jsonl').read_text().splitlines() if x.strip()]
        page=[x for x in events if x.get('guest',{}).get('kind')=='PAGE_EVENT'];ack=next(x for x in page if x['guest']['event'].get('kind')=='ACK')
        close=next((x for x in page if x['guest']['event'].get('kind')=='CLOSE_RETURNED'),None)
        t=end['guest']['guest_end_request_ns'];complete=end['guest']['guest_complete_ns']
        fault=next((x for x in events if x.get('kind')=='FAULT_DISPATCH'),None)
        trace.append(dict(trial_id=a['trial_id'],key=a['key'],end_request_rel_ack_s=(t-ack['guest']['guest_monotonic_ns'])/1e9,end_request_rel_close_s=(t-close['guest']['guest_monotonic_ns'])/1e9 if close else None,end_complete_rel_close_s=(complete-close['guest']['guest_monotonic_ns'])/1e9 if close else None,assigned_fault_after_ack_ms=a['fault_after_ack_ms'],end_request_host_ns=end['host_send_ns'],end_complete_host_ns=end['host_receive_ns'],fault=fault))
assert len(rows)==930 and sum(bool(r['eligible']) for r in rows)==925
reg=read(tracked(ROOT/'confirmatory/REGISTRATION_RECEIPT.json'))
report=dict(assignments=930,eligible=925,first_start=min(rows,key=lambda x:x['start_utc']),last_finish=max((r for r in rows if r['finished_utc']),key=lambda x:x['finished_utc']),registration_receipt=reg,family_mounts={k:[dict(source=s,fstype=f,options=o,count=n) for (s,f,o),n in v.items()] for k,v in groups.items()},family_counts=dict(counts),unmeasured_mount=[r['trial_id'] for r in rows if not r['mount']],trace_windows=trace,rows=rows,source_hashes=inputs,scope='Read-only context verification; no statistical reanalysis or new acquisition')
(OUT/'CAMPAIGN_CONTEXT_VERIFICATION.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:report[k] for k in ['assignments','eligible','first_start','last_finish','family_mounts','unmeasured_mount']},indent=2))
for k in sorted(set(t['key'] for t in trace)):
    ts=[t for t in trace if t['key']==k];v=[t['end_request_rel_close_s'] for t in ts if t['end_request_rel_close_s'] is not None];print(k,len(ts),'end-after-close',min(v) if v else None,max(v) if v else None)
