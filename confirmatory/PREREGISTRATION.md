# Prospective registration: connection lifetime and acknowledged IndexedDB write recovery

Protocol version: 2.0. Prepared UTC: 2026-10-03T14:28:23Z. Status: awaiting the author's OSF URL and repository tag. No new campaign observations have been acquired.

Repository baseline: `136aa1cbb4808606cba6049efc4f1c77268a9cb6`. Superseded unregistered draft: `022fd9fd359f1093e92c0a25dd4364cd3563d5a8`. This revision changes that draft's scientific design. The scientific-plan commit, delivered registration hash and tag instructions are recorded in the registration receipt and NEXT_STEPS.txt. A commit or local timestamp is never represented as external registration.

## 1. Scope, prior knowledge and mandatory gates

All campaign experiments use this one Apple Silicon Mac and an ARM64 Ubuntu guest under HVF. No cloud host, x86 host/guest, source-built Chromium arm or stable-version comparison is included. There is no release-delay manipulation or hypothesis, SysRq panic, btrfs, writeback-sysctl matrix or autosave-editor experiment. Physical-power interruption is **not performed**, with zero assignments. None of the retained fault models establishes physical-power persistence.

Every earlier dataset, including the second-Mac records, is pilot evidence only. Pilot exploration selected the close-aligned and held-open timing windows, and the author and analyst know those outcomes. No pilot trial, smoke, setup, support or qualification record enters a new scientific denominator. Every scientific endpoint must come from a fresh registered assignment. Repetition of a pilot pattern is assessed through the registered contrasts below, without inventing a formal replication criterion for historical populations.

The author must first post this version and its assignment/hash package on OSF and supply the OSF URL and repository tag. Until both are verified against this delivered revision, provisioning, qualification and acquisition are forbidden. There is no waiver route in this revision. Future provisioned binaries/images and execution scripts implement this registered design and require a technical hash lock after qualification, before acquisition. A changed scientific condition, timing rule, count, eligibility rule or oracle requires a prospective dated amendment before affected data collection.

After external registration, build and qualify, then prepare the operator package and its end-to-end qualification demonstration. The current research-writing agent must stop with a hand-off and must not start scientific acquisition. A smaller operator agent will run assigned trials later. No publication ZIP or manuscript text is produced now. The finished campaign and independent analysis precede the publication ZIP; its clean replay precedes the Word manuscript. No PDF is created.

Second-host replication of key conditions is optional and outside the present assignments. It requires later author-supplied access, a registered amendment with fixed fresh counts and its own qualification, and explicit separate-host provenance. Existing second-Mac pilot records cannot satisfy it. There is no portability claim from this one-host campaign.

## 2. Platform and technical lock

Use four vCPUs, 6144 MiB guest RAM, fresh qcow2 overlay and browser profile per attempt, virtio storage, and QEMU `cache=none` with HVF. Record actual host model, architecture, macOS, QEMU version and complete command line. TCG and another platform or cache policy are not substitutes. The inspected pilot host uses QEMU 11.1.1; the new execution version must be captured and locked rather than assumed.

Provision the pinned public Ubuntu 24.04 ARM64 image dated 20260926:

- URL: https://cloud-images.ubuntu.com/releases/noble/release-20260926/ubuntu-24.04-server-cloudimg-arm64.img
- SHA-256: `1d6bffe64b848468ac97f821d369a4846d983de1800ccf6b5ec8853e85cefc55`.
- The saved public package manifest reports Linux 6.8.0-142. This new guest is not asserted byte-equivalent to a pilot guest. Verify downloaded image bytes and the official signed checksum before use; a saved checksum announcement is not download/boot qualification.

Use only packaged Chromium 153.0.8010.12, executable SHA-256 `839efe5fd8b6a773dd81b2e10afdc15f3c0a17316fb82b5908c0533306c4ed9e`. Record its acquisition archive/source, package hashes and executable hash. Its pinned source-reading revision is `971a7443b0c9b0a9b2860529b33331b76077ec62`; matching version does not establish reproducible-build equivalence. An unavailable exact package blocks its cells rather than permitting another browser.

