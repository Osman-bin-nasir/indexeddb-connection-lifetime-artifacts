# Investigation of the five scientific assignment failures

Date: 2026-10-06. This is an append-only investigation, not an eligibility correction, protocol amendment, acquisition authorization, or new observation. No original record or scientific input was changed. No guest was booted, journal replayed, oracle run, or assignment retried.

## Decision

The causes and stopping points can be established from preserved evidence. **None of the five can become an eligible recovery/loss observation from that evidence under the frozen execution and oracle rules.** Four have original unknown RESULT records. One was consumed before measurement and has no RESULT. A fresh prospective assignment is necessary only if additional eligible observations are wanted. The original campaign can be reported with its registered missing endpoints; extra trials are not necessary to finish analysis of the original campaign.

Original assignments remain 930. The current result ledger contains 929 RESULT records: 925 marked technically eligible, four unknown/ineligible. The fifth affected slot has a preserved premeasurement disposition. This is a recount of existing records, not a new independent certification of all 925 eligible endpoints. This investigation salvages zero endpoints and acquires zero new trials.

## Per-assignment findings

| Campaign slot | Exact trial ID | Condition and block | Preserved finding | Eligible endpoint recoverable? |
| --- | --- | --- | --- | --- |
| 353 | scientific-trace_category_timelines-00003 | Relaxed, close at 1 s, fault deadline 2.75 s after host ACK; block 1 | Guest trace emission failed with BlockingIOError; controller timed out waiting for trace-stop. No assigned reset or oracle. | No. Fresh prospective assignment needed for a new observation. |
| 354 | scientific-trace_category_timelines-00004 | Relaxed, immediate close, 2.50 s host-ACK deadline; block 1 | Continuation wrapper supplied addendum004's hash to a backend expecting addendum003. Rejected before VM launch. | No. There was no measurement to recover. |
| 364 | scientific-trace_category_timelines-00014 | Relaxed, close at 1 s, fault deadline 2.75 s after host ACK; block 4 | Same trace-emission failure and missing trace-stop response. No assigned reset or oracle. | No. Fresh prospective assignment needed for a new observation. |
| 370 | scientific-trace_category_timelines-00020 | Relaxed, held 15 s; block 5 | Same trace-emission failure and missing trace-stop response. No assigned reset or oracle. | No. Fresh prospective assignment needed for a new observation. |
| 390 | scientific-fault_scope_comparison-00020 | Relaxed, held 15 s, browser-tree SIGKILL; block 2 | No-replay forensic helper encountered an ext4 inode checksum error. Extraction stopped; cleanup quit the original guest before its same-guest oracle. | No. Saved disks do not preserve the required live guest/kernel/RAM through oracle. |

Campaign slots follow the frozen design manifest's mandatory family order and within-family ordinal. Assigned timings in this table are not claimed achieved fault timings for trials where dispatch never happened.

### Trace trials 00003, 00014, 00020

For each trial, sentinel independent readback, prepare, trace-start, clocks, target ACK and write response were recorded. For 00003 and 00014, CLOSE_REQUEST and CLOSE_RETURNED were also recorded. The pinned controller then requested trace-stop 500 ms before the assigned fault deadline and awaited a response for 0.4 s. Its recorded error was `TimeoutError('Required guest record missing')`.

The more specific failure appears in WORKER_NON_JSON records, not worker-stderr.txt, which is empty. The traceback identifies `/opt/idbv2/trace-worker.py` line126's Tracing.dataCollected callback and line23's JSON print/flush operation, followed by `BlockingIOError: [Errno 11] write could not complete without blocking`. Event-listener error reporting also encountered blocking-write errors. Trace JSON fragments and traceback text were preserved in events.jsonl. The record does not establish why the output stream became unable to accept those writes, so the investigation does not attribute that to a particular fd-setting or Playwright implementation.

All three have zero parsed TRACE_DATA records, zero TRACE_COMPLETE records, zero trace-stop RESPONSE records, zero FAULT_DISPATCH records and no QMP system_reset request. Their QMP logs end with cleanup quit. None contains ORACLE.json. Some partial trace bytes remain diagnostic evidence, but they cannot establish complete trace coverage/loss status, reconstruct an unperformed fault, or supply recovery after that fault.

The earlier explanation emphasizing a 0.4-s controller timeout versus a 5-s guest wait was incomplete. Those two configured limits are real, but the preserved tracebacks establish an actual trace-output failure before the timeout. Increasing a timeout after collection would not repair missing trace bytes or perform the missing registered fault.

Source verification: the recorded measurement worker SHA-256 is `94e2257ca12ff846470753fd71fd05ade156a311b37fdc75d25aaaf198f4b4bd`; the timeline controller SHA-256 is `f5cd2bbb7bf9648070fe32944ee76ee6cb50d475c33135617574a8cd70c46461`. Both match the frozen backend source package. This is an executed capture/transport failure, not merely an independent validator expecting the wrong pathname.

Future work, if authorized prospectively: repair and qualify trace output handling with controlled writes/backpressure, complete trace/loss evidence and a response within the unchanged pre-fault budget. Do not extend the assigned fault deadlines to accommodate collection. Only new excluded qualification IDs and separately registered new scientific IDs may test that repair.

### Premeasurement slot 354, trace trial 00004

The preserved administrative disposition records the v4 wrapper's hash-field error. START.json reserved the slot; backend-console.txt records `RuntimeError: Validator addendum hash mismatch`. There is no engine START, VM launch, events.jsonl, disk image, target ACK, fault or endpoint RESULT for this trial. Existing continuation addenda describe subsequent wrapper correction; correcting the wrapper does not create an observation for this consumed slot.

