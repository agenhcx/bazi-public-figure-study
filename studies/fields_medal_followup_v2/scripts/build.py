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


def apply_patches(roster_payload, input_payloads, patch_payload, validator=None):
    """Return patched copies and a separate round audit; never mutate v1 inputs."""
    v = validator or VALIDATOR
    roster = roster_payload.get("rows") if isinstance(roster_payload, dict) else roster_payload
    v.require(isinstance(roster, list), "Roster rows required")
    v.require(isinstance(patch_payload, dict) and isinstance(patch_payload.get("records"), list), "Patch records required")
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
    audit = {"schema_version": 1, "round": "fields_medal_followup_v2", "at_utc": None,
             "retrieval_performed_by_builder": False, "actor": "root",
             "budget_scope_note": "Each supplied root follow-up used 1 search and 1 body candidate. Exact retrieval times were not recorded. Original v1 budget counters remain unchanged; this separate round is not silently merged into those counters.",
             "patches": []}
    for patch in patch_payload["records"]:
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
        date = patch.get("date")
        v.require(isinstance(date, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", date), "Patch date requires explicit three components")
        year, month, day = map(int, date.split("-"))
        source = {"url": patch.get("source_url"), "status": "body_observed",
                  "access_method": "previously observed root body; offline patch integration",
                  "note": "Supplied in new_body_claims.json. No network retrieval by this builder; retrieval timestamp unknown."}
        v.safe_url(source["url"])
        claim = {"date_raw": patch.get("date_raw", patch.get("excerpt")),
                 "year": year, "month": month, "day": day, "precision": "day",
                 "calendar": patch.get("calendar"), "source_url": source["url"],
                 "source_type": patch.get("source_type"), "source_status": "body_observed",
                 "excerpt": patch.get("excerpt"),
                 "identity_note": patch.get("identity_note", f"Previously collected HLF laureate body supplied by root for {name}; exact name mapped to fixed roster ID {fid} during offline integration.")}
        v.validate_claim(claim, [source])
        old_status, _ = v.derive(record)
        budgets = {key: record[key] for key in ("search_queries_used", "body_candidates_opened", "direct_cv_attempts")}
        record["claims"].append(claim)
        record["sources"].append(source)
        record["status"], _ = v.derive(record)
        record["review_note"] = record.get("review_note", "") + " Follow-up v2 adds the supplied HLF body claim; original partial/failed sources and v1 budget counters retained. No calendar conversion."
        audit["patches"].append({"fields_id": fid, "name": name, "source_url": source["url"],
                                  "source_date_components_iso": date, "prior_status": old_status,
                                  "updated_status": record["status"], "search_queries_used": 1,
                                  "body_candidates_opened": 1, "direct_cv_attempts": 0, "at_utc": None,
                                  "original_v1_budget_counters": budgets})
    return patched, audit


def build(v1_dir, patch_path, output_dir):
    v1 = Path(v1_dir)
    patch_path = Path(patch_path)
    out = Path(output_dir)
    VALIDATOR.require(not out.exists(), "Output directory must be fresh")
    v = load_validator(v1)
    inputs = [v1 / "data" / f"shard{i}.json" for i in range(1, 5)] + [v1 / "data" / "extension2026.json"]
    roster_path = v1 / "fixed_roster.json"
    input_paths = [roster_path, *inputs, patch_path, v1 / "scripts" / "aggregate.py", Path(__file__)]
    before_hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in input_paths}
    roster = json.loads(roster_path.read_text(encoding="utf-8"))
    payloads = [json.loads(p.read_text(encoding="utf-8")) for p in inputs]
    patch = json.loads(patch_path.read_text(encoding="utf-8"))
    _, baseline = v.aggregate(roster, payloads)
    patched, audit = apply_patches(roster, payloads, patch, validator=v)
    records, summary = v.aggregate(roster, patched)
    old_count = baseline["main"]["source_day_coverage_count"]
    new_count = summary["main"]["source_day_coverage_count"]
    delta = {"schema_version": 1, "baseline": "fields_medal_collection_v1",
             "current": "fields_medal_followup_v2", "patch_count": len(audit["patches"]),
             "main_source_day_before": old_count, "main_source_day_after": new_count,
             "main_source_day_delta": new_count - old_count,
             "baseline_main_status_counts": baseline["main"]["status_counts"],
             "current_main_status_counts": summary["main"]["status_counts"],
             "extension2026_unchanged": baseline["extension2026"] == summary["extension2026"],
             "supersession_note": f"The v1 main day-source count {old_count} is retained as a checkpoint and superseded by the v2 count {new_count}.",
             "v1_inputs_immutable": True, "calendar_conversion_performed": False,
             "bazi_record_count": 0, "analysis_record_count": 0, "final_analysis_cohort_freeze": False}
    summary["followup_delta"] = delta
    v.export(records, summary, out, input_paths)
    (out / "patch_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "followup_delta.json").write_text(json.dumps(delta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (out / "summary.txt").open("a", encoding="utf-8") as stream:
        stream.write(delta["supersession_note"] + "\n")
        stream.write(f"Follow-up adds {new_count - old_count:+d} main day-source people; original v1 snapshot and patch audit retained.\n")
    manifest = {"algorithm": "sha256", "outputs": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.iterdir()) if p.name != "hash_manifest.json"},
                "inputs": [{"name": str(p.relative_to(v1)) if p.is_relative_to(v1) else p.name, "sha256": before_hashes[str(p)]} for p in input_paths]}
    (out / "hash_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    v.require(all(hashlib.sha256(p.read_bytes()).hexdigest() == before_hashes[str(p)] for p in input_paths), "An input changed during offline build")
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--v1-dir", type=Path, default=DEFAULT_V1)
    parser.add_argument("--patch", type=Path, default=ROOT / "new_body_claims.json")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "outputs")
    args = parser.parse_args(argv)
    try:
        summary = build(args.v1_dir, args.patch, args.output_dir)
    except (ValueError, OSError) as error:
        parser.error(str(error))
    print(json.dumps({"main": summary["main"], "extension2026": summary["extension2026"], "followup_delta": summary["followup_delta"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
