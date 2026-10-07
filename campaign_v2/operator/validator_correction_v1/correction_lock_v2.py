"""Verify the append-only validator lock and disposition, without data writes."""
import hashlib
import json
from pathlib import Path
import subprocess

from pin_contract import CAMPAIGN, FINAL_LOCK_SHA256, VERSION

HERE = Path(__file__).resolve().parent
TAG_COMMIT = '5a749734a0a63f3e1c662bb91dd829e6f288dc5c'
FAILED_TRIAL = 'scientific-target_byte_diagnostics-00001'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def safe(relative):
    path = CAMPAIGN / relative
    if path.is_symlink() or not path.resolve().is_relative_to(CAMPAIGN.resolve()):
        raise RuntimeError('Unsafe validator evidence path')
    return path


def verify_addendum(expected_sha256):
    path = HERE / 'LOCK_ADDENDUM_002.json'
    if sha(path) != expected_sha256:
        raise RuntimeError('Validator addendum hash mismatch')
    addendum = read(path)
    if addendum['validator_version'] != VERSION or addendum['original_final_lock_sha256'] != FINAL_LOCK_SHA256:
        raise RuntimeError('Unexpected validator contract')
    if sha(CAMPAIGN / 'operator/FINAL_INPUT_LOCK.json') != FINAL_LOCK_SHA256:
        raise RuntimeError('Original final scientific lock changed')
    commit = subprocess.check_output(['git', 'rev-parse', 'prereg-connection-lifetime-mac-v2^{commit}'],
                                     cwd=CAMPAIGN, text=True).strip()
    if commit != TAG_COMMIT:
        raise RuntimeError('Registered repository tag changed')
    for name, digest in addendum['source_and_receipt_hashes'].items():
        if sha(safe(name)) != digest:
            raise RuntimeError('Validator addendum member changed: ' + name)
    for name, digest in addendum['authority_hashes'].items():
        if sha(safe(name)) != digest:
            raise RuntimeError('Validator continuation authority/resource changed: ' + name)
    current_holds = {str(p.relative_to(CAMPAIGN)): sha(p)
                     for p in (CAMPAIGN / 'operator').glob('ACQUISITION_HOLD_*.json')}
    if current_holds != addendum['historical_hold_hashes']:
        raise RuntimeError('New or changed acquisition hold requires disposition')
    disposition = read(HERE / 'DISPOSITION_311.json')
    if (disposition['trial_id'] != FAILED_TRIAL or disposition['eligible'] is not True
        or disposition['trial_retried'] is not False or disposition['original_failed_verdict_preserved'] is not True):
        raise RuntimeError('Invalid consumed-slot disposition')
    if sha(HERE / 'REVALIDATION_311.json') != disposition['revalidation_sha256']:
        raise RuntimeError('Revalidation receipt changed')
    if sha(CAMPAIGN / 'operator/ACQUISITION_HOLD_004.json') != disposition['original_hold_004_sha256']:
        raise RuntimeError('Historical stop changed')
    return addendum


def effective_verification(attempt):
    """Only the explicitly disposed slot can consume the corrected sidecar."""
    attempt = Path(attempt)
    original = read(attempt / 'INDEPENDENT_VERIFICATION.json')
    if original.get('independent_pass') is True:
        return original, 'original_independent_audit'
    if attempt.name != FAILED_TRIAL:
        raise RuntimeError('Undisposed independent verification failure: ' + attempt.name)
    disposition = read(HERE / 'DISPOSITION_311.json')
    receipt = read(HERE / 'REVALIDATION_311.json')
    if sha(attempt / 'INDEPENDENT_VERIFICATION.json') != disposition['original_audit_sha256']:
        raise RuntimeError('Original failed audit changed')
    if sha(HERE / 'REVALIDATION_311.json') != disposition['revalidation_sha256']:
        raise RuntimeError('Corrected revalidation changed')
    actual = {str(p.relative_to(attempt)): sha(p)
              for p in attempt.rglob('*') if p.is_file()}
    if actual != receipt['original_attempt_file_hashes']:
        raise RuntimeError('Disposed attempt evidence changed or is missing')
    review = receipt['corrected_audit_result']
    if (receipt['eligible'] is not True or review['independent_pass'] is not True
        or not all(review['checks'].values()) or review['audit_version'] != VERSION
        or review['audit_source_sha256'] != sha(HERE / 'audit_bytes_v1.py')):
        raise RuntimeError('Corrected consumed-slot verification invalid')
    return review, 'append_only_validator_correction_v1'
