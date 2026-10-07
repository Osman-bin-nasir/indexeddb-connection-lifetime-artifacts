"""Explicit qualified-path dispatch, including quiet workload and QMP scope controls.

The executed backend_v1 integration source is preserved. This new adapter selects
its unchanged role-capable controller using the frozen assignment, with no timing,
oracle, instrumentation or measurement-function changes.
"""
import importlib.util,sys
from pathlib import Path
HERE=Path(__file__).parent;CORE=HERE/'backend_v1';sys.path.insert(0,str(CORE))
spec=importlib.util.spec_from_file_location('operator_backend_core',CORE/'backend.py');core=importlib.util.module_from_spec(spec);spec.loader.exec_module(core)
original_route=core.route
def route(a):
 f=a['experiment']
 if f=='fault_scope_comparison' and a['fault']=='qmp_reset':return 'repairs/004','qualification_candidate'
 if f=='application_and_background_activity' and a['workload']=='single_256_bytes':return 'repairs/004','qualification_candidate'
 return original_route(a)
core.route=route
if __name__=='__main__':core.main()
