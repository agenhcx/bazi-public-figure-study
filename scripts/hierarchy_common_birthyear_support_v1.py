#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


DEFAULT_NOBEL = Path("data/nobel_science_enriched_v1/nobel_science_people.csv")
DEFAULT_OUT = Path("data/hierarchy_common_birthyear_support_v1")


def read_csv(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows, fields=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        fields = list(rows[0].keys()) if rows else []
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def sha256(path: Path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def present(v):
    return str(v or "").strip() not in {"", "nan", "None", "null"}


def extract_year(*values):
    for v in values:
        s = str(v or "").strip()
        m = re.search(r"(?<!\d)(1[0-9]{3}|20[0-9]{2})(?!\d)", s)
        if m:
            return int(m.group(1))
    return None


def exact_iso_date(v):
    s = str(v or "").strip()
    return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", s))


def first_present(row, fields):
    for f in fields:
        if f in row and present(row.get(f)):
            return str(row.get(f)).strip()
    return ""


def load_nobel(path: Path):
    if not path.exists():
        raise RuntimeError(
            f"Frozen Nobel person-level roster not found: {path}\n"
            "Expected the DOB-enriched v1 roster created before hierarchy unblinding."
        )
    rows = read_csv(path)
    if len(rows) != 658:
        raise RuntimeError(f"Expected 658 unique Nobel science laureates, got {len(rows)}")
    ids = [str(r.get("laureate_id") or "").strip() for r in rows]
    if len(set(ids)) != 658 or any(not x for x in ids):
        raise RuntimeError("Nobel laureate_id uniqueness invariant failed")

    parsed = []
    for r in rows:
        year = extract_year(r.get("birth_date"), r.get("birth_year"), r.get("known_year"))
        parsed.append((r, year))

    missing = [r for r, y in parsed if y is None]
    if missing:
        names = [
            first_present(r, ["full_name", "known_name", "name"]) or str(r.get("laureate_id") or "")
            for r in missing[:10]
        ]
        raise RuntimeError(f"Expected known birth year for all 658 Nobel people; missing {len(missing)}: {names}")

    years = [y for _, y in parsed]
    exact_count = sum(
        str(r.get("birth_date_exact") or "").strip() == "1" or exact_iso_date(r.get("birth_date"))
        for r, _ in parsed
    )
    return rows, parsed, min(years), max(years), exact_count


def summarize_candidate_file(label, path, dob_fields):
    if not path.exists():
        return {
            "cohort": label,
            "status": "not_found",
            "path": str(path),
            "input_rows": "",
            "known_birthyear_rows": "",
            "in_window_rows": "",
            "below_window_rows": "",
            "above_window_rows": "",
            "unknown_birthyear_rows": "",
            "sha256": "",
        }, []

    rows = read_csv(path)
    out = []
    for r in rows:
        value = first_present(r, dob_fields)
        y = extract_year(value)
        out.append((r, y))
    return {
        "cohort": label,
        "status": "loaded",
        "path": str(path),
        "input_rows": len(rows),
        "sha256": sha256(path),
    }, out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nobel", default=str(DEFAULT_NOBEL))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    args = ap.parse_args()

    nobel_path = Path(args.nobel)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    nobel_rows, nobel_parsed, ymin, ymax, exact_count = load_nobel(nobel_path)
    year_counts = Counter(y for _, y in nobel_parsed)

    dist = []
    for y in range(ymin, ymax + 1):
        dist.append({
            "birth_year": y,
            "n_nobel_science_people": year_counts.get(y, 0),
            "within_support_window": 1,
            "bazi_variables_computed": 0,
        })
    write_csv(
        out / "nobel_birthyear_distribution.csv",
        dist,
        ["birth_year", "n_nobel_science_people", "within_support_window", "bazi_variables_computed"],
    )

    summary = {
        "dataset": "Nobel-supported hierarchy common birth-year window v1",
        "nobel_person_file": str(nobel_path),
        "nobel_person_file_sha256": sha256(nobel_path),
        "nobel_unique_people": len(nobel_rows),
        "nobel_known_birthyear_people": len(nobel_parsed),
        "nobel_exact_dob_people": exact_count,
        "nobel_min_birth_year": ymin,
        "nobel_max_birth_year": ymax,
        "eligibility_rule": f"{ymin} <= birth_year <= {ymax}",
        "window_definition": "Min/max known birth year among all 658 frozen Nobel science laureates; exact-DOB availability does not define the window.",
        "automatic_dob_changes": 0,
        "bazi_variables_computed": 0,
    }
    (out / "nobel_birthyear_support_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    candidates = [
        (
            "nas_science_core_v17",
            Path("data/nas_science_core_dob_crosswalk/nas_science_core_dob_crosswalk_v17.csv"),
            ["final_exact_dob", "exact_dob", "dob_exact_iso", "birth_date"],
        ),
        (
            "royal_society_past_exact",
            Path("data/royal_society_past_dob_closeout_v1/accepted_exact_dob_final_v1.csv"),
            ["exact_dob", "dob_exact_iso", "final_exact_dob", "birth_date"],
        ),
        (
            "royal_society_current_exact",
            Path("data/royal_society_dob_freeze_v1/royal_society_current_exact_dob_final_v1.csv"),
            ["exact_dob", "dob_exact_iso", "final_exact_dob", "birth_date"],
        ),
        (
            "leopoldina_unique_day_candidate",
            Path("data/leopoldina_dob_local_v1/candidate_unique_day_p569_v1.csv"),
            ["candidate_exact_dob", "final_exact_dob", "birth_date"],
        ),
    ]

    cohort_summary = []
    for label, path, fields in candidates:
        meta, parsed = summarize_candidate_file(label, path, fields)
        if meta["status"] == "loaded":
            ys = [y for _, y in parsed if y is not None]
            meta.update({
                "known_birthyear_rows": len(ys),
                "in_window_rows": sum(ymin <= y <= ymax for y in ys),
                "below_window_rows": sum(y < ymin for y in ys),
                "above_window_rows": sum(y > ymax for y in ys),
                "unknown_birthyear_rows": len(parsed) - len(ys),
            })
        cohort_summary.append(meta)

    write_csv(
        out / "cohort_birthyear_eligibility_summary.csv",
        cohort_summary,
        [
            "cohort", "status", "path", "input_rows", "known_birthyear_rows",
            "in_window_rows", "below_window_rows", "above_window_rows",
            "unknown_birthyear_rows", "sha256",
        ],
    )

    manifest = {
        "dataset": "Hierarchy common birth-year support v1",
        "rule_frozen_before_bazi_unblinding": 1,
        "nobel_support": summary,
        "cohort_eligibility_summary": cohort_summary,
        "notes": [
            "Full historical academy rosters remain unchanged.",
            "Only primary hierarchy eligibility is restricted to the Nobel-supported birth-year interval.",
            "Exact DOB remains required for downstream BaZi analysis but is not required to define the support window.",
            "Further downstream models must control birth-year/era structure within the support window.",
        ],
        "bazi_variables_computed": 0,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
