#!/usr/bin/env python3
"""Reproduce all registered v2 tables from byte-exact released raw records.

Standard library only, Python >=3.11. No network, VM, cached guide or new trials.
CP limits invert exact binomial tails; matched binary tests use exact sign-label
enumeration via its binomial coefficients; Newcombe method10 uses Wilson limits.
"""
import argparse
import csv
import hashlib
import json
import math
import statistics
from collections import Counter,defaultdict
from pathlib import Path


def load(p):return json.loads(p.read_text())
def h(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def summarize(v):
    v=sorted(v)
    return {'n':len(v),'min':v[0],'median':statistics.median(v),'p95':v[math.ceil(.95*len(v))-1],'max':v[-1]} if v else {'n':0,'min':None,'median':None,'p95':None,'max':None}
def cp(x,n,alpha=.05):
    if not n:return [None,None]
    lower=0.
    if x:
        lo,hi=0.,1.
        for _ in range(80):
            p=(lo+hi)/2
            tail=sum(math.comb(n,k)*p**k*(1-p)**(n-k) for k in range(x,n+1))
            if tail<alpha/2:lo=p
            else:hi=p
        lower=(lo+hi)/2
    upper=1.
    if x<n:
        lo,hi=0.,1.
        for _ in range(80):
            p=(lo+hi)/2
            tail=sum(math.comb(n,k)*p**k*(1-p)**(n-k) for k in range(x+1))
            if tail>alpha/2:lo=p
            else:hi=p
        upper=(lo+hi)/2
    return [lower,upper]
def rd(x1,n1,x0,n0):
    z=statistics.NormalDist().inv_cdf(.975)
    def w(x,n):
        p=x/n;den=1+z*z/n;c=(p+z*z/(2*n))/den
        a=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
        return c-a,c+a
    p=x1/n1;q=x0/n0;l,u=w(x1,n1);k,t=w(x0,n0)
    return [p-q,p-q-math.hypot(p-l,t-q),p-q+math.hypot(u-p,q-k)]
def csvout(p,rows):
    if not rows:return
    columns=[]
    for r in rows:
        for k in r:
            if k not in columns:columns.append(k)
    with p.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=columns);w.writeheader()
        for r in rows:w.writerow({k:json.dumps(v,sort_keys=True) if isinstance(v,(list,dict)) else v for k,v in r.items()})
def exact_sign(pos,neg):
    d=pos+neg
    if not d:return 1.,1,1
    den=2**d;num=min(den,2*sum(math.comb(d,k) for k in range(min(pos,neg)+1)))
    return num/den,num,den
