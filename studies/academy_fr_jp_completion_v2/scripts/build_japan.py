#!/usr/bin/env python3
"""Replay restored Japan roster scope and body DOB evidence; no network or analysis."""
import argparse
import collections
import csv
import datetime
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def require(ok, message):
    if not ok:
        raise ValueError(message)


def roster(inputs):
    original = read_csv(inputs / "japan_original435.csv")
    remaining = read_csv(inputs / "japan_remaining40.csv")
    imperial = read_csv(inputs / "japan_imperial332.csv")
    degree = {r["member_key"]: r for r in read_csv(inputs / "japan_frozen_degree199.csv")}
    tierb = read_json(inputs / "japan_tierb_decisions.json")
    output = {}
    for layer, rows in [("restored435", original), ("old_remaining40", remaining), ("imperial332", imperial)]:
        for r in rows:
            key = r["member_key"]
            if key not in output:
                output[key] = dict(r)
                output[key]["restored_layers"] = []
            else:
                require(output[key]["name_jp"] == r["name_jp"], "Same ID has different names")
                for k, v in r.items():
                    if not output[key].get(k) and v:
                        output[key][k] = v
            output[key]["restored_layers"].append(layer)
    imp = {r["member_key"]: r for r in imperial}
    for key, row in output.items():
        historical = imp.get(key, {})
        b = tierb.get(key, {})
        exact = row.get("subsection_official", "")
        if row.get("section_official") == "2":
            status, section = "restored_official_detail_or_current_section_ii", "2"
        elif historical.get("final_section_evidence") == "1":
            status, section = "restored_imperial_official_section_i_exclusion", "1"
        elif historical.get("final_section_evidence") == "2":
            status, section = "restored_imperial_official_section_ii", "2"
            if historical.get("historical_section_conflict") == "1":
                status += "_historical_conflict_retained"
        elif key in degree:
            status, section = "restored_frozen_broad_degree_rule_section_ii", "2"
        elif b.get("accepted_broad_section") in {"I", "II"}:
            section = {"I": "1", "II": "2"}[b["accepted_broad_section"]]
            status = "restored_tier_b_direct_section_" + ("i_exclusion" if section == "1" else "ii")
            exact = b.get("accepted_exact_subsection", "") or exact
        else:
            # The old 11 pre-1906 single-degree rows are retained as a distinct
            # unresolved layer. Do not silently extend a 199-person rule output.
            status = "pre1906_single_science_degree_original_section_unrecovered" if row.get("scope_status") == "degree_suggested_section_ii_not_frozen" else "restored_remaining36_section_unresolved"
            section = ""
        row.update(section_evidence_status=status, broad_section_supported=section,
                   exact_subsection_supported=exact, final_cohort_accepted=False,
                   bazi_variables_computed=0)
    return list(output.values())


def validate_claim(c, people):
    require(c.get("member_key") in people, "Unknown claim member ID")
    require(c.get("name_jp") == people[c["member_key"]]["name_jp"], "Claim name differs from roster")
    require(c.get("body_verified") is True and c.get("identity_body_supported") is True, "A name-only or snippet claim cannot enter body ledger")
    require(c.get("source_url", "").startswith("https://"), "HTTPS source URL required")
    require(c.get("raw_birth_statement") and c.get("identity_support"), "Date and identity wording required")
    p = c.get("precision")
    y, m, d = (c.get(k) for k in ["year", "month", "day"])
    require(type(y) is int and 1 <= y <= 9999, "Bad year")
    require((p == "year" and m is None and d is None) or
            (p == "month" and type(m) is int and d is None) or
            (p == "day" and type(m) is int and type(d) is int), "Precision padding is forbidden")
    require(m is None or 1 <= m <= 12, "Bad month")
    if d is not None:
        if c.get("calendar_comparable") is False:
            require(1 <= d <= 31, "Bad unconverted source day")
        else:
            datetime.date(y, m, d)
    require(c.get("calendar") and type(c.get("calendar_comparable")) is bool, "Explicit calendar routing required")
    return "-".join([f"{y:04d}"] + ([f"{m:02d}"] if m is not None else []) + ([f"{d:02d}"] if d is not None else []))


def consistent(a, b):
    return all(a.get(k) is None or b.get(k) is None or a[k] == b[k] for k in ["year", "month", "day"])


