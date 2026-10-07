"""Synthetic integrity fixtures. No trial or outcome data are generated."""
import importlib.util,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
s=importlib.util.spec_from_file_location('retention_v2_test',Path(__file__).with_name('retention_v2.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class IntegrityTests(unittest.TestCase):
 def fixture(self,root,keep=False):
  p=root/'scientific/attempts/fixture';p.mkdir(parents=True)
  (p/'assignment.json').write_text(json.dumps({'trial_id':'fixture','role':'scientific','keep_full_overlay_seeded':keep}))
  (p/'RESULT.json').write_text(json.dumps({'endpoint':'recovered','technical_eligible':True}))
  (p/'events.jsonl').write_text('synthetic fixture only\n')
  rows={'events.jsonl':m.prior.sha(p/'events.jsonl'),'normal.qcow2':'a'*64}
  (p/'SHA256.json').write_text(json.dumps(rows));(p/'OPERATOR_SHA256.json').write_text(json.dumps(rows))
  return p,{'scientific/attempts/fixture/normal.qcow2':{'sha256':'a'*64,'ledger':'fixture','archive':'fixture'}}
 def test_legitimate_missing_normal_image_verified_in_both_seals(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);p,rows=self.fixture(root)
   with patch.object(m.prior,'ROOT',root),patch.object(m,'removal_records',return_value=rows):
    for inventory in ['SHA256.json','OPERATOR_SHA256.json']:
     r=m.verify_inventory(p,inventory);self.assertEqual(len(r['permitted_absent_normal_images']),1)
 def test_missing_without_ledger_blocks(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);p,_=self.fixture(root)
   with patch.object(m.prior,'ROOT',root),patch.object(m,'removal_records',return_value={}):
    with self.assertRaisesRegex(RuntimeError,'Unexpected missing'):m.verify_inventory(p)
 def test_missing_raw_or_selected_image_blocks_even_with_ledger(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);p,rows=self.fixture(root,keep=True)
   with patch.object(m.prior,'ROOT',root),patch.object(m,'removal_records',return_value=rows):
    with self.assertRaisesRegex(RuntimeError,'Unexpected missing'):m.verify_inventory(p)
   (p/'events.jsonl').unlink();rows['scientific/attempts/fixture/events.jsonl']={'sha256':json.loads((p/'SHA256.json').read_text())['events.jsonl']}
   with patch.object(m.prior,'ROOT',root),patch.object(m,'removal_records',return_value=rows):
    with self.assertRaisesRegex(RuntimeError,'Unexpected missing'):m.verify_inventory(p)
 def test_resident_tamper_blocks(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);p,rows=self.fixture(root);(p/'events.jsonl').write_text('changed fixture\n')
   with patch.object(m.prior,'ROOT',root),patch.object(m,'removal_records',return_value=rows):
    with self.assertRaisesRegex(RuntimeError,'Resident evidence hash mismatch'):m.verify_inventory(p)
if __name__=='__main__':unittest.main()
