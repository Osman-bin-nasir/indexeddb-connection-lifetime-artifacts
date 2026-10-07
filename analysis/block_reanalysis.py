#!/usr/bin/env python3
"""Read-only A1/A2 reproduction from a full repository or compact release.

This script submits no guest workload, starts no VM, and performs no recovery.
It recomputes submission timelines from raw traces. If private original-log.raw
files are missing, the saved log decoder is identified as the evidence source,
not represented as a fresh byte-level decode. Completed derived-reader receipts
can reproduce the dependent prefix table without adding scientific units.
"""
import argparse
import collections
import hashlib
import json
import struct
from pathlib import Path


MAPPED = 252 << 20
BACKING = (253 << 20) | 32
KEYS = ["immediate_close_late_deadline", "delayed_close_short_interval",
        "held_five_seconds", "held_fifteen_seconds"]
FLAGS = [("flush", 1), ("fua", 2), ("discard", 4), ("mark", 8), ("metadata", 16)]


def jr(path):
    return json.loads(path.read_text())


def sha(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def decode_raw(path):
    entries = []
    with path.open("rb") as f:
        magic, version, total, sector = struct.unpack("<QQQI", f.read(28))
        assert magic == 0x6a736677736872 and version == 1 and sector == 512
        f.seek(sector)
        for ordinal in range(total):
            offset = f.tell()
            header = f.read(sector)
            assert len(header) == sector
            location, count, flags, length = struct.unpack("<QQQQ", header[:32])
            assert length <= sector - 32
            private = header[32:32 + length]
            data_offset = f.tell()
            size = count * sector
            payload = f.read(size) if not flags & 4 else b""
            assert flags & 4 or len(payload) == size
            entries.append(dict(ordinal=ordinal, header_offset=offset,
                data_offset=data_offset, sector=location, sectors=count,
                bytes=size, flags=flags,
                flag_names=[name for name, bit in FLAGS if flags & bit],
                private_hex=private.hex(),
                mark=private.rstrip(b"\0").decode("ascii") if flags & 8 else None,
                data_sha256=hashlib.sha256(payload).hexdigest() if not flags & 4 else None))
    return entries


def trace_windows(directory, events):
    ack = next(x for x in events if x["kind"] == "GUEST_RECORD" and
               x["guest"].get("event", {}).get("kind") == "ACK")
    fault = next(x for x in events if x["kind"] == "FAULT_DISPATCH")
    schedule = next(x for x in events if x["kind"] == "SCHEDULED_FAULT")
    samples = schedule["clock_samples"]
    lo = max(s["host_send_ns"] - s["guest"]["guest_after_ns"] for s in samples)
    hi = min(s["host_receive_ns"] - s["guest"]["guest_before_ns"] for s in samples)
    assert lo <= hi
    windows = []
    for line in (directory / "block-trace.raw").read_text().splitlines():
        if not line.startswith("BLOCK "):
            continue
        _, ns, tid, layer, device, sector, count, rwbs = line.split()
        ns = int(ns)
        before = ns + hi < fault["fault"]["dispatch_ns"]
        after = ns + lo > fault["host_monotonic_ns"]
        windows.append(dict(guest_ns=ns, tid=int(tid), layer=layer,
            kernel_dev_t=int(device), sector=int(sector), sectors=int(count),
            rwbs=rwbs, host_earliest_ns=ns + lo, host_latest_ns=ns + hi,
            boundary_classification="before_boundary" if before else
                "after_quiesce_reply" if after else "within_boundary_uncertainty"))
    saved = jr(directory / "BLOCK_EVENT_WINDOWS.json")
    assert windows == saved["events"]
    assert [lo, hi] == saved["offset_bracket_ns"]
    return ack, fault, samples, lo, hi, windows


def immediate_row(root, directory, assignment, events, context):
    ack, fault, samples, lo, hi, windows = context
    close = next(x for x in events if x["kind"] == "GUEST_RECORD" and
                 x["guest"].get("event", {}).get("kind") == "CLOSE_RETURNED")
    page_ns = close["guest"]["event"]["page_ms"] * 1e6
    close_lo = page_ns + max(s["guest"]["guest_before_ns"] -
                             s["guest"]["page_ms"] * 1e6 for s in samples)
    close_hi = page_ns + min(s["guest"]["guest_after_ns"] -
                             s["guest"]["page_ms"] * 1e6 for s in samples)
    assert close_lo <= close_hi
    observed = []
    for event in windows:
        if event["kernel_dev_t"] not in [MAPPED, BACKING]:
            continue
        if "W" not in event["rwbs"] and "F" not in event["rwbs"]:
            continue
        if event["host_earliest_ns"] <= ack["receipt_ns"] or event[
                "boundary_classification"] != "before_boundary":
            continue
        e = dict(event)
        e["after_ack_ms_bounds"] = [(e["host_earliest_ns"] - ack["receipt_ns"]) / 1e6,
                                     (e["host_latest_ns"] - ack["receipt_ns"]) / 1e6]
        e["after_close_ms_bounds"] = [(e["guest_ns"] - close_hi) / 1e6,
                                       (e["guest_ns"] - close_lo) / 1e6]
        e["device"] = "mapped" if e["kernel_dev_t"] == MAPPED else "data_backing"
        observed.append(e)
    row = dict(trial_id=directory.name, path=str(directory.relative_to(root)),
        block=assignment["block"], mapper=assignment["mapper"],
        endpoint=jr(directory / "RESULT.json")["endpoint"], ack_host_ns=ack["receipt_ns"],
        close_page_ms=page_ns / 1e6,
        close_after_ack_host_ms_bounds=[(close_lo + lo - ack["receipt_ns"]) / 1e6,
                                        (close_hi + hi - ack["receipt_ns"]) / 1e6],
        clock_offset_width_ms=(hi - lo) / 1e6,
        page_to_guest_width_ms=(close_hi - close_lo) / 1e6,
        pause_after_ack_ms=(fault["fault"]["dispatch_ns"] - ack["receipt_ns"]) / 1e6,
        raw_trace_sha256=sha(directory / "block-trace.raw"), block_events=observed,
        completion_timestamps_available=False, target_sector_link_available=False)
    if assignment["mapper"] == "dm_flakey_drop_writes":
        transition = jr(directory / "FLAKEY_INTERVAL_START.json")
        t = transition["transition"]
        commands = [r for x in events if x["kind"] == "MAPPER_ACTION" and
                    x.get("phase") == "mapper-drop-after-ack" for r in x["records"]]
        resume = next(r["guest_ns"] for r in commands if r.get("argv", [])[:2] ==
                      ["dmsetup", "resume"])
        reload_return = next(r["guest_ns"] for r in commands if r.get("argv", [])[:2] ==
                             ["dmsetup", "reload"])
        for e in observed:
            e["after_transition_end_ms"] = (e["guest_ns"] - t["end_guest_ns"]) / 1e6
            e["after_resume_ms"] = (e["guest_ns"] - resume) / 1e6
        row.update(transition_host_return_after_ack_ms=(transition["host_bracket"][
            "host_receive_ns"] - ack["receipt_ns"]) / 1e6,
            transition_start_guest_ns=t["start_guest_ns"],
            transition_end_guest_ns=t["end_guest_ns"], resume_guest_ns=resume,
            activation_after_ack_ms_bounds=[(reload_return + lo - ack["receipt_ns"]) / 1e6,
                                            (resume + hi - ack["receipt_ns"]) / 1e6],
            transition_end_after_ack_ms_bounds=[(t["end_guest_ns"] + lo - ack["receipt_ns"]) / 1e6,
                                                (t["end_guest_ns"] + hi - ack["receipt_ns"]) / 1e6],
            resume_after_ack_ms_bounds=[(resume + lo - ack["receipt_ns"]) / 1e6,
                                        (resume + hi - ack["receipt_ns"]) / 1e6],
            transition_end_after_close_ms_bounds=[(t["end_guest_ns"] - close_hi) / 1e6,
                                                  (t["end_guest_ns"] - close_lo) / 1e6],
            pause_after_transition_end_ms_bounds=[(fault["fault"]["dispatch_ns"] -
                t["end_guest_ns"] - hi) / 1e6, (fault["fault"]["dispatch_ns"] -
                t["end_guest_ns"] - lo) / 1e6])
    return row


def log_row(root, directory, assignment, events, context, verify_hash):
    _, fault, _, _, _, windows = context
    saved = jr(directory / "log-prefixes/LOG_DECODE.json")
    raw_path = directory / "log-prefixes/original-log.raw"
    entries = decode_raw(raw_path) if raw_path.exists() else saved["entries"]
    if raw_path.exists():
        assert entries == saved["entries"]
    last_flush = [e for e in entries if e["flags"] & 1][-1]
    last_any = [e for e in entries if e["flags"] & 3][-1]
    prefixes = jr(directory / "REGISTERED_LOG_PREFIXES.json")
    final = prefixes["prefixes"][-1]
    assert final["last_entry"] == len(entries) - 1
    verified_hash = False
    if verify_hash and raw_path.exists():
        assert sha(raw_path) == prefixes["raw_log_sha256"]
        verified_hash = True
    # A FLUSH record's flags include the associated data BIO flags, while its
    # payload is empty. Locate the corresponding mapped BIO by sector and flags.
    matching = [e for e in windows if e["layer"] == "bio" and
                e["kernel_dev_t"] == MAPPED and e["sector"] == last_flush["sector"] and
                e["rwbs"].startswith("F")]
    assert matching
    issue = matching[-1]
    capture = next(e for e in events if e["kind"] == "IMMUTABLE_MULTI_DISK_CAPTURE")
    before = fault["host_monotonic_ns"] < capture["host_monotonic_ns"]
    views = capture["capture"]["views"]
    immutable = all(v["source_node_read_only"] for v in views.values())
    assert before and immutable
    stages = {p["name"]: p["endpoint"] for p in prefixes["prefixes"]}
    return dict(trial_id=directory.name, path=str(directory.relative_to(root)),
        block=assignment["block"], key=assignment["key"], entries=len(entries),
        last_flush=last_flush, last_flush_or_fua=last_any,
        tail_after_last_flush=entries[last_flush["ordinal"] + 1:],
        last_recorded_endpoint=final["endpoint"], registered_prefix_endpoints=stages,
        same_last_flush_or_fua_prefix_as_saved=last_any["ordinal"] == final["last_entry"],
        same_last_flush_only_prefix_as_saved=last_flush["ordinal"] == final["last_entry"],
        saved_prefix_replay_sha256=final["replayed_raw_sha256"],
        raw_log_sha256=prefixes["raw_log_sha256"],
        independent_decode_matches=True if raw_path.exists() else None,
        decode_evidence_source="independent_raw_bytes" if raw_path.exists() else "retained_LOG_DECODE_JSON_only",
        full_raw_log_sha256_independently_verified=verified_hash,
        raw_log_present=raw_path.exists(),
        flag_counts=dict(collections.Counter(e["flags"] for e in entries)),
        last_flush_matching_bio_issue=issue,
        last_flush_issue_definitely_before_host_dispatch=issue["boundary_classification"] == "before_boundary",
        last_flush_completion_wall_timestamp_available=False,
        prefix_capture_source_is_old_immutable_log_view=immutable,
        dispatch_host_ns=fault["fault"]["dispatch_ns"],
        quiesce_reply_host_ns=fault["host_monotonic_ns"])


def span(events, field):
    return [min(e[field][0] for e in events) / 1000,
            max(e[field][1] for e in events) / 1000] if events else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    roots = parser.add_mutually_exclusive_group(required=True)
    roots.add_argument("--root", type=Path, help="Full repository root; source remains read-only")
    roots.add_argument("--release-root", type=Path, help="Compact evidence release root")
    parser.add_argument("--output", type=Path, required=True, help="JSON output path; writes only here")
    parser.add_argument("--last-flush-results", type=Path,
                        help="Completed A2 derived-reader results, not a request to perform new recovery")
    parser.add_argument("--reader-evidence", type=Path,
                        help="Compact completed A2 reader evidence folder; checks saved oracle contents without running it")
    parser.add_argument("--verify-full-log-hashes", action="store_true",
                        help="Also hash each available full private original-log.raw")
    args = parser.parse_args()
    root = (args.root or args.release_root).resolve()
    attempts = sorted((root / "campaign_v2/scientific/attempts").glob("scientific-block_state_recovery-*"))
    assert len(attempts) == 120, f"Expected 120 original block-state attempts, found {len(attempts)}"
    rows, logs = [], []
    for directory in attempts:
        assignment = jr(directory / "assignment.json")
        events = [json.loads(s) for s in (directory / "events.jsonl").read_text().splitlines()]
        context = trace_windows(directory, events)
        if assignment["key"] == "immediate_close_late_deadline":
            rows.append(immediate_row(root, directory, assignment, events, context))
        if assignment["mapper"] == "dm_log_writes":
            logs.append(log_row(root, directory, assignment, events, context, args.verify_full_log_hashes))
    assert len(rows) == 30 and len(logs) == 40
    s5 = []
    for row in sorted(rows, key=lambda r: (r["block"], r["mapper"])):
        bio = [e for e in row["block_events"] if e["layer"] == "bio" and e["device"] == "mapped"]
        writes = [e for e in bio if "W" in e["rwbs"] and e["sectors"] > 0]
        flush = [e for e in bio if "F" in e["rwbs"]]
        s5.append(dict(trial_id=row["trial_id"], block=row["block"], mapper=row["mapper"],
            endpoint=row["endpoint"], W=len(writes), F=len(flush),
            W_after_ack_s=span(writes, "after_ack_ms_bounds"),
            W_after_close_s=span(writes, "after_close_ms_bounds"),
            F_after_close_s=span(flush, "after_close_ms_bounds"),
            table_verification_after_ack_ms=row.get("transition_end_after_ack_ms_bounds")))
    s6, warnings = [], []
    readers = jr(args.last_flush_results) if args.last_flush_results else None
    reader_by_id = {}
    oracle_contents_checked = 0
    if readers is not None:
        assert readers["completed"] == 40 and readers["reader_unknowns"] == 0
        assert readers["scientific_trial_count_added"] == 0
        reader_by_id = {r["trial_id"]: r for r in readers["dependent_results"]}
        assert len(reader_by_id) == 40 and set(reader_by_id) == {r["trial_id"] for r in logs}
        for row in logs:
            receipt = reader_by_id[row["trial_id"]]
            assert receipt["prefix_last_entry"] == row["last_flush"]["ordinal"]
            assert receipt["verified_raw_log_sha256"] == row["raw_log_sha256"]
            assert receipt["scientific_trial_count"] == 0 and receipt["dependent_observation"]
            actual_tail = bool(row["tail_after_last_flush"])
            if "excludes_later_completed_FUA" in receipt and receipt[
                    "excludes_later_completed_FUA"] != actual_tail:
                warnings.append(dict(trial_id=row["trial_id"],
                    preserved_receipt_field="excludes_later_completed_FUA",
                    retained_value=receipt["excludes_later_completed_FUA"],
                    decoded_tail_exists=actual_tail,
                    disposition="Generic reader-receipt wording; actual log ends at literal FLUSH. Original receipt preserved."))
            if args.reader_evidence:
                matching = list(args.reader_evidence.glob("*/" + row["trial_id"] + "/ORACLE.json"))
                assert len(matching) == 1, f"Expected one saved derived oracle: {row['trial_id']}"
                oracle = jr(matching[0])["guest"]
                spec = jr(root / row["path"] / "payload_contract.json")
                assert oracle["sentinel_valid"] is True
                assert oracle["endpoint"] == receipt["endpoint"]
                assert spec["sentinel"] in oracle["all"]
                if oracle["endpoint"] == "recovered":
                    assert oracle["direct"] == spec["targets"] and oracle["indexed"] == spec["targets"]
                    assert len(oracle["all"]) == 2
                else:
                    assert oracle["direct"] == [None] and oracle["indexed"] == []
                    assert oracle["all"] == [spec["sentinel"]]
                oracle_contents_checked += 1
    for key in KEYS:
        group = [r for r in logs if r["key"] == key]
        assert len(group) == 10
        stages = {s: sum(r["registered_prefix_endpoints"][s] == "recovered" for r in group)
                  for s in ["immediately_before_ack_marker", "at_ack_marker", "last_fully_recorded_before_boundary"]}
        literal = collections.Counter(reader_by_id[r["trial_id"]]["endpoint"] for r in group) if readers else None
        if readers:
            saved_cell = next(c for c in readers["per_cell"] if c["key"] == key)
            assert literal["recovered"] == saved_cell["recovered"] and literal["lost"] == saved_cell["lost"]
        s6.append(dict(key=key, original_trials=10, before_ACK_recovered=stages[
            "immediately_before_ack_marker"], at_ACK_recovered=stages["at_ack_marker"],
            final_FLUSH_or_FUA_recovered=stages["last_fully_recorded_before_boundary"],
            literal_last_FLUSH_recovered=literal["recovered"] if readers else None,
            literal_last_FLUSH_lost=literal["lost"] if readers else None,
            derived_reader_unknowns=literal["unknown"] if readers else None))
    missing = [r["path"] + "/log-prefixes/original-log.raw" for r in logs if not r["raw_log_present"]]
    result = dict(schema="idbv2-block-reanalysis-read-only-v1", source_root=str(root),
        original_block_state_assignments=120, new_scientific_units=0,
        immediate_rows=rows, log_rows=logs, supplementary_table_S5=s5,
        supplementary_table_S6=s6, preserved_receipt_semantic_warnings=warnings,
        A2_reader_receipts_checked=40 if readers else 0,
        A2_saved_oracle_contents_independently_checked=oracle_contents_checked,
        A2_oracles_independently_rerun=False,
        A2_completed_reader_evidence="retained_completed_reader_receipts" if readers else "not_provided",
        independent_raw_log_decode_count=sum(r["raw_log_present"] for r in logs),
        independent_full_log_hash_count=sum(r["full_raw_log_sha256_independently_verified"] for r in logs),
        missing_private_raw_log_paths=missing,
        fresh_raw_log_decode_status="blocked_missing_private_raw_log_bytes" if missing else "completed",
        fresh_prefix_replay_status="blocked_missing_private_raw_log_bytes" if missing else "not_performed_by_this_analysis_script",
        fresh_prefix_replay_dependencies=["Exact-hash original-log.raw for each selected trial",
            "Pinned guest base and its complete backing chain, packaged Chromium and existing-database reader",
            "Fresh writable derivatives, required forensic/replay tools and original oracle identities"],
        limitation="Queue/issue timings are not completion times; target-bearing sector attribution is unavailable. Last recorded completed FLUSH is defined by paused capture, not exact host-dispatch time. Compact release permits receipt/table reproduction, not a fresh private log decode or VM oracle replay.")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(dict(A1_matched_rows=len(rows), A2_original_trials=len(logs),
        A2_reader_receipts_checked=result["A2_reader_receipts_checked"],
        A2_saved_oracle_contents_checked=oracle_contents_checked,
        private_raw_logs_present=40 - len(missing),
        independent_raw_log_decode_count=result["independent_raw_log_decode_count"],
        fresh_replay=result["fresh_prefix_replay_status"], new_scientific_units=0,
        receipt_semantic_warnings=len(warnings), output=str(args.output))))


if __name__ == "__main__":
    main()
