import unittest
from guest_volume import profile_options
class ProfileTests(unittest.TestCase):
 def test_default_profiles_have_no_custom_mount_flags(self):
  self.assertEqual(profile_options('ext4_defaults'),('ext4',[],'defaults'))
  self.assertEqual(profile_options('xfs_defaults'),('xfs',[],'defaults'))
 def test_custom_reference_flags_exact(self):self.assertEqual(profile_options('ext4_commit30'),('ext4',['-o','commit=30,discard'],'commit=30,discard'))
 def test_other_profile_blocked(self):
  with self.assertRaises(RuntimeError):profile_options('other')
if __name__=='__main__':unittest.main()
