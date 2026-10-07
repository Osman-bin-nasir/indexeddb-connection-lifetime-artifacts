from backend_runtime import RUN_ROLE, ENGINE, ATTEMPT_RELATIVE, attempt_root, validate_reserved, validate_assignment, deploy_worker
import sys, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
import qualification_environment as q

class EnvironmentTopology(unittest.TestCase):

    def test_dedicated_data_not_helper_boot(self):
        q.DATA = Path('/tmp/test-data.qcow2')
        main = q.vm_args('/tmp/root', '/tmp/qmp', 2233, 'unit')
        helper = q.vm_args('/tmp/helper', '/tmp/qmph', 2234, 'unit', memory=1024)
        self.assertIn('virtio-blk-pci,drive=data-drive,serial=idbv2-data,bus=data-port', main)
        self.assertFalse(any(('test-data' in str(x) for x in helper)))
        self.assertIn('pcie-root-port,id=evidence-port,slot=1,chassis=1', helper)

    def test_frozen_profiles_exact(self):
        self.assertEqual(set(q.PROFILE_MAP), {'ext4_commit30_data_volume', 'ext4_default_data_volume', 'xfs_default_data_volume'})

    def test_scheduled_uptime_preserved_by_contract(self):
        a = next((x for x in q.assignments() if x['experiment'] == 'environment_sensitivity'))
        self.assertEqual(q.contract(a)['planned_uptime_ms'], a['planned_uptime_ms'])
if __name__ == '__main__':
    unittest.main()
