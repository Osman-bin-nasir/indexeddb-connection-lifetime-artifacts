# A3/A4: existing-data reanalysis

No new trials. All raw campaign files read-only. The exploratory tests do not modify any hash-frozen primary/secondary family.

## A3: assigned 2.0-s cells

All 20 endpoints are technically eligible: immediate close 2/10 recovered; 1-s delayed close 1/10 recovered. Times are mapped observed-close-to-host-dispatch estimates, not reset-event times.

| Close s | Block | Trial | Outcome | Achieved estimate s | Mapping half-RTT ms | Pooled rank | Within-stratum rank |
|---:|---:|---|---|---:|---:|---:|---:|
| 0 | 1 | scientific-close_aligned_recovery_grid-00014 | lost | 2.004073584 | 0.3856665 | 15 | 8 |
| 0 | 2 | scientific-close_aligned_recovery_grid-00021 | lost | 2.004027562 | 0.3646460 | 12 | 6 |
| 0 | 3 | scientific-close_aligned_recovery_grid-00053 | lost | 2.008053959 | 0.3696250 | 19 | 10 |
| 0 | 4 | scientific-close_aligned_recovery_grid-00064 | recovered | 2.003238771 | 0.3111040 | 8 | 5 |
| 0 | 5 | scientific-close_aligned_recovery_grid-00089 | lost | 2.004082084 | 0.3359585 | 16 | 9 |
| 0 | 6 | scientific-close_aligned_recovery_grid-00097 | lost | 2.002061771 | 0.2245210 | 4 | 2 |
| 0 | 7 | scientific-close_aligned_recovery_grid-00119 | recovered | 2.004064292 | 0.3470835 | 13 | 7 |
| 0 | 8 | scientific-close_aligned_recovery_grid-00129 | lost | 2.000014271 | 0.5727295 | 1 | 1 |
| 0 | 9 | scientific-close_aligned_recovery_grid-00151 | lost | 2.002500063 | 0.3295625 | 6 | 4 |
| 0 | 10 | scientific-close_aligned_recovery_grid-00164 | lost | 2.002408709 | 0.2985415 | 5 | 3 |
| 1 | 1 | scientific-close_aligned_recovery_grid-00012 | lost | 2.009087354 | 0.4093540 | 20 | 10 |
| 1 | 2 | scientific-close_aligned_recovery_grid-00034 | lost | 2.004532771 | 0.4430205 | 18 | 9 |
| 1 | 3 | scientific-close_aligned_recovery_grid-00043 | lost | 2.004083751 | 0.3026665 | 17 | 8 |
| 1 | 4 | scientific-close_aligned_recovery_grid-00070 | lost | 2.003705500 | 0.3868750 | 11 | 6 |
| 1 | 5 | scientific-close_aligned_recovery_grid-00090 | lost | 2.003423438 | 0.3483125 | 9 | 4 |
| 1 | 6 | scientific-close_aligned_recovery_grid-00105 | lost | 2.004066667 | 0.3738335 | 14 | 7 |
| 1 | 7 | scientific-close_aligned_recovery_grid-00125 | recovered | 2.003587000 | 0.3378750 | 10 | 5 |
| 1 | 8 | scientific-close_aligned_recovery_grid-00127 | lost | 2.001675271 | 0.5501040 | 3 | 2 |
| 1 | 9 | scientific-close_aligned_recovery_grid-00147 | lost | 2.002773979 | 0.3617710 | 7 | 3 |
| 1 | 10 | scientific-close_aligned_recovery_grid-00166 | lost | 2.000978667 | 0.3290830 | 2 | 1 |

Recovered median 2.003587000 s; lost median 2.003705500 s. Recovery ranks 8, 10, 13 give rank sum 31 and U=25 (null mean 25.5). Exact pooled enumeration: one-sided P(U>=25)=615/1140=0.539473684211; two-sided absolute-distance p=1.

Within-close-stratum U values 9 (2 versus 8) and 4 (1 versus 9), sum 13 (null mean 12.5). Enumerating 45*10=450 conditional allocations gives one-sided p=225/450=0.5; two-sided p=1.