Use headed Chromium under Xvfb, viewport 1440 by 1000, deterministic local application, SQLite backend forced and independently confirmed from actual files, no uncontrolled updates or variations downloads. Record and lock package versions, archived dependencies, kernel/modules, frontend, payload/oracle contracts, recovery reader, launch configuration, scripts, derived base/data images and all hashes. Do not perform an unpinned system upgrade. Read and record live writeback sysctls unchanged; they are not experimental arms.

After registration, provision byte capture, forensic snapshots, SysRq reboot, dm-log-writes, dm-flakey, ext4/xfs volume tools and the registered workloads. Their feasibility is pending, not a claimed implementation. Run exactly one excluded qualification attempt per registered cell: 95 for mandatory families, plus 12 only if optional cost is activated. Qualification checks technical readiness and evidence, independently of target recovery. An unqualified cell or family is blocked with preserved evidence. Do not relax gates, silently retry, substitute an implementation or count a qualification as science. Further qualification requires an explicit documented prospective technical amendment with new IDs.

Cold-boot and post-fault guest readiness each have a 180-second ceiling. Recovery requires at least three healthy observations spanning at least five seconds, one expected boot/session identity, and the correct profile/overlay identity. Before acquisition, qualification must establish the timing, fault, oracle, forensic and capture requirements below and measure wall time/disk use for each cell. The corrected resource estimate and all scientific input hashes must be locked before operator hand-off.

## 3. Transaction, endpoint and timing contract

Ordinary targets contain one deterministic 256-byte ASCII payload with trial/database/record identity and checksum metadata in a relaxed transaction. Concatenate SHA-256 hexadecimal strings of `campaign|trial|record|counter`, truncate to the registered length, and lock canonical metadata/checksum serialization before collection. Ten-record targets contain ten such records in one transaction. The optional 64-KiB cost workload uses the same construction. No target is synthesized after a fault.

Create a separate strict sentinel, close and independently verify it; verify target absence before writing. A target ACK requires transaction completion and evidence of the requested durability hint. Retain page completion time, page ACK, host receipt, requested/actual close and fault timestamps. The independent recovery reader opens the same existing database/profile without creation or upgrade and checks the sentinel, identity/version/stores, direct and indexed lookup, record multiplicity, metadata and checksums.

Classify complete, valid target transaction with valid sentinel as **recovered**; wholly absent target with valid sentinel as **lost**. Partial transaction, checksum/multiplicity/metadata disagreement or sentinel loss is **integrity failure**. An interrupted, missing or unreadable endpoint is **unknown**. Technical eligibility is separate from endpoint classification. Unknown/integrity failures never become ordinary loss or recovery. Preserve every raw attempt and reason. Report assigned, started, complete, technically invalid, integrity failure, unknown and remaining counts, with overlapping flags explained rather than added as if disjoint.

Pointwise binary recovery proportions and contrasts use technically eligible, interpretable complete/absent endpoints, with excluded categories and both denominators visible. Also report recovered/acknowledged attempts, integrity failures and pessimistic/optimistic missing-endpoint bounds. Ten assignments do not guarantee ten eligible endpoints. A cell with fewer eligible endpoints is incomplete; no replacement or automatic top-up is allowed. A nonzero integrity-failure count qualifies the simple two-state recovery interpretation.

In the close-aligned grid, schedule close from page ACK, observe its diagnostic, map it using paired guest/host monotonic clock samples, and schedule dispatch from the estimated observed close plus assigned gap. Retain clock samples, diagnostic receipt, mapped close, requested deadline, dispatch, QMP write and observed event. ACK-plus-nominal-close arithmetic is not a measured close time. For all key, held and control cells the fault deadline is measured from host receipt of ACK; close delay remains assigned from page ACK. Held cells must retain the original connection through the deadline, confirmed by telemetry, with no unsolicited close. Four-connection workloads retain the additional three connections regardless of the target connection's close policy.

