#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Validate a yearly birthdate + occupation dataset before running replication analysis.

Example:
python validate_year_dataset.py ^
  --year 1987 ^
  --birth-people birthdate_scan_1987\1987_people.csv ^
  --occupation-people occupation_scan_1987\1987_people_with_occupations.csv ^
  --daily occupation_scan_1987\1987_daily_category_stats.csv

The script DOES NOT inspect/rank high-Music dates.
It only checks structural/data-integrity properties, to avoid contaminating
a preregistered replication.
"""

import argparse
import calendar
from pathlib import Path

import pandas as pd


def parse_bool_series(s):
    return (
        s.astype(str)
         .str.strip()
         .str.lower()
         .map({"true": True, "false": False, "1": True, "0": False})
         .fillna(False)
    )


def fail(msg):
    raise SystemExit(f"FAIL: {msg}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--birth-people", required=True)
    ap.add_argument("--occupation-people", required=True)
    ap.add_argument("--daily", required=True)
    args = ap.parse_args()

    year = args.year
    bp_path = Path(args.birth_people)
    op_path = Path(args.occupation_people)
    daily_path = Path(args.daily)

    for p in [bp_path, op_path, daily_path]:
        if not p.exists():
            fail(f"missing file: {p}")

    bp = pd.read_csv(bp_path, dtype={"qid": str, "dob": str})
    op = pd.read_csv(op_path, dtype={"qid": str})
    daily = pd.read_csv(daily_path)

    print("=" * 72)
    print(f"VALIDATING YEAR {year}")
    print("=" * 72)

    # ------------------------------------------------------------
    # 1. Birth-person file
    # ------------------------------------------------------------
    required_bp = {"qid", "dob"}
    missing = required_bp - set(bp.columns)
    if missing:
        fail(f"birth people file missing columns: {sorted(missing)}")

    bp["dob_dt"] = pd.to_datetime(bp["dob"], errors="coerce")
    if bp["dob_dt"].isna().any():
        fail(f"birth people has {bp['dob_dt'].isna().sum()} invalid DOB values")

    wrong_year = bp["dob_dt"].dt.year.ne(year)
    if wrong_year.any():
        fail(f"birth people has {wrong_year.sum()} DOB rows outside {year}")

    if "dob_conflict" in bp.columns:
        bp["dob_conflict_bool"] = parse_bool_series(bp["dob_conflict"])
    else:
        bp["dob_conflict_bool"] = False

    bp_clean = bp.loc[~bp["dob_conflict_bool"]].copy()

    dup_clean_qid = bp_clean["qid"].duplicated().sum()
    if dup_clean_qid:
        fail(f"birth people clean set has {dup_clean_qid} duplicate QIDs")

    print(f"[OK] Birth people rows: {len(bp):,}")
    print(f"[OK] Unique QIDs: {bp['qid'].nunique():,}")
    print(f"[OK] DOB-conflict QIDs excluded: "
          f"{bp.loc[bp['dob_conflict_bool'], 'qid'].nunique():,}")
    print(f"[OK] Clean unique people expected downstream: {bp_clean['qid'].nunique():,}")

    # ------------------------------------------------------------
    # 2. Occupation-person file
    # ------------------------------------------------------------
    required_op = {"qid"}
    missing = required_op - set(op.columns)
    if missing:
        fail(f"occupation people file missing columns: {sorted(missing)}")

    if op["qid"].duplicated().any():
        fail(f"occupation people has {op['qid'].duplicated().sum()} duplicate QIDs")

    birth_qids = set(bp_clean["qid"])
    occ_qids = set(op["qid"])

    missing_from_occ = birth_qids - occ_qids
    extra_in_occ = occ_qids - birth_qids

    if missing_from_occ:
        fail(f"{len(missing_from_occ)} clean birth QIDs missing from occupation file")
    if extra_in_occ:
        fail(f"{len(extra_in_occ)} occupation QIDs not present in clean birth file")

    print(f"[OK] Occupation people rows: {len(op):,}")
    print(f"[OK] Occupation QIDs exactly match clean birth QIDs")

    if "has_p106" in op.columns:
        p106 = parse_bool_series(op["has_p106"])
        cov = p106.mean()
        print(f"[OK] P106 coverage: {p106.sum():,}/{len(op):,} ({cov:.2%})")
        if cov < 0.95:
            print("WARNING: P106 coverage is below 95%; inspect before analysis.")

    # ------------------------------------------------------------
    # 3. Daily stats
    # ------------------------------------------------------------
    required_daily = {"date", "n_people", "Music__n"}
    missing = required_daily - set(daily.columns)
    if missing:
        fail(f"daily stats missing columns: {sorted(missing)}")

    daily["date_dt"] = pd.to_datetime(daily["date"], errors="coerce")
    if daily["date_dt"].isna().any():
        fail(f"daily stats has {daily['date_dt'].isna().sum()} invalid dates")

    expected_days = 366 if calendar.isleap(year) else 365

    if len(daily) != expected_days:
        fail(f"daily stats has {len(daily)} rows; expected {expected_days}")

    if daily["date_dt"].duplicated().any():
        fail(f"daily stats has duplicate dates")

    expected_index = pd.date_range(f"{year}-01-01", f"{year}-12-31", freq="D")
    got_index = pd.DatetimeIndex(sorted(daily["date_dt"]))
    if not got_index.equals(expected_index):
        missing_dates = expected_index.difference(got_index)
        extra_dates = got_index.difference(expected_index)
        fail(
            f"daily dates are not complete. missing={list(missing_dates[:5])}, "
            f"extra={list(extra_dates[:5])}"
        )

    for col in ["n_people", "Music__n"]:
        daily[col] = pd.to_numeric(daily[col], errors="coerce")
        if daily[col].isna().any():
            fail(f"{col} contains non-numeric values")
        if (daily[col] < 0).any():
            fail(f"{col} contains negative values")

    if (daily["Music__n"] > daily["n_people"]).any():
        fail("some Music__n values exceed n_people")

    daily_people_sum = int(daily["n_people"].sum())
    if daily_people_sum != len(op):
        fail(
            f"sum(daily n_people)={daily_people_sum:,} "
            f"but occupation people rows={len(op):,}"
        )

    print(f"[OK] Daily rows: {len(daily)} ({expected_days} expected)")
    print(f"[OK] All calendar dates from {year}-01-01 through {year}-12-31 present")
    print(f"[OK] Sum of daily people = {daily_people_sum:,} = occupation people rows")
    print(f"[OK] Total Music count = {int(daily['Music__n'].sum()):,}")
    print(f"[OK] Music count never exceeds total people")

    # ------------------------------------------------------------
    # 4. Broad-category consistency (if present)
    # ------------------------------------------------------------
    music_pct_col = "Music__pct"
    if music_pct_col in daily.columns:
        calc = daily["Music__n"] / daily["n_people"].replace(0, pd.NA) * 100
        diff = (calc - pd.to_numeric(daily[music_pct_col], errors="coerce")).abs()
        max_diff = diff.dropna().max() if diff.notna().any() else 0.0
        if max_diff > 1e-6:
            fail(f"Music__pct inconsistent with Music__n/n_people; max diff={max_diff}")
        print(f"[OK] Music__pct matches Music__n / n_people")

    print("=" * 72)
    print("PASS: dataset is structurally consistent for preregistered analysis.")
    print("This validator intentionally did NOT rank dates by Music rate.")
    print("=" * 72)


if __name__ == "__main__":
    main()
