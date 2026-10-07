from backend_runtime import RUN_ROLE, ENGINE, ATTEMPT_RELATIVE, attempt_root, validate_reserved, validate_assignment, deploy_worker
import unittest
from boot_mounts import EXPECTED, transform, validate_inventory
TEXT = '# image configuration\nLABEL=cloudimg-rootfs\t/\text4\tdiscard,commit=30,errors=remount-ro\t0 1\nLABEL=BOOT /boot ext4 defaults 0 2\nLABEL=UEFI /boot/efi vfat umask=0077 0 1\n'

class Tests(unittest.TestCase):

    def test_exact_only_sources(self):
        self.assertEqual(transform(TEXT), TEXT.replace('LABEL=BOOT', '/dev/vda16').replace('LABEL=UEFI', '/dev/vda15'))

    def test_reject_mount_relaxation(self):
        with self.assertRaises(ValueError):
            transform(TEXT.replace('defaults', 'defaults,nofail'))

    def test_reject_missing(self):
        with self.assertRaises(ValueError):
            transform(TEXT.split('LABEL=UEFI')[0])

    def test_reject_duplicate(self):
        with self.assertRaises(ValueError):
            transform(TEXT + TEXT.splitlines()[2] + '\n')

    def test_identity(self):
        i = {'root_source': '/dev/vda1', 'partitions': {e['device']: {k: e[k] for k in ['label', 'type', 'uuid', 'partuuid']} for e in EXPECTED.values()}, 'mount_sources': {m: e['device'] for m, e in EXPECTED.items()}}
        validate_inventory(i)
        i['partitions']['/dev/vda16']['uuid'] = 'wrong'
        with self.assertRaises(ValueError):
            validate_inventory(i)
if __name__ == '__main__':
    unittest.main()

class DirectInventoryTests(unittest.TestCase):

    def test_direct_table_not_cached_uuid(self):
        from boot_mounts import INVENTORY_COMMAND
        self.assertIn("['sudo','sfdisk','--json','/dev/vda']", INVENTORY_COMMAND)
        self.assertNotIn("['lsblk'", INVENTORY_COMMAND)

    def test_blank_partition_uuid_rejected(self):
        i = {'root_source': '/dev/vda1', 'partitions': {e['device']: {k: e[k] for k in ['label', 'type', 'uuid', 'partuuid']} for e in EXPECTED.values()}, 'mount_sources': {m: e['device'] for m, e in EXPECTED.items()}}
        i['partitions']['/dev/vda16']['partuuid'] = ''
        with self.assertRaises(ValueError):
            validate_inventory(i)
