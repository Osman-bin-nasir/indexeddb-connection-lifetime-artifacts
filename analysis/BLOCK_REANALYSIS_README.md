# Reproduce the existing block-state reanalyses

These are read-only, post hoc analyses of the original block-state trials. They add zero scientific units. The original campaign still has 930 consumed assignments, 925 eligible binary endpoints, 340 recovered and 585 lost, four unknown endpoints and one premeasurement slot.

Run from the release root using Python 3.11 or later. No external Python packages are required:

```bash
python3 analysis/block_reanalysis.py \
  --release-root . \
  --last-flush-results analysis/block_last_flush_results.json \
  --reader-evidence analysis/block_last_flush_reader_evidence \
  --output /tmp/idbv2-block-reanalysis.json
```

The command reads the compact release and writes only the requested derived JSON output. It does not start a VM, submit a transaction, dispatch a fault, or run a recovery reader. `supplementary_table_S5` recomputes all thirty immediate-close matched timeline rows from the raw block trace, original clock samples and transition records. `supplementary_table_S6` recomputes the four separate ten-trial dependent-prefix cells from retained registered-prefix records and the completed derived-reader receipts. The optional `--reader-evidence` argument also checks every saved derived oracle's complete target/sentinel contents against its original payload contract.

The thirty timeline rows include only device-mapper BIO submissions definitely after host ACK and before dispatch. W counts writes with nonzero sector counts. F counts PREFLUSH and/or FUA flags and can overlap W; the counts are not added. Request-layer repeats are excluded from S5. The captures have no completion tracepoint or target-byte-to-sector association. Timing brackets are conservative mappings rather than calibrated total-error intervals.

For the literal last completed FLUSH recorded in each immutable paused capture, recovered counts are immediate close 10/10, delayed close 0/10, held 5 s 0/10 and held 15 s 2/10, with no unknown derived endpoints. These are dependent observations of forty original logging trials. In thirty-nine logs the selected FLUSH prefix omits one later 4096-byte FUA metadata write; the other log ends at the FLUSH record itself. All selected last-FLUSH records carry FLUSH, FUA and metadata flag bits but have zero payload bytes. Their FUA bit is not an additional payload-bearing FUA write.

The raw logs have completion ordering under the pinned kernel's dm-log-writes semantics but no completion wall timestamps. One held-15-s matching issue overlaps the controller dispatch/quiesce uncertainty by approximately 0.377 ms. Selection means recorded completion no later than paused capture, not an exact pre-dispatch cache frontier. Neither this replay nor the early flakey write cutoff reproduces physical loss of a volatile device write cache.

## What the compact release cannot replay

The private full `original-log.raw` volumes and VM image backing chain are excluded. The command therefore reports `blocked_missing_private_raw_log_bytes` for fresh raw-log decoding/replay and `retained_LOG_DECODE_JSON_only` as the log-decoder source. It does not claim that the saved decoder was freshly decoded from absent bytes. It can verify receipt consistency and saved oracle contents, but cannot rehash absent original log volumes or rerun a guest recovery oracle.

A fresh private-byte decode requires the forty exact-hash `original-log.raw` files at their registered per-trial paths. Fresh guest recovery additionally requires the pinned guest base and complete backing chain, packaged Chromium, existing-database reader and forensic/replay tools, original payload/oracle identities, and fresh writable derivatives. Do not substitute another guest, browser or oracle. Once the private log files are restored to a separate full repository evidence copy, the same read-only script can decode them:

```bash
python3 analysis/block_reanalysis.py \
  --root /absolute/path/to/full-repository-evidence-copy \
  --last-flush-results analysis/block_last_flush_results.json \
  --reader-evidence analysis/block_last_flush_reader_evidence \
  --verify-full-log-hashes \
  --output /tmp/idbv2-block-full-log-check.json
```

This second command still does not run a VM or recovery reader. It independently decodes the present raw log payloads, compares them with retained decoder entries, and hashes available full logs. Missing private logs are explicitly reported. VM replay remains a separate task with missing private runtime dependencies.

## Preserved analysis incidents and semantic warning

`block_last_flush_reader_evidence/` preserves the initial local socket denial, the first reader's completed oracle followed by asynchronous hot-unplug cleanup error, the append-only acceptance receipt, the 29-prefix batch and storage-floor stop, the final ten-prefix batch, and derivative cleanup/hash receipts. The partial and failed summaries remain as originally written. The combined `block_last_flush_results.json` contains the forty accepted dependent endpoints; it does not replace those earlier records.

One generic reader receipt for `scientific-block_state_recovery-00004` states `excludes_later_completed_FUA: true`, even though its literal last FLUSH is also the final log entry. This is an administrative wording mismatch, not a different selected prefix or endpoint. The receipt remains byte-exact. `preserved_receipt_semantic_warnings` in the recomputed output explicitly records the mismatch and the decoded absence of a trailing event. The other thirty-nine logs do omit a trailing FUA metadata write.

`BLOCK_REANALYSIS_EVIDENCE_COPY.json` records source/destination verification for the compact reader evidence. The reader receipts retain non-secret absolute host-path provenance. They are evidence records, not a relocated or runnable VM environment.

## Pinned source for interpreting flags

- [Linux dm-log-writes documentation](https://docs.kernel.org/admin-guide/device-mapper/log-writes.html)
- [Linux v6.8 dm-log-writes source](https://raw.githubusercontent.com/torvalds/linux/v6.8/drivers/md/dm-log-writes.c), `normal_end_io` and log flags
- [Linux v6.8 block trace source](https://raw.githubusercontent.com/torvalds/linux/v6.8/kernel/trace/blktrace.c), `blk_fill_rwbs`

The pinned kernel source enqueues FLUSH records after completion and FUA writes after completion; ordinary completed writes wait for a subsequent flush group. The source supports completion ordering, not an exact timestamp for the target-bearing write. Runtime callback attribution remains not established.
