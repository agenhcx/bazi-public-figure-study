#!/usr/bin/env python3
"""Independently audit acquired cohorts without modelling or BaZi calculation.

This audit deliberately does not import the collector. A failed identity check
requires explicit adjudication; this script never drops, remaps or refills rows.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import date, datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re

COHORTS = {
    "2013_M": ("cohort_2013_M.csv", "candidate_audit_2013_M.csv", "2013-01"),
    "2023_M_FULL": ("cohort_2023_M_FULL.csv", "candidate_audit_2023_M.csv", "2023-01"),
    "2023_M_NEW_TARGET": ("cohort_2023_M_NEW_TARGET.csv", "candidate_audit_2023_M.csv", "2023-01"),
}
LEGACY_PATHS = [f"chess_north_v3/primary_north_top_{year}_{sex}.csv"
                for year in (1994, 2013) for sex in ("M", "F")]
COMPLETE = "acquisition_complete_no_models_fitted"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or len(reader.fieldnames) != len(set(reader.fieldnames)):
            raise ValueError(f"Invalid CSV header: {path.name}")
        rows = list(reader)
        if any(None in row or any(value is None for value in row.values()) for row in rows):
            raise ValueError(f"Malformed CSV row: {path.name}")
        return rows


def person_id(row):
    raw = row.get("identity_bridge_modern_fide_id", "").strip() or row.get("fide_id", "").strip()
    if not re.fullmatch(r"[0-9]+", raw) or int(raw) < 1:
        raise ValueError("Invalid canonical person ID")
    return str(int(raw))


def qids(row):
    raw = row.get("wikidata_person_qids", "").strip()
    values = set(raw.split(";")) if raw else set()
    if any(not re.fullmatch(r"Q[1-9][0-9]*", value) for value in values):
        raise ValueError("Invalid Wikidata person QID")
    return values


def flag(value):
    value = str(value).strip().lower()
    if value in {"true", "1", "yes"}:
        return True
    if value in {"false", "0", "no", ""}:
        return False
    raise ValueError(f"Unrecognized Boolean value: {value!r}")


def rating(row):
    raw = row.get("rating", "")
    if not re.fullmatch(r"[0-9]+", str(raw)) or not 0 < int(raw) <= 3500:
        raise ValueError("Invalid integer standard Elo")
    return int(raw)


def selected_at_cutoff(rows, target, excluded=()):
    eligible = [row for row in rows if flag(row.get("eligible", ""))
                and person_id(row) not in excluded]
    ordered = sorted(eligible, key=lambda row: (-rating(row), row.get("name", ""), person_id(row)))
    if len(ordered) < target:
        raise ValueError("Candidate audit cannot establish the fixed target")
    cutoff = rating(ordered[target - 1])
    return [row for row in ordered if rating(row) >= cutoff], cutoff


def audit(root, data_dir, expected_target=1000, expected_new_target=500):
    root, data_dir = Path(root), Path(data_dir)
    result = {"status": "failed", "audited_at_utc": datetime.now(timezone.utc).isoformat(),
              "audit_script_sha256": digest(Path(__file__)), "errors": [], "cohorts": {}}
    errors = result["errors"]

    def require(condition, message):
        if not condition:
            errors.append(message)

    try:
        manifest_path, summary_path = data_dir / "manifest.json", data_dir / "summary.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        result["manifest_sha256"] = digest(manifest_path)
        result["summary_sha256"] = digest(summary_path)
        result["executing_collector_commit"] = manifest.get("executing_commit")
        require(manifest.get("status") == COMPLETE, "Manifest does not mark acquisition complete")
        require(summary.get("status") == COMPLETE, "Summary does not mark acquisition complete")
        require(manifest.get("rules", {}).get("target") == expected_target, "Manifest target changed")
        require(summary.get("target") == expected_target, "Summary target changed")
        require(manifest.get("rules", {}).get("new_target") == expected_new_target, "Manifest NEW target changed")
        require(summary.get("new_target") == expected_new_target, "Summary NEW target changed")
        require(bool(re.fullmatch(r"[0-9a-f]{40}", manifest.get("executing_commit", ""))),
                "Manifest lacks an immutable executing collector commit")
        required_files = {entry for paths in COHORTS.values() for entry in paths[:2]}
        required_files.add("excluded_legacy_ids.csv")
        outputs = {item["file"]: item["sha256"] for item in manifest.get("outputs", [])}
        require(required_files <= set(outputs), "Manifest omits required cohort/audit output hashes")
        for name, checksum in outputs.items():
            require(Path(name).name == name, "Manifest output path is not a simple filename")
            path = data_dir / name
            require(path.is_file() and digest(path) == checksum, f"Output hash mismatch: {name}")
        for item in manifest.get("seed_inputs", []) + manifest.get("legacy_exclusion_inputs", []):
            path = root / item["path"]
            require(path.is_file() and digest(path) == item["sha256"], f"Frozen input hash mismatch: {item['path']}")
        result["available_source_archive_checks"] = {}
        for year, source in manifest.get("population_sources", {}).items():
            archive = data_dir.parent / "cache" / f"standard_jan{year[-2:]}frl.zip"
            if archive.is_file():
                matches = digest(archive) == source.get("archive_sha256")
                require(matches, f"Source archive hash mismatch: {year}")
                result["available_source_archive_checks"][year] = matches
        cache_path = data_dir.parent / "cache" / "wikidata_records.json"
        if cache_path.is_file():
            require(digest(cache_path) == manifest.get("wikidata_cache_sha256"), "Wikidata evidence cache hash mismatch")
        for name, key in [("collect_cohorts.py", "collector_sha256"),
                          ("acquisition_protocol.md", "protocol_sha256")]:
            path = Path(__file__).with_name(name)
            require(bool(manifest.get(key)), f"Manifest omits {key}")
            if path.is_file():
                require(digest(path) == manifest.get(key), f"Current {name} differs from acquired version")

        legacy_rows = [row for rel in LEGACY_PATHS for row in read_csv(root / rel)]
        legacy_ids = {person_id(row) for row in legacy_rows}
        legacy_qids = {qid for row in legacy_rows for qid in qids(row)}
        old_2013 = read_csv(root / "chess_north_v3/primary_north_top_2013_M.csv")
        old_ids = {person_id(row) for row in old_2013}
        cohorts = {group: read_csv(data_dir / paths[0]) for group, paths in COHORTS.items()}
        dev_ids = {person_id(row) for row in cohorts["2013_M"]}
        exclusion_union = legacy_ids | dev_ids
        declared_exclusion_rows = read_csv(data_dir / "excluded_legacy_ids.csv")
        declared_exclusions = {str(int(row["canonical_id"])) for row in declared_exclusion_rows}
        require(len(declared_exclusions) == len(declared_exclusion_rows), "Duplicate exclusion-union IDs")
        require(declared_exclusions == exclusion_union, "Saved exclusion union differs from expanded development plus legacy IDs")
        require(old_ids <= dev_ids, "Expanded development loses old frozen development players")
        result["old_development_retained_n"] = len(old_ids & dev_ids)
        result["old_development_n"] = len(old_ids)
        result["exclusion_union_n"] = len(exclusion_union)
        all_people = {}
        qid_sets = {}

        for group, rows in cohorts.items():
            filename, audit_filename, snapshot = COHORTS[group]
            candidates = read_csv(data_dir / audit_filename)
            candidate_ids = [person_id(row) for row in candidates]
            require(len(candidate_ids) == len(set(candidate_ids)), f"{group}: duplicate canonical IDs in candidate audit")
            candidate_ratings = [rating(row) for row in candidates]
            require(candidate_ratings == sorted(candidate_ratings, reverse=True), f"{group}: candidate audit is not in descending Elo order")
            excluded = exclusion_union if group == "2023_M_NEW_TARGET" else set()
            role_target = expected_new_target if group == "2023_M_NEW_TARGET" else expected_target
            expected_rows, cutoff = selected_at_cutoff(candidates, role_target, excluded)
            expected = {person_id(row): row for row in expected_rows}
            ids = [person_id(row) for row in rows]
            require(len(ids) == len(set(ids)), f"{group}: duplicate canonical IDs")
            require(set(ids) == set(expected), f"{group}: selected IDs differ from all eligible cutoff ties in candidate audit")
            require(len(rows) >= role_target, f"{group}: target not reached")
            group_summary = summary.get("cohorts", {}).get(group, {})
            require(group_summary.get("n") == len(rows), f"{group}: summary row count mismatch")
            require(group_summary.get("cutoff_elo") == cutoff, f"{group}: summary cutoff mismatch")
            require(group_summary.get("sha256") == digest(data_dir / filename), f"{group}: summary file hash mismatch")
            qid_counts = Counter()
            calendar_counts = Counter()
            source_counts = Counter()
            for row in rows:
                fid = person_id(row)
                row_qids = qids(row)
                require(len(row_qids) == 1, f"{group}/{fid}: selected person must have exactly one Wikidata QID")
                qid_counts.update(row_qids)
                require(flag(row.get("eligible", "")), f"{group}/{fid}: selected row marked ineligible")
                require(flag(row.get("active", "")), f"{group}/{fid}: inactive selected row")
                require(row.get("sex") == "M", f"{group}/{fid}: selected sex is not M")
                require(row.get("snapshot") == snapshot, f"{group}/{fid}: wrong snapshot")
                require(row.get("birthplace_hemisphere") == "north", f"{group}/{fid}: selected birthplace is not north")
                birth = date.fromisoformat(row.get("exact_dob_frozen", ""))
                require(birth.isoformat() == row.get("exact_dob_frozen"), f"{group}/{fid}: noncanonical DOB")
                require(birth <= date.fromisoformat(snapshot + "-01"), f"{group}/{fid}: DOB after snapshot")
                birth_year = row.get("birth_year", "").strip()
                if re.fullmatch(r"[0-9]+(?:\.0)?", birth_year) and float(birth_year) > 0:
                    require(birth.year == int(float(birth_year)), f"{group}/{fid}: historical birth year mismatch")
                latitudes = [float(value) for value in row.get("birthplace_latitudes", "").split(";") if value]
                require(bool(latitudes) and all(math.isfinite(value) and 0 < value <= 90 for value in latitudes),
                        f"{group}/{fid}: missing or non-northern birthplace coordinates")
                source = row.get("evidence_source", "")
                calendar = row.get("dob_calendar_status", "")
                if source == "new_wikidata_best_rank_query":
                    require(calendar == "explicit_gregorian_required", f"{group}/{fid}: new DOB calendar not explicitly Gregorian")
                else:
                    require(source and calendar.startswith("legacy_"), f"{group}/{fid}: unclassified legacy calendar provenance")
                calendar_counts[calendar] += 1
                source_counts["new" if source == "new_wikidata_best_rank_query" else "legacy"] += 1
                if fid in expected:
                    for field in ("rating", "exact_dob_frozen", "birth_year", "sex", "snapshot",
                                  "birthplace_hemisphere", "wikidata_person_qids"):
                        require(row.get(field) == expected[fid].get(field), f"{group}/{fid}: {field} differs from candidate audit")
                values = (birth.isoformat(), frozenset(row_qids))
                require(fid not in all_people or all_people[fid] == values, f"{group}/{fid}: cross-snapshot DOB/QID disagreement")
                all_people[fid] = values
            duplicate_qids = [qid for qid, count in qid_counts.items() if count > 1]
            require(not duplicate_qids, f"{group}: duplicate person QIDs across distinct selected rows: {duplicate_qids[:10]}")
            qid_sets[group] = set(qid_counts)
            result["cohorts"][group] = {"target_n": role_target, "n": len(rows), "canonical_ids_unique": len(set(ids)) == len(rows),
                "person_qids_n": len(qid_counts), "duplicate_person_qids_n": len(duplicate_qids),
                "cutoff_elo": cutoff, "all_cutoff_ties_present": set(ids) == set(expected),
                "calendar_provenance_counts": dict(calendar_counts), "evidence_source_counts": dict(source_counts)}

        new_ids = {person_id(row) for row in cohorts["2023_M_NEW_TARGET"]}
        dev_new_aliases = qid_sets["2013_M"] & qid_sets["2023_M_NEW_TARGET"]
        legacy_new_aliases = legacy_qids & qid_sets["2023_M_NEW_TARGET"]
        require(not (new_ids & exclusion_union), "NEW contains excluded canonical identities")
        require(not dev_new_aliases, f"Development/NEW Wikidata person alias leakage: {sorted(dev_new_aliases)[:10]}")
        require(not legacy_new_aliases, f"Legacy/NEW Wikidata person alias leakage: {sorted(legacy_new_aliases)[:10]}")
        result["overlaps"] = {"development_new_canonical_ids": len(dev_ids & new_ids),
                              "development_new_person_qids": len(dev_new_aliases),
                              "legacy_new_person_qids": len(legacy_new_aliases)}
        # Independently reconstruct the historical Top500 eligible cutoff.
        if len(cohorts["2013_M"]) >= 500:
            ranked500, cutoff500 = selected_at_cutoff(cohorts["2013_M"], 500)
            ranked500_ids = {person_id(row) for row in ranked500}
            result["ranked500_check"] = {"n": len(ranked500), "cutoff_elo": cutoff500,
                                        "matches_old_frozen_cohort": ranked500_ids == old_ids}
            require(ranked500_ids == old_ids, "Expanded ranked Top500 plus ties differs from old frozen development cohort")
        result["status"] = "passed" if not errors else "failed"
    except (OSError, ValueError, KeyError, TypeError) as error:
        errors.append(f"Audit cannot complete: {type(error).__name__}: {error}")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--data-dir", type=Path, default=Path("studies/chess_single_A_v2/data"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = args.repo_root.resolve()
    data_dir = args.data_dir if args.data_dir.is_absolute() else root / args.data_dir
    output = args.output or data_dir / "independent_audit.json"
    result = audit(root, data_dir)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["status"] == "passed" else 1)


if __name__ == "__main__":
    main()
