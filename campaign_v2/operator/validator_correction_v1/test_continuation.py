"""Offline checks of routing and fail-closed continuation. No guest execution."""
import ast,copy,importlib.util,json,sys,unittest
from pathlib import Path
from unittest.mock import patch
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
import backend_dispatch_validator_v1 as backend
import correction_lock as contract
import operator_validator_v1 as operator

class ContinuationTests(unittest.TestCase):
 def test_only_byte_and_timeline_audit_routes_change(self):
  science,_=backend.frozen()
  families=set()
  for a in science.values():
   folder,name=backend.route(a);directory=backend.rt.ENGINE/folder
   self.assertTrue((directory/(name+'.py')).is_file())
   path=backend.corrected_audit_path(a['experiment'],directory)
   self.assertTrue(path.is_file());families.add(a['experiment'])
   if a['experiment'] not in ('target_byte_diagnostics','trace_category_timelines'):self.assertEqual(path,directory/'independent_audit.py')
  self.assertEqual(len(science),930);self.assertEqual(len(families),9)
 def test_measurement_invocation_and_audit_sequence_retained(self):
  old=ast.parse((backend.core.HERE/'backend.py').read_text());new=ast.parse((HERE/'backend_dispatch_validator_v1.py').read_text())
  old=next(n for n in old.body if isinstance(n,ast.FunctionDef) and n.name=='execute')
  adjusted=copy.deepcopy(old)
  # The new selector inserts only guards before the unchanged scientific branch.
  adjusted.body[1:1]=ast.parse("if role!='scientific':raise RuntimeError('Validator continuation accepts only frozen scientific assignments')\nstart=read(out/'START.json')\naddendum=verify_addendum(start['validator_addendum_sha256'])").body
  for n in ast.walk(adjusted):
   if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='spec_from_file_location':n.args[1]=ast.parse("corrected_audit_path(a['experiment'],directory)",mode='eval').body
   if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='sha' and ast.unparse(n.args[0])=="HERE / 'ENGINE_SOURCE_MANIFEST.json'":n.args[0]=ast.parse("core.HERE/'ENGINE_SOURCE_MANIFEST.json'",mode='eval').body
   if isinstance(n,ast.Dict) and any(isinstance(k,ast.Constant) and k.value=='controller_pass' for k in n.keys):
    n.keys += [ast.Constant('validator_version'),ast.Constant('validator_addendum_sha256')];n.values += [ast.Name('VERSION',ast.Load()),ast.parse("start['validator_addendum_sha256']",mode='eval').body]
  actual=next(n for n in new.body if isinstance(n,ast.FunctionDef) and n.name=='execute')
  self.assertEqual(ast.dump(adjusted,include_attributes=False),ast.dump(actual,include_attributes=False))
 def test_backend_rejects_qualification_before_acquisition(self):
  with self.assertRaisesRegex(RuntimeError,'only frozen scientific'):backend.execute({'role':'qualification'},Path('/not-created'))
 def test_bad_addendum_rejected_before_measurement(self):
  with patch.object(backend,'read',return_value={'validator_addendum_sha256':'bad'}),patch.object(backend,'verify_addendum',side_effect=RuntimeError('wrong digest')),patch.object(backend,'frozen') as forbidden:
   with self.assertRaisesRegex(RuntimeError,'wrong digest'):backend.execute({'role':'scientific'},Path('/not-created'))
   forbidden.assert_not_called()
 def test_other_failed_attempt_never_accepted(self):
  with patch.object(contract,'read',return_value={'independent_pass':False}):
   with self.assertRaisesRegex(RuntimeError,'Undisposed'):contract.effective_verification(Path('/other-failed-slot'))
 def test_wrong_addendum_digest_never_accepted(self):
  with patch.object(contract,'sha',return_value='actual'):
   with self.assertRaisesRegex(RuntimeError,'hash mismatch'):contract.verify_addendum('different')
 def test_next_slot_is_312_and_no_retry(self):
  self.assertEqual(operator.selected(1)[0]['trial_id'],'scientific-target_byte_diagnostics-00002')
  with self.assertRaises(RuntimeError):operator.selected(21)
  self.assertFalse((operator.b.SCI/'scientific-target_byte_diagnostics-00002').exists())

if __name__=='__main__':unittest.main(verbosity=2)
