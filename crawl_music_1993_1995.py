#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Orchestrate data collection for the frozen Music × BaZi 1993–1995 validation.

This script does NOT run association analyses and does NOT inspect Music × BaZi results.
It only:
  1) crawls exact birth dates,
  2) fetches frozen P106 occupation classification,
  3) enriches birthplace hemisphere using the existing v3 script.

Expected existing project scripts:
  birthdate_scan_v7.py
  occupation_scan_1986.py
  hemisphere_tengod_sensitivity_v3.py

Examples:
  python crawl_music_1993_1995.py --proxy http://127.0.0.1:10808 --stage all
  python crawl_music_1993_1995.py --proxy http://127.0.0.1:10808 --stage birthdates
  python crawl_music_1993_1995.py --proxy http://127.0.0.1:10808 --stage occupations
  python crawl_music_1993_1995.py --proxy http://127.0.0.1:10808 --stage hemisphere
"""

import argparse
import subprocess
import sys
from pathlib import Path

YEARS = [1993, 1994, 1995]


def run(cmd, title):
    print()
    print("=" * 88)
    print(title)
    print("=" * 88)
    print(" ".join(f'"{x}"' if " " in str(x) else str(x) for x in cmd))
    cp = subprocess.run(cmd)
    if cp.returncode != 0:
        raise SystemExit(f"\nFAILED: {title}\nExit code: {cp.returncode}")


def require(path: Path, label: str):
    if not path.exists():
        raise SystemExit(f"Missing {label}: {path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--proxy", default="http://127.0.0.1:10808")
    ap.add_argument(
        "--stage",
        choices=["birthdates", "occupations", "hemisphere", "all"],
        default="all",
    )
    ap.add_argument("--batch-size", type=int, default=50)
    ap.add_argument("--sleep", type=float, default=0.8)
    ap.add_argument("--project-dir", default=".")
    args = ap.parse_args()

    root = Path(args.project_dir).resolve()
    py = sys.executable

    birth_script = root / "birthdate_scan_v7.py"
    occ_script = root / "occupation_scan_1986.py"
    hemi_script = root / "hemisphere_tengod_sensitivity_v3.py"

    if args.stage in ("birthdates", "all"):
        require(birth_script, "birthdate scanner")
        for y in YEARS:
            outdir = root / f"birthdate_scan_{y}"
            outfile = outdir / f"{y}_people.csv"
            if outfile.exists():
                print(f"[skip] birthdates {y}: {outfile} already exists")
                continue
            run(
                [
                    py, str(birth_script),
                    "--year", str(y),
                    "--outdir", str(outdir),
                    "--proxy", args.proxy,
                    "--batch-size", str(args.batch_size),
                    "--sleep", str(args.sleep),
                ],
                f"BIRTHDATES {y}",
            )
            require(outfile, f"{y} birthdate output")

    if args.stage in ("occupations", "all"):
        require(occ_script, "occupation scanner")
        for y in YEARS:
            birth = root / f"birthdate_scan_{y}" / f"{y}_people.csv"
            require(birth, f"{y} birthdate people CSV")

            outdir = root / f"occupation_scan_{y}"
            outfile = outdir / f"{y}_people_with_occupations.csv"
            if outfile.exists():
                print(f"[skip] occupations {y}: {outfile} already exists")
                continue

            run(
                [
                    py, str(occ_script),
                    "--input", str(birth),
                    "--year", str(y),
                    "--proxy", args.proxy,
                    "--outdir", str(outdir),
                    "--batch-size", str(args.batch_size),
                    "--sleep", str(args.sleep),
                ],
                f"OCCUPATIONS {y}",
            )
            require(outfile, f"{y} occupation output")

    if args.stage in ("hemisphere", "all"):
        require(hemi_script, "hemisphere v3 script")
        for y in YEARS:
            occ = root / f"occupation_scan_{y}" / f"{y}_people_with_occupations.csv"
            require(occ, f"{y} occupation people CSV")

        outputs = [
            root / f"hemisphere_{y}" / f"{y}_people_with_hemisphere.csv"
            for y in YEARS
        ]
        if all(p.exists() for p in outputs):
            print("[skip] hemisphere: all three output files already exist")
        else:
            run(
                [
                    py, str(hemi_script),
                    "--proxy", args.proxy,
                    "--years", *[str(y) for y in YEARS],
                    "--fetch-only",
                ],
                "HEMISPHERE 1993–1995",
            )

        for y, p in zip(YEARS, outputs):
            require(p, f"{y} hemisphere output")

    print()
    print("DATA COLLECTION COMPLETE FOR REQUESTED STAGE.")
    for y in YEARS:
        for p in [
            root / f"birthdate_scan_{y}" / f"{y}_people.csv",
            root / f"occupation_scan_{y}" / f"{y}_people_with_occupations.csv",
            root / f"hemisphere_{y}" / f"{y}_people_with_hemisphere.csv",
        ]:
            if p.exists():
                print("  OK", p)


if __name__ == "__main__":
    main()
