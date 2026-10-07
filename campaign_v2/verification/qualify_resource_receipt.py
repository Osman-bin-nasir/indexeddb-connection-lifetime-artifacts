"""Bind actual independent qualification receipts and forecast measured campaign costs.

No acquisition, deletion, input-lock fabrication or readiness flag override.
"""
import datetime,hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(p.read_text())
def save(p,v):
 with p.open('x') as f:json.dump(v,f,indent=2);f.write('\n')
def main():
 progress=read(ROOT/'CAMPAIGN_PROGRESS.json');expected={};science=[];frozen=ROOT.parent/'confirmatory'
 for item in read(frozen/'design/MANIFEST.json')['experiments']:
  if item['optional']:continue
  d=read(frozen/item['path']);expected.update({(a['experiment'],a['condition_id']):a for a in d['qualification_assignments']});science+=d['assignments']
 covered={}
 for row in progress['independent_cell_receipts']:covered.setdefault((row['family'],row['condition_id']),row)
 if set(expected)!=set(covered) or len(expected)!=95:raise RuntimeError('95-cell coverage incomplete')
 receipts={}
 def discover(v,path,trail=()):
  if isinstance(v,dict):
   if v.get('independent_pass') is True and v.get('trial_id') and isinstance(v.get('checks'),dict):receipts.setdefault(v['trial_id'],[]).append((path,trail,v))
   for k,x in v.items():discover(x,path,trail+(k,))
  elif isinstance(v,list):
   for i,x in enumerate(v):discover(x,path,trail+(i,))
 for top in [ROOT/'repairs',ROOT/'extensions']:
  for directory in top.iterdir():
   if not directory.is_dir():continue
   for p in directory.glob('*.json'):discover(read(p),p)
 cells=[];cost={}
 for key,row in covered.items():
  tid=row['trial_id'];path=ROOT/'qualification/attempts'/tid;a=read(path/'assignment.json');r=read(path/'RESULT.json')
  if a['role']!='qualification' or r['role']!='qualification' or r['scientific_denominator'] is not False or not r['qualification_passed']:raise RuntimeError('Invalid qualified provenance '+tid)
  raw=read(path/'SHA256.json')
  for n,h in raw.items():
   p=path/n
   if p.is_symlink() or not p.resolve().is_relative_to(path.resolve()) or sha(p)!=h:raise RuntimeError('Qualified raw evidence hash mismatch '+tid+'/'+n)
  choices=receipts.get(tid)
  if not choices:raise RuntimeError('No retained independent receipt '+tid)
  ap,trail,review=min(choices,key=lambda x:(len(x[1]),len(str(x[0]))))
  if not all(review['checks'].values()):raise RuntimeError('Audit did not pass every check '+tid)
  snapshot=ROOT/'verification/qualification_receipts';snapshot.mkdir(exist_ok=True)
  target=snapshot/(tid+'.json');save(target,{'trial_id':tid,'independent_pass':True,'checks':review['checks'],'original_audit_path':str(ap.relative_to(ROOT)),'original_audit_sha256':sha(ap),'original_audit_json_path':trail,'source_receipt_copied_without_changing_original':True})
  cell={'family':key[0],'condition_id':key[1],'trial_id':tid,'audit_path':str(target.relative_to(ROOT)),'audit_sha256':sha(target),'attempt_path':str(path.relative_to(ROOT)),'raw_inventory_sha256':sha(path/'SHA256.json'),'raw_members_verified':len(raw),'wall_seconds':r['wall_seconds'],'allocated_bytes':r['allocated_bytes'],'logical_bytes':r['logical_bytes']};cells.append(cell);cost[key]=cell
 utc=datetime.datetime.now(datetime.timezone.utc).isoformat();q={'utc':utc,'required_cells':95,'cells':cells,'all_independently_qualified':True,'scientific_started':0,'unknown_originals_reclassified':False,'frozen_sha256s_sha256':sha(frozen/'SHA256SUMS')};save(ROOT/'operator/QUALIFICATION_RECEIPT_001.json',q)
 families={}
 for a in science:
  c=cost[a['experiment'],a['condition_id']];f=families.setdefault(a['experiment'],{'assigned':0,'qualification_projected_seconds':0,'temporary_evidence_projected_allocated_bytes':0,'max_measured_trial_allocated_bytes':0})
  f['assigned']+=1;f['qualification_projected_seconds']+=c['wall_seconds'];f['temporary_evidence_projected_allocated_bytes']+=c['allocated_bytes'];f['max_measured_trial_allocated_bytes']=max(f['max_measured_trial_allocated_bytes'],c['allocated_bytes'])
 total=sum(f['qualification_projected_seconds'] for f in families.values());space=sum(f['temporary_evidence_projected_allocated_bytes'] for f in families.values());free=shutil.disk_usage(ROOT).free
 v={'utc':utc,'scientific_assigned':930,'scientific_started':0,'families':families,'qualification_wall_projection_hours':total/3600,'projection_scope':'one independently qualified attempt per cell, weighted by frozen scientific assignment count; controller wall time excludes some final hashing, independent verification, archival, transfer, incidents and operator integration. Not a completion deadline or confidence interval.','uncompressed_retained_temporary_evidence_projected_gib':space/1024**3,'disk_free_gib':free/1024**3,'floor_gib':6,'offload_verified':False,'registered_campaign_fits_current_retained_storage':False,'resource_gate_passed':False,'reason':'All-original local acquisition cannot fit forecast. Full family or declared complete-block/batch archive boundaries and measured safe archive headroom, then actual author-managed Drive upload/download hash verification remain required. No original evidence deleted.','max_trial_allocated_bytes':max(c['allocated_bytes'] for c in cells),'operation_headroom_provisional_bytes':3*1024**3,'final_lock_created':False}
 save(ROOT/'operator/RESOURCE_FORECAST_001.json',v)
 text='Qualification-based controller-time projection for930 trials: '+format(total/3600,'.2f')+' hours, before final hashing, independent verification, archiving, transfer, incidents and integration overhead. Temporary trial evidence projection: '+format(space/1024**3,'.2f')+' GiB. Actual free: '+format(free/1024**3,'.2f')+' GiB. Storage readiness is blocked until bounded archive/offload gates pass. This is not an acquisition completion ETA.\n'
 (ROOT/'operator/RESOURCE_FORECAST_001.txt').write_text(text);print(text)
if __name__=='__main__':main()
