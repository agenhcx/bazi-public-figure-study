#!/usr/bin/env python3
"""Replay birthplace-only annotations without changing native DOB or eligibility."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import gzip
import json
import math
from pathlib import Path

EXPECTED = {"NAS": 2242, "UK_Royal_Society": 4983, "DE_Leopoldina": 778,
            "CAS": 1230, "France": 775, "Japan": 368,
            "Fields_main": 63, "Nobel_science": 655}
VALID_HEMISPHERES = {"north", "south", "equator", "unknown"}


def load_rows(path):
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8-sig") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def compact(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def supplement_hemisphere(row):
    """Several locations can support one hemisphere without choosing one city."""
    if row.get("hemisphere") in {"north", "south", "equator"}:
        return row["hemisphere"], row.get("reason", ""), False
    reason = row.get("reason", "")
    if reason not in {"multiple_distinct_birthplace_P19_conflict",
                      "multiple_distinct_direct_coordinates_conflict"}:
        return "unknown", reason, False
    evidence = row.get("place_evidence", [])
    if not evidence:
        return "unknown", reason, False
    # Import the frozen collector's extent guard rather than infer a country
    # hemisphere from its representative point.
    from academy_birthplace_wikidata_v1 import BROAD_PLACE_TYPES
    signs = set()
    for place in evidence:
        types = {item["qid"] for item in place.get("instance_of_claims", [])}
        self_country = any(item["qid"] == place.get("qid")
                           for item in place.get("country_claims_descriptive_only", []))
        coords = place.get("coordinates", [])
        if place.get("error") or types.intersection(BROAD_PLACE_TYPES) or self_country or not coords:
            return "unknown", reason, False
        for coordinate in coords:
            lat, precision = coordinate.get("lat"), coordinate.get("precision")
            if (isinstance(lat, bool) or isinstance(precision, bool)
                or not isinstance(lat, (int, float)) or not isinstance(precision, (int, float))
                or not math.isfinite(lat) or not math.isfinite(precision)
                or precision < 0 or abs(lat) <= precision):
                return "unknown", reason, False
            signs.add("north" if lat > 0 else "south")
    if len(signs) == 1:
        return signs.pop(), "all_explicit_P19_coordinate_alternatives_same_hemisphere", True
    return "unknown", "birthplace_alternatives_cross_hemispheres", True


def merge(base, supplement):
    original_hemisphere = base.get("hemisphere", "unknown")
    if original_hemisphere not in VALID_HEMISPHERES:
        raise ValueError("Invalid baseline hemisphere")
    result = dict(base)
    result.setdefault("birthplace_source_grade", "unknown")
    result["baseline_birthplace_hemisphere"] = original_hemisphere
    result["supplement_used_for_hemisphere"] = False
    result["geographic_conflict_pending_review"] = False
    result["place_alternatives_retained"] = False
    result["dob_or_native_acceptance_modified"] = False
    if supplement:
        if supplement.get("dob", "") != base.get("dob", ""):
            raise ValueError("Supplement DOB differs from baseline: " + base["record_id"])
        sign, reason, alternatives = supplement_hemisphere(supplement)
        result["supplement_birthplace_hemisphere"] = sign
        result["supplement_reason"] = reason
        result["lookup_qid"] = supplement.get("qid", "")
        result["lookup_identity_provenance"] = supplement.get("identity_link_provenance", "")
        result["supplement_birthplace_source_grade"] = "S3"
        result["place_alternatives_retained"] = alternatives
        if (original_hemisphere != "unknown" and
            (sign != "unknown" and original_hemisphere != sign
             or reason == "birthplace_alternatives_cross_hemispheres")):
            result["hemisphere"] = "unknown"
            result["reason"] = "stored_body_and_S3_supplement_disagree_on_hemisphere"
            result["geographic_conflict_pending_review"] = True
        elif original_hemisphere == "unknown" and sign != "unknown":
            result["hemisphere"] = sign
            result["reason"] = reason
            result["raw_birthplace"] = supplement.get("raw_birthplace", "")
            result["country"] = ""
            result["lat"] = None if alternatives else supplement.get("lat")
            result["lon"] = None if alternatives else supplement.get("lon")
            result["birthplace_source_urls"] = supplement.get("birthplace_source_urls", [])
            result["birthplace_source_url"] = ""
            result["birthplace_source_grade"] = "S3"
            result["birthplace_evidence_kind"] = "Wikidata_P19_to_direct_Earth_P625_supplement"
            result["supplement_used_for_hemisphere"] = True
        elif original_hemisphere == "unknown":
            result["unresolved_supplement_reason"] = reason
    # These flags are geography annotations only, never final analysis flags.
    result["northern_birthplace_candidate"] = result.get("hemisphere") == "north"
    result["southern_birthplace_separate"] = result.get("hemisphere") == "south"
    result["final_analysis_eligibility_assigned"] = False
    return result


def assemble(study, output):
    baselines = []
    for path in sorted((study / "inputs/existing").glob("*.jsonl.gz")):
        for row in load_rows(path):
            row["baseline_evidence_file"] = str(path.relative_to(study))
            baselines.append(row)
    keys = [(row["cohort"], row["record_id"]) for row in baselines]
    if len(keys) != len(set(keys)):
        raise ValueError("Duplicate baseline cohort/record IDs")
    baseline_keys = set(keys)
    counts = Counter(row["cohort"] for row in baselines)
    if dict(counts) != EXPECTED:
        raise ValueError("Baseline conservation mismatch: " + repr(dict(counts)))
    addendum_path = study / "inputs/birthplace_body_addenda.json"
    addenda = json.loads(addendum_path.read_text()) if addendum_path.exists() else []
    baseline_by_key = {(row["cohort"], row["record_id"]): row for row in baselines}
    for addendum in addenda:
        key = addendum["cohort"], addendum["record_id"]
        if key not in baseline_by_key:
            raise ValueError("Unmatched explicit-body addendum")
        row = baseline_by_key[key]
        row["initial_baseline_hemisphere"] = row["hemisphere"]
        row["birthplace_body_addendum"] = addendum
        for field in ("hemisphere", "raw_birthplace", "country", "birthplace_source_url",
                      "birthplace_source_grade", "birthplace_evidence_kind", "reason"):
            row[field] = addendum[field]
        row["lat"], row["lon"] = None, None
    supplements = {}
    for path in sorted((study / "inputs/supplements").glob("*.jsonl.gz")):
        for row in load_rows(path):
            key = row["cohort"], row["record_id"]
            if key not in baseline_keys or key in supplements:
                raise ValueError("Unmatched or duplicate supplement key: " + repr(key))
            supplements[key] = row
    rows = [merge(row, supplements.get((row["cohort"], row["record_id"]))) for row in baselines]
    rows.sort(key=lambda row: (row["cohort"], row["record_id"]))
    output.mkdir(parents=True, exist_ok=True)
    all_bytes = ("".join(compact(row) + "\n" for row in rows)).encode()
    (output / "birthplace_rows.jsonl.gz").write_bytes(gzip.compress(all_bytes, mtime=0))
    fields = ["cohort", "record_id", "name", "dob", "raw_birthplace", "country", "lat", "lon",
              "hemisphere", "northern_birthplace_candidate", "southern_birthplace_separate",
              "birthplace_source_grade", "birthplace_evidence_kind", "birthplace_source_url",
              "reason", "supplement_used_for_hemisphere", "geographic_conflict_pending_review",
              "lookup_qid", "final_analysis_eligibility_assigned"]
    by_cohort = defaultdict(list)
    for row in rows:
        by_cohort[row["cohort"]].append(row)
    summary_rows = []
    for cohort, cohort_rows in sorted(by_cohort.items()):
        with (output / (cohort + ".csv")).open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            for row in cohort_rows:
                csv_row = dict(row)
                urls = row.get("birthplace_source_urls", [])
                if not csv_row.get("birthplace_source_url") and urls:
                    csv_row["birthplace_source_url"] = " | ".join(urls)
                writer.writerow(csv_row)
        hemisphere_counts = Counter(row.get("hemisphere", "unknown") for row in cohort_rows)
        entry = {"cohort": cohort, "baseline_rows": len(cohort_rows),
                 **{key: hemisphere_counts[key] for key in ("north", "south", "equator", "unknown")},
                 "S3_geography_supplement_used": sum(row["supplement_used_for_hemisphere"] for row in cohort_rows),
                 "hemisphere_conflicts": sum(row["geographic_conflict_pending_review"] for row in cohort_rows),
                 "baseline_scope": "reconstructed_award_ID_scope_not_hash_verified_final_DOB_table"
                 if cohort == "Nobel_science" else "native_day_claim_layer_not_accepted_Gregorian_DOB"
                 if cohort == "CAS" else "existing_native_day_level_baseline"}
        assert entry["baseline_rows"] == sum(entry[key] for key in ("north", "south", "equator", "unknown"))
        summary_rows.append(entry)
    with (output / "summary.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(summary_rows[0]))
        writer.writeheader()
        writer.writerows(summary_rows)
    summary = {"schema": "academy_birthplace_screen_v1", "by_cohort": summary_rows,
               "cross_cohort_deduplicated": False, "native_DOB_or_acceptance_modified": False,
               "birth_window_changed": False, "final_analysis_cohort_frozen": False,
               "birthplace_grade_independent_of_DOB_grade": True,
               "source_S1_S2_and_S1_S2_S3_comparison_not_yet_run": True}
    (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    print(json.dumps(assemble(args.study, args.output or args.study / "outputs"), ensure_ascii=False))


if __name__ == "__main__":
    main()
