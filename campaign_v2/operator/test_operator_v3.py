"""Synthetic stop/reservation fixtures only. No scientific or guest data fabricated."""
import importlib.util,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
s=importlib.util.spec_from_file_location('operator_v3_test',Path(__file__).with_name('operator_v3.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class OperatorTests(unittest.TestCase):
 def test_author_hold_blocks_without_consuming(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)
   with patch.object(m.base,'STATE',root),patch.object(m.base,'assignments',return_value=[]),patch.object(m.base.subprocess,'check_output',return_value=m.base.TAG+'\n'):
    with self.assertRaisesRegex(RuntimeError,'AUTHOR_HOLD'):m.batch(1)
   self.assertFalse((root/'RUNNING.lock').exists())
 def test_backend_failure_consumes_one_and_stops_without_retry(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);state=root/'operator';state.mkdir();sci=root/'scientific/attempts';a={'trial_id':'fixture-one','experiment':'fixture','role':'scientific'};b=dict(a,trial_id='fixture-two')
   (state/'FINAL_INPUT_LOCK.json').write_text(json.dumps({'resource_receipt':'resource.json','operation_headroom_bytes':1,'input_hashes':{},'backend_script':'never-executed-fixture.py'}));(root/'resource.json').write_text(json.dumps({'max_trial_allocated_bytes':1,'archive_scratch_headroom_bytes':1}))
   with patch.object(m,'ROOT',root),patch.object(m,'HERE',state),patch.object(m.base,'SCI',sci),patch.object(m.base,'STATE',state),patch.object(m,'preflight',return_value={'passed':True}),patch.object(m.base,'disk_check',return_value={'passed':True}),patch.object(m.base,'assignments',return_value=[a,b]),patch.object(m.base,'status',return_value={}),patch.object(m.subprocess,'run',return_value=type('Result',(),{'returncode':2})()) as backend:
    with self.assertRaisesRegex(RuntimeError,'consumed slot'):m.batch(2)
    self.assertEqual(backend.call_count,1);self.assertTrue((sci/'fixture-one/START.json').exists());self.assertFalse((sci/'fixture-two').exists());self.assertFalse((state/'RUNNING.lock').exists());self.assertFalse(json.loads((state/'LAST_BATCH.json').read_text())['passed'])
 def test_independent_audit_required_beyond_controller_result(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'assignment.json').write_text(json.dumps({'trial_id':p.name,'role':'scientific','keep_full_overlay_seeded':False}));(p/'RESULT.json').write_text(json.dumps({'role':'scientific','scientific_denominator':True,'endpoint':'recovered'}));(p/'SHA256.json').write_text('{}');(p/'INDEPENDENT_VERIFICATION.json').write_text(json.dumps({'trial_id':p.name,'scientific_denominator':True,'independent_pass':False}))
   with patch.object(m.retention,'removal_records',return_value={}):
    with self.assertRaisesRegex(RuntimeError,'Independent scientific'):m.verify_attempt(p)
if __name__=='__main__':unittest.main()
