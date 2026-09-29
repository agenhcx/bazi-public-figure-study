#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Resumable crawler for Gregorian birth cohorts 1990–1992.

Uses the already-tested project scripts:
  birthdate_scan_v7.py
  occupation_scan_1986.py
  validate_year_dataset.py

Two stages:
  --stage birthdates
      Fetch only birth-date data (P569 side). This does NOT fetch occupation/P106.
      Best choice before a new Ten-God preregistration is frozen.

  --stage full
      Fetch birth dates if missing, then P106 occupations and daily category stats,
      and validate each year. This does NOT run any Ten-God association analysis.

Examples:
  python crawl_1990_1992.py --proxy http://127.0.0.1:10808 --stage birthdates
  python crawl_1990_1992.py --proxy http://127.0.0.1:10808 --stage full

The script is resumable: existing completed outputs are skipped.
"""

import argparse
import subprocess
import sys
from pathlib import Path

YEARS = [1990, 1991, 1992]

def run_logged(cmd, title, log_path):
    print("\n" + "="*80)
    print(title)
    print("="*80)
    print(" ".join(map(str, cmd)))
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as log:
        log.write("\n" + "="*80 + "\n")
        log.write(title + "\n")
        log.write("="*80 + "\n")
        log.write(" ".join(map(str, cmd)) + "\n")
        log.flush()
        p = subprocess.run(
            cmd,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
        )
    if p.returncode != 0:
        raise SystemExit(
            f"FAILED: {title} (exit {p.returncode}). See log: {log_path}"
        )

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--proxy", default="http://127.0.0.1:10808")
    ap.add_argument(
        "--stage",
        choices=["birthdates", "full"],
        default="birthdates",
        help="birthdates = P569 only; full = also P106 occupations + validation",
    )
    ap.add_argument("--sleep", type=float, default=0.8)
    ap.add_argument("--batch-size", type=int, default=50)
    args = ap.parse_args()

    root = Path(".").resolve()
    py = sys.executable

    birth_script = root / "birthdate_scan_v7.py"
    occ_script = root / "occupation_scan_1986.py"
    validator = root / "validate_year_dataset.py"

    if not birth_script.exists():
        raise SystemExit(f"Missing: {birth_script}")
    if args.stage == "full":
        if not occ_script.exists():
            raise SystemExit(f"Missing: {occ_script}")
        if not validator.exists():
            raise SystemExit(f"Missing: {validator}")

    logdir = root / "crawl_1990_1992_logs"
    logdir.mkdir(exist_ok=True)

    for year in YEARS:
        bdir = root / f"birthdate_scan_{year}"
        bcsv = bdir / f"{year}_people.csv"

        if bcsv.exists() and bcsv.stat().st_size > 0:
            print(f"[SKIP] {year} birth data already exists: {bcsv}")
        else:
            run_logged(
                [
                    py, str(birth_script),
                    "--year", str(year),
                    "--proxy", args.proxy,
                    "--outdir", str(bdir),
                    "--batch-size", str(args.batch_size),
                    "--sleep", str(args.sleep),
                ],
                f"{year}: birth-date crawl",
                logdir / f"{year}_birthdate.log",
            )
            if not bcsv.exists():
                raise SystemExit(f"Expected output missing after crawl: {bcsv}")

        if args.stage == "birthdates":
            continue

        odir = root / f"occupation_scan_{year}"
        ocsv = odir / f"{year}_people_with_occupations.csv"
        daily = odir / f"{year}_daily_category_stats.csv"

        if (
            ocsv.exists() and ocsv.stat().st_size > 0
            and daily.exists() and daily.stat().st_size > 0
        ):
            print(f"[SKIP] {year} occupation data already exists: {odir}")
        else:
            run_logged(
                [
                    py, str(occ_script),
                    "--input", str(bcsv),
                    "--year", str(year),
                    "--proxy", args.proxy,
                    "--outdir", str(odir),
                    "--batch-size", str(args.batch_size),
                    "--sleep", str(args.sleep),
                ],
                f"{year}: P106 occupation crawl",
                logdir / f"{year}_occupation.log",
            )

        run_logged(
            [
                py, str(validator),
                "--year", str(year),
                "--birth-people", str(bcsv),
                "--occupation-people", str(ocsv),
                "--daily", str(daily),
            ],
            f"{year}: structural validation",
            logdir / f"{year}_validation.log",
        )

    print("\n" + "="*80)
    print("CRAWL COMPLETE")
    print("="*80)
    print(f"Stage: {args.stage}")
    print("Years: 1990, 1991, 1992")
    print(f"Logs: {logdir}")
    if args.stage == "birthdates":
        print("\nNo P106 occupation outcomes were fetched in this stage.")
        print("After freezing/preregistering the 1990–1992 Ten-God hypotheses,")
        print("run the same script with --stage full.")
    else:
        print("\nP106/daily data are now available, but this script did NOT run")
        print("any Ten-God association analysis.")

if __name__ == "__main__":
    main()
