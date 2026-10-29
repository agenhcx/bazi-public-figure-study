#!/usr/bin/env python3
"""Offline, standard-library-only Fields Medal source collection validator.

This exports source date components, not calendar-converted birth dates. It
retains snippets as leads, counts only observed bodies, and never fills dates.
"""
from __future__ import annotations

import argparse
import collections
import copy
import csv
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

STATUSES = {"day_source_verified", "month_only", "year_only", "not_found", "blocked", "conflicting_sources"}
CALENDARS = {"not_stated", "gregorian_explicit", "julian_explicit", "lunar_explicit"}
SOURCE_TYPES = {"institutional_biography", "first_person_cv", "institutional_cv", "official_award"}
SOURCE_STATUSES = {"body_observed", "blocked", "search_snippet_only"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def safe_url(value):
    require(isinstance(value, str) and not re.search(r"[\s\x00-\x1f\x7f]", value), "Invalid URL characters")
    try:
        parsed = urlsplit(value)
        require(parsed.scheme in {"http", "https"} and bool(parsed.hostname), "HTTP(S) source URL required")
        require(parsed.username is None and parsed.password is None, "Credential-bearing source URL rejected")
        parsed.port
    except (ValueError, TypeError) as error:
        raise ValueError(f"Invalid source URL: {value}") from error
    return value


def components_iso(claim):
    parts = [f"{claim['year']:04d}"]
    if claim["month"] is not None:
        parts.append(f"{claim['month']:02d}")
    if claim["day"] is not None:
        parts.append(f"{claim['day']:02d}")
    return "-".join(parts)


def validate_claim(claim, sources):
    require(isinstance(claim, dict), "Claim must be an object")
    require(all(k in claim for k in ("year", "month", "day")), "Explicit nullable date components required")
    require(claim.get("precision") in {"year", "month", "day"}, "Invalid claim precision")
    require(claim.get("calendar") in CALENDARS, "Invalid calendar label")
    require(claim.get("source_type") in SOURCE_TYPES, "Invalid source type")
    require(claim.get("source_status") in {"body_observed", "search_snippet_only"}, "Invalid claim source status")
    require(isinstance(claim.get("date_raw"), str) and claim["date_raw"].strip(), "Missing raw date")
    require(isinstance(claim.get("identity_note"), str) and claim["identity_note"].strip(), "Missing identity note")
    excerpt = claim.get("excerpt")
    require(isinstance(excerpt, str) and excerpt.strip(), "Missing evidence excerpt")
    require(len(excerpt.split()) <= 25, "Evidence excerpt exceeds 25 words")
    year, month, day = (claim.get(k) for k in ("year", "month", "day"))
    require(type(year) is int and 1 <= year <= 9999, "Invalid source year")
    precision = claim["precision"]
    require((precision == "year" and month is None and day is None)
            or (precision == "month" and type(month) is int and day is None)
            or (precision == "day" and type(month) is int and type(day) is int),
            "Precision/components mismatch; partial dates cannot be filled")
    require(month is None or 1 <= month <= 12, "Invalid source month")
    require(day is None or 1 <= day <= 31, "Invalid source day")
    url = safe_url(claim.get("source_url"))
    matches = [s for s in sources if s["url"] == url]
    require(bool(matches), "Claim URL missing from source ledger")
    if claim["source_status"] == "body_observed":
        require(any(s["status"] == "body_observed" for s in matches), "Body claim requires same-URL observed source body")


def derive(record):
    accepted = [c for c in record["claims"] if c["source_status"] == "body_observed"]
    # Compare only explicitly supplied overlapping components, without calendar conversion.
    conflict = any(any(a[k] is not None and b[k] is not None and a[k] != b[k]
                       for k in ("year", "month", "day"))
                   for i, a in enumerate(accepted) for b in accepted[i + 1:])
    if conflict:
        return "conflicting_sources", ""
    if accepted:
        best = max(accepted, key=lambda c: {"year": 1, "month": 2, "day": 3}[c["precision"]])
        return {"day": "day_source_verified", "month": "month_only", "year": "year_only"}[best["precision"]], components_iso(best)
    if record["status"] == "blocked" and any(s["status"] == "blocked" for s in record["sources"]):
        return "blocked", ""
    return "not_found", ""


def institution_key(url):
    host = urlsplit(url).hostname.lower()
    if host == "mathshistory.st-andrews.ac.uk" or host.endswith(".st-andrews.ac.uk"):
        return "st-andrews.ac.uk"
    # Exact host is deliberately retained; no guessed public-suffix/institution mapping.
    return host


def cohort_summary(records):
    counts = dict(collections.Counter(r["derived_status"] for r in records))
    body_people = [r for r in records if any(c["source_status"] == "body_observed" for c in r["claims"])]
    single = 0
    mactutor = 0
    for r in body_people:
        accepted = [c for c in r["claims"] if c["source_status"] == "body_observed"]
        keys = {institution_key(c["source_url"]) for c in accepted}
        single += len(keys) == 1
        mactutor += any(urlsplit(c["source_url"]).hostname == "mathshistory.st-andrews.ac.uk" for c in accepted)
    return {"roster_count": len(records), "status_counts": counts,
            "body_date_claim_people": len(body_people),
            "source_day_coverage_count": counts.get("day_source_verified", 0),
            "single_institution_source_people": single,
            "mactutor_body_date_people": mactutor,
            "snippet_only_claim_count": sum(c["source_status"] == "search_snippet_only" for r in records for c in r["claims"])}


def aggregate(roster_payload, input_payloads):
    roster = roster_payload.get("rows") if isinstance(roster_payload, dict) else roster_payload
    require(isinstance(roster, list) and len(roster) == 68, "Fixed roster must contain 68 rows")
    by_id = {}
    for row in roster:
        require(isinstance(row, dict) and row.get("fields_id") and isinstance(row.get("name"), str) and row["name"].strip(), "Roster identity missing")
        require(row["fields_id"] not in by_id, "Duplicate fixed roster ID")
        require("wiles" not in row["name"].casefold(), "Wiles is excluded from Fields Medal roster")
        require(type(row.get("award_year")) is int, "Invalid award year")
        require(type(row.get("original_through_2025")) is bool and type(row.get("award_declined")) is bool, "Roster flags missing")
        require((row["original_through_2025"] and row["award_year"] <= 2025)
                or (not row["original_through_2025"] and row["award_year"] == 2026), "Invalid main/extension roster split")
        by_id[row["fields_id"]] = row
    require(sum(r["original_through_2025"] for r in roster) == 64, "Roster requires 64 main and 4 extension rows")
    received = {}
    for payload in input_payloads:
        require(isinstance(payload, dict) and payload.get("schema_version") == 1 and isinstance(payload.get("records"), list), "Invalid shard schema")
        for record in payload["records"]:
            require(isinstance(record, dict), "Record must be an object")
            fid = record.get("fields_id")
            require(fid in by_id, "Unexpected record ID")
            require(fid not in received, "Duplicate record ID")
            row = by_id[fid]
            require(record.get("name") == row["name"] and record.get("award_year") == row["award_year"], "Record name/award year differs from fixed roster")
            require(record.get("status") in STATUSES, "Invalid collection status")
            for key, limit in (("search_queries_used", 2), ("body_candidates_opened", 2), ("direct_cv_attempts", 1)):
                require(type(record.get(key)) is int and 0 <= record[key] <= limit, f"Collection budget exceeded or missing: {key}")
            require(isinstance(record.get("sources"), list) and isinstance(record.get("claims"), list), "Sources/claims must be lists")
            for source in record["sources"]:
                require(isinstance(source, dict), "Source ledger entry must be an object")
                safe_url(source.get("url"))
                require(source.get("status") in SOURCE_STATUSES, "Invalid source ledger status")
            for claim in record["claims"]:
                validate_claim(claim, record["sources"])
            result = copy.deepcopy(record)
            result["award_declined"] = row["award_declined"]
            result["original_through_2025"] = row["original_through_2025"]
            result["cohort"] = "main" if row["original_through_2025"] else "extension2026"
            result["derived_status"], result["source_date_components_iso"] = derive(record)
            received[fid] = result
    require(set(received) == set(by_id), "Missing fixed roster records")
    records = [received[r["fields_id"]] for r in roster]
    summary = {"schema_version": 1,
               "main": cohort_summary([r for r in records if r["cohort"] == "main"]),
               "extension2026": cohort_summary([r for r in records if r["cohort"] == "extension2026"]),
               "collection_first_pass_complete": True, "final_analysis_cohort_freeze": False,
               "bazi_record_count": 0, "analysis_record_count": 0,
               "calendar_conversion_performed": False,
               "coverage_rule": "Only body_observed date claims count; no partial components are filled.",
               "institution_dependency_rule": "Exact source host, except St Andrews subdomains grouped; not independent-source verification."}
    return records, summary


def write_csv(path, columns, rows):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def export(records, summary, output_dir, input_paths=()):
    out = Path(output_dir)
    require(not out.exists(), "Output directory must be fresh")
    out.mkdir(parents=True)
    roster_columns = ["fields_id", "name", "award_year", "award_declined", "cohort", "status", "derived_status", "source_date_components_iso", "calendars", "accepted_body_claim_count", "snippet_claim_count", "review_note"]
    claim_columns = ["fields_id", "name", "award_year", "award_declined", "cohort", "claim_index", "source_date_components_iso", "date_raw", "precision", "year", "month", "day", "calendar", "source_url", "source_type", "source_status", "counts_toward_body_coverage", "excerpt", "identity_note", "birthplace_raw"]
    source_columns = ["fields_id", "name", "award_year", "cohort", "source_index", "url", "status", "access_method", "note"]
    for cohort in ("main", "extension2026"):
        people = [r for r in records if r["cohort"] == cohort]
        rows = []
        claims = []
        sources = []
        for r in people:
            rows.append(dict(r, calendars="|".join(sorted({c["calendar"] for c in r["claims"]})), accepted_body_claim_count=sum(c["source_status"] == "body_observed" for c in r["claims"]), snippet_claim_count=sum(c["source_status"] == "search_snippet_only" for c in r["claims"])))
            for i, c in enumerate(r["claims"], 1):
                claims.append(dict(c, **{k: r[k] for k in ("fields_id", "name", "award_year", "award_declined", "cohort")}, claim_index=i, source_date_components_iso=components_iso(c), counts_toward_body_coverage=c["source_status"] == "body_observed"))
            for i, source in enumerate(r["sources"], 1):
                sources.append(dict(source, **{k: r[k] for k in ("fields_id", "name", "award_year", "cohort")}, source_index=i))
        write_csv(out / f"{cohort}_roster.csv", roster_columns, rows)
        write_csv(out / f"{cohort}_dob_source_ledger.csv", claim_columns, claims)
        write_csv(out / f"{cohort}_source_ledger.csv", source_columns, sources)
    queue = [r for r in records if r["derived_status"] != "day_source_verified"]
    write_csv(out / "missing_partial_queue.csv", roster_columns, queue)
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["Fields Medal source collection: first pass complete.", "Final analysis cohort freeze: false. BaZi: 0. Analysis: 0.", "Dates are source components; no calendar conversion or Gregorian acceptance asserted."]
    for group in ("main", "extension2026"):
        s = summary[group]
        lines.extend([f"{group}: {s['roster_count']} fixed roster people; {s['source_day_coverage_count']} body-source day claims.", f"  Statuses: {json.dumps(s['status_counts'], sort_keys=True)}", f"  Single institution source dependence: {s['single_institution_source_people']}; MacTutor: {s['mactutor_body_date_people']}."])
    (out / "summary.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    manifest = {"algorithm": "sha256", "outputs": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.iterdir())}, "inputs": [{"name": Path(p).name, "sha256": hashlib.sha256(Path(p).read_bytes()).hexdigest()} for p in input_paths]}
    (out / "hash_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--roster", type=Path, required=True)
    parser.add_argument("--inputs", type=Path, nargs=5, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        roster = json.loads(args.roster.read_text(encoding="utf-8"))
        shards = [json.loads(p.read_text(encoding="utf-8")) for p in args.inputs]
        records, summary = aggregate(roster, shards)
        export(records, summary, args.output_dir, [args.roster, *args.inputs])
    except (ValueError, OSError) as error:
        parser.error(str(error))
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
