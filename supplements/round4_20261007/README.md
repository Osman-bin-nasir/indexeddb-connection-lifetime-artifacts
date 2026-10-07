# Verified supporting syscall evidence and manuscript revision artifacts

Version 1.1.0, prepared 7 October 2026 after acquisition. This supplement accompanies the same connection-lifetime IndexedDB study. It adds unpublished supporting experiments collected on 28 September 2026, verified acquisition and filesystem context, updated presentation figures, and manuscript table exports. It is an evidence and analysis copy, not a runnable VM environment.

The registered campaign remains **930 assigned slots, 929 result records and 925 eligible endpoints**, comprising 340 recovered and 585 lost observations. Four endpoints remain unknown and one slot had no measurement. The deliberately heterogeneous conditions are never pooled into an aggregate recovery rate. This revision adds **zero registered scientific units** and performs no new experiment or registered statistical test.

Earlier supporting experiments remain pilot evidence under the frozen v2 protocol. Their original dates, populations and denominators are retained, even though they are presented within the same paper. Raw identifiers retain historical names; these do not designate an additional published paper.

## Obtain the underlying registered-campaign evidence

The complete compact evidence for all 930 assignments and the original frozen package remain in [release v1.0.0](https://github.com/Osman-bin-nasir/indexeddb-connection-lifetime-artifacts/releases/tag/v1.0.0). This version is an additive supplement and does not replace those assets. Download and verify the v1.0.0 assets using their original `ARTIFACT_SHA256SUMS.txt` before extracting.

The original prospective registration is [OSF b3xpe](https://osf.io/b3xpe/), DOI [10.17605/OSF.IO/B3XPE](https://doi.org/10.17605/OSF.IO/B3XPE). This post-acquisition supplement is deposited in [OSF svrjy](https://osf.io/svrjy/). The registration and repository freeze are unchanged. The original registration snapshot's file-package limitations and historical archive-verification waiver remain disclosed in v1.0.0 and in the paper.

## Acquisition chronology

| Event | UTC timestamp | Evidence |
|---|---|---|
| Prospective OSF registration | 2026-10-03T18:48:13.446328 | Retained public OSF API receipt |
| First scientific attempt started | 2026-10-04T14:03:18.148755+00:00 | `scientific-close_aligned_recovery_grid-00001/START.json` |
| Last assigned attempt's integration completed | 2026-10-06T10:57:40.678224+00:00 | `scientific-application_and_background_activity-00160/OPERATOR_INTEGRATION_RESULT.json` |

These are administrative acquisition bounds, not the target ACK or fault timestamps. `CAMPAIGN_CONTEXT_VERIFICATION.json` verifies 930 starts, 929 completion receipts and 929 acquisition mounts. The earlier administrative registration receipt retains its original pending-status fields; the later public OSF API receipt supplies the registration timestamp. Neither was silently edited.

## Supporting syscall observations

Each row has its own eight-trial denominator. The timing and close-versus-held populations each contain 16 trials and remain separate.

| Population / condition | Recovered | Completed post-ACK WAL fdatasync | Successful WAL unlinkat after sync |
|---|---|---|---|
| Timing: closed, 2.00 s reset deadline | 0/8 | 0/8 | Not traced |
| Timing: closed, 2.25 s reset deadline | 8/8 | 8/8 | Not traced |
| Close versus held: closed, 2.25 s | 8/8 | 8/8 | 8/8 |
| Close versus held: held, 2.25 s | 0/8 | 0/8 | 0/8 |

Recovering timing trials have reconstructed WAL sync entry times +2.007074205 to +2.022462043 s relative to the historical ACK anchor. Recovering close-versus-held trials have +2.011089505 to +2.029098298 s, followed by successful deletion of the same WAL after the completed sync. The held trials show neither post-ACK event within the observed window. All 32 recovery payloads, checksums, sentinels, boot-ID changes and traces were independently rechecked.

The raw records show one pre-ACK WAL fdatasync in every trial and a second completed call in the 16 recovering trials. The historical clock reconstruction uses a median paired guest realtime-minus-monotonic offset and a separate post-ACK uptime RPC. Browser ACK realtime and uptime were separate samples. The residual latency prevents exact timer or callback attribution. Reported times are entries of completed zero-return calls, with durations retained. The timing population did not trace unlinkat; missing unlink events there are not negative observations.

Both populations used packaged Chromium 153.0.8010.12, SQLite enabled, and an ARM64 guest under HVF. Their freeze-bound tracing pipelines, order and identity files match their recorded hashes. No per-trial executable digest is present in these earlier populations; available package, flags, format, guest and host provenance is retained. Function uprobes were not successfully armed and provide no callback attribution. The source `trial.json` harness placeholders are preserved separately from the final eligible `result.json` records. Full original VM overlays are not included.

## Filesystem and trace context

Principal campaign families used browser profiles on the guest root `/dev/vda1`, ext4 with `commit=30,discard`: close-aligned grid, held sweep, six-key, byte capture, category traces, fault scope and workloads. Block-state acquisition instead used `/dev/mapper/idbv2-browser` mounted at `/var/lib/idbv2` with ext4 defaults. Environment acquisition used a separate `/dev/vdc` browser-data volume: custom ext4 with `commit=30,discard`, default ext4 at fixed or randomized uptime, or XFS defaults. Recovery/helper device attachments are not acquisition devices. One premeasurement trace slot has no observed mount.

Trace end requests were 1.246810917 to 1.254130625 s after delayed close, before the approximately 2 s candidate interval, and 2.000867460 to 2.009048959 s after immediate close, near it. The traces therefore cannot uniformly be described as missing that interval. The declared final half-second before fault dispatch was outside coverage, and the category traces supplied no direct callback marker.

## Reproduce verification without acquisition

Python 3.11 or later and the standard library suffice. From this supplement directory:

```bash
python3 verify.py --root .
python3 verify_campaign_context.py \
  --release-root /absolute/path/IndexedDB_930_Public_Artifacts \
  --out /tmp/idbv2-context-reproduced
```

`verify.py` checks 1,732 byte-exact copied input hashes, the two original freezes and orders, all 32 raw recovery oracles, connection states, timing validity, syscall events and reconstructed times. It never imports the acquisition runner. `sync_parser.py` and `historical_oracle.py` are pure-function extractions; original source snapshots are retained. The second command reads the original v1.0.0 compact campaign records and writes context verification outside that source folder.

To rebuild the current six named presentation figures, first reproduce the v1.0.0 registered results and grid re-analysis using its README. Then use Matplotlib and NumPy in an analysis environment:

```bash
python3 rebuild_figures_round4.py \
  --release-root /absolute/path/IndexedDB_930_Public_Artifacts \
  --recomputed /tmp/idbv2-reproduced/RECOMPUTED_RESULTS.json \
  --a3-a4 /tmp/idbv2-reproduced/a3_a4/A3_A4_RESULTS.json \
  --out /tmp/idbv2-round4-figures
```

All 81 plotted cell series and 20 achieved-time points match v1.0.0 exactly. Only titles and count-label presentation changed. Rendering may vary with font or plotting versions. These figures do not add scientific observations or identify an exact recovery threshold.

## File map and manuscript revision

- `raw/`: byte-exact original compact records for the two supporting populations.
- `source_snapshots/`: original design, configuration, trace pipeline, freeze, order, identity and execution records.
- `INPUT_SHA256.json`: copied-source identities; verification also checked the originals before publication.
- `SYSCALL_VERIFICATION.json`, `SUPPORT_FREEZE_VERIFICATION.json`, `trials.csv`: detailed supporting observations and limits.
- `CAMPAIGN_CONTEXT_VERIFICATION.json`: all acquisition receipts, mounts and relevant trace windows, with source hashes.
- `PUBLIC_AND_GIT_PROVENANCE_PRIOR_VERIFIED.json`: preserved earlier OSF/freeze provenance verification receipt.
- `figures/`: six revised named figures and numerical series.
- `Table_1_filesystem_mapping.csv`, `Table_2_incidents.csv`: new descriptive context tables.
- `Table_3_inventory.csv`, `Table_4_primary_tests.csv`, `Table_5_secondary_significant.csv`: current main-paper table exports.
- `Table_S7_primary_intervals.csv`: unchanged complete original primary estimates and intervals.
- `Table_S8_supporting_syscall_cells.csv`: four separate supporting cells.
- `ROUND4_MANUSCRIPT_AUDIT.json`: all 19 original scientific tables, p-values, plotted values, author placeholders and abstract preserved; 36-page document visually checked.

The main primary table omits marginal intervals for readability; S7 preserves them, and paired exact tests remain the inference. Exploratory rank analysis and administrative chronology move to the supplement. Results and Discussion use six named figures without subsection headings. The conclusion has two paragraphs. A post hoc two-path hypothesis remains explicitly speculative. Callback attribution, target-page sync attribution, safe waiting times, physical-power guarantees and portability are not established.

The edited manuscript is retained locally pending the author's final author details. This artifact deposit is not a journal submission and does not publish a separate earlier paper.

## Evidence and rights limits

Images, ISO files, credentials and keys are excluded. Compact records retain non-secret original host paths and artificial guest identities as provenance; they are not described as de-identified. Source evidence was not modified. Public ZIP/download verification proves the deposited compact package's bytes, not the integrity of every separately offloaded full archive. The earlier 20/41 archive verification limit remains unchanged.

No new blanket software or data license is introduced by the GitHub release. Existing source notices and third-party rights are preserved. The OSF component inherited the associated project's existing CC0 metadata; this does not establish a license for every third-party file. AI tools assisted drafting, scripting and verification; original data and dispositions remain intact.
