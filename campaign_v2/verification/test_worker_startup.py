"""Regression fixture: startup failure must release the worker and its log."""
import io,sys,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch,Mock
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'repairs/002'))
from qualification_candidate import Worker

class WorkerStartup(unittest.TestCase):
    def test_missing_readiness_cleans_up_before_propagating(self):
        proc=Mock();proc.stdin=io.BytesIO();proc.stdout=iter([]);proc.poll.return_value=None;proc.wait.return_value=0
        w=object.__new__(Worker)
        with tempfile.TemporaryDirectory() as d,patch('qualification_candidate.subprocess.Popen',return_value=proc),patch.object(Worker,'wait',side_effect=TimeoutError('synthetic readiness timeout')):
            with self.assertRaises(TimeoutError):Worker.__init__(w,types.SimpleNamespace(port=1),{'trial_id':'synthetic'},d,lambda *a,**k:None)
            self.assertTrue(w.error.closed);self.assertFalse(w.thread.is_alive());proc.wait.assert_called_once()

if __name__=='__main__':unittest.main(verbosity=2)
