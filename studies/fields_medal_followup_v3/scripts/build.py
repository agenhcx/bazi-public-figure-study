#!/usr/bin/env python3
"""Integrate already observed follow-up bodies offline; v1 remains immutable."""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_V1 = ROOT.parent / "fields_medal_collection_v1"


def load_validator(v1_dir):
    path = Path(v1_dir) / "scripts" / "aggregate.py"
    spec = importlib.util.spec_from_file_location("fields_v1_aggregate", path)
    module = importlib.util.module_from_spec(spec)
    # Compile in memory so importing the immutable v1 creates no bytecode file.
    exec(compile(path.read_bytes(), str(path), "exec"), module.__dict__)
    return module


VALIDATOR = load_validator(DEFAULT_V1)


def apply_patches(roster_payload, input_payloads, patch_payload, log_payload, validator=None):
    """Return patched copies and a separate round audit; never mutate v1 inputs."""
    v = validator or VALIDATOR
    roster = roster_payload.get("rows") if isinstance(roster_payload, dict) else roster_payload
    v.require(isinstance(roster, list), "Roster rows required")
    rows = patch_payload if isinstance(patch_payload, list) else patch_payload.get("records")
    v.require(isinstance(rows, list), "Patch records required")
    v.require(isinstance(log_payload, dict) and isinstance(log_payload.get("body_requests"), list), "Body audit log required")
    body_log = {}
    for event in log_payload["body_requests"]:
        v.require(event["name"] not in body_log, "Duplicate body log identity")
        body_log[event["name"]] = event
    by_name = {}
    for row in roster:
        v.require(row["name"] not in by_name, "Ambiguous fixed roster name")
        by_name[row["name"]] = row
    patched = copy.deepcopy(input_payloads)
    targets = {}
    for payload in patched:
        for record in payload["records"]:
            v.require(record["fields_id"] not in targets, "Duplicate base record ID")
            targets[record["fields_id"]] = record
    seen = set()
    audit = {"schema_version": 1, "round": "fields_medal_followup_v3", "at_utc": None,
             "retrieval_performed_by_builder": False, "actor": "worker",
             "budget_scope_note": "Per-person counters come from the saved worker log: reused-query discovery has 0 new queries; other people have 1 new query; every person has 1 body candidate. Exact request times are null. Original v1 counters remain unchanged and this round is separate.",
             "patches": []}
    for patch in rows:
        v.require(isinstance(patch, dict), "Patch must be an object")
        name = patch.get("name")
        v.require(name in by_name, "Patch name does not match fixed roster")
        row = by_name[name]
        fid = row["fields_id"]
        v.require("fields_id" not in patch or patch["fields_id"] == fid, "Patch ID/name mismatch")
        v.require("award_year" not in patch or patch["award_year"] == row["award_year"], "Patch award year mismatch")
        v.require(fid not in seen, "Duplicate patch identity")
        seen.add(fid)
        v.require(fid in targets, "Patch target missing from base input")
        record = targets[fid]
        v.require(record["name"] == name and record["award_year"] == row["award_year"], "Base identity differs from fixed roster")
        v.require(row.get("original_through_2025") is True, "This follow-up patches the main roster only")
        v.require(patch.get("source_status") == "body_observed", "Follow-up requires previously observed body evidence")
        event = body_log.get(name)
        v.require(event is not None and event.get("url") == patch.get("source_url") and event.get("status") == "body_observed", "Patch requires same-person same-URL body audit")
        queries = event.get("current_round_search_queries_used")
        bodies = event.get("current_round_body_opens")
        v.require(type(queries) is int and 0 <= queries <= 1 and type(bodies) is int and bodies == 1, "Invalid worker follow-up budget")
        if "date" in patch:
            date = patch["date"]
            v.require(isinstance(date, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", date), "Patch date requires explicit three components")
            year, month, day = map(int, date.split("-"))
            precision = "day"
        else:
            year, month, day = (patch.get(k) for k in ("year", "month", "day"))
            precision = patch.get("precision")
            v.require(precision == "month" and "day" in patch and day is None, "Partial follow-up requires explicit month precision and null day")
        source = {"url": patch.get("source_url"), "status": "body_observed",
                  "access_method": "previously observed worker body; offline patch integration",
                  "note": "Supplied in v3 day/partial patch inputs and saved worker audit. No network retrieval by this builder; retrieval timestamp unknown."}
        v.safe_url(source["url"])
        claim = {"date_raw": patch.get("date_raw", patch.get("excerpt")),
                 "year": year, "month": month, "day": day, "precision": precision,
                 "calendar": patch.get("calendar"), "source_url": source["url"],
                 "source_type": patch.get("source_type"), "source_status": "body_observed",
                 "excerpt": patch.get("excerpt"),
                 "identity_note": patch.get("identity_note", f"Previously collected HLF laureate body supplied by worker for {name}; exact name mapped to fixed roster ID {fid} during offline integration.")}
        v.validate_claim(claim, [source])
        old_status, _ = v.derive(record)
        budgets = {key: record[key] for key in ("search_queries_used", "body_candidates_opened", "direct_cv_attempts")}
        record["claims"].append(claim)
        record["sources"].append(source)
        record["status"], _ = v.derive(record)
        record["review_note"] = record.get("review_note", "") + " Follow-up v3 adds the supplied HLF body claim; original partial/failed sources and v1 budget counters retained. No calendar conversion."
        audit["patches"].append({"fields_id": fid, "name": name, "source_url": source["url"],
                                  "source_date_components_iso": v.components_iso(claim), "prior_status": old_status,
                                  "updated_status": record["status"], "actor": "worker", "search_queries_used": queries,
                                  "body_candidates_opened": bodies, "direct_cv_attempts": 0, "at_utc": event.get("timestamp_utc"),
                                  "original_v1_budget_counters": budgets})
    return patched, audit


def load_v2(v2_dir):
    path = Path(v2_dir) / "scripts" / "build.py"
    spec = importlib.util.spec_from_file_location("fields_v2_builder", path)
    module = importlib.util.module_from_spec(spec)
    exec(compile(path.read_bytes(), str(path), "exec"), module.__dict__)
    return module


def build(v1_dir, v2_dir, day_path, partial_path, log_path, output_dir):
    v1, v2, out = Path(v1_dir), Path(v2_dir), Path(output_dir)
    VALIDATOR.require(not out.exists(), "Output directory must be fresh")
    v = load_validator(v1)
    previous_builder = load_v2(v2)
    paths = [v1 / "fixed_roster.json", *[v1 / "data" / f"shard{i}.json" for i in range(1, 5)], v1 / "data" / "extension2026.json"]
    extra = [v2 / "new_body_claims.json", v2 / "outputs" / "summary.json", Path(day_path), Path(partial_path), Path(log_path), v1 / "scripts" / "aggregate.py", v2 / "scripts" / "build.py", Path(__file__)]
    inputs = paths + extra
    before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
    read = lambda p: json.loads(Path(p).read_text(encoding="utf-8"))
    roster = read(paths[0])
    base_payloads = [read(p) for p in paths[1:]]
    _, baseline = v.aggregate(roster, base_payloads)
    previous_payloads, _ = previous_builder.apply_patches(roster, base_payloads, read(v2 / "new_body_claims.json"), validator=v)
    _, previous = v.aggregate(roster, previous_payloads)
    v.require(previous["main"]["source_day_coverage_count"] == read(v2 / "outputs" / "summary.json")["main"]["source_day_coverage_count"], "v2 reconstruction differs from saved checkpoint")
    days, partial = read(day_path), read(partial_path)
    rows = (days if isinstance(days, list) else days["records"]) + (partial if isinstance(partial, list) else partial["records"])
    patched, audit = apply_patches(roster, previous_payloads, rows, read(log_path), validator=v)
    records, summary = v.aggregate(roster, patched)
    b, p, n = [s["main"]["source_day_coverage_count"] for s in (baseline, previous, summary)]
    delta = {"schema_version": 1, "baseline_v1_main_day_count": b, "previous_v2_main_day_count": p,
             "current_v3_main_day_count": n, "main_day_delta_from_v2": n - p,
             "main_day_delta_from_v1": n - b, "patch_count": len(rows),
             "new_day_body_claims": sum("date" in r for r in rows),
             "new_month_body_claims": sum(r.get("precision") == "month" for r in rows),
             "v1_main_status_counts": baseline["main"]["status_counts"],
             "v2_main_status_counts": previous["main"]["status_counts"],
             "v3_main_status_counts": summary["main"]["status_counts"],
             "extension2026_unchanged": previous["extension2026"] == summary["extension2026"],
             "supersession_note": f"The current v3 main day-source count {n} supersedes v2 {p}; v1 {b} and v2 {p} are retained as checkpoints.",
             "v1_v2_inputs_immutable": True, "calendar_conversion_performed": False,
             "bazi_record_count": 0, "analysis_record_count": 0, "final_analysis_cohort_freeze": False}
    summary["followup_delta"] = delta
    audit["current_round_totals"] = {"search_queries_used": sum(x["search_queries_used"] for x in audit["patches"]), "body_candidates_opened": sum(x["body_candidates_opened"] for x in audit["patches"]), "direct_cv_attempts": 0}
    v.export(records, summary, out, [])
    for name, obj in (("patch_audit.json", audit), ("followup_delta.json", delta)):
        (out / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (out / "summary.txt").open("a", encoding="utf-8") as stream:
        stream.write(delta["supersession_note"] + "\n")
        stream.write(f"Main day-source delta from v2: +{n - p}; Birkar remains month-only without a day.\n")
    manifest = {"algorithm": "sha256", "outputs": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.iterdir()) if p.name != "hash_manifest.json"},
                "inputs": [{"name": str(p.relative_to(ROOT.parent)), "sha256": before[p]} for p in inputs]}
    (out / "hash_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    v.require(all(hashlib.sha256(p.read_bytes()).hexdigest() == before[p] for p in inputs), "An input changed during the offline build")
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--v1-dir", type=Path, default=DEFAULT_V1)
    parser.add_argument("--v2-dir", type=Path, default=ROOT.parent / "fields_medal_followup_v2")
    parser.add_argument("--day-patch", type=Path, default=ROOT / "new_body_claims.json")
    parser.add_argument("--partial-patch", type=Path, default=ROOT / "partial.json")
    parser.add_argument("--log", type=Path, default=ROOT / "collection_log.json")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "outputs")
    args = parser.parse_args(argv)
    try:
        summary = build(args.v1_dir, args.v2_dir, args.day_patch, args.partial_patch, args.log, args.output_dir)
    except (ValueError, OSError) as error:
        parser.error(str(error))
    print(json.dumps({"main": summary["main"], "extension2026": summary["extension2026"], "followup_delta": summary["followup_delta"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

