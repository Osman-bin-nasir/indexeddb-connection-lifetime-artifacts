# Assignment 311: preserved worker-pin gate investigation

Investigated UTC: 2026-10-04T23:57:27Z. Scientific assignment: `scientific-target_byte_diagnostics-00001`. Scope: source/configuration inspection and read-only recomputation from preserved records. No qualification, new scientific attempt, repair, retry, original verdict replacement, or denominator change was performed.

**Finding: A relative to the active final scientific input lock.** The independent validator retained the qualification worker's path AND hash, although the scientific controller correctly launched the separately pinned operator worker. No unpinned worker substitution or change to the measurement/oracle body was detected. The scientific worker is not byte-identical to the original qualification worker: it is a documented, pre-locked adaptation. That distinction is essential to this conclusion.

## Registered design and authoritative locks

The local `confirmatory/PREREGISTRATION.md` and its version in the registered repository tag both hash to `a3dfb023a7fb9e4862edc4242a7cbac1b3b8865790dbcbb1156fddfd128b13b1`. The tag `prereg-connection-lifetime-mac-v2` resolves to commit `5a749734a0a63f3e1c662bb91dd829e6f288dc5c`. Every member listed in `confirmatory/SHA256SUMS` matches its recorded hash. The registered protocol fixes the reader/oracle behavior and requires a later technical hash lock; it does not prescribe either of the two literal Python installation paths.

The active `operator/FINAL_INPUT_LOCK.json` has SHA-256 `6b41534b91721debdfb664cf0296e22c32ac5debc22f345df75ef41914f00798`, exactly the hash in this attempt's `START.json`. Its recorded timestamp is 2026-10-04T14:01:41.687350+00:00, before the attempt's start at 2026-10-04T23:27:28.428873+00:00. All 1,193 internal inputs and five external runtime/firmware inputs were independently rehashed and matched. These are local technical-lock records, not a claim of a new external OSF posting.

| Source | Intended guest path | Pinned SHA-256 |
| --- | --- | --- |
| Original qualification/base worker | `/opt/idbv2/worker/guest_worker.py` | `055980789fa5993910dce05eebdec01fcbc026ed94680c2182865ed5ce0b0fda` |
| Scientific operator worker | `/opt/idbv2/operator/guest_worker.py` | `1179ac7e17c71781009cd5487edd96fd792394b50a8cb478c075d9c1d8acfd9b` |
| Transaction and oracle JavaScript | `/opt/idbv2/worker/transaction.js` | `5b3f7de6e26246c9ccf97450e997973f4daa360ca6d6c265551f56cd6101c23e` |

The original and generated worker hashes are both documented in the frozen `operator/backend_v1/ENGINE_SOURCE_MANIFEST.json`; the generated worker is independently bound by the final lock. The manifest hash is `ac94ad26323901f60033aea56839514ab831c737856da48a17f3a514cb6b44ed`, which also matches this attempt's integration receipt.

## Exact source and execution chain

The preserved batch plan `operator/batches/batch-v2-20261004T230258699071Z/PLAN.json` and the resume console identify the continuation wrapper `operator_v9.py` and frozen `operator_v4.py` batch runner. The final lock selects `backend_dispatch_v3.py`, which uses `backend_dispatch_v2.py` and `backend_v1/backend.py`. For this family the exact route is `engine/repairs/012/qualification_bytes.py` with `engine/repairs/012/independent_audit.py`. The measurement controller and audit hashes recorded in `ENGINE_START.json` match those exact locked files.

The controller's `Worker.__init__` deploys the operator worker separately before launch, hashes that guest file, compares it with `ENGINE / 'guest_worker.py'`, records `WORKER_EXECUTABLE_SOURCE`, and launches the same path. Both the measurement worker and recovery reader use this constructor. The measurement launch is additionally visible in the preserved strace `execve` record for `/opt/idbv2/venv/bin/python` with `/opt/idbv2/operator/guest_worker.py` as its script argument. Both pre-launch hash events record `1179ac7e...`, one with `recovery=false`, the other with `recovery=true`. Both match the active scientific pin.

A complete AST comparison of the original and scientific worker found precisely two semantic differences:

1. `ROOT` changes from the script's directory to the explicit `/opt/idbv2/worker` directory. At the old qualification installation path these resolve to the same directory. The scientific worker therefore serves the original `transaction.js`, rather than seeking a JavaScript file beside the relocated Python file.
2. The role guard accepts `scientific` in addition to `qualification`. The generated tuple contains a harmless duplicated `scientific` entry, also present in the locked source.

