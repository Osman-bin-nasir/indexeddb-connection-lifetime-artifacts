# Mac-only connection-lifetime campaign registration

Version 2 replaces the unregistered broad draft at `022fd9fd359f1093e92c0a25dd4364cd3563d5a8`. All old/second-Mac observations are pilot-only and are not pooled with this campaign. This package contains prospective design files, no new observations, runner or manuscript.

- PREREGISTRATION.md: authoritative conditions, eligibility, tests, gate and retention.
- design/: ten active families, scientific and separate excluded qualification schedules, counts and file hashes.
- DESIGN_VALIDATION.json: regenerated offline matrix/order/retention/gate checks.
- generate_design.py / check_design.py: reproduce and independently constrain the matrices and deterministic complete blocks.
- PILOT_RESOURCE_BASELINE.json: raw-event source hashes and resource measurements only.
- estimate_resources.py / RESOURCE_ESTIMATES.json / FEASIBILITY.md: explicit provisional runtime/disk scenarios, pending qualification.
- sources/: saved pinned ARM64 and Chromium-version receipts.
- GATE.json / REGISTRATION_RECEIPT.json / NEXT_STEPS.txt / OSF_HANDOFF.md: author gate and registration instructions.
- SHA256SUMS: every active package file except the self-referential inventory and ignored Python cache.

Mandatory: 370 Tier 1 plus 560 Tier 2 = 930 scientific assignments and 95 excluded qualification attempts. Optional cost: 120 plus 12 qualification. All use this one Mac, ARM64/HVF and packaged Chromium. Timelines have five blocks; all other cells have ten. Obsolete broad-design files were removed from the active directory; their previous bytes remain in Git history.

Verify/reproduce offline:

```sh
cd browser-storage-crash-research
python3 confirmatory/generate_design.py
python3 confirmatory/check_design.py
python3 confirmatory/estimate_resources.py
(cd confirmatory && shasum -a 256 -c SHA256SUMS)
```

Do not regenerate or edit posted scientific files after the external freeze except through a prospective amendment. The hash check passes only against the matching committed revision. Reproduction creates the same deterministic files.

**STOP at Step 1.** The author must return the matching OSF URL and repository tag before Step 2 build/qualification. No waiver, acquisition, operator execution, paper or PDF is authorized now. Step 3 and Step 4 follow qualification later. This research-writing agent must hand off scientific acquisition rather than start it.

The disk plan uses 35 GiB as requested, measured roughly 31 GiB at revision time, a 6-GiB hard stop, and verified zstd offload. The author-managed offload destination is `Google Drive, author-managed folder IndexedDB-Mac-Confirmatory-v2 (folder URL pending)`. Estimated mandatory total is about 27 to 50 machine-hours under explicit unqualified scenarios. Actual cell qualification must replace these estimates.
