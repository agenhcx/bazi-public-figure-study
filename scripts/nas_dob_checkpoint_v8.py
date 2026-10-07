#!/usr/bin/env python3
# Triggered through PR CI so checkpoint artifacts are retrievable for audit.
from __future__ import annotations

import csv
import json
from pathlib import Path

BASE = Path("data/nas_science_core_dob_crosswalk")
V7 = BASE / "nas_science_core_dob_crosswalk_v8.csv"
AVAIL = BASE / "nas_science_core_dob_availability_v1.csv"
WIKI = BASE / "nas_wikipedia_birthdate_diagnostic.csv"

OUT_UNRESOLVED = BASE / "nas_science_core_dob_unresolved_v8.csv"
OUT_WIKI = BASE / "nas_wikipedia_supplement_candidates_v8.csv"
OUT_CONFLICTS = BASE / "nas_wikipedia_validation_conflicts_v8.csv"
OUT_SUMMARY = BASE / "summary_checkpoint_v8.json"

def read_csv(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def write_csv(path: Path, rows, fields=None):
    if fields is None:
        fields = list(rows[0].keys()) if rows else []
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

def present(v):
    return str(v or "").strip() not in ("", "nan", "None")

rows = read_csv(V7)
if len(rows) != 3051:
    raise RuntimeError(f"Expected 3051 v7 rows, got {len(rows)}")

avail_by_url = {}
if AVAIL.exists():
    avail_by_url = {r["profile_url"]: r for r in read_csv(AVAIL)}

wiki_rows = read_csv(WIKI) if WIKI.exists() else []
wiki_missing = {
    r["profile_url"]: r
    for r in wiki_rows
    if r.get("purpose") == "missing"
}
wiki_validation = [r for r in wiki_rows if r.get("purpose") == "validation"]

unresolved = []
for r in rows:
    if present(r.get("final_exact_dob")):
        continue
    a = avail_by_url.get(r["profile_url"], {})
    w = wiki_missing.get(r["profile_url"], {})
    unresolved.append({
        "profile_url": r.get("profile_url", ""),
        "name": r.get("name", ""),
        "affiliation": r.get("affiliation", ""),
        "election_year": r.get("election_year", ""),
        "membership_type": r.get("membership_type", ""),
        "deceased": r.get("deceased", ""),
        "primary_section": r.get("primary_section", ""),
        "secondary_section": r.get("secondary_section", ""),
        "dob_status": r.get("dob_status", ""),
        "wikidata_qid": r.get("wikidata_qid", ""),
        "wikidata_match_method": r.get("wikidata_match_method", ""),
        "global_candidate_qid": r.get("global_candidate_qid", ""),
        "global_match_accepted": r.get("global_match_accepted", ""),
        "birth_year_known": a.get("birth_year_known", ""),
        "birth_year": a.get("birth_year", ""),
        "birth_year_source": a.get("birth_year_source", ""),
        "birth_year_conflict": a.get("birth_year_conflict", ""),
        "enwiki_title": w.get("enwiki_title", ""),
        "wikipedia_birth_date_values": w.get("wikipedia_birth_date_values", ""),
        "wikipedia_birth_date_count": w.get("wikipedia_birth_date_count", ""),
        "wikipedia_age_at_election": w.get("wikipedia_age_at_election", ""),
        "wikipedia_age_plausible": w.get("wikipedia_age_plausible", ""),
        "wikipedia_candidate_for_supplement": w.get("candidate_for_supplement", ""),
        "manual_review_status": r.get("manual_review_status", ""),
        "manual_review_note": r.get("manual_review_note", ""),
    })

write_csv(OUT_UNRESOLVED, unresolved)

wiki_candidates = [
    r for r in unresolved
    if str(r.get("wikipedia_candidate_for_supplement", "")).strip() == "1"
    and r.get("manual_review_status", "") != "unresolved_conflict"
]
write_csv(OUT_WIKI, wiki_candidates)

conflicts = [
    r for r in wiki_validation
    if r.get("validation_comparison") == "conflict"
]
write_csv(OUT_CONFLICTS, conflicts)

living = [r for r in rows if r.get("deceased") != "Y"]
dead = [r for r in rows if r.get("deceased") == "Y"]
living_unresolved = [r for r in unresolved if r.get("deceased") != "Y"]
dead_unresolved = [r for r in unresolved if r.get("deceased") == "Y"]

summary = {
    "dataset": "NAS science-core DOB checkpoint after audited supplement v2",
    "science_core_rows": len(rows),
    "final_exact_dob_rows_v8": sum(present(r.get("final_exact_dob")) for r in rows),
    "final_exact_dob_coverage_v8": round(sum(present(r.get("final_exact_dob")) for r in rows) / len(rows), 6),
    "remaining_without_exact_dob": len(unresolved),
    "living_rows": len(living),
    "living_exact_dob_rows": sum(present(r.get("final_exact_dob")) for r in living),
    "living_remaining_without_exact_dob": len(living_unresolved),
    "deceased_rows": len(dead),
    "deceased_exact_dob_rows": sum(present(r.get("final_exact_dob")) for r in dead),
    "deceased_remaining_without_exact_dob": len(dead_unresolved),
    "unresolved_with_birth_year_known": sum(str(r.get("birth_year_known", "")).strip() == "1" for r in unresolved),
    "unresolved_with_wikipedia_unique_exact_date": sum(str(r.get("wikipedia_birth_date_count", "")).strip() == "1" for r in unresolved),
    "wikipedia_supplement_candidates_after_v7": len(wiki_candidates),
    "wikipedia_validation_rows": len(wiki_validation),
    "wikipedia_validation_comparable_rows": sum(r.get("validation_comparison") in ("match", "conflict") for r in wiki_validation),
    "wikipedia_validation_matches": sum(r.get("validation_comparison") == "match" for r in wiki_validation),
    "wikipedia_validation_conflicts": len(conflicts),
    "wikipedia_validation_match_rate": (
        round(
            sum(r.get("validation_comparison") == "match" for r in wiki_validation)
            / sum(r.get("validation_comparison") in ("match", "conflict") for r in wiki_validation),
            6,
        )
        if sum(r.get("validation_comparison") in ("match", "conflict") for r in wiki_validation)
        else None
    ),
    "bazi_variables_computed": 0,
    "policy_note": (
        "Checkpoint after audited supplement v2. Only independently audited candidates are "
        "accepted; remaining Wikipedia candidates stay unresolved for further review."
    ),
}
OUT_SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(summary, ensure_ascii=False, indent=2))
