"""Synthetic unit fixtures only. This file never boots a guest or creates a trial."""
import json
from pathlib import Path
import struct
import tempfile
import types
import unittest
from unittest.mock import patch

from forensic_formats import checksum,inspect
from payload import contract
from qualification import assignments,mapped_close,vm_args,VM


class ContractTests(unittest.TestCase):
    def test_frozen_qualification_roles_unique(self):
        values=assignments()
        self.assertEqual(len(values),95)
        self.assertEqual(len({x['trial_id'] for x in values}),95)
        self.assertTrue(all(x['role']=='qualification' for x in values))

    def test_workload_lengths_and_sentinel_separation(self):
        base=assignments()[0]
        for workload,n,size in [('single_256_bytes',1,256),('ten_records_one_transaction',10,256),('four_connections',1,256)]:
            c=contract({**base,'workload':workload})
            self.assertEqual(len(c['targets']),n)
            self.assertEqual(len({x['id'] for x in c['targets']}),n)
            self.assertTrue(all(len(x['payload'])==size for x in c['targets']))
            self.assertNotIn(c['sentinel']['id'],{x['id'] for x in c['targets']})

    def test_unknown_workload_blocks(self):
        with self.assertRaises(ValueError):
            contract({**assignments()[0],'workload':'accidental-substitute'})

    def test_clock_mapping_uses_observed_diagnostic(self):
        sample={'host_send_ns':1_000_000_000,'host_receive_ns':1_002_000_000,'guest':{'page_ms':100}}
        event={'guest':{'event':{'page_ms':132}}}
        result=mapped_close([sample],event)
        self.assertEqual(result['estimate_ns'],1_033_000_000)
        self.assertEqual(result['uncertainty_ns'],1_000_000)

    def test_wal_checksum_and_corruption(self):
        page=bytes(512)
        header=struct.pack('>6I',0x377f0682,3007000,512,0,1,2)
        initial=checksum(header,'<')
        h=header+struct.pack('>2I',*initial)
        fields=struct.pack('>2I',7,8)
        next_c=checksum(fields+page,'<',initial)
        frame=fields+struct.pack('>4I',1,2,*next_c)+page
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'synthetic-wal'
            path.write_bytes(h+frame)
            result=inspect(path)
            self.assertTrue(result['frames'][0]['checksum_valid'])
            self.assertEqual(result['frames'][0]['commit_database_pages'],8)
            path.write_bytes(h+frame[:-1]+b'x')
            self.assertFalse(inspect(path)['frames'][0]['checksum_valid'])

    def test_helper_cannot_boot_with_evidence(self):
        with self.assertRaises(RuntimeError):
            vm_args(Path('/synthetic/helper'),Path('/synthetic/qmp'),1234,'test',memory=1024,readonly_disk=Path('/synthetic/evidence'))
        values=vm_args(Path('/synthetic/helper'),Path('/synthetic/qmp'),1234,'test',memory=1024)
        self.assertIn('pcie-root-port,id=evidence-port,slot=1,chassis=1',values)
        self.assertFalse(any('evidence.qcow2' in x for x in values))

    def test_readonly_hotplug_requires_expected_helper_root(self):
        vm=object.__new__(VM);vm.port=1234
        vm.qmp=types.SimpleNamespace(execute=lambda *a:None)
        vm.events=lambda *a,**k:None
        with patch('qualification.remote',return_value=types.SimpleNamespace(stdout=b'/dev/vdc1\n')):
            with self.assertRaises(RuntimeError):vm.attach_evidence_after_boot(Path('/synthetic/evidence'))

    def test_readonly_hotplug_command_and_identity(self):
        calls=[];vm=object.__new__(VM);vm.port=1234
        vm.qmp=types.SimpleNamespace(execute=lambda *a:calls.append(a))
        vm.events=lambda *a,**k:None
        responses=[types.SimpleNamespace(stdout=b'/dev/vda1\n'),types.SimpleNamespace(returncode=0,stdout=b'1\nidbv2-evidence\n')]
        with patch('qualification.remote',side_effect=responses):vm.attach_evidence_after_boot(Path('/synthetic/evidence'))
        self.assertTrue(calls[0][1]['read-only'])
        self.assertTrue(calls[0][1]['file']['read-only'])
        self.assertTrue(calls[0][1]['file']['cache']['direct'])
        self.assertEqual(calls[1][1]['bus'],'evidence-port')


if __name__=='__main__':unittest.main(verbosity=2)