Dispatch must not precede its registered deadline. Dispatch over 25 ms late is timing-ineligible for primary/narrow timing analysis, but the endpoint remains in the full ledger and broad sensitivity summaries. Missing/contradictory clock mapping blocks precise close-aligned inference. Report achieved ACK-to-fault, close-to-dispatch, close delay, overshoot, uncertainty and uptime distributions using n, minimum, median, p95 and maximum. Assignment spacing of 0.1 s does not establish calibrated physical-fault resolution. No safe waiting time, persistence guarantee or exact timer attribution follows.

## 4. Fixed families and counts

Every ordinary scientific family has ten randomized complete blocks, one trial per cell per block. Trace-category timelines are the explicit exception: five complete blocks, as requested. Counts are planned assignments, not acquired data or a pooled denominator.

The four relaxed key conditions are immediate close with 2.50 s host-ACK deadline; close after 1 s with 2.75 s deadline; held 5 s; held 15 s. The dedicated six-key family adds relaxed held 30 s and a strict immediate-close control with 0.50 s deadline. These additional two are not added to the four-key families.

| Tier | Family | Cells | Blocks | Scientific assignments | Excluded qualification |
| --- | --- | ---: | ---: | ---: | ---: |
| 1 | Close-aligned grid | 18 | 10 | 180 | 18 |
| 1 | Held sweep and close-allowed controls | 7 | 10 | 70 | 7 |
| 1 | Six key conditions | 6 | 10 | 60 | 6 |
| 1 | Packaged-binary byte capture and forensics | 4 | 10 | 40 | 4 |
| 1 | Packaged-binary trace-category timelines | 4 | 5 | 20 | 4 |
| 2 | Fault scope | 12 | 10 | 120 | 12 |
| 2 | Block state | 12 | 10 | 120 | 12 |
| 2 | Environment | 16 | 10 | 160 | 16 |
| 2 | Workload | 16 | 10 | 160 | 16 |
| 3 optional | Durability cost | 12 | 10 | 120 | 12 |

Mandatory Tier 1: **370**; mandatory Tier 2: **560**; total **930 scientific assignments and 95 excluded qualification attempts**, or 1,025 prospective attempts. Optional Tier 3 adds 120 scientific and 12 qualification attempts. There are no physical-power assignments.

### Tier 1

The grid crosses close times {0, 1} s with gaps {1.6, 1.7, 1.8, 1.9, 2.0, 2.1, 2.2, 2.3, 2.4} s. All are relaxed QMP-reset trials. The complete grid is descriptive apart from the single prespecified endpoint contrast below. Publish each cell and achieved-time scatter; do not infer a continuous boundary from unsupported cells.

The held sweep uses {5, 7.5, 10, 12.5, 15} s host-ACK deadlines. Only 5 and 15 s receive additional immediate-close-allowed controls. The six-key family uses ordinary instrumentation under QMP reset, including the strict short-deadline control and held-30 descriptive extension.

Byte capture uses the packaged binary for the four relaxed keys, with no source-built or additional capture-disabled arm. Capture writes/pwrite/writev/pwritev and sync operations, offsets, byte counts/data, inode/device/open-file-description identity, descriptor reuse, children, return status and capture loss. Link serialized target bytes through the actual file/page representation rather than assume plaintext occurs on disk. A successful sync covering tracked earlier writes supports only that observed file-level relationship. A missing/truncated capture cannot establish absence. Ordinary key-family results give descriptive instrumentation context, not an invented within-block capture-on/off contrast.

