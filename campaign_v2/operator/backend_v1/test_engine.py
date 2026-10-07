"""Static integration checks. No VM or scientific acquisition."""
import ast,importlib.util,json,subprocess,sys,unittest
from pathlib import Path
HERE=Path(__file__).parent;ROOT=HERE.parents[1];sys.path.insert(0,str(HERE))
spec=importlib.util.spec_from_file_location('backend_static',HERE/'backend.py');backend=importlib.util.module_from_spec(spec);spec.loader.exec_module(backend)
def func(p,name):
 tree=ast.parse(p.read_text());return next(n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name==name)
class IntegrationTests(unittest.TestCase):
 def test_all_registered_routes_implemented(self):
  science,quals=backend.frozen();self.assertEqual(len(science),930);self.assertEqual(len(quals),95)
  for a in science.values():f,m=backend.route(a);self.assertTrue((HERE/'engine'/f/(m+'.py')).is_file());self.assertTrue((HERE/'engine'/f/'independent_audit.py').is_file())
 def test_helper_and_controller_sources_match_manifest(self):backend.verify_sources()
 def test_close_mapping_and_deadline_wait_unchanged(self):
  for folder in ['repairs/004','repairs/007','repairs/009','repairs/010','repairs/011','repairs/012','extensions/environment']:
   module=next(p for p in (ROOT/folder).glob('qualification_*.py') if p.name not in ['qualification_mapped.py'])
   for name in ['mapped_close','wait_deadline']:
    self.assertEqual(ast.dump(func(module,name),include_attributes=False),ast.dump(func(HERE/'engine'/folder/module.name,name),include_attributes=False))
 def test_original_browser_worker_measurement_body_unchanged(self):
  original=func(ROOT/'guest_worker.py','main');copy=func(HERE/'engine/guest_worker.py','main')
  # Only the explicit role guard changed. The remaining asynchronous measurement,
  # readiness, preparation, close, ACK and oracle operations must be identical.
  self.assertIsInstance(original.body[1],ast.If);self.assertIsInstance(copy.body[1],ast.If)
  self.assertEqual(ast.dump(ast.Module(body=original.body[2:],type_ignores=[]),include_attributes=False),ast.dump(ast.Module(body=copy.body[2:],type_ignores=[]),include_attributes=False))
 def test_no_design_file_changed(self):backend.frozen();self.assertEqual(subprocess.check_output(['git','rev-parse','prereg-connection-lifetime-mac-v2^{commit}'],cwd=ROOT,text=True).strip(),'5a749734a0a63f3e1c662bb91dd829e6f288dc5c')
 def test_scientific_guard_requires_final_lock(self):
  science,_=backend.frozen();a=next(iter(science.values()))
  with self.assertRaisesRegex(RuntimeError,'Final input lock absent'):backend.execute(a,ROOT/'scientific/attempts'/a['trial_id'])
  self.assertFalse((ROOT/'scientific/attempts'/a['trial_id']).exists())
if __name__=='__main__':unittest.main()
