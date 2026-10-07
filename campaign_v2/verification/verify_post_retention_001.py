"""Read-only integrity audit after author-directed temporary-image cleanup."""
import datetime,hashlib,importlib.util,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OP=ROOT/'operator'
s=importlib.util.spec_from_file_location('post_retention',OP/'retention_v2.py');r=importlib.util.module_from_spec(s);s.loader.exec_module(r)
rows=[]
for attempt in sorted((ROOT/'qualification/attempts').iterdir()):
 if not (attempt/'START.json').exists():continue
 row=r.verify_inventory(attempt)
 if (attempt/'OPERATOR_SHA256.json').exists():row['operator_seal']=r.verify_inventory(attempt,'OPERATOR_SHA256.json')
 rows.append(row)
# Hash every resident retained scientific-capture image and backing member from
# the immutable archive manifest. Administrative snapshots are historic copies
# and are not compared with newer administrative status files.
arc=OP/'archives/qualification-full-evidence-20261004-002';manifest=r.prior.read(arc/'TRANSFER_MANIFEST.json');images=[]
for n,v in manifest['members'].items():
 p=ROOT/n
 if not r.prior.arc.image(p) and not n.startswith('provision/'):continue
 if not p.is_file() or p.stat().st_size!=v['bytes'] or r.prior.sha(p)!=v['sha256']:raise RuntimeError('Retained image/backing input changed '+n)
 images.append(n)
frozen=ROOT.parent/'confirmatory'
for line in (frozen/'SHA256SUMS').read_text().splitlines():
 h,n=line.split(maxsplit=1)
 if r.prior.sha(frozen/n.strip())!=h:raise RuntimeError('Frozen design changed')
tag=subprocess.check_output(['git','rev-parse','prereg-connection-lifetime-mac-v2^{}'],cwd=ROOT,text=True).strip()
if tag!='5a749734a0a63f3e1c662bb91dd829e6f288dc5c':raise RuntimeError('Frozen tag changed')
scientific=list((ROOT/'scientific/attempts').iterdir()) if (ROOT/'scientific/attempts').exists() else []
if scientific:raise RuntimeError('Scientific acquisition present during author hold')
value={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'passed':True,'scope':'post-cleanup resident raw/console inventories and retained image/backing hashes','qualification_attempts_checked':len(rows),'resident_inventory_members_checked':sum(x['resident_members_verified'] for x in rows),'permitted_missing_normal_images':sum(len(x['permitted_absent_normal_images']) for x in rows),'retained_images_and_provision_inputs_checked':len(images),'rows':rows,'retained_images':images,'frozen30_files_match':True,'frozen_tag_peeled':tag,'scientific_started':0,'author_hold':True,'independent_returned_download_verified':False,'no_raw_results_or_inventories_edited':True}
with (OP/'POST_RETENTION_VERIFICATION_001.json').open('x') as f:json.dump(value,f,indent=2);f.write('\n')
print(json.dumps({k:value[k] for k in ['passed','qualification_attempts_checked','resident_inventory_members_checked','permitted_missing_normal_images','retained_images_and_provision_inputs_checked','scientific_started']}))
