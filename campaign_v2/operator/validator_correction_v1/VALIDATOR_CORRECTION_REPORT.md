# Validator correction report

Completed 2026-10-05T00:50:34.155019+00:00.

- Assignment311 became eligible as **lost**, through an append-only corrected audit of its existing evidence. The original failed independent audit and all58 raw attempt files, including every full image, are unchanged. No retry, replacement or new qualification was performed.
- Corrected audit version: `scientific-worker-pin-audit-v1.0.0`.
- Byte-audit SHA-256: `9873f6e91abf529e0105389503769d712c9c7c6cc4bd0ff4898dca0da1935f66`.
- Timeline-audit SHA-256: `21acbf218dce88575711863715793d9f6916ffe3b50f47ce3fd269da2c14aa1c`.
- Active append-only lock SHA-256: `3c25b75788403f2ccfdebbaa6b25c42d84d89146607ace72f34983794a785875` (`LOCK_ADDENDUM_002.json`). Addendum001 and continuation revision1 are preserved development records and were never used for acquisition. Revision2 additionally locks the authorization and resource receipt hashes.
- Assignment312 is technically safe to start through the corrected entrypoint following a fresh preflight. It has **not started**. The current read-only preflight passed for exactly312-331.
- Current eligible scientific count: **311/930**. Started311, finished311, unstarted619. Of these,310 have their original passing independent audits and one has the expressly authorized corrected sidecar. Earlier and second-Mac pilots and qualification records are excluded.

The defect was the qualification executable path and hash in two scientific audit predicates. The active pre-acquisition lock already bound the scientific worker. The new audit verifies exact ordered source events against those locked source hashes, including the separately pinned trace worker. AST comparisons confirm all other audit predicates and the measurement invocation are unchanged. Offline tests passed:14 methods covering the audit and continuation,44 negative worker-event fixtures, plus seven continuation-revision2 checks. All930 assignment routes resolve. These fixtures are not scientific observations.

The corrected full byte audit passed all29 checks on assignment311, including its oracle, capture, source, timing, reset and immutable-forensic gates. Source inspection supports classification A relative to the scientific input lock. The scientific worker is separately adapted and is not byte-identical to the qualification worker. Its measurement and reader bodies and transaction payload are unchanged. The disk-view extraction did not recover the operator file contents; execution attribution uses the locked prelaunch hashes and recorded execve. No causal mechanism or callback attribution is added.

The frozen protocol, tag commit, all1193 internal inputs and five external runtime inputs passed integrity checks. Original FINAL_INPUT_LOCK.json SHA-256 remains `6b41534b91721debdfb664cf0296e22c32ac5debc22f345df75ef41914f00798`. Registered assignments remain930. Preserved historical holds are hash-bound, and a new/changed hold, any undisposed failure, an incomplete attempt or any evidence/input drift blocks the corrected continuation.

Available disk at preflight:15.46GiB. For the exact next20 assignments, twice qualified trial allocation plus archive scratch is8.01GiB, leaving the6GiB floor protected. This is a bounded resource check, not assurance that all remaining619 fit. Keep all311 images because of its historical validator incident. Do not use the old continuation wrapper.

Read-only command executed under caffeinate:

```bash
python3 campaign_v2/operator/validator_correction_v1/operator_validator_v2.py --addendum-sha256 3c25b75788403f2ccfdebbaa6b25c42d84d89146607ace72f34983794a785875 preflight --n 20
```

Command for a subsequently requested bounded batch, not executed in this correction:

```bash
python3 campaign_v2/operator/validator_correction_v1/operator_validator_v2.py --addendum-sha256 3c25b75788403f2ccfdebbaa6b25c42d84d89146607ace72f34983794a785875 run-batch 20
```

Supporting receipts: REVALIDATION_311.json, DISPOSITION_311.json, FINAL_OFFLINE_TEST_RECEIPT.json, CONTINUATION_V2_TEST_RECEIPT.json, PREFLIGHT_312_331_CONSOLE.txt and FINAL_CORRECTION_RECEIPT.json.

Technical Amendment014 records the actual post-acquisition correction chronology locally. No new OSF posting was made by this task, and the original immutable registration was not changed.
