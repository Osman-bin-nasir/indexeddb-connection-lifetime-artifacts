"""All frozen assignments must satisfy their selected controller's technical guard."""
import ast,importlib.util,unittest
from pathlib import Path
HERE=Path(__file__).parent
s=importlib.util.spec_from_file_location('dispatch_check',HERE/'backend_dispatch_v2.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class DispatchTests(unittest.TestCase):
 def test_every_assignment_satisfies_selected_exact_condition_guard(self):
  science,quals=m.core.frozen()
  for a in [*science.values(),*quals.values()]:
   f,name=m.route(a);tree=ast.parse((HERE/'backend_v1/engine'/f/(name+'.py')).read_text());fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='run_one')
   candidates=[]
   for n in ast.walk(fn):
    if not isinstance(n,ast.If) or not n.body or not isinstance(n.body[0],ast.Raise):continue
    reason=ast.unparse(n.body[0])
    if any(t in reason for t in ['Required extended cell','Only exact registered','Unsupported exact registered']):candidates.append(n.test)
   self.assertTrue(candidates,a['trial_id'])
   values={'assignment':a,'a':a,'RUN_ROLE':a['role']}
   for n in tree.body:
    if isinstance(n,ast.Assign):
     for target in n.targets:
      if isinstance(target,ast.Name) and target.id=='PROFILE_MAP':values['PROFILE_MAP']=ast.literal_eval(n.value)
   for guard in candidates:
    self.assertFalse(eval(compile(ast.Expression(guard),'<static registered-condition guard>','eval'),{'__builtins__':{}},values),a['trial_id']+' routed to '+f+'/'+name)
 def test_qmp_scope_and_quiet_workload_use_qualified_ordinary_path(self):
  science,_=m.core.frozen()
  for a in science.values():
   if (a['experiment']=='fault_scope_comparison' and a['fault']=='qmp_reset') or (a['experiment']=='application_and_background_activity' and a['workload']=='single_256_bytes'):self.assertEqual(m.route(a),('repairs/004','qualification_candidate'))
if __name__=='__main__':unittest.main()
