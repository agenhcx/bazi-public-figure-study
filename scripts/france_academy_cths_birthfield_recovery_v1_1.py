#!/usr/bin/env python3
"""Reparse 33 frozen CTHS birth-field exceptions, entirely offline.

This produces an ADDITIVE candidate-delta; original 562-row DOB CSV and
source archive are never modified. No DOB/member acceptance or BaZi analysis.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path

SRC = Path("data/france_academy_cths_profile_dob_harvest_v1/cths_dob_claims_all_targets_candidate_only_v1.csv")
OUT = Path("local_runs/france_academy_cths_birthfield_recovery_v1_1")
MONTHS = dict(zip(
    "janvier fevrier mars avril mai juin juillet aout septembre octobre novembre decembre".split(),
    range(1, 13)))
MONTH_TYPOS = {"avil": "avril", "fevier": "fevrier"}
DATE_RE = re.compile(
    r"^(?P<day>1er|1ere|[1-9]|[12]\d|3[01])\s+"
    r"(?P<month>[a-z]+)\s+(?P<year>1[6789]\d{2}|20[012]\d)\b", re.I)


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", (s or "").casefold())
    return "".join(c for c in s if not unicodedata.combining(c))


def csv_read(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def csv_write(path: Path, rows: list[dict], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def file_sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for data in iter(lambda: f.read(1024 * 1024), b""):
            h.update(data)
    return h.hexdigest()


def parse(raw: str, expected_year: int) -> tuple[str, str, str]:
    s = norm(raw.strip())
    if not s:
        return "missing_birth_field", "", "No birth date recorded"
    if re.match(r"^1er\s+juin\s+ou\s+juillet\s+1902\b", s):
        return "ambiguous_month_unresolved", "", "The source explicitly says June OR July"
    match = DATE_RE.match(s)
    if match is None:
        if re.match(r"^\d{4}\b", s):
            return "year_only_unresolved", "", "Year without month/day"
        return "unparsed_manual_review", "", "Date syntax not recognized"
    word = match.group("month")
    month = MONTH_TYPOS.get(word, word)
    if month not in MONTHS:
        return "unparsed_manual_review", "", "Month word not recognized"
    day_text = match.group("day")
    day = 1 if day_text.startswith("1er") else int(day_text)
    year = int(match.group("year"))
    try:
        iso = dt.date(year, MONTHS[month], day).isoformat()
    except ValueError:
        return "invalid_date_unresolved", "", "Calendar-invalid field"
    if year != expected_year:
        return "year_conflict_unresolved", "", "Birth-year mismatch with frozen CTHS roster"
    if word in MONTH_TYPOS:
        return "month_typo_provisional_review", iso, "Source month spelling typo: " + word
    if day_text in ("1er", "1ere"):
        return "ordinal_1er_recovered_candidate", iso, "French first-day ordinal"
    return "numeric_unexpected_parser_gap", iso, "Unexpected old-parser gap; inspect"


def self_test() -> None:
    examples = [
        ("1er août 1924 à Dabrowica", 1924, "ordinal_1er_recovered_candidate", "1924-08-01"),
        ("1er avril 1933 à Constantine", 1933, "ordinal_1er_recovered_candidate", "1933-04-01"),
        ("16 avil 1887", 1887, "month_typo_provisional_review", "1887-04-16"),
        ("11 févier 1904", 1904, "month_typo_provisional_review", "1904-02-11"),
        ("1er juin ou juillet 1902", 1902, "ambiguous_month_unresolved", ""),
        ("1839 à Lyon", 1839, "year_only_unresolved", ""),
        ("", 1958, "missing_birth_field", ""),
    ]
    for text, year, expected_class, expected_date in examples:
        cls, date, _ = parse(text, year)
        if (cls, date) != (expected_class, expected_date):
            raise AssertionError((text, cls, date))


def main() -> int:
    self_test()
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, default=SRC)
    p.add_argument("--out", type=Path, default=OUT)
    args = p.parse_args()
    records = csv_read(args.input)
    if len(records) != 562 or len({r["cths_person_id"] for r in records}) != 562:
        raise RuntimeError("Expected unique 562-person frozen input")
    known = [r for r in records if r["cths_birth_parser_status"] == "candidate_exact_day"]
    old_failed = [r for r in records if r["cths_birth_parser_status"] != "candidate_exact_day"]
    if len(known) != 529 or len(old_failed) != 33:
        raise RuntimeError("V1 frozen parser counts changed unexpectedly")
    delta = []
    for r in sorted(old_failed, key=lambda v: int(v["cths_person_id"])):
        status, date, reason = parse(r["cths_birth_raw"], int(r["CTHS_roster_year_provisional"]))
        delta.append({
            "cths_person_id": r["cths_person_id"],
            "name": r["name"],
            "year_provisional": r["CTHS_roster_year_provisional"],
            "CTHS_birth_field_raw": r["cths_birth_raw"],
            "v1_1_status": status,
            "v1_1_date_candidate_only": date,
            "manual_review_note": reason if status != "ordinal_1er_recovered_candidate" else "",
            "source_url": r["url"],
            "source_sha256": r["source_raw_html_sha256"],
            "independent_dob_evidence_checked": "0",
            "official_full_member_verified": "0",
        })
    counts = Counter(r["v1_1_status"] for r in delta)
    expected = Counter({
        "ordinal_1er_recovered_candidate": 28,
        "month_typo_provisional_review": 2,
        "ambiguous_month_unresolved": 1,
        "year_only_unresolved": 1,
        "missing_birth_field": 1,
    })
    if counts != expected:
        raise RuntimeError(f"Classification drift; manual review required: {dict(counts)}")
    mixed = [r for r in records
             if r["CTHS_roster_membership_class_provisional"] == "full_and_foreign_mixed_manual"]
    if len(mixed) != 4:
        raise RuntimeError("Unexpected mixed membership count")
    manual = [r for r in delta if r["manual_review_note"]]
    for r in mixed:
        manual.append({
            "cths_person_id": r["cths_person_id"], "name": r["name"],
            "year_provisional": r["CTHS_roster_year_provisional"],
            "CTHS_birth_field_raw": r["cths_birth_raw"],
            "v1_1_status": "mixed_historical_membership",
            "v1_1_date_candidate_only": r["cths_exact_dob_claim_candidate_only"],
            "manual_review_note": "CTHS shows both full-like and foreign Academy classes",
            "source_url": r["url"], "source_sha256": r["source_raw_html_sha256"],
            "independent_dob_evidence_checked": "0", "official_full_member_verified": "0",
        })
    if len(manual) != 9 or len({r["cths_person_id"] for r in manual}) != 9:
        raise RuntimeError("Review queue should include 5 date anomalies and 4 mixed-status people")
    args.out.mkdir(parents=True, exist_ok=True)
    columns = list(delta[0])
    csv_write(args.out / "birthfield_parser_delta_33_v1_1.csv", delta, columns)
    csv_write(args.out / "manual_review_remaining_9_v1_1.csv", manual, columns)
    summary = {
        "parser_version": "france-academy-cths-birthfield-recovery-v1_1",
        "input_sha256": file_sha(args.input),
        "network_requests": 0,
        "frozen_original_CTHS_exact_DOB_claims": len(known),
        "new_1er_day_candidates": counts["ordinal_1er_recovered_candidate"],
        "typo_corrected_provisional_DOB_candidates": counts["month_typo_provisional_review"],
        "CTHS_exact_date_claims_with_unambiguous_date_syntax": len(known) + counts["ordinal_1er_recovered_candidate"],
        "possible_CTHS_exact_date_claims_after_typo_review": len(known) + counts["ordinal_1er_recovered_candidate"] + counts["month_typo_provisional_review"],
        "ambiguous_month": counts["ambiguous_month_unresolved"],
        "year_only": counts["year_only_unresolved"],
        "birth_field_missing": counts["missing_birth_field"],
        "mixed_historical_membership_for_separate_review": len(mixed),
        "unique_people_in_remaining_manual_review": len(manual),
        "independent_DOB_evidence_accepted": 0,
        "official_member_evidence_accepted_by_this_stage": 0,
        "bazi_variables_computed": 0,
        "warning": "No original v1 rows changed; extracted dates are not independently verified and first-day heaping still warrants provenance review.",
    }
    (args.out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
