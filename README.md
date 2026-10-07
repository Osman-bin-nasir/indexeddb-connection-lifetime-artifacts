# Connection lifetime and acknowledged IndexedDB write recovery

This public artifact package contains data, analysis code, frozen design files, and retained diagnostic evidence for a completed prospective campaign using packaged Chromium 153.0.8010.12 with SQLite explicitly enabled, an ARM64 Ubuntu guest, and one Apple Silicon host. The registered experimental conditions and original evidence are preserved. The package is an evidence and analysis copy, not a relocated runnable VM environment.

## Current revision supplement

[Version 1.1.0](https://github.com/Osman-bin-nasir/indexeddb-connection-lifetime-artifacts/releases/tag/v1.1.0) adds verified unpublished supporting syscall evidence, acquisition and filesystem context, revised named figures and current manuscript table exports. It is also deposited in [OSF svrjy](https://osf.io/svrjy/). See [the supplement README](supplements/round4_20261007/README.md) for byte verification, reproduction commands, separate denominators and limits. The original v1.0.0 complete campaign assets remain unchanged and are still required for all-930 reproduction.

## Obtain the complete artifact package

Download `IndexedDB_930_Public_Artifacts_v1.0.0.zip`, `OSF_REGISTRATION_V2_5a749734.zip`, and `ARTIFACT_SHA256SUMS.txt` from the [versioned release](https://github.com/Osman-bin-nasir/indexeddb-connection-lifetime-artifacts/releases/tag/v1.0.0). Verify both ZIPs before extracting the evidence package:

```bash
shasum -a 256 -c ARTIFACT_SHA256SUMS.txt
unzip IndexedDB_930_Public_Artifacts_v1.0.0.zip
cd IndexedDB_930_Public_Artifacts
python3 analysis/verify_manifest.py --release-root .
```

The Git repository contains the protocol, analysis scripts, derived tables and figures. The full per-trial evidence is supplied in the release ZIP. Reproduction commands requiring raw records must run from the extracted complete package.

## Scope and denominators

There are 930 assigned scientific slots, 929 result records, and 925 technically eligible complete/absent endpoint oracles across 95 mandatory cells. Eligible endpoints comprise 340 recovered and 585 lost observations. Four result endpoints remain unknown, and one slot was consumed before measurement. These inventory totals cover different conditions and must not be pooled into a recovery rate.

Pilot, second-host pilot, support, smoke and qualification datasets contribute no registered scientific endpoints. The v1.1.0 supplement presents 32 earlier supporting syscall observations separately, with their original collection dates and denominators; they are not pooled with the 930 registered assignments. The frozen protocol contains the original optional cost design and pilot-derived resource estimates as prospective provenance; that optional family was not acquired. Dependent log-prefix reconstructions add zero scientific units. Unknown and premeasurement slots are retained, never converted into losses or replaced by retries.

## Registration and publication chronology

The public OSF registration is [b3xpe](https://osf.io/b3xpe/), DOI [10.17605/OSF.IO/B3XPE](https://doi.org/10.17605/OSF.IO/B3XPE), registered on 3 October 2026 at 18:48:13.446328 UTC. Scientific acquisition started on 4 October 2026 at 14:03:18.148755 UTC and ended with the last integration-completion receipt on 6 October 2026 at 10:57:40.678224 UTC. These bounds refer to administrative attempt receipts, not ACK or fault timestamps. Its initial immutable file snapshot did not contain the later complete hashed file package. Historical associated-project upload and return-check records remain distinct from that registration snapshot.

This public GitHub release was prepared on 7 October 2026 after scientific acquisition and analysis. It does not create a retrospective preregistration timestamp. The separately supplied `OSF_REGISTRATION_V2_5a749734.zip` is the exact retained original frozen package: SHA-256 `ee5dd24cefabb0ea3ea682cd7368f4bad5dc6ccfdd21d6d8ad9c4deac5223a2f`. All 30 files listed in its inventory match the frozen repository tag `prereg-connection-lifetime-mac-v2` and the authoritative source. The ZIP also includes `SHA256SUMS` itself.

The protocol SHA-256 is `a3dfb023a7fb9e4862edc4242a7cbac1b3b8865790dbcbb1156fddfd128b13b1`; the design manifest SHA-256 is `5584eb171e36f5e3df890bc3879f2658f84414652849ef44ed6db0540f68ee42`.

## Reproduce the tables from raw records

Python 3.11 or later and the standard library suffice. Write reproduced outputs outside the extracted evidence folder:

```bash
python3 analysis/recompute.py --release-root . --out /tmp/idbv2-reproduced
python3 analysis/grid_strict_reanalysis.py --root . --out /tmp/idbv2-reproduced/a3_a4
python3 analysis/block_reanalysis.py \
  --release-root . \
  --last-flush-results analysis/block_last_flush_results.json \
  --reader-evidence analysis/block_last_flush_reader_evidence \
  --output /tmp/idbv2-reproduced/block-reanalysis.json
```

| Manuscript item | Reproduction output |
|---|---|
| Current Table 3 assignment inventory | `Table_1_inventory.csv` |
| Current Table 4 primary comparisons; complete intervals in S7 | `Table_2_primary_tests.csv` |
| Current Table 5 significant secondary comparisons | `Table_3_secondary_significant.csv` |
| All secondary comparisons, including nonsignificant results | `All_registered_secondary_tests.csv` |
| Tables A1 to A9, all 95 cells | `Table_A1_cells.csv` through `Table_A9_cells.csv` |
| Table A12 pinned hashes | `Table_A12_hashes.csv` |
| Supplementary Table S1 dispatch overshoot | `Table_4_dispatch_overshoot.csv` |
| Supplementary Table S2 observed close delays | `Table_A10_close_delays.csv` |
| Supplementary Table S3 environment uptimes | `Table_A11_uptimes.csv` |
| Supplementary Table S4 achieved 2.0-second trial intervals | `a3_a4/A3_A4_RESULTS.json` |
| Supplementary Tables S5 and S6 mapper timelines and dependent prefixes | `block-reanalysis.json`, fields `supplementary_table_S5` and `supplementary_table_S6` |
| Every scientific slot and disposition | `All_930_dispositions.csv` |
| Trial timing records | `All_trial_timings.csv` |

The main recomputation independently verifies the copied assignments, eligible endpoint contents, and 11,140 scoped original hashes. It recomputes exact Clopper-Pearson intervals, exact blocked paired comparisons, Holm corrections for the registered families, and Newcombe method 10 marginal risk-difference intervals. The original 43 registered comparisons are preserved. The rank-based timing analysis and log-prefix reads are explicitly post hoc and descriptive.

## Reproduce the six grayscale figures

Matplotlib and NumPy are needed only for plotting. See `analysis/FIGURE_REPRODUCTION_README.md` for reference versions and interpretation limits.

```bash
python3 -m pip install matplotlib numpy
python3 analysis/rebuild_figures.py \
  --release-root . \
  --recomputed /tmp/idbv2-reproduced/RECOMPUTED_RESULTS.json \
  --a3-a4 /tmp/idbv2-reproduced/a3_a4/A3_A4_RESULTS.json \
  --out /tmp/idbv2-reproduced/figures
```

The original v1.0.0 reference PNGs are in `figures/`. Current named presentation figures are in `supplements/round4_20261007/figures/`; use that supplement’s `rebuild_figures_round4.py` for the revised presentation. All numerical series are unchanged. Rendering differences can arise from different library or font versions even when numerical series agree. Intervals are pointwise, and the achieved-time panel uses recorded mapping half-RTT rather than a calibrated total timing-error bound.

## Original failures and audit correction

Assignment 311 retains its original failed audit and unchanged raw LOST endpoint. Its accepted eligibility comes from the append-only validator correction in `campaign_v2/operator/validator_correction_v1/REVALIDATION_311.json`; it was not rerun. The four unknown endpoints and one premeasurement slot remain outside binary outcome denominators. `EXCLUSION_DISPOSITIONS.json` indexes the original five noneligible dispositions.

The original `campaign_v2/operator/STATUS.md` is stale and reports an earlier 420-slot stage. The preserved machine-readable `status.json` reports the final 930 consumed assignments. Neither was silently reconciled. Raw-record recomputation supplies the reported scientific counts.

## Evidence and privacy limits

The scientific records are byte-exact originals, including non-secret host paths and artificial guest/network identities where these are part of provenance. They are not described as de-identified. `PUBLIC_PACKAGING_PROVENANCE.json` inventories copies and omissions. Full disk overlays, ISO images, full log/replay volumes, private keys, credentials, private Google Drive maps, and operational transfer instructions are excluded. The files were scanned for private-key and common credential markers before publication. No source campaign file was modified.

This package reproduces statistical tables, timing analyses and summaries of retained diagnostics. It cannot recreate guest RAM, missing full disk state or a new physical power-loss experiment. Fresh replay of dm-log-writes prefixes requires the excluded private log/data volumes and compatible guest images. The supplied compact reader receipts and oracles verify the reported dependent counts, not a fresh replay from absent volumes. See `analysis/BLOCK_REANALYSIS_README.md`.

Earlier offloads used an author-authorized waiver of returned-byte verification before local cleanup. Later checks verified 20 of 41 offloaded compressed archive objects and 21 of 62 chunks. Remaining archive returns were paused at the author's request; one chunk encountered a browser download block. The original waiver remains part of the acquisition chronology. Verification of this public package does not establish integrity of every separately offloaded full archive.

## Rights and attribution

This publication does not introduce a blanket software or data license. Existing notices in individual source files are preserved. The OSF registration's CC0 selection does not establish the license of every file in this separate release. Third-party software and documents retain their original rights; full software distributions are not included. A future explicit release license requires the author's choice.

AI tools assisted drafting, analysis scripting and verification. The scientific evidence and its original dispositions remain unchanged. Manuscript authorship and venue-specific disclosures are separate from this artifact deposit.
