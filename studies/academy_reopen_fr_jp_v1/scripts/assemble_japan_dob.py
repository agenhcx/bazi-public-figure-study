#!/usr/bin/env python3
"""Offline assembly of Japan science roster candidates and bounded DOB claims.

Candidate discovery, individual date evidence, and final eligibility remain
separate. No network, calendar conversion, missing-component filling or BaZi.
"""
import argparse
import collections
import copy
import csv
import datetime
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
STATUSES = {"day_source_verified", "month_only", "year_only", "not_found", "blocked", "conflicting_sources"}
CALENDARS = {"not_stated", "gregorian_explicit", "julian_explicit", "lunar_explicit"}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def safe_url(url):
    require(isinstance(url, str) and not re.search(r"[\s\x00-\x1f\x7f]", url), "Invalid source URL")
    p = urlsplit(url)
    require(p.scheme in {"http", "https"} and bool(p.hostname) and p.username is None and p.password is None, "HTTP(S) source without credentials required")
    p.port


def validate_claim(claim):
    precision = claim.get("precision")
    require(precision in {"day", "month", "year"}, "Unknown date precision")
    require(claim.get("calendar") in CALENDARS, "Unknown source calendar")
    require(all(k in claim for k in ("year", "month", "day")), "Nullable source components required")
    y, m, d = (claim[k] for k in ("year", "month", "day"))
    require(type(y) is int and 1 <= y <= 9999, "Invalid year")
    require((precision == "year" and m is None and d is None)
            or (precision == "month" and type(m) is int and d is None)
            or (precision == "day" and type(m) is int and type(d) is int), "Precision/components mismatch; no date padding")
    require(m is None or 1 <= m <= 12, "Invalid month")
    if d is not None:
        if claim["calendar"] == "lunar_explicit":
            require(1 <= d <= 30, "Invalid lunar day")
        else:
            try:
                datetime.date(y, m, d)
            except ValueError as error:
                raise ValueError("Invalid day components") from error
    require(claim.get("source_status") in {"body_observed", "search_snippet_only"}, "Unknown evidence access status")
    require(isinstance(claim.get("identity_note"), str) and claim["identity_note"].strip(), "Identity note required")
    require(isinstance(claim.get("date_raw"), str) and claim["date_raw"].strip(), "Raw source date required")
    require(isinstance(claim.get("excerpt"), str) and claim["excerpt"].strip() and len(claim["excerpt"].split()) <= 25, "Short evidence excerpt required")
    safe_url(claim.get("source_url"))
    return "-".join([f"{y:04d}"] + ([f"{m:02d}"] if m is not None else []) + ([f"{d:02d}"] if d is not None else []))


