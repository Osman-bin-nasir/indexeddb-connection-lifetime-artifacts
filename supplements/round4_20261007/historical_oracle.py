import math
import json
import hashlib

def check(x, message):
    if not x:
        raise AssertionError(message)

def expected(e, t, sentinel=False):
    seed = 'browser-storage-crash-research|targeted-baseline-sentinel-v1|' if sentinel else f'{e}|{t}|1|'
    value = dict(experimentId='targeted-baseline-v1' if sentinel else e, trialId='__targeted_baseline_sentinel_v1__' if sentinel else t, sequenceNumber=1, transactionId='__targeted_baseline_transaction_v1__' if sentinel else f'{t}-target-tx-1', payload=(seed * math.ceil(256 / len(seed)))[:256])
    material = [value[k] for k in ['experimentId', 'trialId', 'sequenceNumber', 'transactionId', 'payload']]
    value['checksum'] = hashlib.sha256(json.dumps(material, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
    return value

def verify_payload(p, e, t, mode):
    check(all((p.get(k) == v for k, v in dict(experimentId=e, trialId=t, origin='http://127.0.0.1:5173', databaseName='browser-storage-crash-research-v1', databaseVersion=2).items())), (e, t, 'read identity'))
    check(set(p['objectStoreNames']) == {'records', 'metadata', 'quotaChunks'}, (e, t, 'stores'))
    check(p['sentinel'] == expected(e, t, True) and p['sentinelRecordCount'] == 1, (e, t, 'sentinel'))
    target = p['targetDirect']
    check(p['targetRecords'] == ([] if target is None else [target]), (e, t, 'index'))
    check(target is None or target == expected(e, t), (e, t, 'target/checksum'))
    meta = None if target is None else dict(trialId=t, experimentId=e, lastSequenceNumber=1, recordCount=1, workload='target-transaction', requestedDurability=mode)
    check(p['metadata'] == meta, (e, t, 'metadata'))
    return target is not None
