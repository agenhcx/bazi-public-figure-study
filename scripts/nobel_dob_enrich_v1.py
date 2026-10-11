#!/usr/bin/env python3
"""
Create Nobel science DOB-enriched roster v1 WITHOUT modifying the frozen raw roster.

Input:
  data/nobel_science_master/
    nobel_science_people.csv
    nobel_science_awards.csv
    manifest.json

Output (default):
  data/nobel_science_enriched_v1/
    nobel_science_people.csv
    nobel_science_awards.csv
    nobel_science_summary.csv
    dob_enrichment_log.csv
    dob_unresolved.csv
    manifest.json

Important:
- No BaZi variables are computed.
- The frozen raw roster is never modified.
- Only 10 exact DOB enrichments are applied.
- Michael Houghton, Ardem Patapoutian, and John Jumper remain unresolved.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any


# Exact DOB enrichments frozen for v1.
# We deliberately DO NOT include:
#   986 Michael Houghton: reliable public sources currently give only 1949.
#   998 Ardem Patapoutian: conflicting public sources (1967-10-01 vs 1967-10-02).
#   1041 John Jumper: reliable public sources currently give only 1985;
#                     some secondary pages expand this to Jan 1 without adequate support.
ENRICHMENTS = {
    "1050": {
        "name": "John Clarke",
        "birth_date": "1942-02-10",
        "confidence": "medium",
        "source_label": "Wikidata / public biography",
        "source_url": "https://www.wikidata.org/wiki/Q555849",
    },
    "1030": {
        "name": "Louis E. Brus",
        "birth_date": "1943-08-10",
        "confidence": "high",
        "source_label": "PNAS biographical memorial",
        "source_url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC13367852/",
    },
    "1031": {
        "name": "Aleksey Yekimov",
        "birth_date": "1945-02-28",
        "confidence": "medium",
        "source_label": "Wikidata",
        "source_url": "https://www.wikidata.org/wiki/Q1547368",
    },
    "1036": {
        "name": "Gary Ruvkun",
        "birth_date": "1952-03-26",
        "confidence": "medium",
        "source_label": "Wikidata / public biography",
        "source_url": "https://www.wikidata.org/wiki/Q504021",
    },
    "841": {
        "name": "Venkatraman Ramakrishnan",
        "birth_date": "1952-04-04",
        "confidence": "high",
        "source_label": "Academy of Achievement via Wikidata",
        "source_url": "https://achievement.org/achiever/venki-ramakrishnan-ph-d/",
    },
    "1051": {
        "name": "Michel H. Devoret",
        "birth_date": "1953-03-05",
        "confidence": "high",
        "source_label": "Astro-Databank; source note says quoted birth certificate",
        "source_url": "https://www.astro.com/astro-databank/Devoret,_Michel",
    },
    "1052": {
        "name": "John M. Martinis",
        "birth_date": "1958-07-13",
        "confidence": "high",
        "source_label": "Wikidata; references include GND and Ancestry",
        "source_url": "https://www.wikidata.org/wiki/Q28976188",
    },
    "864": {
        "name": "Saul Perlmutter",
        "birth_date": "1959-09-22",
        "confidence": "high",
        "source_label": "Wikidata / public biography",
        "source_url": "https://www.wikidata.org/wiki/Q106949",
    },
    "1029": {
        "name": "Moungi G. Bawendi",
        "birth_date": "1961-03-15",
        "confidence": "high",
        "source_label": "Wikidata; stated in IdRef",
        "source_url": "https://www.wikidata.org/wiki/Q15433043",
    },
    "1039": {
        "name": "David Baker",
        "birth_date": "1962-10-06",
        "confidence": "medium",
        "source_label": "Wikidata / public biography",
        "source_url": "https://www.wikidata.org/wiki/Q3814528",
    },
}

UNRESOLVED = [
    {
        "laureate_id": "986",
        "name": "Michael Houghton",
        "known_year": "1949",
        "reason": "Reliable public sources currently confirm only birth year 1949.",
        "candidate_dates": "",
    },
    {
        "laureate_id": "998",
        "name": "Ardem Patapoutian",
        "known_year": "1967",
        "reason": (
            "Conflicting sources: Scripps CV says 1967-10-01, while Wikidata "
            "cites a public post by Patapoutian for 1967-10-02. Keep unresolved."
        ),
        "candidate_dates": "1967-10-01; 1967-10-02",
    },
    {
        "laureate_id": "1041",
        "name": "John Jumper",
        "known_year": "1985",
        "reason": (
            "Nobel/Lindau-style authoritative biographies give only 1985; "
            "do not treat secondary 1985-01-01 values as exact without stronger evidence."
        ),
        "candidate_dates": "",
    },
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        if not rows:
            raise RuntimeError(f"Cannot infer CSV fields for empty file: {path}")
        fields = list(rows[0].keys())
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def exact_date(s: str) -> bool:
    try:
        dt.date.fromisoformat(s)
        return len(s) == 10
    except Exception:
        return False


def get_name(row: dict[str, str]) -> str:
    return (
        row.get("full_name")
        or row.get("known_name")
        or row.get("name")
        or ""
    ).strip()


def apply_to_people(people: list[dict[str, str]]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    by_id = {r.get("laureate_id", ""): r for r in people}
    log: list[dict[str, str]] = []

    for lid, e in ENRICHMENTS.items():
        if lid not in by_id:
            raise RuntimeError(f"Enrichment laureate_id {lid} not found in people CSV")

        row = by_id[lid]
        old = row.get("birth_date", "")
        old_exact = row.get("birth_date_exact", "")

        # Safety: the official/raw year must match the enrichment year.
        new_year = e["birth_date"][:4]
        old_year = old[:4] if len(old) >= 4 else ""
        if old_year and old_year != new_year:
            raise RuntimeError(
                f"Year mismatch for laureate {lid} {get_name(row)}: raw={old}, new={e['birth_date']}"
            )

        # If an exact date already exists, do not silently replace a conflict.
        if old_exact == "1" and old and old != e["birth_date"]:
            raise RuntimeError(
                f"Existing exact DOB conflict for laureate {lid}: raw={old}, new={e['birth_date']}"
            )

        row["birth_date"] = e["birth_date"]
        row["birth_date_exact"] = "1"

        log.append({
            "laureate_id": lid,
            "name": get_name(row) or e["name"],
            "old_birth_date": old,
            "new_birth_date": e["birth_date"],
            "confidence": e["confidence"],
            "source_label": e["source_label"],
            "source_url": e["source_url"],
        })

    return people, log


def apply_to_awards(awards: list[dict[str, str]]) -> list[dict[str, str]]:
    seen = set()
    for row in awards:
        lid = row.get("laureate_id", "")
        if lid not in ENRICHMENTS:
            continue
        e = ENRICHMENTS[lid]
        old = row.get("birth_date", "")
        old_year = old[:4] if len(old) >= 4 else ""
        new_year = e["birth_date"][:4]
        if old_year and old_year != new_year:
            raise RuntimeError(
                f"Award-row year mismatch for laureate {lid}: raw={old}, new={e['birth_date']}"
            )
        row["birth_date"] = e["birth_date"]
        row["birth_date_exact"] = "1"
        seen.add(lid)

    missing = set(ENRICHMENTS) - seen
    if missing:
        raise RuntimeError(f"Enrichment IDs absent from awards CSV: {sorted(missing)}")

    return awards


def person_level_summary(
    awards: list[dict[str, str]],
    people: list[dict[str, str]],
) -> list[dict[str, Any]]:
    p_by_id = {p["laureate_id"]: p for p in people}

    categories = [
        ("Physics", "phy"),
        ("Chemistry", "che"),
        ("Physiology or Medicine", "med"),
    ]

    out = []
    for label, code in categories:
        rows = [r for r in awards if r.get("prize_category_code") == code]
        ids = sorted({r["laureate_id"] for r in rows})
        persons = [p_by_id[i] for i in ids]
        exact = sum(p.get("birth_date_exact") == "1" for p in persons)
        years = [int(r["award_year"]) for r in rows]

        out.append({
            "group": label,
            "award_rows_1901_2025": len(rows),
            "unique_people": len(persons),
            "exact_birth_date_people": exact,
            "missing_or_inexact_birth_date_people": len(persons) - exact,
            "earliest_award_year": min(years),
            "latest_award_year": max(years),
        })

    exact_all = sum(p.get("birth_date_exact") == "1" for p in people)
    years_all = [int(r["award_year"]) for r in awards]
    out.append({
        "group": "ALL_SCIENCE",
        "award_rows_1901_2025": len(awards),
        "unique_people": len(people),
        "exact_birth_date_people": exact_all,
        "missing_or_inexact_birth_date_people": len(people) - exact_all,
        "earliest_award_year": min(years_all),
        "latest_award_year": max(years_all),
    })
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--input-dir",
        default=r".\data\nobel_science_master",
        help="Frozen raw Nobel roster directory",
    )
    ap.add_argument(
        "--output-dir",
        default=r".\data\nobel_science_enriched_v1",
        help="DOB-enriched output directory",
    )
    args = ap.parse_args()

    src = Path(args.input_dir)
    out = Path(args.output_dir)

    people_path = src / "nobel_science_people.csv"
    awards_path = src / "nobel_science_awards.csv"
    raw_manifest_path = src / "manifest.json"

    for p in (people_path, awards_path, raw_manifest_path):
        if not p.exists():
            raise RuntimeError(f"Required input missing: {p}")

    if out.exists() and any(out.iterdir()):
        raise RuntimeError(
            f"Output directory already exists and is not empty: {out}\n"
            "Refusing to overwrite an existing enrichment snapshot."
        )
    out.mkdir(parents=True, exist_ok=True)

    people = read_csv(people_path)
    awards = read_csv(awards_path)

    before_exact = sum(p.get("birth_date_exact") == "1" for p in people)
    before_n = len(people)

    people, log = apply_to_people(people)
    awards = apply_to_awards(awards)

    # Verify every newly written date is syntactically valid.
    for row in people:
        if row.get("birth_date_exact") == "1" and not exact_date(row.get("birth_date", "")):
            raise RuntimeError(
                f"Invalid exact DOB after enrichment: {row.get('laureate_id')} {row.get('birth_date')}"
            )

    after_exact = sum(p.get("birth_date_exact") == "1" for p in people)

    # Frozen expectation for v1: 645 raw + 10 enriched = 655/658.
    if before_n != 658:
        raise RuntimeError(f"Unexpected unique person count: {before_n}, expected 658")
    if before_exact != 645:
        raise RuntimeError(f"Unexpected raw exact-DOB count: {before_exact}, expected 645")
    if after_exact != 655:
        raise RuntimeError(f"Unexpected enriched exact-DOB count: {after_exact}, expected 655")

    # Write enriched data.
    people_out = out / "nobel_science_people.csv"
    awards_out = out / "nobel_science_awards.csv"
    summary_out = out / "nobel_science_summary.csv"
    log_out = out / "dob_enrichment_log.csv"
    unresolved_out = out / "dob_unresolved.csv"

    write_csv(people_out, people)
    write_csv(awards_out, awards)
    summary = person_level_summary(awards, people)
    write_csv(
        summary_out,
        summary,
        fields=[
            "group",
            "award_rows_1901_2025",
            "unique_people",
            "exact_birth_date_people",
            "missing_or_inexact_birth_date_people",
            "earliest_award_year",
            "latest_award_year",
        ],
    )
    write_csv(
        log_out,
        log,
        fields=[
            "laureate_id",
            "name",
            "old_birth_date",
            "new_birth_date",
            "confidence",
            "source_label",
            "source_url",
        ],
    )
    write_csv(
        unresolved_out,
        UNRESOLVED,
        fields=[
            "laureate_id",
            "name",
            "known_year",
            "reason",
            "candidate_dates",
        ],
    )

    # Copy the frozen raw acquisition manifest verbatim for auditability.
    shutil.copy2(raw_manifest_path, out / "parent_raw_manifest.json")

    files_to_hash = [
        people_out,
        awards_out,
        summary_out,
        log_out,
        unresolved_out,
        out / "parent_raw_manifest.json",
    ]

    manifest = {
        "study": "Professor -> Academy -> Nobel/Fields academic-selection study",
        "dataset": "Nobel science DOB-enriched roster v1",
        "created_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "parent_dataset": str(src),
        "parent_git_tag_expected": "nobel-science-roster-raw-v1",
        "blinding_note": "No BaZi variables or hypothesis outcomes are computed.",
        "enrichment_rule": (
            "Apply only pre-reviewed exact DOB values listed in ENRICHMENTS. "
            "Ambiguous/conflicting cases remain unresolved."
        ),
        "raw_unique_person_count": before_n,
        "raw_exact_birth_date_person_count": before_exact,
        "enriched_exact_birth_date_person_count": after_exact,
        "unresolved_person_count": before_n - after_exact,
        "enriched_person_count": len(ENRICHMENTS),
        "unresolved_ids": [x["laureate_id"] for x in UNRESOLVED],
        "files": {
            str(p.name): {
                "sha256": sha256(p),
                "bytes": p.stat().st_size,
            }
            for p in files_to_hash
        },
    }
    manifest_path = out / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("DOB enrichment v1 complete.")
    print(f"  raw exact DOB:      {before_exact}/{before_n}")
    print(f"  enriched exact DOB: {after_exact}/{before_n}")
    print(f"  newly enriched:     {len(ENRICHMENTS)}")
    print(f"  unresolved:         {before_n - after_exact}")
    print(f"  output:             {out.resolve()}")
    print()
    print("Unresolved:")
    for x in UNRESOLVED:
        print(f"  {x['laureate_id']}  {x['name']}: {x['reason']}")
    print()
    print("No BaZi variables were computed.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())