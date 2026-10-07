"""One author-directed normal-overlay cleanup, with verification limits explicit.

The author states that the Drive files were verified and explicitly requests
local space release. This script does not represent that statement as an agent
performed return-download hash check or as a scientific acquisition gate pass.
"""
import argparse,datetime,hashlib,importlib.util,json,os,subprocess
from pathlib import Path
HERE=Path(__file__).parent;ROOT=HERE.parent
s=importlib.util.spec_from_file_location('author_retention_prior',HERE/'retention_v1.py');prior=importlib.util.module_from_spec(s);s.loader.exec_module(prior)
def save(p,v):prior.arc.save(p,v)
def cleanup(folder):
 folder=Path(folder);attestation=prior.read(folder/'AUTHOR_OFFLOAD_ATTESTATION_001.json')
 if attestation.get('author_directed_normal_overlay_cleanup') is not True or attestation.get('independent_returned_download_verified') is not False:raise RuntimeError('Exact author authorization/provenance missing')
 if prior.sha(folder/'TRANSFER_MANIFEST.json')!=attestation['local_manifest_sha256'] or prior.sha(folder/'CHUNKS.json')!=attestation['local_chunks_manifest_sha256']:raise RuntimeError('Author-attested archive changed')
 processes=subprocess.check_output(['ps','-axo','comm'],text=True)
 if any(Path(line.strip()).name=='qemu-system-aarch64' for line in processes.splitlines()):raise RuntimeError('VM active; stop')
 verified=prior.arc.roundtrip(folder)
 if verified.get('passed') is not True:raise RuntimeError('Local member roundtrip failed')
 manifest=prior.read(folder/'TRANSFER_MANIFEST.json');files=[];attempts=set()
 for n,v in manifest['omitted_normal_unselected_images'].items():
  p=prior.safe(n)
  if not n.startswith('qualification/attempts/') or not prior.arc.image(p):raise RuntimeError('Cleanup restricted to excluded temporary images')
  attempt=ROOT.joinpath(*Path(n).parts[:3]);a=prior.read(attempt/'assignment.json');r=prior.read(attempt/'RESULT.json')
  if a['role']!='qualification' or r['scientific_denominator'] is not False or prior.arc.required_full(a,r)[0]:raise RuntimeError('Retained/anomalous/unknown image cannot be removed')
  if n in manifest['members'] or any(x['backing']==n for x in manifest['backing_chains'].values()):raise RuntimeError('Archived member/backing dependency protected')
  if not p.is_file() or prior.sha(p)!=v['sha256'] or p.stat().st_size!=v['bytes']:raise RuntimeError('Temporary image changed '+n)
  files.append({'path':n,**v,'allocated_bytes':p.stat().st_blocks*512});attempts.add(attempt)
 # Verify every historical raw inventory before any deletion. Results/inventories
 # are retained unchanged, with missing temporary images explained in this ledger.
 for attempt in attempts:prior.verify_resident(attempt)
 ledger=HERE/'author_retention'/folder.name;ledger.mkdir(parents=True,exist_ok=False)
 save(ledger/'INTENT.json',{'utc':prior.arc.now(),'archive':str(folder.relative_to(ROOT)),'attestation_sha256':prior.sha(folder/'AUTHOR_OFFLOAD_ATTESTATION_001.json'),'manifest_sha256':prior.sha(folder/'TRANSFER_MANIFEST.json'),'chunks_manifest_sha256':prior.sha(folder/'CHUNKS.json'),'local_roundtrip':verified,'verification_basis':'author confirmation plus fresh agent local archive/member verification; no agent return-download verification','independent_returned_download_verified':False,'scientific_acquisition_gate_passed':False,'files':files,'raw_results_and_inventories_unchanged':True})
 removed=[]
 with (ledger/'events.jsonl').open('x') as events:
  for v in files:
   p=prior.safe(v['path'])
   if prior.sha(p)!=v['sha256']:raise RuntimeError('Image changed during cleanup')
   p.unlink();events.write(json.dumps({'utc':prior.arc.now(),'kind':'AUTHOR_DIRECTED_NORMAL_UNSELECTED_TEMPORARY_IMAGE_REMOVAL',**v})+'\n');events.flush();os.fsync(events.fileno());removed.append(v)
 save(ledger/'STOP.json',{'utc':prior.arc.now(),'passed':True,'removed_images':len(removed),'removed_source_hashes':[{'path':v['path'],'sha256':v['sha256']} for v in removed],'freed_allocated_bytes':sum(v['allocated_bytes'] for v in removed),'raw_evidence_deleted':False,'sampled_or_failed_images_deleted':False,'independent_returned_download_verified':False,'scientific_acquisition_gate_passed':False})
 return prior.read(ledger/'STOP.json')
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--archive',type=Path,required=True);a=ap.parse_args();print(json.dumps(cleanup(a.archive),indent=2))