def assemble(roster_rows, claims_payload):
    require(isinstance(roster_rows, list) and bool(roster_rows), "Nonempty candidate roster required")
    index = {}
    for row in roster_rows:
        key = row.get("member_key")
        require(isinstance(key, str) and key and key not in index, "Missing or duplicate roster ID")
        require(isinstance(row.get("name_jp"), str) and row["name_jp"].strip(), "Roster name required")
        index[key] = row
    records = claims_payload if isinstance(claims_payload, list) else claims_payload.get("records")
    require(isinstance(records, list), "Claim records required")
    seed = {}
    ledger = []
    details = {}
    for record in records:
        key = record.get("member_key")
        require(key in index and key not in seed, "Unknown or duplicate claim identity")
        row = index[key]
        require(record.get("name_jp") == row["name_jp"] and record.get("name_en", "") == row.get("name_en", ""), "Claim name differs from exact roster identity")
        status = record.get("status")
        require(status in STATUSES, "Unknown processing status")
        require(isinstance(record.get("claims"), list), "Claims list required")
        accepted = []
        original = record.get("source_original_calendar_birth")
        if original:
            require(original.get("calendar") in CALENDARS and original.get("date_raw"), "Invalid original-calendar source record")
            safe_url(original.get("source_url"))
            require(original.get("source_status") == "body_observed", "Original calendar must have observed source body")
        original_json = json.dumps(original, ensure_ascii=False, sort_keys=True) if original else ""
        for number, claim in enumerate(record["claims"], 1):
            iso = validate_claim(claim)
            is_body = claim["source_status"] == "body_observed"
            if is_body:
                accepted.append((claim, iso))
            item = {k: copy.deepcopy(v) for k, v in claim.items() if k != "tool_refs"}
            item.update(member_key=key, name_jp=record["name_jp"], name_en=record.get("name_en", ""), claim_index=number,
                        source_date_components_iso=iso, counts_toward_body_coverage=is_body,
                        source_original_calendar_birth_json=original_json, final_cohort_accepted=False,
                        individually_verified_scope="DOB source claim only; broad Section II does not establish exact subsection or final eligibility", bazi_variables_computed=0)
            ledger.append(item)
        if status in {"day_source_verified", "month_only", "year_only"}:
            precision = {"day_source_verified": "day", "month_only": "month", "year_only": "year"}[status]
            candidates = [(c, iso) for c, iso in accepted if c["precision"] == precision]
            require(bool(candidates), "Verified/partial date status requires same-precision observed source body")
            require(len({iso for c, iso in candidates}) == 1, "Unresolved body date conflict requires conflicting_sources status")
            iso = candidates[0][1]
            require(record.get("date") in (None, "", iso), "Top-level date differs from supplied source precision")
        else:
            iso = ""
            require(not record.get("date"), "Missing/conflicting record cannot select a date")
            if status in {"not_found", "blocked"}:
                require(not accepted, "Failure status cannot hide observed date claim")
        details[key] = (iso, original_json)
        seed[key] = record
    master = []
    for key, row in index.items():
        record = seed.get(key)
        iso, original = details.get(key, ("", ""))
        item = copy.deepcopy(row)
        item.update(dob_status=record["status"] if record else "not_processed", processed_this_round=bool(record),
                    source_date_components_iso=iso, source_original_calendar_birth_json=original,
                    source_calendars="|".join(sorted({c["calendar"] for c in record["claims"]})) if record else "",
                    membership_scope_from_seed=record.get("membership_scope_status", "") if record else "",
                    exact_subsection_proved_this_round=False, final_cohort_accepted=False, bazi_variables_computed=0,
                    individually_verified_scope=("DOB body source only; existing broad Section II scope; exact subsection and final eligibility not established" if record and record["status"] == "day_source_verified" else "DOB searched, no full day verification; final eligibility not established" if record else "Not individually checked in this round"),
                    review_note=record.get("review_note", "") if record else "")
        master.append(item)
    missing = [r for r in master if r["dob_status"] != "day_source_verified"]
    counts = dict(collections.Counter(r["dob_status"] for r in master))
    summary = {"schema_version": 1, "candidate_count": len(master), "processed_count": len(seed), "not_processed_count": len(master) - len(seed),
               "day_body_verified_count": counts.get("day_source_verified", 0), "missing_queue_count": len(missing), "status_counts": counts,
               "full_japan_missing_count": None, "roster_scope": "Science-core discovery candidates; not a final eligible national Academy roster",
               "source_count_discrepancy": {"reported_values": [139, 137], "reconciled": False, "note": "Source-count difference retained without correction; not final eligible cohort counts."},
               "membership_scope_note": "Seed's broad Section II qualification is retained; exact subsections and final inclusion are not inferred.",
               "calendar_note": "Source calendar labels and source-supplied dual-calendar wording are preserved; no collector conversion and no conflict inferred from an explicitly supplied equivalent.",
               "final_cohort_accepted": False, "bazi_variables_computed": 0, "analysis_record_count": 0, "network_requests": 0}
    if isinstance(claims_payload, dict):
        summary["seed_metadata"] = {k: v for k, v in claims_payload.items() if k != "records"}
    return master, ledger, missing, summary


def write_csv(path, rows, default_columns):
    columns = list(dict.fromkeys([*default_columns, *(k for row in rows for k in row)]))
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v, ensure_ascii=False, sort_keys=True) if isinstance(v, (dict, list)) else v for k, v in row.items()})


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--roster", type=Path, default=ROOT / "inputs" / "japan_science_candidates.csv")
    parser.add_argument("--claims", type=Path, default=ROOT / "inputs" / "japan_dob_seed.json")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        require(not args.output_dir.exists(), "Output directory must be fresh")
        with args.roster.open(encoding="utf-8-sig", newline="") as stream:
            roster = list(csv.DictReader(stream))
        master, ledger, missing, summary = assemble(roster, json.loads(args.claims.read_text(encoding="utf-8")))
        args.output_dir.mkdir(parents=True)
        write_csv(args.output_dir / "master.csv", master, ["member_key", "name_jp", "name_en"])
        write_csv(args.output_dir / "claims_ledger.csv", ledger, ["member_key", "name_jp", "name_en", "source_date_components_iso", "calendar", "source_url"])
        write_csv(args.output_dir / "missing_queue.csv", missing, ["member_key", "name_jp", "dob_status"])
        (args.output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        manifest = {"algorithm": "sha256", "inputs": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (args.roster, args.claims)},
                    "outputs": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(args.output_dir.iterdir())}}
        (args.output_dir / "hashes.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    except (ValueError, OSError) as error:
        parser.error(str(error))
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
