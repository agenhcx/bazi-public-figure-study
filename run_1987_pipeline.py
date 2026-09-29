#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
One-shot 1987 replication pipeline.

Assumes the following files are in the current project directory:
  occupation_scan_1986.py
  validate_year_dataset.py
  bazi_hour_marginal_analysis_v2_prereg.py

And that birth-date fetching already finished:
  birthdate_scan_1987\1987_people.csv

Pipeline:
  1) Fetch/derive occupations for 1987
  2) Validate structural integrity
  3) Run preregistered 1987 BaZi/Music replication

Example:
  python run_1987_pipeline.py --proxy http://127.0.0.1:10808
"""

import argparse
import subprocess
import sys
from pathlib import Path


def run(cmd, title):
    print()
    print("=" * 80)
    print(title)
    print("=" * 80)
    print(" ".join(f'"{x}"' if " " in str(x) else str(x) for x in cmd))
    print()

    result = subprocess.run(cmd)
    if result.returncode != 0:
        raise SystemExit(
            f"\nFAILED during: {title}\n"
            f"Exit code: {result.returncode}"
        )


def require_file(path: Path, description: str):
    if not path.exists():
        raise SystemExit(
            f"Missing {description}:\n  {path}\n"
            f"Put this file in the expected location and rerun."
        )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=1987)
    ap.add_argument("--proxy", default="http://127.0.0.1:10808")
    ap.add_argument("--permutations", type=int, default=50000)
    ap.add_argument("--project-dir", default=".")
    args = ap.parse_args()

    year = args.year
    root = Path(args.project_dir).resolve()

    occupation_script = root / "occupation_scan_1986.py"
    validator_script = root / "validate_year_dataset.py"
    analysis_script = root / "bazi_hour_marginal_analysis_v2_prereg.py"

    birth_dir = root / f"birthdate_scan_{year}"
    birth_people = birth_dir / f"{year}_people.csv"

    occupation_dir = root / f"occupation_scan_{year}"
    occupation_people = occupation_dir / f"{year}_people_with_occupations.csv"
    daily_stats = occupation_dir / f"{year}_daily_category_stats.csv"

    require_file(birth_people, f"{year} birth people CSV")
    require_file(occupation_script, "occupation script")
    require_file(validator_script, "validator script")
    require_file(analysis_script, "preregistered v2 analysis script")

    py = sys.executable

    print("=" * 80)
    print(f"{year} REPLICATION PIPELINE")
    print("=" * 80)
    print(f"Project directory : {root}")
    print(f"Birth input       : {birth_people}")
    print(f"Occupation output : {occupation_dir}")
    print(f"Permutations      : {args.permutations:,}")
    print(f"Proxy             : {args.proxy}")
    print()
    print("This pipeline does NOT inspect or rank high-Music dates before analysis.")

    # Step 1: occupation fetch + broad category construction
    run(
        [
            py,
            str(occupation_script),
            "--input", str(birth_people),
            "--year", str(year),
            "--proxy", args.proxy,
            "--outdir", str(occupation_dir),
        ],
        f"STEP 1/3 — Fetch occupations and build {year} daily category stats",
    )

    require_file(occupation_people, f"{year} occupation people CSV")
    require_file(daily_stats, f"{year} daily category stats CSV")

    # Step 2: structural validation
    run(
        [
            py,
            str(validator_script),
            "--year", str(year),
            "--birth-people", str(birth_people),
            "--occupation-people", str(occupation_people),
            "--daily", str(daily_stats),
        ],
        f"STEP 2/3 — Validate {year} dataset integrity",
    )

    # Step 3: preregistered replication
    run(
        [
            py,
            str(analysis_script),
            "--input", str(daily_stats),
            "--year", str(year),
            "--permutations", str(args.permutations),
        ],
        f"STEP 3/3 — Run preregistered {year} replication",
    )

    analysis_dir = root / f"bazi_hour_marginal_{year}"
    summary = analysis_dir / f"{year}_hour_marginal_summary.txt"

    print()
    print("=" * 80)
    print("PIPELINE COMPLETE")
    print("=" * 80)
    print(f"Occupation data: {occupation_dir}")
    print(f"Analysis output : {analysis_dir}")
    if summary.exists():
        print(f"Main summary    : {summary}")
    print()
    print("Do not re-run with modified hypotheses after viewing the result;")
    print("treat this as the first preregistered replication run.")


if __name__ == "__main__":
    main()
