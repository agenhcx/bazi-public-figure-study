#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse, subprocess, sys
from pathlib import Path

def run(cmd,title):
    print("\n"+"="*80); print(title); print("="*80)
    print(" ".join(map(str,cmd)))
    rc=subprocess.run(cmd).returncode
    if rc!=0: raise SystemExit(f"FAILED: {title} (exit {rc})")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--proxy",default="http://127.0.0.1:10808")
    ap.add_argument("--permutations",type=int,default=50000)
    a=ap.parse_args()
    root=Path(".").resolve(); py=sys.executable
    for year in [1988,1989]:
        bdir=root/f"birthdate_scan_{year}"
        bcsv=bdir/f"{year}_people.csv"
        odir=root/f"occupation_scan_{year}"
        ocsv=odir/f"{year}_people_with_occupations.csv"
        daily=odir/f"{year}_daily_category_stats.csv"
        if not bcsv.exists():
            run([py,"birthdate_scan_v7.py","--year",str(year),"--proxy",a.proxy,"--outdir",str(bdir)],f"{year}: birth fetch")
        run([py,"occupation_scan_1986.py","--input",str(bcsv),"--year",str(year),"--proxy",a.proxy,"--outdir",str(odir)],f"{year}: occupations")
        run([py,"validate_year_dataset.py","--year",str(year),"--birth-people",str(bcsv),"--occupation-people",str(ocsv),"--daily",str(daily)],f"{year}: validation")
        run([py,"bazi_hour_marginal_analysis_v2_prereg.py","--input",str(daily),"--year",str(year),"--permutations",str(a.permutations)],f"{year}: per-year analysis")
    run([py,"bazi_pooled_1988_1989_prereg.py"],"1988+1989 pooled confirmatory analysis")

if __name__=="__main__":
    main()