Timeline runs use available trace categories on the same four keys. Record enabled/available categories, event identities, timestamps, buffers and loss status. A stripped packaged binary may expose insufficient events. Report that limitation. Source-implied steps are distinguishable from observed events; callback attribution remains **not established**. Neither family has a formal mechanism-significance test.

After every fault, preserve an immutable disk view before the browser oracle reads it. Record capture latency and any boot/filesystem activity before capture. A delayed snapshot is not the instantaneous crash state. Keep hashed read-only database, WAL/journal and relevant filesystem extracts, including header/format, WAL length/frames/checksums/commit markers/page identities and target-bearing-page interpretation when possible, for recovered and lost trials alike. Preserve replay/recovery derivatives separately. Unsupported formats/tools yield an unavailable observation, not an inferred loss location. If this preservation cannot be qualified, the affected cell/family is blocked.

### Tier 2

Fault scope crosses four keys with QMP reset, guest SysRq immediate reboot and browser-tree SIGKILL. Reset requires QMP reset/reason evidence and changed boot ID; SysRq requires guest command plus independent serial/kernel/reboot and changed boot-ID evidence. SIGKILL requires the selected process tree's identity and exit evidence and unchanged boot ID. Recovery machinery is separately labelled. No SysRq panic or physical-power interpretation is included.

Block state crosses four keys with matched linear control, dm-log-writes and dm-flakey drop-writes on an ext4-default mapped browser data volume. At the assigned boundary quiesce execution, capture immutable block state, and recover from a separate derivative with guest volatile state discarded. Record boundary/snapshot uncertainty and mapping/storage identity. In flakey cells the validated drop-writes interval starts after ACK and lasts until the boundary; preceding sentinel/target operations use the healthy mapping. Record transitions, writes, flush/FUA observations and capture completeness. An unvalidated transition or unavailable mapper blocks that cell.

For dm-log-writes reconstruct three registered prefixes: immediately before ACK marker, at ACK marker, and last fully recorded prefix before boundary. Pre-ACK is a precondition control, not acknowledged-write loss. Prefixes are dependent within one independent capture, and never counted as three scientific trials. Compare the boundary endpoint with the matched linear endpoint; report other prefixes descriptively. Unrecorded boundaries remain unknown. This is a block-state recovery model, without a physical-power guarantee.

Environment crosses four keys with exactly four profiles on matched browser data volumes: custom ext4 (`commit=30,discard`) at fixed 60-s target-launch uptime; ext4 defaults (no custom mount options; record actual defaults) at fixed 60 s; ext4 defaults at seeded integer-uniform 45,000 through 180,000 ms; xfs defaults at fixed 60 s. Record root/data-volume distinction, filesystem/mount values, unchanged live sysctls, scheduled launch uptime and actual uptime at ACK. No sysctl matrix is performed. Actual ACK uptime is not replaced by planned launch uptime.

Workload crosses four keys with quiet single-record reference; 32-KiB background writes plus fsync every 100 ms on a separate file on the same filesystem; ten 256-byte records in one transaction; four concurrent connections/tabs with three additional connections retained. Record achieved background operations and connection states. Check all ten records atomically; partial recovery is integrity failure. Disappearance or reversal of a pattern is reported, without changing the workload. No autosave editor is included.

### Optional Tier 3

Only if explicitly activated before any scientific acquisition, the registered cost family crosses strict/relaxed with {256-byte record, 64-KiB record, ten 256-byte records} and {retained, close/reopen per transaction}: 12 cells by ten blocks. Activation is logged independently of new outcomes. It has no crash and cannot enter a recovery denominator. Ten warm-ups and 100 measured transactions are nested within each fresh-overlay trial. Capture request/completion times, batch duration and independent readback. Throughput includes the declared connection policy. Later activation based on already observed campaign data requires a prospective amendment and separate status.

## 5. Randomization, attempts and stopping

