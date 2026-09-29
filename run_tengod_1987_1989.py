#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Run the existing Ten-God v2 exploratory analysis for 1987, 1988, 1989
using already-downloaded daily occupation statistics, then make a compact
cross-year comparison table.

Expected project layout:
  occupation_scan_1987/1987_daily_category_stats.csv
  occupation_scan_1988/1988_daily_category_stats.csv
  occupation_scan_1989/1989_daily_category_stats.csv
  bazi_music_tengod_1986_v2.py

Run:
  python run_tengod_1987_1989.py
"""

import subprocess
import sys
from pathlib import Path
import pandas as pd

YEARS = [1987, 1988, 1989]

def run(cmd, title):
    print("\n" + "="*80)
    print(title)
    print("="*80)
    print(" ".join(map(str, cmd)))
    rc = subprocess.run(cmd).returncode
    if rc != 0:
        raise SystemExit(f"FAILED: {title} (exit {rc})")

def main():
    root = Path(".").resolve()
    py = sys.executable
    analyzer = root / "bazi_music_tengod_1986_v2.py"
    if not analyzer.exists():
        raise SystemExit(f"Missing analyzer: {analyzer}")

    summary_rows = []
    enrichment_rows = []

    for year in YEARS:
        daily = root / f"occupation_scan_{year}" / f"{year}_daily_category_stats.csv"
        if not daily.exists():
            raise SystemExit(
                f"Missing {daily}\n"
                f"Run/fix the {year} data pipeline first."
            )

        outdir = root / f"bazi_tengod_music_{year}_v2"

        run(
            [
                py, str(analyzer),
                "--input", str(daily),
                "--year", str(year),
                "--outdir", str(outdir),
            ],
            f"{year}: exploratory Ten-God analysis",
        )

        tests = pd.read_csv(outdir / f"{year}_all20_tengod_tests.csv")
        tests["year"] = year
        summary_rows.append(tests)

        for location, filename in [
            ("month_stem", f"{year}_month_stem_tengod_enrichment.csv"),
            ("month_order", f"{year}_month_order_tengod_enrichment.csv"),
        ]:
            e = pd.read_csv(outdir / filename)
            e["year"] = year
            enrichment_rows.append(e)

    all_tests = pd.concat(summary_rows, ignore_index=True)
    all_enrichment = pd.concat(enrichment_rows, ignore_index=True)

    all_tests.to_csv(
        root / "1987_1989_tengod_all_tests_long.csv",
        index=False,
        encoding="utf-8-sig",
    )
    all_enrichment.to_csv(
        root / "1987_1989_tengod_enrichment_long.csv",
        index=False,
        encoding="utf-8-sig",
    )

    # Wide comparison: OR and nominal one-sided p for each year.
    wide_or = all_tests.pivot_table(
        index=["location", "ten_god"],
        columns="year",
        values="adjusted_or",
        aggfunc="first",
    )
    wide_p = all_tests.pivot_table(
        index=["location", "ten_god"],
        columns="year",
        values="glm_one_sided_p",
        aggfunc="first",
    )
    wide_enr = all_enrichment.pivot_table(
        index=["location", "ten_god"],
        columns="year",
        values="enrichment_ratio",
        aggfunc="first",
    )

    comp = pd.DataFrame(index=wide_or.index).reset_index()
    for year in YEARS:
        comp[f"OR_{year}"] = wide_or[year].values
        comp[f"p1_{year}"] = wide_p[year].values
        comp[f"enrichment_{year}"] = wide_enr[year].values

    # Count directional consistency.
    comp["n_years_OR_gt_1"] = sum(comp[f"OR_{y}"] > 1 for y in YEARS)
    comp["n_years_OR_lt_1"] = sum(comp[f"OR_{y}"] < 1 for y in YEARS)
    comp["geomean_OR"] = (
        comp[[f"OR_{y}" for y in YEARS]].prod(axis=1) ** (1/len(YEARS))
    )
    comp["mean_enrichment"] = comp[
        [f"enrichment_{y}" for y in YEARS]
    ].mean(axis=1)

    comp = comp.sort_values(
        ["n_years_OR_gt_1", "geomean_OR"],
        ascending=[False, False],
    )

    comp.to_csv(
        root / "1987_1989_tengod_crossyear_comparison.csv",
        index=False,
        encoding="utf-8-sig",
    )

    lines = [
        "1987–1989 exploratory Ten-God cross-year comparison",
        "",
        "IMPORTANT: these years have already been used for other Music/BaZi analyses.",
        "Treat this as exploratory follow-up, not a clean preregistered Ten-God replication.",
        "",
        "Rows sorted by number of years with OR>1, then geometric-mean OR.",
        "",
    ]

    for _, r in comp.iterrows():
        lines.append(
            f"{r['location']} {r['ten_god']}: "
            f"OR87={r['OR_1987']:.3f}, "
            f"OR88={r['OR_1988']:.3f}, "
            f"OR89={r['OR_1989']:.3f}; "
            f"positive years={int(r['n_years_OR_gt_1'])}/3; "
            f"geomean OR={r['geomean_OR']:.3f}; "
            f"mean enrichment={r['mean_enrichment']:.3f}"
        )

    out = root / "1987_1989_tengod_crossyear_summary.txt"
    out.write_text("\n".join(lines), encoding="utf-8")
    print("\n" + "\n".join(lines))
    print("\nSaved:")
    print("  1987_1989_tengod_crossyear_summary.txt")
    print("  1987_1989_tengod_crossyear_comparison.csv")
    print("  1987_1989_tengod_all_tests_long.csv")
    print("  1987_1989_tengod_enrichment_long.csv")

if __name__ == "__main__":
    main()
