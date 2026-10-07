"""Temporary fixtures verify evidence integrity, denominator separation and stop behavior."""
import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import importlib.util
spec=importlib.util.spec_from_file_location('idbv2_operator',Path(__file__).with_name('operator.py'));op=importlib.util.module_from_spec(spec);spec.loader.exec_module(op)
class EvidenceTests(unittest.TestCase):
 def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name)
 def tearDown(self):self.tmp.cleanup()
 def complete(self):
  p=self.base/'attempt';p.mkdir();(p/'RESULT.json').write_text('{}');(p/'raw.json').write_text('{"real_fixture":true}');(p/'SHA256.json').write_text(json.dumps({'raw.json':op.sha(p/'raw.json')}));return p
 def test_tampering_rejected(self):
  p=self.complete();op.inventory_check(p);(p/'raw.json').write_text('changed')
  with self.assertRaisesRegex(RuntimeError,'hash mismatch'):op.inventory_check(p)
 def test_unfinished_not_verified(self):
  with self.assertRaisesRegex(RuntimeError,'Unfinished'):op.inventory_check(self.base)
 def test_inventory_cannot_escape_root(self):
  p=self.complete();(p/'SHA256.json').write_text(json.dumps({'../secret':'irrelevant'}))
  with self.assertRaisesRegex(RuntimeError,'Unsafe'):op.inventory_check(p)
 def test_qualification_not_scientific_result(self):
  with self.assertRaisesRegex(RuntimeError,'provenance'):op.validate_result({'role':'qualification','scientific_denominator':False,'endpoint':'lost'})
 def test_unknown_is_separate_endpoint(self):
  op.validate_result({'role':'scientific','scientific_denominator':True,'endpoint':'unknown'})
 def test_directory_without_result_consumed_and_unknown(self):
  sci=self.base/'scientific';(sci/'s1').mkdir(parents=True)
  fake=[{'trial_id':'s1','experiment':'family'},{'trial_id':'s2','experiment':'family'}]
  with patch.object(op,'assignments',return_value=fake),patch.object(op,'SCI',sci),patch.object(op,'STATE',self.base/'state'):
   s=op.status(write=False);self.assertEqual(s['started'],1);self.assertEqual(s['complete'],0);self.assertEqual(s['remaining'],1);self.assertEqual(s['families']['family']['unknown'],1)
 def test_disk_floor_includes_headroom(self):
  with patch.object(op.shutil,'disk_usage',return_value=type('Usage',(),{'free':8*1024**3})()):
   with self.assertRaisesRegex(RuntimeError,'DISK_STOP'):op.disk_check(3*1024**3)
 def test_missing_gate_blocks_before_consumption(self):
  with patch.object(op,'assignments',return_value=[]),patch.object(op,'STATE',self.base/'state'),patch.object(op.subprocess,'check_output',return_value=op.TAG+'\n'):
   with self.assertRaisesRegex(RuntimeError,'final input lock'):op.run_batch(1)
  self.assertFalse((self.base/'state/RUNNING.lock').exists())
class ArchiveIntegrationTests(unittest.TestCase):
 def test_chunks_roundtrip_and_tamper_rejection(self):
  import os
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);p=root/'qualification/attempts/temp-fixture-only';p.mkdir(parents=True)
   (p/'RESULT.json').write_text(json.dumps({'role':'qualification','scientific_denominator':False}))
   (p/'fixture-bytes.bin').write_bytes(os.urandom(65536))
   (p/'SHA256.json').write_text(json.dumps({n:op.sha(p/n) for n in ['RESULT.json','fixture-bytes.bin']}))
   with patch.object(op,'ROOT',root),patch.object(op,'STATE',root/'operator'),patch.object(op,'CHUNK',4096):
    result=op.archive(['temp-fixture-only']);out=Path(result['archive']);self.assertTrue(result['passed']);self.assertFalse(result['offload_verified']);self.assertTrue(p.exists())
    chunks=op.read(out/'CHUNKS.json')['chunks'];self.assertGreater(len(chunks),1);self.assertTrue(all(c['bytes']<=4096 for c in chunks))
    self.assertTrue(op.verify_archive(out)['passed'])
    c=out/chunks[0]['name'];data=c.read_bytes();c.write_bytes(bytes([data[0]^1])+data[1:])
    with self.assertRaises(Exception):op.verify_archive(out)
if __name__=='__main__':unittest.main()