Seed: `indexeddb-connection-lifetime-mac-20261003-v2`. Within each family and block, sort canonical condition JSON by SHA-256 of `seed|role|family|block|condition`, breaking ties by canonical JSON. Scientific and qualification roles have distinct identities and orders. Integer-uniform uptime draws use the documented SHA-256 rank in generate_design.py. The manifest binds all schedules and family order. Qualify all mandatory cells, lock inputs, build the operator package, and then an operator follows the Tier 1 and Tier 2 family order and within-family ordinal. Optional cost follows only if activated.

An assigned scientific slot is consumed once started, even if interrupted. Never retry, overwrite, silently collapse attempts or replace a missing endpoint. A resume takes the next unused slot. Extra trials require a prospective amendment with new identities. An independent eligibility check uses technical telemetry rather than target recovery: wrong condition/binary/backend; precondition or ACK failure; wrong fault or identity; early/late timing; missing close or unexpected held close; required capture failure; unreadable endpoint; interruption. Record analysis-specific eligibility separately from broad endpoint status and report all reasons/evidence.

No efficacy/futility stopping or outcome-dependent count changes. Stop for failed qualification, unsafe guest operation, unresolved evidence corruption, inadequate storage or unavailable tooling. Report affected cells/families and remaining assignments as blocked, and continue independently qualified families only through the later operator. Lower observed recovery does not authorize retries or another platform.

## 6. Analyses, multiplicity and attainable p-values

Three two-sided primary tests form one fixed Holm family at alpha 0.05:

1. Grid recovery at gap 2.4 s minus 1.6 s, stratified by close time {0, 1} s, matched within block and close stratum. The statistic sums the 20 possible within-pair signed recovery differences. Enumerate independent label swaps within each of these close-stratum pairs conditional on block/stratum, not an unpaired test or a pooled grid.
2. Ordering reversal: immediate close at 2.50 s minus delayed 1-s close at 2.75 s, using the ten matched blocks in the dedicated six-key family only.
3. Held 15-s minus held 5-s recovery, using the ten matched blocks in the dedicated held sweep only.

A directional hypothesis is supported only if the observed difference has the predicted direction and its Holm-adjusted exact p-value is at most 0.05. Failure is reported plainly. Unavailable/nonanalyzable registered tests receive p=1 in the fixed correction, rather than reducing family size or choosing a replacement. Repeated key conditions across different families are not pooled. Controls, held-30, instrumentation and the rest of the grid are descriptive.

For binary paired comparisons use complete, technically eligible two-state pairs; sum signed differences and calculate the exact two-sided tail including ties through enumeration or equivalent exact integer dynamic programming. Zero differences contribute no sign. No Monte Carlo substitute. Report complete-pair counts, missing-pair reasons, excluded integrity failures and missing-endpoint sensitivity bounds. Marginal cell estimates retain their own denominators; pairing is required for the exact tests.

Report exact two-sided 95% Clopper-Pearson intervals per eligible cell. Risk differences use Newcombe method 10, Wilson components without continuity correction, with direction and both denominators. These are pointwise marginal intervals, not simultaneous or block-adjusted paired intervals. Do not substitute Clopper-Pearson components under the Newcombe name.

Each secondary family uses the same exact block-paired procedure and its own Holm correction. Fault scope has **8** comparisons (two non-QMP faults versus QMP, four keys); block state has **8** (two mapped interventions versus linear at boundary, four keys); environment has **12** (three alternatives versus custom-ext4/fixed-uptime reference, four keys); workload has **12** (three alternatives versus quiet, four keys). Unavailable contrasts remain p=1. Comparisons between distinct families are descriptive, with no pooled scientific denominator or prespecified cross-family paired test.

