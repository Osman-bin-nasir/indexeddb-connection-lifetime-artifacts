# One-Mac resource plan, registration version 2

Status: provisional planning scenarios, not qualification or acquisition. Resource calculations are in RESOURCE_ESTIMATES.json and reproducible with estimate_resources.py. All existing trials are pilot-only and none supply a new scientific endpoint.

## Counts

Tier 1 has 370 assignments and 39 excluded qualification attempts. Tier 2 has 560 and 56. Mandatory total: 930 scientific assignments, 95 qualification attempts, 1,025 attempts. Optional cost adds 120 scientific and 12 qualification attempts. Timeline cells have five blocks; the other cells have ten.

## Time

PILOT_RESOURCE_BASELINE.json identifies and hashes 90 original-host pilot event streams. Their first-to-last host-monotonic spans have median 37.019 s, mean 36.494 s, range 18.391 to 67.570 s. This omits unlogged preparation/intertrial/archive time, and none of these pilots used the new complete forensic, mapped-volume and uptime design. It is a resource reference, not a measured forecast for new cells.

The following explicit per-attempt assumptions allow additional preparation, forensic inspection, captures, prefix recovery and uptime waits. They are planning ranges, not confidence intervals or measured new runtimes.

| Family | Science + qualification | Assumed seconds/attempt | Machine-hours |
| --- | ---: | ---: | ---: |
| Close grid | 180 + 18 | 60 to 90 | 3.30 to 4.95 |
| Held sweep | 70 + 7 | 60 to 90 | 1.28 to 1.93 |
| Six keys | 60 + 6 | 60 to 90 | 1.10 to 1.65 |
| Byte capture | 40 + 4 | 120 to 240 | 1.47 to 2.93 |
| Trace timelines | 20 + 4 | 90 to 180 | 0.60 to 1.20 |
| Fault scope | 120 + 12 | 60 to 120 | 2.20 to 4.40 |
| Block state and dependent replays | 120 + 12 | 180 to 300 | 6.60 to 11.00 |
| Environment and uptime waits | 160 + 16 | 120 to 210 | 5.87 to 10.27 |
| Workloads | 160 + 16 | 60 to 120 | 2.93 to 5.87 |
| **Mandatory attempts** | **1,025** | mixed | **25.35 to 44.19** |
| Optional cost | 120 + 12 | 90 to 180 | 3.30 to 6.60 extra |

Reserve another 2 to 6 machine-hours for provisioning and archive/round-trip verification: **about 27 to 50 machine-hours mandatory overall**, before registration waiting, human intervention or blocked-tool debugging. Optional cost is additional. These are sequential single-Mac estimates. Qualification will replace them with cell-level measured wall time, actual snapshot/replay cost, offload speed and storage consumption. No completion date is promised.

## Disk

The author-specified planning budget is 35 GiB free. The filesystem actually reported **31.002 GiB** during this revision. Preflight uses current measured free space, with a **6-GiB hard floor** and projected operation headroom. Existing pilot evidence is not removed to make room.

The historical STORAGE_PROJECTION.md reports a 54.11-MiB mean overlay, 61.75-MiB maximum and 0.74-MiB raw mean from 36 pilot smoke trials. That source and the event streams are hash-bound in PILOT_RESOURCE_BASELINE.json. This is not a guarantee for the new image, mapped volumes or forensic captures.

| Item | Planning occupancy |
| --- | ---: |
| All 1,025 mandatory overlays simultaneously, pilot mean | 54.16 GiB, does not fit |
| Largest complete family including qualification, 198 overlays | 10.46 GiB at pilot mean; 11.94 GiB at pilot maximum |
| All mandatory raw at pilot mean | 0.74 GiB |
| Added forensic/capture extracts, assumed 1 to 8 MiB/attempt | 1.00 to 8.01 GiB across the campaign |
| New provisioned base/tools reservation | 3 to 6 GiB |
| Streaming archive/verification scratch reservation | 2 GiB |
| Seeded retained full overlays, 51 images, before zstd | 2.69 GiB, plus all anomalies |
| Seeded overlays after hypothetical 10% / 25% / 100% zstd ratio | 0.27 / 0.67 / 2.69 GiB, plus anomalies |

Zstd compression is **not measured yet**. The old gzip/xz measurements are not used as zstd results. Extract budgets are assumptions, not limits permitting capture truncation. Additional mapped-volume images, replay derivatives or larger capture streams may exceed them. Qualification must measure allocated and logical bytes on every active filesystem, image backing chains, anomaly/archive overhead and scratch. If it does not fit, report blocked cells/families rather than reducing evidence or changing conditions.

A conservative largest-family scenario is 6 GiB new base/tools + 11.94 GiB overlays + 1.69 GiB raw/forensics + 2 GiB scratch = **21.63 GiB additional occupancy**. Against 31.00 GiB current free, this leaves about 9.37 GiB, including the 6-GiB floor and only 3.37 GiB extra margin. Earlier completed families must already be offloaded. This conditional calculation is not a feasibility pass. A high anomaly count or mapped-volume growth can exhaust the margin.

No public source build or its large build-storage reservation is required. ARM64/HVF, the exact packaged binary, forensic/capture tools and guest volume capabilities remain unqualified. No fallback platform is authorized.

## Retention and offload

Keep raw JSON/event/capture streams, forensic extracts and hashes for every attempt. Retain full overlays for technical/integrity anomalies, unknowns, interruptions and contradictory oracle/forensic evidence, plus the frozen seeded sample: 51 of 1,025 mandatory IDs (4.9756%); optional cost separately 6 of 132 (4.5455%). Compress retained full images with zstd, preserve byte/hash manifests and prove decompression round trips. Sampling never depends on recovery outcome.

Offload destination: **Google Drive, author-managed folder IndexedDB-Mac-Confirmatory-v2 (folder URL pending)**. The author will upload the operator-prepared chunks to Google Drive when each family or declared intermediate archive is ready. No experimental upload is needed now. Record the folder URL and qualify transfer before acquisition. Manual upload time and network-dependent download verification are not measured in the current hour range and can extend elapsed time. A second directory on the same APFS container does not add capacity. Completed-family archives, or intermediate archives at declared complete-block/batch boundaries if needed, require destination reread/hash verification and recoverable selected/anomalous full images before any local evidence deletion. Unsampled normal overlays can only be discarded after verified offload of their forensic extracts/hashes and all required raw evidence, according to this disclosed policy.

Check disk before every attempt and before archive; stop below 6 GiB or before predicted headroom crosses it. Never delete unverified evidence to bypass that stop. No offload or compression has been attempted in this registration revision.

## Pending qualification

Every mandatory cell's image, toolchain, fault, timing, oracle, immutable pre-reader snapshot and retention workflow is pending after OSF/tag confirmation. No cell is falsely recorded as qualified. The destination is explicitly unresolved. Provisioning or qualification failure becomes a documented blocked cell/family. Second-host replication remains outside this plan until fresh access and a prospective amendment.

Google Drive hand-off: the future operator writes an exact upload list and numbered chunks of at most 1 GiB, plus hashes/transfer manifest. Upload all listed raw/capture/forensic/incident/qualification evidence and sampled/anomalous full-overlay archives. Download each chunk back to bounded scratch, verify SHA-256 and streaming member/round-trip hashes, then record the successful destination verification. Never remove local evidence merely because Drive shows an upload complete. Uploads contain no host private keys or unlock credentials. No cloud compute is authorized.