def assemble(rows, claims, holds, processed, authority):
    people = {r["member_key"]: r for r in rows}
    require(len(people) == len(rows), "Duplicate roster ID")
    grouped = collections.defaultdict(list)
    seen = set()
    ledger = []
    for raw in claims:
        c = dict(raw)
        iso = validate_claim(c, people)
        identity = (c["member_key"], c["source_url"], c["raw_birth_statement"], iso, c["calendar"])
        if identity in seen:
            continue
        seen.add(identity)
        c.update(source_date_components_iso=iso, final_cohort_accepted=False, bazi_variables_computed=0)
        c["claim_id"] = hashlib.sha256(json.dumps(identity, ensure_ascii=False).encode()).hexdigest()[:20]
        grouped[c["member_key"]].append(c)
        ledger.append(c)
    master = []
    for row in rows:
        row = dict(row)
        key = row["member_key"]
        all_claims = grouped[key]
        comparable = [c for c in all_claims if c["calendar_comparable"]]
        conflicts = any(not consistent(a, b) for i, a in enumerate(comparable) for b in comparable[i + 1:])
        note = holds.get(key)
        selected = ""
        if note:
            status = note["status"]
        elif conflicts:
            status = "source_date_conflict_hold"
        elif comparable:
            rank = {"year": 0, "month": 1, "day": 2}
            best = max(comparable, key=lambda c: rank[c["precision"]])
            status = {"day": "body_day_no_known_conflict", "month": "body_month_only", "year": "body_year_only"}[best["precision"]]
            selected = best["source_date_components_iso"]
        elif all_claims:
            status = "source_calendar_hold"
        elif key in processed:
            status = "bounded_search_no_body_birth_claim"
        else:
            status = "not_institutionally_processed"
        a = authority.get(key, {})
        row.update(dob_status=status, source_date_components_iso=selected,
                   birth_claim_count=len(all_claims), birth_claim_ids=[c["claim_id"] for c in all_claims],
                   birth_source_urls=sorted({c["source_url"] for c in all_claims}),
                   calendar_labels=sorted({c["calendar"] for c in all_claims}),
                   dob_hold_note=note.get("reason", "") if note else "",
                   ndl_authority_matching_status=a.get("match_status", a.get("status", "not_in_authority_batch")),
                   ndl_authority_name_only_candidates=a,
                   institutionally_processed=key in processed or bool(all_claims),
                   final_cohort_accepted=False, bazi_variables_computed=0)
        # Name-only authority matches never supply the selected birth date.
        master.append(row)
    science = [r for r in master if r["broad_section_supported"] != "1"]
    queue = [r for r in science if r["dob_status"] != "body_day_no_known_conflict" or not r["broad_section_supported"]]
    status = dict(collections.Counter(r["dob_status"] for r in master))
    summary = {
        "restored_candidate_universe": len(master),
        "original435": sum("restored435" in r["restored_layers"] for r in master),
        "section_status_counts": dict(collections.Counter(r["section_evidence_status"] for r in master)),
        "broad_section_ii_supported": sum(r["broad_section_supported"] == "2" for r in master),
        "section_i_excluded": sum(r["broad_section_supported"] == "1" for r in master),
        "section_unresolved": sum(not r["broad_section_supported"] for r in master),
        "nonexcluded_science_and_unresolved_candidates": len(science),
        "institutional_body_birth_people": sum(r["birth_claim_count"] > 0 for r in master),
        "body_claim_rows": len(ledger), "dob_status_counts": status,
        "body_day_no_known_conflict": status.get("body_day_no_known_conflict", 0),
        "nonexcluded_body_day_no_known_conflict": sum(r["dob_status"] == "body_day_no_known_conflict" for r in science),
        "section_ii_and_body_day_no_known_conflict": sum(r["dob_status"] == "body_day_no_known_conflict" and r["broad_section_supported"] == "2" for r in master),
        "nonexcluded_dob_not_day_count": sum(r["dob_status"] != "body_day_no_known_conflict" for r in science),
        "next_action_queue_count": len(queue),
        "authority_name_only_not_accepted": True,
        "calendar_conversions_performed": 0, "default_date_components_filled": 0,
        "final_cohort_accepted": False, "full_national_missing_birthdays": None,
        "bazi_variables_computed": 0, "analysis_record_count": 0,
        "scope_note": "Union of restored435, old40 and imperial332; seven restored Section I exclusions retained. Counts describe this restored candidate universe, not a frozen national eligible cohort. Eleven pre-1906 degree-only records and 36 prior section cases remain explicit holds.",
    }
    return master, ledger, queue, summary


def write_csv(path, rows):
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows({k: json.dumps(v, ensure_ascii=False, sort_keys=True) if isinstance(v, (dict, list)) else v for k, v in r.items()} for r in rows)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--inputs", type=Path, default=ROOT / "inputs")
    p.add_argument("--output-dir", type=Path, required=True)
    a = p.parse_args()
    require(not a.output_dir.exists(), "Output directory must be fresh")
    rows = roster(a.inputs)
    processed = set(read_json(a.inputs / "japan_processed_ids.json"))
    authority = {}
    for f in ["ndl_candidate_matches435.csv", "ndl_candidate_matches40.csv"]:
        for r in read_csv(a.inputs / f):
            require(r["member_key"] not in authority, "Overlapping authority batch IDs")
            authority[r["member_key"]] = r
    master, ledger, queue, summary = assemble(rows, read_json(a.inputs / "japan_body_claims.json"), read_json(a.inputs / "japan_dob_holds.json"), processed, authority)
    a.output_dir.mkdir(parents=True)
    for name, values in [("japan_master.csv", master), ("japan_body_claims_ledger.csv", ledger), ("japan_next_action_queue.csv", queue)]:
        write_csv(a.output_dir / name, values)
    (a.output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
