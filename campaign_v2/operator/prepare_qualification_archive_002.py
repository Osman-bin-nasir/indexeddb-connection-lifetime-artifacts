"""Bounded local archive preparation. No experiment, offload or evidence deletion."""
import importlib.util,json,datetime
from pathlib import Path
HERE=Path(__file__).parent;ROOT=HERE.parent
s=importlib.util.spec_from_file_location('archive_engine',HERE/'archive_v2.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
def main():
 name='qualification-full-evidence-20261004-002';admin=HERE/'archive_plans';admin.mkdir(exist_ok=True);manifest=admin/(name+'.json');measurement=admin/(name+'-compression.json');out=HERE/'archives'/name
 ids=sorted(p.name for p in (ROOT/'qualification/attempts').iterdir() if (p/'RESULT.json').exists())
 package=m.inventory(ids,'qualification')
 # Include the prospective plans, exact executed source snapshots, administrative
 # audits, immutable protocol and operator. Exclude images here since selected
 # image dependencies are already enumerated, plus all credentials and payloads.
 for top in [ROOT/'repairs',ROOT/'extensions',ROOT/'verification',HERE/'backend_v1']:
  for p in top.rglob('*'):
   if not p.is_file() or '__pycache__' in p.parts or p.suffix not in ['.json','.md','.txt','.py','.bt','.diff']:continue
   package['members'][str(p.relative_to(ROOT))]={'sha256':m.sha(p),'bytes':p.stat().st_size}
 for p in [HERE/'archive_v2.py',HERE/'operator_v2.py',HERE/'operator.py',HERE/'QUALIFICATION_RECEIPT_001.json',HERE/'RESOURCE_FORECAST_001.json']:
  package['members'][str(p.relative_to(ROOT))]={'sha256':m.sha(p),'bytes':p.stat().st_size}
 m.save(manifest,package);receipt=m.measure(package,measurement);result=m.pack(package,out,receipt);m.save(admin/(name+'-STOP.json'),{'utc':m.now(),**result,'scientific_started':0,'originals_retained':True});print(json.dumps(result,indent=2))
if __name__=='__main__':main()
