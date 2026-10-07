"""Registered normal-image cleanup, only after actual verified Drive offload.

Raw JSON/events/byte streams/forensic extracts, failed/unknown images and sampled
images are never deleted by this tool. Original inventories and results stay
unchanged. A separate ledger accounts for permitted missing temporary images.
"""
import argparse,hashlib,importlib.util,json,os,subprocess
from pathlib import Path
HERE=Path(__file__).parent;ROOT=HERE.parent
s=importlib.util.spec_from_file_location('retention_archive',HERE/'archive_v2.py');arc=importlib.util.module_from_spec(s);s.loader.exec_module(arc)
def read(p):return json.loads(Path(p).read_text())
def sha(p):return arc.sha(p)
def safe(n):return arc.inside(n)
def validate_offload(folder):
 folder=Path(folder);receipt=read(folder/'RETURNED_DOWNLOAD_VERIFICATION.json');provenance=read(folder/'ACTUAL_BROWSER_DOWNLOAD_PROVENANCE.json')
 if receipt.get('offload_verified') is not True or provenance.get('actual_download_verified') is not True or provenance['returned_receipt_sha256']!=sha(folder/'RETURNED_DOWNLOAD_VERIFICATION.json'):raise RuntimeError('Actual offload provenance absent')
 if receipt['destination_url']!=provenance['destination_url']:raise RuntimeError('Offload URL mismatch')
 if sha(folder/'TRANSFER_MANIFEST.json')!=receipt['original_manifest_sha256']:raise RuntimeError('Transferred manifest changed')
 # Repeat local chunk and all-member decode before normal temporary deletion.
 arc.roundtrip(folder)
 return receipt,provenance

def cleanup(folder):
 folder=Path(folder);receipt,provenance=validate_offload(folder);manifest=read(folder/'TRANSFER_MANIFEST.json')
 running=subprocess.check_output(['ps','-axo','command'],text=True)
 if any(l.lstrip().startswith('qemu-system-aarch64 ') for l in running.splitlines()):raise RuntimeError('VM active; cleanup forbidden')
 files=[]
 for n,v in manifest['omitted_normal_unselected_images'].items():
  p=safe(n)
  if not (n.startswith('qualification/attempts/') or n.startswith('scientific/attempts/')) or not arc.image(p):raise RuntimeError('Non-temporary path in cleanup plan')
  attempt=ROOT/Path(n).parts[0]/Path(n).parts[1]/Path(n).parts[2];a=read(attempt/'assignment.json');r=read(attempt/'RESULT.json')
  if arc.required_full(a,r)[0]:raise RuntimeError('Sampled/anomalous/extra administrative image cannot be deleted')
  if n in manifest['members'] or any(x['backing']==n for x in manifest['backing_chains'].values()):raise RuntimeError('Recoverable backing dependency cannot be removed')
  if not p.is_file() or sha(p)!=v['sha256'] or p.stat().st_size!=v['bytes']:raise RuntimeError('Temporary image missing or changed before cleanup '+n)
  files.append({'path':n,**v,'allocated_bytes':p.stat().st_blocks*512})
 ledger=HERE/'retention'/folder.name;ledger.mkdir(parents=True,exist_ok=False)
 arc.save(ledger/'INTENT.json',{'utc':arc.now(),'archive':str(folder.relative_to(ROOT)),'offload_receipt_sha256':sha(folder/'RETURNED_DOWNLOAD_VERIFICATION.json'),'download_provenance_sha256':sha(folder/'ACTUAL_BROWSER_DOWNLOAD_PROVENANCE.json'),'manifest_sha256':sha(folder/'TRANSFER_MANIFEST.json'),'only_normal_unselected_images':True,'files':files,'raw_results_and_inventories_unchanged':True})
 removed=[]
 with (ledger/'events.jsonl').open('x') as events:
  for v in files:
   p=safe(v['path'])
   if sha(p)!=v['sha256']:raise RuntimeError('Image changed during cleanup; stop')
   p.unlink();row={'utc':arc.now(),'kind':'REMOVED_NORMAL_UNSELECTED_TEMPORARY_IMAGE',**v};events.write(json.dumps(row)+'\n');events.flush();os.fsync(events.fileno());removed.append(v)
 arc.save(ledger/'STOP.json',{'utc':arc.now(),'passed':True,'removed_images':len(removed),'removed_source_hashes':[{'path':v['path'],'sha256':v['sha256']} for v in removed],'freed_allocated_bytes':sum(v['allocated_bytes'] for v in removed),'raw_evidence_deleted':False,'sampled_or_failed_images_deleted':False})
 return read(ledger/'STOP.json')

def removal_records():
 rows={};top=HERE/'retention'
 if not top.exists():return rows
 for folder in top.iterdir():
  if not (folder/'STOP.json').exists():raise RuntimeError('Interrupted image cleanup, preserve and inspect')
  intent=read(folder/'INTENT.json');stop=read(folder/'STOP.json');archive=safe(intent['archive'])
  if stop['passed'] is not True or sha(archive/'RETURNED_DOWNLOAD_VERIFICATION.json')!=intent['offload_receipt_sha256'] or sha(archive/'ACTUAL_BROWSER_DOWNLOAD_PROVENANCE.json')!=intent['download_provenance_sha256'] or sha(archive/'TRANSFER_MANIFEST.json')!=intent['manifest_sha256']:raise RuntimeError('Cleanup ledger provenance mismatch')
  manifest=read(archive/'TRANSFER_MANIFEST.json')
  for v in stop['removed_source_hashes']:
   n=v['path']
   if n not in manifest['omitted_normal_unselected_images'] or manifest['omitted_normal_unselected_images'][n]['sha256']!=v['sha256']:raise RuntimeError('Deletion is outside verified manifest')
   rows[n]={'sha256':v['sha256'],'ledger':str(folder.relative_to(ROOT)),'archive':intent['archive']}
 return rows

def verify_resident(attempt):
 attempt=Path(attempt);a=read(attempt/'assignment.json');r=read(attempt/'RESULT.json');removed=removal_records();checked=0;absent=[]
 for n,h in read(attempt/'SHA256.json').items():
  p=attempt/n
  if p.is_symlink() or not p.resolve().is_relative_to(attempt.resolve()):raise RuntimeError('Unsafe evidence inventory path')
  if p.is_file():
   if sha(p)!=h:raise RuntimeError('Resident raw evidence hash mismatch '+str(p))
   checked+=1
  else:
   relative=str(p.relative_to(ROOT));record=removed.get(relative)
   if not record or record['sha256']!=h or not arc.image(p) or arc.required_full(a,r)[0]:raise RuntimeError('Unexpected missing evidence '+relative)
   absent.append({'path':relative,**record})
 return {'trial_id':attempt.name,'passed':True,'resident_members_verified':checked,'permitted_absent_normal_images':absent,'original_inventory_unchanged':True}

def main():
 ap=argparse.ArgumentParser();sp=ap.add_subparsers(dest='command',required=True);p=sp.add_parser('cleanup');p.add_argument('--archive',type=Path,required=True);p=sp.add_parser('verify');p.add_argument('--attempt',type=Path,required=True);a=ap.parse_args();print(json.dumps(cleanup(a.archive) if a.command=='cleanup' else verify_resident(a.attempt),indent=2))
if __name__=='__main__':main()
