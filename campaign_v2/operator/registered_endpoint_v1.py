"""Prospective registered endpoint projection. Never edits a controller result.

PREREGISTRATION section 4.2 specifies the three dependent dm-log-writes prefixes.
The last fully recorded prefix before the boundary is the log-model boundary
endpoint for the matched linear comparison. The captured physical data-device
oracle is preserved as a distinct observation. Prefixes never add trials.
"""
import hashlib,json
from pathlib import Path
HERE=Path(__file__).parent;ROOT=HERE.parent;PROTOCOL=ROOT.parent/'confirmatory/PREREGISTRATION.md'
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def project(out):
 out=Path(out);a=read(out/'assignment.json');r=read(out/'RESULT.json')
 result={'trial_id':a['trial_id'],'role':a['role'],'scientific_denominator':a['role']=='scientific','protocol_sha256':sha(PROTOCOL),'controller_result_sha256':sha(out/'RESULT.json'),'controller_endpoint':r['endpoint'],'registered_endpoint':r['endpoint'],'controller_result_unchanged':True,'dependent_prefixes_add_trials':False,'scientific_trial_increment':0,'source':'captured recovery oracle','full_images_required_for_endpoint_disagreement':False}
 if a.get('mapper')!='dm_log_writes':return result
 # A failed attempt stays unknown/noneligible. Projection cannot rescue it.
 if r.get('technical_eligible',r.get('qualification_passed')) is not True:
  result.update(registered_endpoint='unknown',source='failed log-model capture; no valid boundary endpoint');return result
 p=out/'REGISTERED_LOG_PREFIXES.json';capture=read(p);decode=read(out/'log-prefixes/LOG_DECODE.json')
 if capture.get('all_prefixes_interpretable') is not True or capture.get('prefixes_not_trials') is not True:raise RuntimeError('Unrecorded log-model boundary')
 names=['immediately_before_ack_marker','at_ack_marker','last_fully_recorded_before_boundary']
 rows=capture['prefixes']
 if [x['name'] for x in rows]!=names:raise RuntimeError('Wrong registered prefix set/order')
 boundary=rows[2]
 if boundary['last_entry']!=decode['last_fully_recorded_entry'] or boundary['prefix_includes_ack_marker'] is not True:raise RuntimeError('Boundary prefix identity mismatch')
 oracle=out/boundary['oracle_path']
 if oracle.is_symlink() or not oracle.resolve().is_relative_to(out.resolve()):raise RuntimeError('Unsafe prefix oracle path')
 endpoint=read(oracle)['guest']['endpoint']
 if endpoint not in ['recovered','lost'] or endpoint!=boundary['endpoint']:raise RuntimeError('Boundary prefix oracle disagreement')
 result.update(registered_endpoint=endpoint,source='last fully recorded dm-log-writes prefix before boundary',prefix_receipt_sha256=sha(p),log_decode_sha256=sha(out/'log-prefixes/LOG_DECODE.json'),boundary_oracle_sha256=sha(oracle),boundary_last_entry=boundary['last_entry'],full_images_required_for_endpoint_disagreement=endpoint!=r['endpoint'])
 return result