The appropriate retained classification is consumed before measurement, endpoint unknown, ineligible, no retry or replacement. It must not be represented as an observed recovery, loss, or guest measurement failure. A future new ID would be a new prospective observation, not an audit repair to slot354.

### Browser SIGKILL trial 00020, campaign slot390

The process-only fault did execute. Preserved process selection, signals and exits support the recorded SIGKILL classification; post-fault boot identity was unchanged. The host dispatch overshoot was 4.107167 ms. The guest was paused and its disk redirected to active-after-snapshot.qcow2, preserving overlay.qcow2 as a read-only, hash-bound snapshot. These successful stages do not establish the missing endpoint.

The helper mounted the original attachment read-only/no-replay. Its preserved console records:

`EXT4-fs error (device vdc1): ext4_lookup:1864: inode #265000: comm python: iget: checksum invalid`

The original-noload.stderr traceback records `OSError: [Errno 74] Bad message` while statting this trial's `profile/Default/IndexedDB` directory. The pinned projection code permits its specific missing-directory branch, but refuses other original-extractor failures. Accordingly it raised `Original extractor failed for a different reason; no substitution`. Raw journal extraction and forensic replay projection were not reached.

The original QEMU PID65619 received quit in cleanup. No SIGKILL_ORACLE_SAME_GUEST event, recovery identity readback, or ORACLE.json exists. There is no saved VM/RAM state file in the attempt inventory. The disk snapshot and its small post-snapshot overlay survive, but neither encodes the original live kernel state. Technical Amendment010 and the pinned independent audit expressly require the same original guest boot/RAM/QEMU through the oracle and prohibit deriving the endpoint from the forensic replay helper. Booting a disk derivative now, or replaying it and running a browser elsewhere, cannot satisfy that rule.

The original snapshot and backing chain can support separately labelled forensic diagnosis. Its SHA-256 is `2ae968da4e9d4624dacc2f2d870cde568af9d84feaa44f5a6209c5a18038f30f`. qemu-img check without repair reports no qcow2 errors. That container-level check does not contradict the ext4 checksum error or establish filesystem consistency. The checksum error in this no-replay view does not by itself establish permanent corruption after replay, target-record corruption, loss, or any causal mechanism. The original scientific endpoint remains unknown.

Future work, if authorized prospectively: define and qualify handling of this unavailable no-replay observation while preserving raw evidence, derived-view provenance and the original live guest oracle. Do not quietly treat errno74 as the allowed missing-directory case or infer a recovery/loss result from forensic files.

## Verification and preserved evidence

The active PREREGISTRATION.md matches both its recorded protocol hash and the repository tag `prereg-connection-lifetime-mac-v2`. Relevant locked backend sources and all recorded candidate repair-source pins match. All five assignments match their frozen design entries.

All 208 entries across the four completed attempts' original SHA256.json and OPERATOR_SHA256.json inventories verify. The five evidence hashes in slot354's disposition also verify. All six retained qcow2 images across these attempts pass qemu-img check without repairs. Hashes of every file in the five original attempt directories were recorded before inspection and rechecked afterward; every original file remained unchanged.

Primary sources relative to the repository:

- `confirmatory/PREREGISTRATION.md`, sections3 and5: unknown endpoints, eligibility, incomplete cells, consumed IDs and prospective extras.
- `confirmatory/design/trace_category_timelines.json`, `fault_scope_comparison.json`, `MANIFEST.json`: assignments, blocks and execution order.
- `campaign_v2/operator/FINAL_INPUT_LOCK.json`: locked scientific implementation.
- `campaign_v2/operator/backend_v1/engine/repairs/011/guest_worker_trace.py`, `qualification_timelines.py`: executed trace emitter, completion and dispatch sequence.
- `campaign_v2/operator/validator_correction_v1/DISPOSITION_354_PREMEASUREMENT_FAILURE_001.json`: premeasurement rejection and original evidence hashes.
- `campaign_v2/repairs/010/TECHNICAL_AMENDMENT_010_LOCAL.md`: same original SIGKILL guest oracle; forensic derivatives are not endpoint oracles. Its original record explicitly identifies its OSF posting as pending at creation; this investigation does not assert later posting.
- `campaign_v2/operator/backend_v1/engine/repairs/010/projection_qualified.py`, `qualification_fault_scope.py`, `independent_audit.py`, `live_capture.py`: extractor refusal, snapshot provenance, original guest retention and cleanup.
- Each affected `campaign_v2/scientific/attempts/<trial_id>/` directory: raw events, original dispositions/results, source pins, image/hash inventories and audit errors.

`StopIteration()` in the three trace audits and `FileNotFoundError` in the SIGKILL audit are secondary failures caused by mandatory later evidence not having been produced. Better audit diagnostics could enumerate those missing gates, but cannot produce an eligible endpoint.

Machine-readable checks and source-bound excerpts are in `INVESTIGATION_RESULTS.json`. Reproducible read-only inspection is in `inspect_failures.py`; rerunning it requires a new output path because it refuses to overwrite a report.

## Consequences for reporting and future acquisition

Timeline coverage is16 eligible assignments out of20 assigned: immediate close4/5, delayed close3/5, held5 s5/5, held15 s4/5. Fault scope has119 eligible out of120; the SIGKILL held15-s cell has9/10. Other campaign families are unaffected by these five missing observations. Those are assigned/eligible counts, not pooled recovery proportions.

No original failure may be removed, relabelled recovered/lost, silently topped up, or merged with a later replacement. If additional observations are requested, define their counts, repaired technical inputs, qualification IDs, assignment IDs and reporting status in a prospective amendment before collection. Later observations remain transparently additional data; the original930-slot campaign and its incomplete cells remain visible. With no additional acquisition, analysis can proceed using the preregistered exclusion reporting and missing-endpoint sensitivity rules.