These results do not show the three recoveries had longer achieved intervals than the 17 losses. With only three recoveries, the analysis is descriptive. Direction was selected exploratorily; recovery labels were not assigned at random, and the conditional permutation assumptions are additional assumptions, not the original blocked binary randomization test.

### Mapping uncertainty sensitivity

Across 51 recovery/loss pairs, 20 have recovery definitely longer, 13 have loss definitely longer, and 18 overlap under estimate±reported half-RTT. Pooled U can range 20–38, with exploratory one-sided p range 0.107894736842–0.727192982456. Stratified U can range 11–18, p range 0.155555555556–0.653333333333.

The recorded half-RTT is not a calibrated full timing-error bound or confidence interval. Sensitivity endpoint choices are independent extremes, not additional observations. They do not change outcomes. Even these optimistic interval choices do not establish a positive timing association.

### Entire 180-trial grid extremes

Smallest achieved estimate with recovery: **2.003238771 s**, mapping uncertainty±0.3111040 ms; [2.0029276670, 2.0035498750] s; close 0 s, block 4, scientific-close_aligned_recovery_grid-00064.

Largest achieved estimate with loss: **2.009087354 s**, mapping uncertainty±0.4093540 ms; [2.0086780000, 2.0094967080] s; close 1 s, block 1, scientific-close_aligned_recovery_grid-00012.

The recovered minimum is shorter than the lost maximum even after the recorded uncertainty intervals. The grid does not identify a deterministic recoverability threshold or a safe waiting time.

## A4: strict immediate-close 0.50-s control

10/10 eligible recovered; all ten raw target ACK events report durability_requested=strict and **durability_observed=strict**. Each separate sentinel precondition also reports observed strict. The pinned page reads the target's actual JavaScript `IDBTransaction.durability` property at transaction creation and carries it into the ACK emitted after transaction completion; observed is not merely copied from requested. The matching frozen JS SHA-256 is `5b3f7de6e26246c9ccf97450e997973f4daa360ca6d6c265551f56cd6101c23e`.

| Block | Trial | Requested | Observed target | Observed sentinel | Endpoint | ACK-to-dispatch s | Raw ACK line |
|---:|---|---|---|---|---|---:|---:|
| 1 | scientific-six_key_conditions-00004 | strict | strict | strict | recovered | 0.504018208 | 26 |
| 2 | scientific-six_key_conditions-00007 | strict | strict | strict | recovered | 0.504065167 | 26 |
| 3 | scientific-six_key_conditions-00014 | strict | strict | strict | recovered | 0.509081250 | 26 |
| 4 | scientific-six_key_conditions-00022 | strict | strict | strict | recovered | 0.504090708 | 26 |
| 5 | scientific-six_key_conditions-00029 | strict | strict | strict | recovered | 0.504089875 | 26 |
| 6 | scientific-six_key_conditions-00033 | strict | strict | strict | recovered | 0.504074000 | 26 |
| 7 | scientific-six_key_conditions-00038 | strict | strict | strict | recovered | 0.509065292 | 26 |
| 8 | scientific-six_key_conditions-00047 | strict | strict | strict | recovered | 0.502861250 | 26 |
| 9 | scientific-six_key_conditions-00051 | strict | strict | strict | recovered | 0.502984375 | 26 |
| 10 | scientific-six_key_conditions-00060 | strict | strict | strict | recovered | 0.509103333 | 26 |

Observed ACK-to-dispatch min/median/max: 0.502861250/0.504081938/0.509103333 s. All close-delay assignments were 0 and deadlines exactly host ACK + 0.5 s.

This verifies the API-reported strict hint, separate from the requested field. It does not independently demonstrate each SQL sync/syscall or hardware persistence. The result remains one cell, n = 10, under this reset model.

Checks: frozen protocol hash and both family design hashes matched; 190 assignments matched their frozen records; 760 scoped source record hashes passed. JSON contains source paths, event line references, hashes, and all 180 grid observations for reproduction.

