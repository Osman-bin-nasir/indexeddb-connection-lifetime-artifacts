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
