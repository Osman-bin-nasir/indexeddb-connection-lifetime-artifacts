#!/usr/bin/env python3
"""Read-only A3/A4 reanalysis of existing frozen v2 records (stdlib only).

Exploratory rank tests condition on the numbers recovered. They are not
randomization tests of experimentally assigned recovery outcomes, and do not
change the frozen primary or secondary families. Outputs are separate from raw.
"""
import argparse
import hashlib
import itertools
import json
import math
import statistics
from collections import Counter
from pathlib import Path


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def read(p):
    return json.loads(p.read_text())


def ratio(num, den):
    return {"numerator": num, "denominator": den, "p": num / den}


def rank_distribution(n, k):
    # No ties in achieved point estimates. Rank sum minus k(k+1)/2 is U.
    return [sum(c) - k * (k + 1) // 2 for c in itertools.combinations(range(1, n + 1), k)]


def exact_p(dist, observed):
    mean = sum(dist) / len(dist)
    return {
        "U": observed,
        "null_mean_U": mean,
        "one_sided_recovered_longer": ratio(sum(v >= observed for v in dist), len(dist)),
        "two_sided_absolute_distance_from_null_mean": ratio(
            sum(abs(v - mean) >= abs(observed - mean) for v in dist), len(dist)
        ),
    }


def u_value(rows):
    r = [x for x in rows if x["endpoint"] == "recovered"]
    l = [x for x in rows if x["endpoint"] == "lost"]
    return sum(a["gap_ns"] > b["gap_ns"] for a in r for b in l)


def uncertainty_u_bounds(rows):
    rs = [r for r in rows if r["endpoint"] == "recovered"]
    ls = [r for r in rows if r["endpoint"] == "lost"]
    wins = losses = overlaps = 0
    for r in rs:
        for l in ls:
            if r["interval_lower_twice_ns"] > l["interval_upper_twice_ns"]:
                wins += 1
            elif r["interval_upper_twice_ns"] < l["interval_lower_twice_ns"]:
                losses += 1
            else:
                overlaps += 1
    # Independent interval endpoints attain both bounds simultaneously:
    # all recovery intervals low/all loss intervals high, or the reverse.
    return {"U_min": wins, "U_max": wins + overlaps, "definitely_recovery_longer": wins,
            "definitely_loss_longer": losses, "overlapping_pairs": overlaps,
            "cross_outcome_pairs": len(rs) * len(ls)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    ap.add_argument("--out", type=Path, default=Path(__file__).resolve().parents[1] / "derived" / "a3_a4")
    args = ap.parse_args()
    root, out = args.root, args.out
    out.mkdir(parents=True, exist_ok=True)
    manifest = read(root / "confirmatory/design/MANIFEST.json")
    family_designs = {}
    design_hashes = {}
    for family in ["close_aligned_recovery_grid", "six_key_conditions"]:
        entry = next(x for x in manifest["experiments"] if x["name"] == family)
        path = root / "confirmatory" / entry["path"]
        assert sha(path) == entry["sha256"]
        design_hashes[str(path.relative_to(root))] = sha(path)
        family_designs[family] = {a["trial_id"]: a for a in read(path)["assignments"]}
    protocol = root / "confirmatory/PREREGISTRATION.md"
    protocol_hash = sha(protocol)
    assert protocol_hash == "a3dfb023a7fb9e4862edc4242a7cbac1b3b8865790dbcbb1156fddfd128b13b1"
    hash_checks = []
    grid = []
    strict = []
    for family, frozen in family_designs.items():
        for trial_id, a_frozen in frozen.items():
            d = root / "campaign_v2/scientific/attempts" / trial_id
            a = read(d / "assignment.json")
            assert a == a_frozen
            if family == "six_key_conditions" and a["key"] != "strict_short_deadline":
                continue
            r = read(d / "RESULT.json")
            assert r["technical_eligible"] and r["endpoint"] in ["recovered", "lost"]
            oracle = read(d / "ORACLE.json")["guest"]
            assert oracle["endpoint"] == r["endpoint"] and oracle["sentinel_valid"]
            hashes = read(d / "SHA256.json")
            for fn in ["assignment.json", "RESULT.json", "events.jsonl", "ORACLE.json"]:
                assert sha(d / fn) == hashes[fn]
                hash_checks.append({"file": str((d / fn).relative_to(root)), "sha256": hashes[fn]})
            ev = [(i + 1, json.loads(v)) for i, v in enumerate((d / "events.jsonl").read_text().splitlines())]
            def event(kind):
                return next((i, e) for i, e in ev if e["kind"] == kind)
            def page(kind):
                return next((i, e) for i, e in ev if e.get("guest", {}).get("kind") == "PAGE_EVENT" and e["guest"]["event"]["kind"] == kind)
            ai, ack = page("ACK")
            ci, close = page("CLOSE_RETURNED")
            si, sched = event("SCHEDULED_FAULT")
            fi, fault = event("FAULT_DISPATCH")
            entry = {"trial_id": trial_id, "ordinal": a["ordinal"], "block": a["block"],
                     "condition_id": a["condition_id"], "assigned_close_ms": a["close_ms"],
                     "endpoint": r["endpoint"], "technical_eligible": r["technical_eligible"],
                     "record_directory": str(d.relative_to(root)),
                     "event_lines": {"ack": ai, "close_returned": ci, "scheduled_fault": si, "fault_dispatch": fi},
                     "ack_receipt_ns": ack["receipt_ns"], "dispatch_ns": fault["fault"]["dispatch_ns"],
                     "achieved_ack_to_dispatch_s": (fault["fault"]["dispatch_ns"] - ack["receipt_ns"]) / 1e9,
                     "observed_close_delay_page_s": (close["guest"]["event"]["page_ms"] - ack["guest"]["event"]["ack_ms"]) / 1000,
                     "durability_requested": ack["guest"]["event"]["durability_requested"],
                     "durability_observed": ack["guest"]["event"]["durability_observed"]}
            assert entry["durability_requested"] == entry["durability_observed"] == a["durability"]
            assert close["guest"]["event"]["assigned_close_ms"] == a["close_ms"]
            if family == "close_aligned_recovery_grid":
                m = sched["mapping"]
                samples = sched["clock_samples"]
                assert len(samples) == 9
                chosen = min(samples, key=lambda s: s["host_receive_ns"] - s["host_send_ns"])
                estimated = (chosen["host_send_ns"] + chosen["host_receive_ns"]) // 2 + round((close["guest"]["event"]["page_ms"] - chosen["guest"]["page_ms"]) * 1e6)
                assert estimated == m["estimate_ns"]
                assert m["uncertainty_ns"] == (chosen["host_receive_ns"] - chosen["host_send_ns"]) / 2
                assert m["selected_sample"] == chosen
                assert sched["deadline_ns"] == estimated + a["fault_after_close_ms"] * 1000000
                g = fault["fault"]["dispatch_ns"] - estimated
                u2 = chosen["host_receive_ns"] - chosen["host_send_ns"]
                entry.update(assigned_gap_s=a["fault_after_close_ms"] / 1000, gap_ns=g,
                             achieved_estimated_gap_s=g / 1e9, mapped_close_ns=estimated,
                             clock_mapping_uncertainty_ns=m["uncertainty_ns"], clock_mapping_uncertainty_ms=m["uncertainty_ns"] / 1e6,
                             interval_lower_twice_ns=2 * g - u2, interval_upper_twice_ns=2 * g + u2,
                             interval_lower_s=(2 * g - u2) / 2e9, interval_upper_s=(2 * g + u2) / 2e9)
                grid.append(entry)
            else:
                pi, pre = page("SENTINEL_INDEPENDENT_READBACK")
                assert pre["guest"]["event"]["durability_observed"] == "strict"
                assert pre["guest"]["event"]["readback"]["sentinel_valid"]
                assert pre["guest"]["event"]["readback"]["endpoint"] == "lost"
                assert a["fault_after_ack_ms"] == 500 and a["close_ms"] == 0
                assert sched["deadline_ns"] == ack["receipt_ns"] + 500000000
                assert r["endpoint"] == "recovered"
                entry["sentinel_event_line"] = pi
                entry["sentinel_durability_observed"] = "strict"
                strict.append(entry)
    assert len(grid) == 180 and len(strict) == 10
    selected = sorted([r for r in grid if r["assigned_gap_s"] == 2], key=lambda x: (x["assigned_close_ms"], x["block"]))
    assert len(selected) == 20
    assert Counter(r["endpoint"] for r in selected) == {"recovered": 3, "lost": 17}
    for rank, r in enumerate(sorted(selected, key=lambda x: x["gap_ns"]), 1):
        r["pooled_rank"] = rank
    distributions = {}
    pooled_dist = rank_distribution(20, 3)
    distributions["pooled"] = exact_p(pooled_dist, u_value(selected))
    strata = []
    stratum_dists = []
    for close_ms in [0, 1000]:
        sr = [r for r in selected if r["assigned_close_ms"] == close_ms]
        k = sum(r["endpoint"] == "recovered" for r in sr)
        dist = rank_distribution(10, k)
        for rank, r in enumerate(sorted(sr, key=lambda x: x["gap_ns"]), 1):
            r["within_stratum_rank"] = rank
        strata.append({"close_ms": close_ms, "recovered": k, "lost": 10-k, **exact_p(dist, u_value(sr)), "uncertainty": uncertainty_u_bounds(sr)})
        stratum_dists.append(dist)
    strat_dist = [a + b for a, b in itertools.product(*stratum_dists)]
    distributions["stratified"] = {"statistic": "sum of within-close-stratum Mann-Whitney U", "strata": strata,
                                     **exact_p(strat_dist, sum(s["U"] for s in strata))}
    pu = uncertainty_u_bounds(selected)
    su = {"U_min": sum(s["uncertainty"]["U_min"] for s in strata), "U_max": sum(s["uncertainty"]["U_max"] for s in strata)}
    for u, dist in [(pu, pooled_dist), (su, strat_dist)]:
        u["minimum_one_sided_p_over_reported_intervals"] = exact_p(dist, u["U_max"])["one_sided_recovered_longer"]
        u["maximum_one_sided_p_over_reported_intervals"] = exact_p(dist, u["U_min"])["one_sided_recovered_longer"]
    recovered = [r for r in grid if r["endpoint"] == "recovered"]
    lost = [r for r in grid if r["endpoint"] == "lost"]
    minimum_recovery = min(recovered, key=lambda x: x["gap_ns"])
    maximum_loss = max(lost, key=lambda x: x["gap_ns"])
    medians = {e: statistics.median(r["achieved_estimated_gap_s"] for r in selected if r["endpoint"] == e) for e in ["recovered", "lost"]}
    js = root / "campaign_v2/transaction.js"
    js_sha = sha(js)
    assert js_sha == "5b3f7de6e26246c9ccf97450e997973f4daa360ca6d6c265551f56cd6101c23e"
    js_source = js.read_text()
    assert "const observedDurability = tx.durability;" in js_source
    assert "durability_observed: observedDurability" in js_source
    strict_times = [r["achieved_ack_to_dispatch_s"] for r in strict]
    result = {
        "scope": "A3/A4 read-only exploratory reanalysis; no new trials or altered records",
        "root": ".", "protocol_sha256": protocol_hash, "design_file_hashes": design_hashes,
        "hash_checks_passed": len(hash_checks), "hash_checks": hash_checks,
        "registered_primary_families_unchanged": True,
        "grid_counts": dict(Counter(r["endpoint"] for r in grid)), "all_grid_records": grid,
        "two_second_records": selected,
        "exploratory_rank_tests": distributions,
        "rank_test_assumptions": "Conditional label exchangeability within the pooled sample or close strata; outcome was not randomized. One-sided longer-recovery direction chosen after inspecting existing records. These descriptive tests are outside the frozen confirmatory families. Stratification respects close time but does not make recovery labels randomized or fully account for cross-stratum within-block dependence.",
        "two_second_outcome_medians_s": medians,
        "uncertainty_sensitivity": {"pooled": pu, "stratified": su,
            "interpretation": "Treat each recorded mapping half-RTT as an interval around its estimate, solely for sensitivity. It is not a calibrated confidence interval, complete error bound or physical-fault-time uncertainty. Endpoint choices are independent extreme sensitivity settings."},
        "grid_extremes": {"smallest_point_estimated_recovery": minimum_recovery, "largest_point_estimated_loss": maximum_loss,
            "recovery_shorter_than_loss_robust_to_reported_mapping_intervals": minimum_recovery["interval_upper_twice_ns"] < maximum_loss["interval_lower_twice_ns"]},
        "strict": {"n": 10, "recovered": 10, "observed_strict_target_ACKs": 10, "observed_strict_sentinels": 10,
            "observed_target_durability_property_source": "const observedDurability = tx.durability; at target transaction creation; value retained until ACK after oncomplete",
            "source_path": str(js.relative_to(root)), "source_sha256": js_sha,
            "ack_to_dispatch_s": {"min": min(strict_times), "median": statistics.median(strict_times), "max": max(strict_times)},
            "records": sorted(strict, key=lambda r: r["block"]),
            "limit": "Transaction.durability property observation verifies API-reported hint; it is not direct verification of every syscall, SQLite synchronous setting or hardware persistence, nor a general 0.5-s guarantee."}
    }
    (out / "A3_A4_RESULTS.json").write_text(json.dumps(result, indent=2) + "\n")
    lines = ["# A3/A4: existing-data reanalysis", "", "No new trials. All raw campaign files read-only. The exploratory tests do not modify any hash-frozen primary/secondary family.", "", "## A3: assigned 2.0-s cells", "", "All 20 endpoints are technically eligible: immediate close 2/10 recovered; 1-s delayed close 1/10 recovered. Times are mapped observed-close-to-host-dispatch estimates, not reset-event times.", "", "| Close s | Block | Trial | Outcome | Achieved estimate s | Mapping half-RTT ms | Pooled rank | Within-stratum rank |", "|---:|---:|---|---|---:|---:|---:|---:|"]
    for r in selected:
        lines.append(f"| {r['assigned_close_ms']/1000:g} | {r['block']} | {r['trial_id']} | {r['endpoint']} | {r['achieved_estimated_gap_s']:.9f} | {r['clock_mapping_uncertainty_ms']:.7f} | {r['pooled_rank']} | {r['within_stratum_rank']} |")
    p, s = distributions["pooled"], distributions["stratified"]
    lines += ["", f"Recovered median {medians['recovered']:.9f} s; lost median {medians['lost']:.9f} s. Recovery ranks 8, 10, 13 give rank sum 31 and U=25 (null mean 25.5). Exact pooled enumeration: one-sided P(U>=25)={p['one_sided_recovered_longer']['numerator']}/{p['one_sided_recovered_longer']['denominator']}={p['one_sided_recovered_longer']['p']:.12g}; two-sided absolute-distance p={p['two_sided_absolute_distance_from_null_mean']['p']:.12g}.", "", f"Within-close-stratum U values 9 (2 versus 8) and 4 (1 versus 9), sum 13 (null mean 12.5). Enumerating 45*10=450 conditional allocations gives one-sided p={s['one_sided_recovered_longer']['numerator']}/450={s['one_sided_recovered_longer']['p']:.12g}; two-sided p={s['two_sided_absolute_distance_from_null_mean']['p']:.12g}.", "", "These results do not show the three recoveries had longer achieved intervals than the 17 losses. With only three recoveries, the analysis is descriptive. Direction was selected exploratorily; recovery labels were not assigned at random, and the conditional permutation assumptions are additional assumptions, not the original blocked binary randomization test.", "", "### Mapping uncertainty sensitivity", "", f"Across 51 recovery/loss pairs, {pu['definitely_recovery_longer']} have recovery definitely longer, {pu['definitely_loss_longer']} have loss definitely longer, and {pu['overlapping_pairs']} overlap under estimate±reported half-RTT. Pooled U can range {pu['U_min']}–{pu['U_max']}, with exploratory one-sided p range {pu['minimum_one_sided_p_over_reported_intervals']['p']:.12g}–{pu['maximum_one_sided_p_over_reported_intervals']['p']:.12g}. Stratified U can range {su['U_min']}–{su['U_max']}, p range {su['minimum_one_sided_p_over_reported_intervals']['p']:.12g}–{su['maximum_one_sided_p_over_reported_intervals']['p']:.12g}.", "", "The recorded half-RTT is not a calibrated full timing-error bound or confidence interval. Sensitivity endpoint choices are independent extremes, not additional observations. They do not change outcomes. Even these optimistic interval choices do not establish a positive timing association.", "", "### Entire 180-trial grid extremes", ""]
    for label, r in [("Smallest achieved estimate with recovery", minimum_recovery), ("Largest achieved estimate with loss", maximum_loss)]:
        lines.append(f"{label}: **{r['achieved_estimated_gap_s']:.9f} s**, mapping uncertainty±{r['clock_mapping_uncertainty_ms']:.7f} ms; [{r['interval_lower_s']:.10f}, {r['interval_upper_s']:.10f}] s; close {r['assigned_close_ms']/1000:g} s, block {r['block']}, {r['trial_id']}.")
        lines.append("")
    lines += ["The recovered minimum is shorter than the lost maximum even after the recorded uncertainty intervals. The grid does not identify a deterministic recoverability threshold or a safe waiting time.", "", "## A4: strict immediate-close 0.50-s control", "", "10/10 eligible recovered; all ten raw target ACK events report durability_requested=strict and **durability_observed=strict**. Each separate sentinel precondition also reports observed strict. The pinned page reads the target's actual JavaScript `IDBTransaction.durability` property at transaction creation and carries it into the ACK emitted after transaction completion; observed is not merely copied from requested. The matching frozen JS SHA-256 is `5b3f7de6e26246c9ccf97450e997973f4daa360ca6d6c265551f56cd6101c23e`.", "", "| Block | Trial | Requested | Observed target | Observed sentinel | Endpoint | ACK-to-dispatch s | Raw ACK line |", "|---:|---|---|---|---|---|---:|---:|"]
    for r in result["strict"]["records"]:
        lines.append(f"| {r['block']} | {r['trial_id']} | {r['durability_requested']} | {r['durability_observed']} | strict | {r['endpoint']} | {r['achieved_ack_to_dispatch_s']:.9f} | {r['event_lines']['ack']} |")
    lines += ["", f"Observed ACK-to-dispatch min/median/max: {min(strict_times):.9f}/{statistics.median(strict_times):.9f}/{max(strict_times):.9f} s. All close-delay assignments were 0 and deadlines exactly host ACK + 0.5 s.", "", "This verifies the API-reported strict hint, separate from the requested field. It does not independently demonstrate each SQL sync/syscall or hardware persistence. The result remains one cell, n = 10, under this reset model.", "", f"Checks: frozen protocol hash and both family design hashes matched; 190 assignments matched their frozen records; {len(hash_checks)} scoped source record hashes passed. JSON contains source paths, event line references, hashes, and all 180 grid observations for reproduction.", ""]
    text = "\n".join(lines)
    (out / "A3_A4_FINDINGS.md").write_text(text + "\n")
    print(json.dumps({"grid": result["grid_counts"], "pooled": p, "stratified": s,
                      "uncertainty": result["uncertainty_sensitivity"], "extremes": result["grid_extremes"],
                      "strict_counts": [10, 10, 10], "hash_checks": len(hash_checks)}, indent=2))


if __name__ == "__main__":
    main()