After normalizing these two documented changes, the complete module ASTs are identical. Browser executable/hash, launch arguments, viewport, page setup, preparation, transaction invocation, ACK/connection telemetry, clock commands, and oracle invocation are unchanged in the Python source. The recorded measurement and recovery `WORKER_READY` events show the same assigned profile, launch flags and Chromium version. This establishes source/configuration consistency; it does not assert identical execution latency or absence of every possible runtime effect.

## Cause of rejection

`engine/repairs/012/independent_audit.py:87` checks both records against `/opt/idbv2/worker/guest_worker.py` AND `REPAIRED_BASE_LOCK.json['worker_files']['guest_worker.py']`, namely the original `05598078...` pin. Both parts of that predicate are false for the correctly pinned scientific operator worker.

The omission originates in `build_engine.py`: controller launch/path constants and controller executable hash lookups are adapted to the operator worker, but the literal path in the audit and the audit's base-worker hash lookup are left unchanged. The base lock still correctly describes the original installed base inputs; it is the wrong expected executable contract for this scientific audit predicate.

Changing only the expected path would not resolve the failure. The hash expectation also needs to reference the correct frozen scientific worker contract. Blindly allowing either path or either hash would not be a sufficient provenance check.

The original audit was executed again read-only against the original records. Its complete returned object exactly matches the preserved `INDEPENDENT_VERIFICATION.json`. `pinned_measurement_and_reader` is the sole false check; every other predicate remains true. A separately recorded diagnostic using the correct final-lock worker path/hash, exactly two events and measurement/recovery flags `[false, true]` passes. With that single expected-contract correction, all existing audit predicates would pass. This diagnostic is not a replacement acceptance receipt and has not changed the failed original verdict.

The four byte-family qualification attempts used the old path and old `05598078...` worker and passed that expectation correctly. The subsequent live operator integration used only a close-aligned grid cell. The static integration tests verified routes and worker/timing source equivalence, but did not exercise this family's executable-pin predicate after adaptation. The discrepancy consequently first became visible at the first scientific byte-family assignment. The timeline recovery audit contains the same obsolete worker path/hash pattern at `engine/repairs/011/independent_audit.py:93`; that is a static finding for a pending family, not an observed timeline-trial failure.

## Preserved guest-file inspection and its limits

The preserved overlay and recovery qcow2 chains were read using `qemu-img dd` virtual block reads, followed by a bounded ext4 inode/extent/directory walk. No VM was booted, no journal was replayed and no evidence disk was written. The investigation utility and extracted files are retained with this report.

In both the immutable overlay and recovery derivative, the original `/opt/idbv2/worker/guest_worker.py` and `/opt/idbv2/worker/transaction.js` were directly extracted and matched their exact pins. Their sizes are 6,365 and 6,857 bytes respectively.

In both no-replay disk views, the relocated operator worker's directory entry exists, but its inode reports size zero. Thus these views do not reconstruct the operator worker's executed bytes. The live pre-launch hash checks, source-bound controller and measurement `execve` trace establish which worker was used. This report does not infer a specific writeback, journal or callback mechanism from the zero-length stored inode, and does not claim disk extraction independently recovered the operator source.

The overlay and recovery hashes matched their preserved image pins before and after inspection. All 58 attempt files were rehashed before and after the investigation and remained identical; both `SHA256.json` and `OPERATOR_SHA256.json` inventories passed. The oracle continues to report an absent target with a valid sentinel. That raw oracle output and the original failed independent audit have not been edited.

## Disposition

The immediate gate failure is an inconsistent validator expectation, not evidence of an unpinned measurement/reader substitution. The exact claim that the scientific Python file is byte-identical to the qualification Python file would be false; its documented role/path adaptation and distinct prospective pin must remain explicit.

Acquisition remains on hold. Assignment 311 has not been retried or reclassified, its failed audit remains preserved, and later assignments remain unstarted. A future validator correction should be separately versioned and source-bound to the final scientific worker contract, with append-only revalidation evidence and explicit disposition of this consumed slot. The registration, existing lock, raw record and original verdict must not be rewritten to conceal the discrepancy.

Machine-readable evidence: `INVESTIGATION_RESULTS.json`. Exact original-audit recomputation: `REPRODUCED_AUDIT.json`. Guest disk inspection: `GUEST_SOURCE_INSPECTION.json` and `guest_source_extracts/`. Reproducible bounded inspection utility: `inspect_preserved_guest.py`.
