"""Qualified dispatch plus a derived registered-endpoint receipt.

All executed measurement/controller/audit sources remain unchanged. This adapter
adds a source-bound projection after the independent audit; it never rewrites a
raw result or adds a trial. Log-prefix disagreement requires full-image retention.
"""
import argparse,importlib.util,sys
from pathlib import Path
HERE=Path(__file__).parent
s=importlib.util.spec_from_file_location('qualified_dispatch_v2',HERE/'backend_dispatch_v2.py');prior=importlib.util.module_from_spec(s);s.loader.exec_module(prior)
s=importlib.util.spec_from_file_location('registered_endpoint_projection',HERE/'registered_endpoint_v1.py');projection=importlib.util.module_from_spec(s);s.loader.exec_module(projection)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--assignment',type=Path,required=True);ap.add_argument('--attempt-dir',type=Path,required=True);args=ap.parse_args()
 a=prior.core.read(args.assignment)
 if a['role']!='scientific':raise RuntimeError('This adapter consumes only explicitly reserved scientific assignments')
 success=prior.core.execute(a,args.attempt_dir)
 if (args.attempt_dir/'RESULT.json').exists():prior.core.save(args.attempt_dir/'REGISTERED_ENDPOINT.json',projection.project(args.attempt_dir))
 raise SystemExit(0 if success else 2)
if __name__=='__main__':main()
