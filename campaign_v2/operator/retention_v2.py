"""Integrity verification after documented normal-overlay removal.

Historical inventories remain unchanged. Missing members are accepted only when
an immutable completed cleanup ledger binds their original hashes to verified
Drive offload. Observer streams and retained images can never use this exception.
"""
import importlib.util
from pathlib import Path
HERE=Path(__file__).parent
spec=importlib.util.spec_from_file_location('retention_v1_preserved',HERE/'retention_v1.py')
prior=importlib.util.module_from_spec(spec);spec.loader.exec_module(prior)

def removal_records():
 rows=prior.removal_records();top=HERE/'author_retention'
 if not top.exists():return rows
 for folder in top.iterdir():
  if (folder/'FAILURE.json').exists():
   failure=prior.read(folder/'FAILURE.json')
   if failure.get('failed_before_intent_or_events') is not True or failure.get('removed_images')!=0 or (folder/'INTENT.json').exists() or (folder/'events.jsonl').exists():raise RuntimeError('Unresolved author cleanup failure')
   continue
  if not (folder/'STOP.json').exists():raise RuntimeError('Interrupted author-directed cleanup; preserve and inspect')
  intent=prior.read(folder/'INTENT.json');stop=prior.read(folder/'STOP.json');archive=prior.safe(intent['archive'])
  if stop.get('passed') is not True or intent.get('independent_returned_download_verified') is not False:raise RuntimeError('Author cleanup provenance invalid')
  for name,key in [('AUTHOR_OFFLOAD_ATTESTATION_001.json','attestation_sha256'),('TRANSFER_MANIFEST.json','manifest_sha256'),('CHUNKS.json','chunks_manifest_sha256')]:
   if prior.sha(archive/name)!=intent[key]:raise RuntimeError('Author cleanup receipt hash changed')
  author=prior.read(archive/'AUTHOR_OFFLOAD_ATTESTATION_001.json')
  if author.get('author_directed_normal_overlay_cleanup') is not True or author.get('independent_returned_download_verified') is not False:raise RuntimeError('Author confirmation missing or misrepresented')
  manifest=prior.read(archive/'TRANSFER_MANIFEST.json');planned={v['path']:v['sha256'] for v in intent['files']}
  events=[__import__('json').loads(line) for line in (folder/'events.jsonl').read_text().splitlines()]
  if {v['path']:v['sha256'] for v in events}!=planned or len(events)!=len(planned):raise RuntimeError('Author cleanup event ledger incomplete')
  if {v['path']:v['sha256'] for v in stop['removed_source_hashes']}!=planned or stop['removed_images']!=len(planned):raise RuntimeError('Author cleanup STOP ledger incomplete')
  for n,h in planned.items():
   if n not in manifest['omitted_normal_unselected_images'] or manifest['omitted_normal_unselected_images'][n]['sha256']!=h:raise RuntimeError('Author cleanup outside manifest')
   rows[n]={'sha256':h,'ledger':str(folder.relative_to(prior.ROOT)),'archive':intent['archive'],'verification_basis':'author-confirmed offload; agent local roundtrip','independent_returned_download_verified':False}
 return rows

def verify_inventory(attempt,filename='SHA256.json'):
 attempt=Path(attempt);a=prior.read(attempt/'assignment.json');r=prior.read(attempt/'RESULT.json')
 removed=removal_records();checked=0;absent=[]
 for n,h in prior.read(attempt/filename).items():
  p=attempt/n
  if p.is_symlink() or not p.resolve().is_relative_to(attempt.resolve()):raise RuntimeError('Unsafe evidence inventory path')
  if p.is_file():
   if prior.sha(p)!=h:raise RuntimeError('Resident evidence hash mismatch '+str(p))
   checked+=1
  else:
   relative=str(p.relative_to(prior.ROOT));record=removed.get(relative)
   if not record or record['sha256']!=h or not prior.arc.image(p) or prior.arc.required_full(a,r)[0]:raise RuntimeError('Unexpected missing evidence '+relative)
   absent.append({'path':relative,**record})
 return {'trial_id':attempt.name,'passed':True,'inventory':filename,'resident_members_verified':checked,'permitted_absent_normal_images':absent,'original_inventory_unchanged':True}
