"""Observed byte-to-file-range correspondences only. Missing correspondence does not establish absence."""
from backend_runtime import RUN_ROLE, ENGINE, ATTEMPT_RELATIVE, attempt_root, validate_reserved, validate_assignment, deploy_worker
import hashlib, json
from pathlib import Path

def relationships(capture, inventory, folder, contract):
    result = []
    payloads = {r['id']: r['payload'].encode('ascii') for r in contract['targets']}
    for r in capture['records']:
        if r['data_hex'] is None or r['returned'] <= 0 or r['offset'] is None:
            continue
        data = bytes.fromhex(r['data_hex'])[:r['returned']]
        path = r['path'] or ''
        for f in inventory['files']:
            if not path.endswith('/' + f['relative_path']):
                continue
            image = (Path(folder) / f['relative_path']).read_bytes()
            off = r['offset']
            chunk = image[off:off + len(data)]
            result.append({'capture_line': r['line'], 'path': f['relative_path'], 'offset': off, 'returned_bytes': r['returned'], 'observed_bytes_sha256': hashlib.sha256(data).hexdigest(), 'immutable_extract_sha256': f['sha256'], 'exact_file_range_matches': chunk == data, 'file_magic_hex': image[:32].hex(), 'payload_occurrences_in_observed_argument': [{'target_id': k, 'offset_in_argument': data.find(b), 'interpretation': 'positive byte occurrence only; serialized field identity/page-cell decoding not established'} for k, b in payloads.items() if b in data]})
    return {'observed_correspondences': result, 'source_kind': 'read-only extract after reset and boot activity, not instantaneous fault state', 'no_missing_event_or_target_absence_claim': True, 'serialized_field_or_callback_attribution': 'not established', 'sqlite_wal_page_formats_recorded_separately': True}
