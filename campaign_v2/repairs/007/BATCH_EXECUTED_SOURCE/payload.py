"""Canonical prospective payload contract, shared with verification, never generated after fault."""
import hashlib
import json

CAMPAIGN = 'indexeddb-connection-lifetime-mac-20261003-v2'


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True)


def record(trial_id, number, count=1, size=256, sentinel=False):
    role = f'sentinel-{number}' if sentinel else str(number)
    chunks = [hashlib.sha256(f'{CAMPAIGN}|{trial_id}|{role}|{i}'.encode()).hexdigest()
              for i in range((size+63)//64)]
    payload = ''.join(chunks)[:size]
    metadata = {'campaign': CAMPAIGN, 'trial': trial_id, 'record': role,
                'record_count': count, 'payload_bytes': size, 'sentinel': sentinel}
    return {'id': f'{trial_id}:{role}', 'trial': f'{trial_id}:sentinel' if sentinel else trial_id,
            'payload': payload, 'metadata': metadata,
            'checksum': hashlib.sha256((canonical(metadata)+'\n'+payload).encode('ascii')).hexdigest()}


def contract(assignment):
    a = dict(assignment)
    if a['workload'] not in {'single_256_bytes','single_64k_bytes','ten_records_one_transaction',
                             'four_connections','background_fsync'}:
        raise ValueError('Unrecognized registered workload')
    count = 10 if a['workload'] == 'ten_records_one_transaction' else 1
    size = 65536 if a['workload'] == 'single_64k_bytes' else 256
    a.update(database=f'{CAMPAIGN}:{a["trial_id"]}',
             sentinel=record(a['trial_id'],0,sentinel=True),
             targets=[record(a['trial_id'],i,count,size) for i in range(count)],
             canonical_metadata_policy='sorted ASCII JSON without spaces, newline, ASCII payload')
    return a
