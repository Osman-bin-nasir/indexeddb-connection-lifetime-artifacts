import unittest
from guest_fault_agent import select_tree
EXE='/opt/chromium';PROFILE='/var/lib/idbv2/unique/profile'
def row(pid,ppid,pgrp,root=False):
 return {'pid':pid,'ppid':ppid,'pgrp':pgrp,'session':pid,'start_ticks':pid*10,'exe':EXE,'cmdline':['--user-data-dir='+PROFILE] if root else ['--type=renderer'],'state':'S'}
class Tests(unittest.TestCase):
 def test_descendants_selected_and_group_unique(self):
  values={40001:row(40001,10,40001,True),40002:row(40002,40001,40001),40003:row(40003,40002,40001),40004:row(40004,7,40004)}
  got=select_tree(values,PROFILE,EXE);self.assertEqual([x['pid'] for x in got['processes']],[40001,40002,40003]);self.assertEqual(got['groups'],[40001])
 def test_duplicate_browser_refused(self):
  with self.assertRaises(RuntimeError):select_tree({40001:row(40001,10,40001,True),40002:row(40002,10,40002,True)},PROFILE,EXE)
 def test_outsider_refused(self):
  with self.assertRaises(RuntimeError):select_tree({40001:row(40001,10,40001,True),40002:row(40002,7,40001)},PROFILE,EXE)
 def test_wrong_executable_refused(self):
  with self.assertRaises(RuntimeError):select_tree({40001:row(40001,10,40001,True)},PROFILE,'wrong')
 def test_unsafe_group_refused(self):
  with self.assertRaises(RuntimeError):select_tree({40001:row(40001,10,1,True)},PROFILE,EXE)
if __name__=='__main__':unittest.main()

class FlattenedTitleTests(unittest.TestCase):
 def test_real_packaged_title_selects_only_root(self):
  import json
  from pathlib import Path
  doc=json.loads((Path(__file__).resolve().parents[2]/'support/process_diagnostics/support-process-selection-20261004-00001/CHROME_PROCESSES.json').read_text())
  got=select_tree({r['pid']:r for r in doc['processes']},doc['profile_requested'],doc['executable_expected'])
  self.assertEqual(got['root_pid'],1994);self.assertEqual(got['groups'],[1994]);self.assertNotIn(1996,{r['pid'] for r in got['processes']})
 def test_prefix_profile_refused(self):
  root=row(40001,10,40001,True);root['cmdline']=[EXE+' --user-data-dir='+PROFILE+'-other about:blank']
  with self.assertRaises(RuntimeError):select_tree({40001:root},PROFILE,EXE)
 def test_flattened_child_not_another_root(self):
  root=row(40001,10,40001,True);root['cmdline']=[EXE+' --user-data-dir='+PROFILE+' about:blank']
  child=row(40002,40001,40001);child['cmdline']=[EXE+' --type=renderer --user-data-dir='+PROFILE+' trailing']
  got=select_tree({40001:root,40002:child},PROFILE,EXE);self.assertEqual(got['root_pid'],40001)