| Family | Fixed tests | Maximum pairs per test | Smallest possible two-sided exact raw p | Smallest first-step Holm p at that pair count |
| --- | ---: | ---: | ---: | ---: |
| Primary grid endpoint contrast | part of 3 | 20 (2 close strata by 10 blocks) | 0.0000019073486328125 | 0.0000057220458984375 |
| Each other primary contrast | part of 3 | 10 | 0.001953125 | 0.005859375 |
| Fault scope | 8 | 10 | 0.001953125 | 0.015625 |
| Block state | 8 | 10 | 0.001953125 | 0.015625 |
| Environment | 12 | 10 | 0.001953125 | 0.0234375 |
| Workload | 12 | 10 | 0.001953125 | 0.0234375 |
| Optional durability cost | 12 | 10 | 0.001953125 | 0.0234375 |

These are attainability bounds, not power calculations or observed p-values. For binary contrasts with d discordant interpretable pairs the raw lower bound is `2 / 2^d`; ties, missing pairs and statistic ties can raise it. The grid's 20 swaps are explicitly conditional within close-stratum pairs, not ten joint whole-block sign flips. First-step Holm values multiply the smallest raw p by the full family size; later ranks use smaller factors. Ten complete binary pairs do not guarantee significance; an eight-comparison or twelve-comparison family needs at least nine fully aligned discordant pairs to pass its first step. Five-block timelines are descriptive with **zero** formal tests; a hypothetical five-pair two-sided test could not attain below 0.0625 and is not added.

Optional cost pairs strict/relaxed by workload, lifetime policy and block. Use exact 2^10 sign patterns of trial-level mean transaction duration and trial-level batch duration for throughput contrasts; Holm across six latency and six throughput contrasts. Report trial-level mean differences, throughput rates/ratios and within-trial median/p95 descriptives, with deterministic 10,000-resample paired-block percentile intervals under the master seed and their bootstrap assumptions. Do not treat nested transactions as independent trials.

## 7. Evidence ladder and mechanism limits

Keep observed recovery/timing; identity-resolved runtime instrumentation; consistency with pinned source reading; and not-established explanations distinct. Source reading may describe candidate control flow but cannot establish that a packaged-binary callback executed. Trace timelines and complete byte capture may support only their actual observed events and file relationships. Callback attribution remains **not established**, including an exact timer/destruction/checkpoint attribution. No delay intervention is performed, and significance of a recovery contrast alone does not identify a causal mechanism. Report absent events, capture loss, contradictions and unsupported links. No safe waiting time, physical-power claim, persistence guarantee or portability claim is made.

## 8. Disk retention and verified offload

Plan against **35 GiB total free**, with actual free space checked on the evidence filesystem. The measured revision-time free space is about 31 GiB, so the 35-GiB assumption is not a preflight result. Stop before a trial/archive if free space is below **6 GiB** or projected operation headroom would cross that floor. A new trial requires measured qualification-based headroom for overlay, forensic/capture data and safe archival. No acquisition starts without adequate full-family or verified intermediate-archive headroom.

Keep immutable raw JSON and all other raw event/capture streams, forensic extracts, exclusion/incidents and hashes for every attempt, including unknowns and qualification. Hash each full overlay before disposal. Retain full overlays for all technical/integrity anomalies, unknown/interrupted attempts and contradictory oracle/forensic evidence, plus a fixed seeded random sample independent of outcomes. An unexpected complete/absent outcome by itself is not an excuse to remove raw evidence or change sampling.

Random retention uses the SHA-256 rank of `seed|overlay-retention|trial_id`. Select the lowest floor(5%) of the 1,025 mandatory scientific-plus-qualification IDs: **51 full overlays, 4.9756%**, plus anomalies. Optional cost has a separate fixed selection of **6 of 132, 4.5455%**, plus anomalies. Selection flags are already in the assignment files; technical anomalies add retention and cannot remove a sampled image. All stored full overlays use zstd compression, with source/compressed hashes, byte counts and a decompression round-trip hash. Do not apply pilot gzip/xz ratios as measured zstd performance.

