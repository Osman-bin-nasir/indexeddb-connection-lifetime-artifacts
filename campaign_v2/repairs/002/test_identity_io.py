"""Synthetic support tests, no VM or campaign assignment."""
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch
from identity_io import GUEST_WRITE,read_identity,write_identity

class IdentityTests(unittest.TestCase):
    def test_invalid_responses_fail_with_exact_bytes_retained(self):
        for raw in [b'',b'not json',b'null',b'{}',b'\xff']:
            with self.subTest(raw=raw),tempfile.TemporaryDirectory() as d:
                reply=types.SimpleNamespace(returncode=0,stdout=raw,stderr=b'diagnostic')
                with self.assertRaises(RuntimeError):read_identity(lambda *a,**k:reply,1,{'trial_id':'fixture'},d,'recovery')
                self.assertEqual((Path(d)/'recovery.stdout').read_bytes(),raw)
                self.assertEqual((Path(d)/'recovery.stderr').read_bytes(),b'diagnostic')

    def test_failed_remote_cannot_become_valid_identity(self):
        with tempfile.TemporaryDirectory() as d:
            reply=types.SimpleNamespace(returncode=1,stdout=b'{"trial_id":"fixture"}',stderr=b'failure')
            with self.assertRaises(RuntimeError):read_identity(lambda *a,**k:reply,1,{'trial_id':'fixture'},d,'recovery')

    def test_write_uses_independent_readback_and_requires_sync_receipt(self):
        expected={'trial_id':'fixture'};calls=[]
        with tempfile.TemporaryDirectory() as d:
            responses=iter([types.SimpleNamespace(returncode=0,stdout=json.dumps({'identity':expected,'file_fsync_completed':True,'directory_fsync_completed':True}).encode(),stderr=b''),types.SimpleNamespace(returncode=0,stdout=json.dumps(expected).encode(),stderr=b'')])
            def remote(*a,**k):calls.append((a,k));return next(responses)
            self.assertEqual(write_identity(remote,1,expected,d),expected)
            self.assertEqual(len(calls),2)

    def test_missing_sync_receipt_blocks_readback(self):
        calls=[]
        with tempfile.TemporaryDirectory() as d:
            def remote(*a,**k):calls.append(a);return types.SimpleNamespace(returncode=0,stdout=b'{"identity":{"trial_id":"fixture"}}',stderr=b'')
            with self.assertRaises(RuntimeError):write_identity(remote,1,{'trial_id':'fixture'},d)
            self.assertEqual(len(calls),1)

    def test_guest_writer_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            target=Path(d)/'attempt.json';target.write_bytes(b'original')
            script=GUEST_WRITE.replace("'/opt/idbv2/attempt.json'",repr(str(target)))
            import subprocess,sys
            result=subprocess.run([sys.executable,'-c',script],input=b'{"trial_id":"fixture"}',capture_output=True)
            self.assertNotEqual(result.returncode,0);self.assertEqual(target.read_bytes(),b'original')

    def test_sync_failure_prevents_success_receipt(self):
        with tempfile.TemporaryDirectory() as d:
            target=Path(d)/'attempt.json'
            script=GUEST_WRITE.replace("'/opt/idbv2/attempt.json'",repr(str(target)))
            script=script.replace('identity=json.loads(raw)',"identity=json.loads(raw)\ndef fail_sync(fd):raise OSError('synthetic sync failure')\nos.fsync=fail_sync")
            import subprocess,sys
            result=subprocess.run([sys.executable,'-c',script],input=b'{"trial_id":"fixture"}',capture_output=True)
            self.assertNotEqual(result.returncode,0);self.assertEqual(result.stdout,b'')

if __name__=='__main__':unittest.main(verbosity=2)
