#!/usr/bin/env python3
"""Offline read-only verification of supporting raw oracles, hashes and syscall times.

Usage: python3 verify.py --root /path/to/round4-support
No VM, network, experiment runner or source modification. Uses standard library only.
"""
import argparse,datetime,hashlib,json,re,statistics
from pathlib import Path
from sync_parser import parse_strace,is_wal
from historical_oracle import expected,verify_payload

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parent)
args=parser.parse_args();root=args.root.resolve()
def read(p):return json.loads(p.read_text())
manifest=read(root/'INPUT_SHA256.json')
for rel,h in manifest.items():
    p=root/rel;assert p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest()==h,rel
for pop in ['wal_sync_timing','connection_close_vs_hold']:
    src=root/'source_snapshots'/pop;freeze=read(src/'support/experiment-freeze.json');order=read(src/'support/order.json')
    assert hashlib.sha256((src/'support/order.json').read_bytes()).hexdigest()==freeze['order_sha256']
    assert hashlib.sha256((src/'support/identity.json').read_bytes()).hexdigest()==freeze['identity_sha256']
    assert order['slots']==freeze['order'] and len(order['slots'])==16
    pipeline=hashlib.sha256(''.join(f"{name} {hashlib.sha256((src/name).read_bytes()).hexdigest()}\n" for name in freeze['tracing_pipeline_components']).encode()).hexdigest()
    assert pipeline==freeze['tracing_pipeline_sha256']
    for slot in order['slots']:
        result=read(root/'raw'/pop/slot['trial_id']/'result.json')
        assert result['experiment_id']==order['experiment_id']
        for key in ['trial_id','held','delay_s','mode','action']:assert result[key]==slot[key],(pop,slot['trial_id'],key)
report=read(root/'SYSCALL_VERIFICATION.json');checked=0
for saved in report['rows']:
    td=root/saved['raw_copy_relative'];r=read(td/'result.json');ack=read(td/'ack.json');eid=r['experiment_id'];tid=r['trial_id']
    assert r['technical_valid'] and r['primary_endpoint_eligible'] and not r['errors']
    assert r['timing_valid']
    if saved['population']=='connection_close_vs_hold':
        if saved['held']:assert r['connection_held_at_ready_before'] and r['connection_held_at_ready_after'] and r['connection_retained_event_observed'] and not r['connection_close_call_observed']
        else:assert r['connection_close_call_observed'] and not r['connection_held_at_ready_after']
    assert ack['targetRecord']==expected(eid,tid) and ack['sentinelBefore']==expected(eid,tid,True)
    recovered=verify_payload(read(td/'post-response.json')['response']['value'],eid,tid,'relaxed')
    assert ('recovered' if recovered else 'lost')==saved['endpoint']
    assert r['classification']==('SENTINEL_SURVIVED_TARGET_SURVIVED' if recovered else 'SENTINEL_SURVIVED_TARGET_LOST')
    assert r['pre_boot_id']!=r['post_boot_id']
    samples=[json.loads(line) for line in (td/'cachestat.jsonl').read_text().splitlines() if line.strip()]
    off=int(statistics.median(s['guest_realtime_ns']-s['guest_monotonic_ns'] for s in samples if 'guest_realtime_ns' in s and 'guest_monotonic_ns' in s))
    anchor=read(td/'uptime-at-ack.json')['response']['guest_monotonic_ns'];assert anchor==r['ack_anchor_guest_monotonic_ns']
    def rel(ts):return (round(ts*1e9)-off-anchor)/1e9
    sync=[dict(entry_rel_ack_s=rel(x['guest_realtime_s']),duration_s=x['duration_s'],return_value=x['return_value'],path=x['fd_path'],raw=x['raw']) for x in parse_strace((td/'strace.stderr.txt').read_text())['events'] if x['syscall']=='fdatasync' and x['completed'] and x['fd_path'] and is_wal(x['fd_path'])]
    assert sync==saved['wal_fdatasync']
    post=[x for x in sync if x['entry_rel_ack_s']>0];assert post==saved['post_ack_wal_fdatasync']
    assert len(sync)==(2 if post else 1) and sync[0]['entry_rel_ack_s']<0
    unlinks=[]
    for line in (td/'strace.stderr.txt').read_text().splitlines():
        m=re.search(r'(\d+\.\d+)\s+unlinkat\([^,]+,\s*"([^"]+)".*?\)\s*=\s*0',line)
        if m and is_wal(m[2]):unlinks.append(dict(entry_rel_ack_s=rel(float(m[1])),path=m[2],raw=line))
    assert unlinks==saved['wal_unlink']
    after=[u for u in unlinks if any(u['path']==s['path'] and u['entry_rel_ack_s']>s['entry_rel_ack_s']+(s['duration_s'] or 0) for s in post)]
    assert after==saved['wal_unlink_after_post_ack_sync']
    checked+=1
assert checked==32 and report['new_scientific_assignments']==0 and report['registered_v2_assignments']==930 and report['registered_v2_eligible']==925
print(json.dumps(dict(passed=True,hashes_checked=len(manifest),oracles_and_syscall_traces_verified=checked,registered_assignments_unchanged=930,registered_eligible_unchanged=925,new_trials=0),indent=2))