Completed-family evidence is compressed, hash-verified and offloaded to **Google Drive, author-managed folder IndexedDB-Mac-Confirmatory-v2 (folder URL pending)**. The author will create the Google Drive folder and upload the prepared archive chunks when prompted. No experimental-evidence upload is needed at Step 1. This is offsite storage only; no cloud experiments are authorized. Before acquisition, record the actual folder URL and qualify upload/download hash verification. Another folder on the same APFS container does not provide additional free space.

The operator prepares numbered archive chunks no larger than 1 GiB, with a transfer manifest and explicit upload instructions at each completed family or declared intermediate archive boundary. The author uploads every listed chunk and manifest to Google Drive. Download each uploaded chunk back into bounded verification scratch, check its SHA-256, and stream decompression/member-hash verification. Upload completion, a Drive filename or cloud sync alone is not verification. Record returned-download hashes and the destination URL. Do not upload host private keys, unlock passwords or credential files. Before deleting any local evidence, reread and verify the offloaded raw/forensic/hash package and every selected/anomalous full overlay, verify round-trips and record the transfer manifest and destination. Unselected normal overlays are temporary acquisition artifacts under this declared retention policy: they may be discarded only after their hashes/forensic extracts and the full required evidence package have verified offload. Selected/anomalous overlays remain recoverable in verified compressed offload before any local removal. Keep all originals while offload is pending; never delete evidence to evade the 6-GiB stop. If a family cannot fit before offload, pause at a declared complete-block/batch boundary and verify an intermediate archive, without changing assignment order or outcomes. If that cannot be done, report storage blocking.

## 9. Subsequent work, without acquisition by this agent

Step 2 is authorized only after the author supplies the matching OSF URL and repository tag. Provision and qualify each registered cell once, record blocked cells/families, correct runtime/storage estimates, and lock all scientific inputs/scripts/hashes.

Step 3 builds a resumable operator CLI with status, preflight, run-batch N, verify, archive and disk-check, all under caffeinate. It consumes the next N unused assignments in registered order, never retries a scientific slot, never overwrites evidence, and writes unique attempt directories. RUNBOOK.md must give exact commands, checklist, stop conditions and error explanations. STATUS.md/status.json must update per batch with per-family assigned/started/complete/technically-invalid/integrity-failure/unknown/remaining counts, disk free, last batch and ETA. Include INCIDENT_TEMPLATE.md. Demonstrate status, run-batch, verify and archive end to end using a disposable copy/replay of one completed excluded qualification cell, with dry-run output explicitly labelled and the original untouched. This demonstration adds no scientific assignment, fabricated observation or qualification retry.

Step 4 stops with counts, corrected hours, verified disk/offload plan, blocked families, RUNBOOK.md path and the exact smaller-agent hand-off message. Scientific acquisition belongs to that later operator. The current gate ends at Step 1, before any provisioning or qualification.

The later results summary determines allowed claims and must report completed, contradicted, blocked and not-performed work plainly. Exact raw-derived analysis and evidence archival precede the tested publication ZIP; only then may the Word manuscript be written. Physical-power work remains not performed, and previous/second-host pilots remain separate.

## 10. Saved public-source identities

Saved sources cover the dated Ubuntu checksums/ARM64 package manifest and pinned Chromium VERSION. The official checksum file lists multiple public architectures; only the ARM64 image above is an active input. Removed source-build and stable-version receipts are recoverable from the superseded draft's Git history, not active design inputs.

Pinned source reading references, without runtime attribution:

- https://github.com/chromium/chromium/blob/971a7443b0c9b0a9b2860529b33331b76077ec62/content/browser/indexed_db/instance/sqlite/database_connection.cc
- https://github.com/chromium/chromium/blob/971a7443b0c9b0a9b2860529b33331b76077ec62/content/browser/indexed_db/instance/bucket_context.cc

New image bytes, packaged executable, trace capability and guest tooling are pending technical verification after the external-registration gate. No current source receipt is a claim of successful qualification.