def adjust(ts):
    running=0.
    for rank,i in enumerate(sorted(range(len(ts)),key=lambda i:ts[i]['raw_p'])):
        running=max(running,min(1.,(len(ts)-rank)*ts[i]['raw_p']))
        ts[i]['adjusted_p']=running;ts[i]['family_size']=len(ts)
    return ts


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--release-root',type=Path,default=Path(__file__).resolve().parents[1])
    ap.add_argument('--out',type=Path,default=None)
    args=ap.parse_args();root=args.release_root.resolve();out=(args.out or root/'derived').resolve()
    if out==root/'campaign_v2/scientific/attempts':raise RuntimeError('Output cannot be raw directory')
    out.mkdir(parents=True,exist_ok=True)
    manifest=load(root/'confirmatory/design/MANIFEST.json')
    design={};frozen={};family_order=[]
    for entry in manifest['experiments']:
        p=root/'confirmatory'/entry['path'];assert h(p)==entry['sha256']
        d=load(p);design[entry['name']]=d
        if entry['optional']:continue
        family_order.append(entry['name'])
        for a in d['assignments']:frozen[a['trial_id']]=a
    assert len(frozen)==930
    rows=[];hashchecks=0;oraclechecks=0;versions=Counter();flagsets=Counter();initial_audit_counts=Counter()
    corrected=load(root/'campaign_v2/operator/validator_correction_v1/REVALIDATION_311.json')
    assert corrected['eligible'] and corrected['registered_endpoint']=='lost'
    for d in sorted((root/'campaign_v2/scientific/attempts').glob('scientific-*')):
        a=load(d/'assignment.json');assert a==frozen[a['trial_id']]
        r=load(d/'RESULT.json') if (d/'RESULT.json').exists() else None
        es=[json.loads(v) for v in (d/'events.jsonl').read_text().splitlines()] if (d/'events.jsonl').exists() else []
        audit=load(d/'INDEPENDENT_VERIFICATION.json') if (d/'INDEPENDENT_VERIFICATION.json').exists() else None
        if audit:initial_audit_counts[str(audit.get('independent_pass'))]+=1
        eligible=bool(r and r['technical_eligible'] and r['endpoint'] in {'recovered','lost'})
        if eligible:
            if a['trial_id']==corrected['trial_id']:
                assert r['endpoint']==corrected['registered_endpoint'] and not audit['independent_pass']
            else:assert audit and audit['independent_pass']
        for fn in ['SHA256.json','OPERATOR_SHA256.json']:
            if not (d/fn).exists():continue
            hashes=load(d/fn);hashes=hashes.get('files',hashes)
            for rel,expected in hashes.items():
                if rel not in ['assignment.json','RESULT.json','events.jsonl','ORACLE.json','REGISTERED_ENDPOINT.json','INDEPENDENT_VERIFICATION.json','payload_contract.json']:continue
                p=d/rel
                if p.exists() and isinstance(expected,str):assert h(p)==expected;hashchecks+=1
        page=[e for e in es if e.get('guest',{}).get('kind')=='PAGE_EVENT']
        ack=next((e for e in page if e['guest']['event']['kind']=='ACK'),None)
        close=next((e for e in page if e['guest']['event']['kind']=='CLOSE_RETURNED'),None)
        sched=next((e for e in es if e['kind']=='SCHEDULED_FAULT'),None)
        dispatch=next((e for e in es if e['kind']=='FAULT_DISPATCH'),None)
        timing={}
        if ack and dispatch:timing['ack_to_dispatch_s']=(dispatch['fault']['dispatch_ns']-ack['receipt_ns'])/1e9
        if close and ack:timing['close_delay_s']=(close['guest']['event']['page_ms']-ack['guest']['event']['ack_ms'])/1000
        if dispatch:timing['overshoot_ms']=(dispatch['fault']['dispatch_ns']-dispatch['deadline_ns'])/1e6
        if a['experiment']=='close_aligned_recovery_grid' and sched and dispatch:
            m=sched['mapping'];best=min(sched['clock_samples'],key=lambda s:s['host_receive_ns']-s['host_send_ns'])
            mapped=(best['host_send_ns']+best['host_receive_ns'])//2+round((close['guest']['event']['page_ms']-best['guest']['page_ms'])*1e6)
            assert mapped==m['estimate_ns'] and sched['deadline_ns']==mapped+a['fault_after_close_ms']*1000000
            timing['close_to_dispatch_s']=(dispatch['fault']['dispatch_ns']-mapped)/1e9
            timing['mapping_uncertainty_ms']=m['uncertainty_ns']/1e6
        if a['experiment']=='environment_sensitivity':
            launch=next((e['guest'] for e in es if e.get('guest',{}).get('kind')=='SCHEDULED_TARGET_LAUNCH'),None)
            if launch:
                timing['uptime_planned_s']=launch['planned_uptime_ms']/1000
                timing['uptime_launch_s']=launch['actual_launch_uptime_ns']/1e9
            if ack:timing['uptime_ACK_s']=ack['guest']['guest_boot_ns']/1e9
        for e in es:
            g=e.get('guest',{})
            if g.get('kind')=='WORKER_READY':versions[g.get('browser_version')]+=1;flagsets[tuple(g.get('args',[]))]+=1
        if eligible:
            assert ack and ack['guest']['event']['durability_observed']==a['durability']
            assert dispatch and 0<=timing['overshoot_ms']<=25
            oracle=load(d/'ORACLE.json')['guest'];contract=load(d/'payload_contract.json')
            assert oracle['endpoint']==r['endpoint'] and oracle['sentinel_valid']
            assert contract['sentinel'] in oracle['all']
            for record in contract['targets']+[contract['sentinel']]:
                expected=hashlib.sha256((json.dumps(record['metadata'],sort_keys=True,separators=(',',':'),ensure_ascii=True)+'\n'+record['payload']).encode('ascii')).hexdigest()
                assert expected==record['checksum']
            if r['endpoint']=='recovered':
                assert oracle['direct']==contract['targets'] and sorted(oracle['indexed'],key=lambda z:z['id'])==sorted(contract['targets'],key=lambda z:z['id'])
                assert all(t in oracle['all'] for t in contract['targets'])
            else:
                assert oracle['direct']==[None]*len(contract['targets']) and oracle['indexed']==[]
                assert all(t not in oracle['all'] for t in contract['targets'])
            endpoint=load(d/'REGISTERED_ENDPOINT.json')
            assert endpoint['registered_endpoint']==r['endpoint']
            oraclechecks+=1
        rows.append({'assignment':a,'result':r,'eligible':eligible,'ack_observed':ack is not None,'timing':timing,'record_directory':str(d.relative_to(root))})
    assert len(rows)==930 and len({r['assignment']['trial_id'] for r in rows})==930
    counts=Counter((r['result'] or {}).get('endpoint','no_result') for r in rows)
    assert counts=={'recovered':340,'lost':585,'unknown':4,'no_result':1}
    cells=[];inventory=[];A10=[];A11=[];table4=[];grid_uncertainty=[]
    for fam in family_order:
        fr=[r for r in rows if r['assignment']['experiment']==fam]
        fcounts=Counter((r['result'] or {}).get('endpoint','no_result') for r in fr)
        inventory.append({'family':fam,'registered_cells':len(design[fam]['cells']),'blocks':design[fam]['repetitions'],'assigned':len(fr),'results':sum(r['result'] is not None for r in fr),'eligible':sum(r['eligible'] for r in fr),'recovered':fcounts['recovered'],'lost':fcounts['lost'],'unknown_result':fcounts['unknown'],'premeasurement':fcounts['no_result'],'ACK':sum(r['ack_observed'] for r in fr)})
        seen=[]
        for a in design[fam]['assignments']:
            if a['condition_id'] not in seen:seen.append(a['condition_id'])
        crs=[]
        for cond in seen:
            rs=[r for r in fr if r['assignment']['condition_id']==cond];a=rs[0]['assignment']
            n=sum(r['eligible'] for r in rs);x=sum(r['eligible'] and r['result']['endpoint']=='recovered' for r in rs)
            cc=Counter((r['result'] or {}).get('endpoint','no_result') for r in rs)
            lo,hi=cp(x,n)
            field='close_to_dispatch_s' if fam=='close_aligned_recovery_grid' else 'ack_to_dispatch_s'
            ts=summarize([r['timing'][field] for r in rs if r['eligible']])
            row={'family':fam,'condition_id':cond,'assigned':len(rs),'ACK':sum(r['ack_observed'] for r in rs),'eligible':n,'recovered':x,'lost':n-x,'unknown_result':cc['unknown'],'premeasurement':cc['no_result'],'proportion':x/n if n else None,'cp95_lower':lo,'cp95_upper':hi,'close_ms':a['close_ms'],'gap_ms':a['fault_after_close_ms'],'ack_deadline_ms':a['fault_after_ack_ms'],'key':a.get('key'),'fault':a['fault'],'mapper':a['mapper'],'environment_profile':a.get('environment_profile'),'workload':a['workload'],'durability':a['durability'],'timing_anchor':field,**{'timing_'+k:v for k,v in ts.items()}}
            crs.append(row);cells.append(row)
        csvout(out/f'Table_A{family_order.index(fam)+1}_cells.csv',crs)
        ts=summarize([r['timing']['overshoot_ms'] for r in fr if r['eligible']])
        table4.append({'family':fam,'units':'milliseconds',**ts})
        for close_ms in [0,1000]:
            ts=summarize([r['timing']['close_delay_s'] for r in fr if r['eligible'] and r['assignment']['close_ms']==close_ms])
            if ts['n']:A10.append({'family':fam,'assigned_close_ms':close_ms,'units':'seconds',**ts})
        if fam=='close_aligned_recovery_grid':grid_uncertainty=[r['timing']['mapping_uncertainty_ms'] for r in fr if r['eligible']]
        if fam=='environment_sensitivity':
            for env in ['ext4_custom_reference','ext4_defaults_fixed','ext4_defaults_random','xfs_fixed']:
                for kind in ['planned','launch','ACK']:
                    ts=summarize([r['timing']['uptime_'+kind+'_s'] for r in fr if r['eligible'] and r['assignment']['environment_profile']==env])
                    A11.append({'profile':env,'timepoint':kind,'units':'seconds',**ts})
    assert len(cells)==95
    def compare(fam,c1,c0,stratum=False,label=None):
        fr=[r for r in rows if r['assignment']['experiment']==fam]
        def select(cond):
            return {(r['assignment']['block'],r['assignment']['close_ms'] if stratum else None):int(r['result']['endpoint']=='recovered') for r in fr if r['eligible'] and all(r['assignment'].get(k)==v for k,v in cond.items())}
        m,n=select(c1),select(c0);common=sorted(set(m)&set(n));diffs=[m[k]-n[k] for k in common]
        pos=sum(d>0 for d in diffs);neg=sum(d<0 for d in diffs);p,num,den=exact_sign(pos,neg)
        x1,n1,x0,n0=sum(m.values()),len(m),sum(n.values()),len(n)
        return {'family':fam,'label':label,'contrast1':c1,'contrast0':c0,'complete_pairs':len(common),'positive_discordances':pos,'negative_discordances':neg,'ties':len(common)-pos-neg,'x1':x1,'n1':n1,'x0':x0,'n0':n0,'risk_difference_newcombe':rd(x1,n1,x0,n0),'raw_p':p,'exact_p_numerator':num,'exact_p_denominator':den,'diffs':diffs}
    primary=adjust([compare('close_aligned_recovery_grid',{'fault_after_close_ms':2400},{'fault_after_close_ms':1600},True,'2.4 minus1.6s, close-stratified'),compare('six_key_conditions',{'key':'immediate_close_late_deadline'},{'key':'delayed_close_short_interval'},label='Immediate minus delayed close'),compare('held_connection_recovery_sweep',{'held':True,'fault_after_ack_ms':15000},{'held':True,'fault_after_ack_ms':5000},label='Held15 minus5s')])
    secondary={}
    for name,fam,dim,ref,alts in [('fault_scope','fault_scope_comparison','fault','qmp_reset',['sysrq_reboot','browser_sigkill']),('block_state','block_state_recovery','mapper','linear_control',['dm_log_writes','dm_flakey_drop_writes']),('environment','environment_sensitivity','environment_profile','ext4_custom_reference',['ext4_defaults_fixed','ext4_defaults_random','xfs_fixed']),('workload','application_and_background_activity','workload','single_256_bytes',['background_fsync','ten_records_one_transaction','four_connections'])]:
        tests=[]
        for key in ['immediate_close_late_deadline','delayed_close_short_interval','held_five_seconds','held_fifteen_seconds']:
            for alt in alts:tests.append({'key':key,'alternative':alt,'reference':ref,**compare(fam,{'key':key,dim:alt},{'key':key,dim:ref})})
        secondary[name]=adjust(tests)
    assert len(primary)+sum(len(v) for v in secondary.values())==43
    assert [t['adjusted_p'] for t in primary]==[.0000057220458984375,.00390625,1.]
    csvout(out/'Table_1_inventory.csv',inventory);csvout(out/'Table_2_primary_tests.csv',primary)
    all_secondary=[{'correction_family':k,**t} for k,v in secondary.items() for t in v]
    csvout(out/'Table_3_secondary_significant.csv',[t for t in all_secondary if t['adjusted_p']<.05])
    csvout(out/'All_registered_secondary_tests.csv',all_secondary)
    csvout(out/'Table_4_dispatch_overshoot.csv',table4);csvout(out/'Table_A10_close_delays.csv',A10);csvout(out/'Table_A11_uptimes.csv',A11)
    csvout(out/'All_95_cells.csv',cells)
    csvout(out/'All_930_dispositions.csv',[{'trial_id':r['assignment']['trial_id'],'family':r['assignment']['experiment'],'block':r['assignment']['block'],'endpoint':(r['result'] or {}).get('endpoint','premeasurement'),'eligible':r['eligible'],'ACK':r['ack_observed'],'reasons':(r['result'] or {}).get('reasons',[])} for r in rows])
    csvout(out/'All_trial_timings.csv',[{'trial_id':r['assignment']['trial_id'],'family':r['assignment']['experiment'],'eligible':r['eligible'],**r['timing']} for r in rows])
    A12=[{'object':'protocol','path':'confirmatory/PREREGISTRATION.md','sha256':h(root/'confirmatory/PREREGISTRATION.md')},{'object':'design_manifest','path':'confirmatory/design/MANIFEST.json','sha256':h(root/'confirmatory/design/MANIFEST.json')},{'object':'scientific_input_lock','path':'campaign_v2/operator/FINAL_INPUT_LOCK.json','sha256':h(root/'campaign_v2/operator/FINAL_INPUT_LOCK.json')},{'object':'scientific_worker','path':'campaign_v2/operator/backend_v1/engine/guest_worker.py','sha256':h(root/'campaign_v2/operator/backend_v1/engine/guest_worker.py')},{'object':'corrected_byte_audit','path':'campaign_v2/operator/validator_correction_v1/audit_bytes_v1.py','sha256':h(root/'campaign_v2/operator/validator_correction_v1/audit_bytes_v1.py')},{'object':'corrected_timeline_audit','path':'campaign_v2/operator/validator_correction_v1/audit_timelines_v1.py','sha256':h(root/'campaign_v2/operator/validator_correction_v1/audit_timelines_v1.py')},{'object':'append_only_revalidation','path':'campaign_v2/operator/validator_correction_v1/REVALIDATION_311.json','sha256':h(root/'campaign_v2/operator/validator_correction_v1/REVALIDATION_311.json')},{'object':'packaged_chromium_receipt_only','sha256':'839efe5fd8b6a773dd81b2e10afdc15f3c0a17316fb82b5908c0533306c4ed9e'},{'object':'public_ubuntu_base_receipt_only','sha256':'1d6bffe64b848468ac97f821d369a4846d983de1800ccf6b5ec8853e85cefc55'}]
    csvout(out/'Table_A12_hashes.csv',A12)
    result={'scope':'Existing mandatory930scientificassignments only; excluded support/qualification/pilots not read','counts':dict(counts),'eligible':sum(r['eligible'] for r in rows),'oracles_content_verified':oraclechecks,'scoped_raw_hashes_verified':hashchecks,'original_audit_pass_counts':dict(initial_audit_counts),'append_only_correction_trial':corrected['trial_id'],'versions':dict(versions),'launch_variants':[{'arguments':list(k),'n':n} for k,n in flagsets.items()],'grid_mapping_uncertainty_ms':summarize(grid_uncertainty),'cells':cells,'inventory':inventory,'primary':primary,'secondary':secondary,'timing_table4':table4,'timing_A10':A10,'uptime_A11':A11,'rows':rows}
    (out/'RECOMPUTED_RESULTS.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ['counts','eligible','oracles_content_verified','scoped_raw_hashes_verified','original_audit_pass_counts']},indent=2))
    print('All95cells,43tests, exactCP,Holm,Newcombe10 and timing tables reproduced from raw. No cached results used.')


if __name__=='__main__':main()
