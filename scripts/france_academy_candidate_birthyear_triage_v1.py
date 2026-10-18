#!/usr/bin/env python3
"""Analyze *candidate-source* year coverage without accepting France Academy membership or DOB.

No BaZi features and no inferential comparisons. Input comes from Wikidata P6282/P463
candidate snapshots; historical roster inclusion remains explicitly unresolved.
"""
from __future__ import annotations
import argparse
import csv
import datetime as dt
import json
from collections import Counter, defaultdict
from pathlib import Path

SUPPORT_MIN, SUPPORT_MAX = 1835, 1985


def read_csv(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict], headers: list[str]):
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--folder", default="data/france_academy_wikidata_candidate_discovery_v1")
    args = ap.parse_args()
    folder = Path(args.folder)
    people = read_csv(folder / "candidate_people_v1.csv")
    statuses = Counter()
    route_counts = Counter()
    decade = defaultdict(lambda: Counter())
    per_person = []

    for p in people:
        years = sorted(set(int(y) for y in p["birth_year_candidates"].split(" | ") if y.strip().isdigit()))
        has_official_id = bool(p["official_id_claims"].strip())
        routes = p["discovery_routes"].strip()
        route_counts[routes] += 1

        if not years:
            status = "birthyear_missing"
        elif len(years) > 1:
            status = "conflicting_birthyears_manual_review"
        elif SUPPORT_MIN <= years[0] <= SUPPORT_MAX:
            status = "candidate_in_primary_year_window"
        elif years[0] < SUPPORT_MIN:
            status = "candidate_before_window"
        else:
            status = "candidate_after_window"
        statuses[status] += 1
        if len(years) == 1:
            label = f"{(years[0] // 10) * 10}s"
            decade[label][status] += 1
            decade[label]["with_official_profile_id_claim"] += int(has_official_id)

        per_person.append({
            "qid": p["qid"],
            "candidate_name": p["name_candidate"],
            "birthyear_status_candidate_only": status,
            "birth_year_candidates": " | ".join(map(str, years)),
            "official_profile_id_claim": int(has_official_id),
            "discovery_routes": routes,
            "full_member_accepted": 0,
            "exact_dob_accepted": 0,
        })

    write_csv(folder / "candidate_birthyear_triage_v1.csv", per_person, [
        "qid", "candidate_name", "birthyear_status_candidate_only",
        "birth_year_candidates", "official_profile_id_claim", "discovery_routes",
        "full_member_accepted", "exact_dob_accepted"])
    write_csv(folder / "candidate_by_birth_decade_v1.csv",
              [{"decade": x, **dict(d)} for x, d in sorted(decade.items())],
              ["decade", "candidate_in_primary_year_window", "candidate_before_window",
               "candidate_after_window", "birthyear_missing", "with_official_profile_id_claim"])
    report = {
        "script": "france-academy-candidate-birthyear-triage-v1",
        "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "study_support_birthyears": [SUPPORT_MIN, SUPPORT_MAX],
        "candidate_source_rows": len(people),
        "candidate_birthyear_status_counts": dict(statuses),
        "candidate_discovery_route_counts": dict(route_counts),
        "verified_full_members": 0,
        "verified_exact_dobs": 0,
        "final_roster_frozen": False,
        "bazi_variables_computed": 0,
        "warning": "This is coverage of unverified Wikidata identity candidates, NOT DOB coverage of an accepted Academy cohort.",
    }
    (folder / "candidate_triage_summary_v1.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
