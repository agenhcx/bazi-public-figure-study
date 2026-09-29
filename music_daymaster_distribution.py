#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Music Day-Master distribution analysis, modeled after the table-tennis project.

DEFAULT DISCOVERY SAMPLE:
    1986-1989 only.

This script intentionally does NOT include 1990-1992 by default.

It analyzes Music-classified public figures and reports:

A. 10 Day Masters:
   甲乙丙丁戊己庚辛壬癸

B. Day-Master Five Elements:
   木火土金水

For each category:
- observed N / %
- calendar-matched expected N / %
- enrichment ratio
- lower-tail p
- upper-tail enrichment p
- two-sided p
- Holm correction within the 10-stem family or 5-element family

The null is matched to the ACTUAL Gregorian birth-year composition of the
Music sample, exactly in the spirit of the prior table-tennis analysis:
for each birth year, enumerate every calendar date and calculate the Day Master.

It also gives a global Monte-Carlo goodness-of-fit test for:
- 10 Day Masters
- 5 Day-Master elements

Scopes:
- full: all Music people
- known: Music people with known P19/P625 latitude
- north: Music people with P19/P625 latitude > 0

This is useful because "north" excludes both Southern-Hemisphere people AND
people with missing birthplace coordinates. Comparing known vs north isolates
the effect of removing known Southern-Hemisphere/equator cases from the
known-coordinate sample more cleanly.

Expected input from the hemisphere crawler:
    hemisphere_YEAR/YEAR_people_with_hemisphere.csv

Example:
    python music_daymaster_distribution.py --years 1986 1987 1988 1989

After a future preregistration, you can explicitly run:
    python music_daymaster_distribution.py --years 1990 1991 1992
"""

import argparse
import math
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import binom
from lunar_python import Solar


STEMS = list("甲乙丙丁戊己庚辛壬癸")
ELEMENTS = ["木","火","土","金","水"]
STEM_ELEMENT = {
    "甲":"木","乙":"木",
    "丙":"火","丁":"火",
    "戊":"土","己":"土",
    "庚":"金","辛":"金",
    "壬":"水","癸":"水",
}


def all_dates_in_year(y):
    d = date(y,1,1)
    end = date(y,12,31)
    while d <= end:
        yield d
        d += timedelta(days=1)


def daymaster_for_date(y,m,d):
    ec = Solar.fromYmdHms(int(y),int(m),int(d),12,0,0).getLunar().getEightChar()
    stem = ec.getDayGan()
    return stem, STEM_ELEMENT[stem]


def build_calendar_baseline(years):
    result = {}
    for y in sorted(set(map(int, years))):
        stem = Counter()
        elem = Counter()
        total = 0
        for dt in all_dates_in_year(y):
            s,e = daymaster_for_date(dt.year,dt.month,dt.day)
            stem[s] += 1
            elem[e] += 1
            total += 1
        result[y] = {
            "total": total,
            "stem": stem,
            "element": elem,
        }
        print(
            f"  baseline {y}: {total} days; "
            + ", ".join(f"{k}={stem[k]}" for k in STEMS)
        )
    return result


def pmf_sum_of_binomials(year_counts, baseline, family, category):
    """
    Exact null PMF for sum across year-specific Binomial(n_y, p_y).
    This is much faster than individual-level O(N^2) Poisson-binomial because
    the probability is identical for all people in the same Gregorian birth year.
    """
    pmf = np.array([1.0], dtype=float)

    for y,n in sorted(year_counts.items()):
        b = baseline[int(y)]
        p = b[family][category] / b["total"]
        k = np.arange(n + 1)
        this = binom.pmf(k, n, p)
        pmf = np.convolve(pmf, this)

    pmf = np.maximum(pmf, 0)
    s = pmf.sum()
    if s > 0:
        pmf /= s
    return pmf


def exact_tails_from_pmf(pmf, observed):
    observed = int(observed)
    lower = float(pmf[:observed+1].sum())
    upper = float(pmf[observed:].sum())
    two = min(1.0, 2.0 * min(lower, upper))
    return lower, upper, two


def holm_adjust(p_values):
    p = list(map(float, p_values))
    m = len(p)
    order = sorted(range(m), key=lambda i: p[i])
    out = [None]*m
    running = 0.0
    for rank,idx in enumerate(order):
        x = min(1.0, (m-rank)*p[idx])
        running = max(running, x)
        out[idx] = running
    return out


def analyze_categories(rows, baseline, family, categories, label):
    n = len(rows)
    obs = Counter(rows[family])
    year_counts = Counter(int(y) for y in rows["birth_year"])

    results = []

    for cat in categories:
        expected = 0.0
        for y,ny in year_counts.items():
            b = baseline[y]
            expected += ny * b[family][cat] / b["total"]

        observed = int(obs[cat])
        obs_pct = observed/n if n else np.nan
        exp_pct = expected/n if n else np.nan

        pmf = pmf_sum_of_binomials(
            year_counts, baseline, family, cat
        )
        p_lower,p_upper,p_two = exact_tails_from_pmf(pmf, observed)

        results.append({
            "analysis": label,
            "category": cat,
            "observed_n": observed,
            "observed_pct": obs_pct,
            "expected_n": expected,
            "expected_pct": exp_pct,
            "enrichment": obs_pct/exp_pct if exp_pct else np.nan,
            "p_lower": p_lower,
            "p_upper_enrichment": p_upper,
            "p_two_sided": p_two,
        })

    adj = holm_adjust([r["p_two_sided"] for r in results])
    for r,a in zip(results, adj):
        r["p_holm_family"] = a

    return pd.DataFrame(results)


def pearson_stat(observed, expected):
    observed = np.asarray(observed,dtype=float)
    expected = np.asarray(expected,dtype=float)
    return float(np.sum((observed-expected)**2 / expected))


def global_monte_carlo(rows, baseline, family, categories, reps, seed):
    """
    Simulate matched-year category counts under the calendar null.
    For each Gregorian birth year, draw a multinomial with the calendar-derived
    category probabilities and that year's observed Music sample size.
    """
    rng = np.random.default_rng(seed)
    year_counts = Counter(int(y) for y in rows["birth_year"])
    obs_counter = Counter(rows[family])

    observed = np.array([obs_counter[c] for c in categories], dtype=float)
    expected = np.zeros(len(categories), dtype=float)

    probs_by_year = {}
    for y,n in year_counts.items():
        b = baseline[y]
        probs = np.array(
            [b[family][c]/b["total"] for c in categories],
            dtype=float
        )
        probs /= probs.sum()
        probs_by_year[y] = probs
        expected += n*probs

    obs_stat = pearson_stat(observed, expected)

    ge = 0
    # chunk the simulations to keep memory modest
    chunk = 5000
    done = 0
    while done < reps:
        r = min(chunk, reps-done)
        sims = np.zeros((r,len(categories)),dtype=int)
        for y,n in year_counts.items():
            sims += rng.multinomial(n, probs_by_year[y], size=r)

        stats = ((sims-expected[None,:])**2 / expected[None,:]).sum(axis=1)
        ge += int(np.sum(stats >= obs_stat - 1e-12))
        done += r

    p = (ge+1)/(reps+1)
    return {
        "family": family,
        "n": len(rows),
        "pearson_stat": obs_stat,
        "mc_reps": reps,
        "mc_p": p,
    }


def load_music_people(root, years):
    frames = []
    for y in years:
        p = root / f"hemisphere_{y}" / f"{y}_people_with_hemisphere.csv"
        if not p.exists():
            raise SystemExit(
                f"Missing {p}\n"
                f"Run the hemisphere crawler for {y} first."
            )

        d = pd.read_csv(p, encoding="utf-8-sig")

        if "_music" not in d.columns:
            raise SystemExit(f"{p} has no _music column.")
        if "_birth_date_norm" not in d.columns:
            raise SystemExit(f"{p} has no _birth_date_norm column.")
        if "hemisphere" not in d.columns:
            raise SystemExit(f"{p} has no hemisphere column.")

        d = d.loc[pd.to_numeric(d["_music"],errors="coerce").fillna(0).astype(int)==1].copy()
        d["dob"] = pd.to_datetime(d["_birth_date_norm"],errors="coerce")
        d = d.loc[d["dob"].notna()].copy()
        d["birth_year"] = d["dob"].dt.year.astype(int)

        # Derive Day Master from civil date at noon.
        dm = [
            daymaster_for_date(x.year,x.month,x.day)
            for x in d["dob"]
        ]
        d["stem"] = [x[0] for x in dm]
        d["element"] = [x[1] for x in dm]
        d["source_year"] = int(y)

        frames.append(d)

    if not frames:
        raise SystemExit("No data loaded.")

    return pd.concat(frames, ignore_index=True)


def scope_filter(d, scope):
    if scope == "full":
        return d.copy()
    if scope == "known":
        return d.loc[d["hemisphere"].isin(["north","south","equator"])].copy()
    if scope == "north":
        return d.loc[d["hemisphere"]=="north"].copy()
    raise ValueError(scope)


def summarize_scope(d, baseline, scope, outdir, reps, seed):
    x = scope_filter(d,scope)
    if len(x)==0:
        return None

    print(f"\n=== {scope.upper()} ===")
    print(f"Music N={len(x):,}")
    print(
        x["hemisphere"].value_counts(dropna=False).to_string()
        if "hemisphere" in x.columns else ""
    )

    stem = analyze_categories(
        x, baseline, "stem", STEMS, "Day Master / 10 stems"
    )
    elem = analyze_categories(
        x, baseline, "element", ELEMENTS, "Day-Master / 5 elements"
    )
    stem["scope"] = scope
    elem["scope"] = scope

    global_rows = [
        global_monte_carlo(
            x, baseline, "stem", STEMS, reps, seed+1
        ),
        global_monte_carlo(
            x, baseline, "element", ELEMENTS, reps, seed+2
        ),
    ]
    glob = pd.DataFrame(global_rows)
    glob["scope"] = scope

    stem.to_csv(
        outdir/f"{scope}_daymaster_10stem.csv",
        index=False,encoding="utf-8-sig"
    )
    elem.to_csv(
        outdir/f"{scope}_daymaster_5element.csv",
        index=False,encoding="utf-8-sig"
    )
    glob.to_csv(
        outdir/f"{scope}_global_tests.csv",
        index=False,encoding="utf-8-sig"
    )

    print("\n10 DAY MASTERS")
    print(
        stem[
            ["category","observed_n","observed_pct","expected_n","expected_pct",
             "enrichment","p_two_sided","p_holm_family"]
        ].to_string(index=False)
    )

    print("\n5 ELEMENTS")
    print(
        elem[
            ["category","observed_n","observed_pct","expected_n","expected_pct",
             "enrichment","p_two_sided","p_holm_family"]
        ].to_string(index=False)
    )

    return stem,elem,glob,x


def write_human_summary(results, years, outdir):
    lines = [
        "Music Day-Master distribution analysis",
        f"Years: {', '.join(map(str,years))}",
        "",
        "Null: calendar-matched to the Music sample's actual Gregorian birth-year composition.",
        "Day Master evaluated from the civil birth date at 12:00.",
        "",
    ]

    for scope,(stem,elem,glob,x) in results.items():
        lines += [
            "="*80,
            f"SCOPE: {scope}",
            f"Music N: {len(x):,}",
            "",
            "10 DAY MASTERS, sorted by enrichment:",
        ]
        for _,r in stem.sort_values("enrichment",ascending=False).iterrows():
            lines.append(
                f"  {r['category']}: "
                f"obs={int(r['observed_n'])} ({100*r['observed_pct']:.2f}%), "
                f"exp={r['expected_n']:.1f} ({100*r['expected_pct']:.2f}%), "
                f"enrichment={r['enrichment']:.3f}, "
                f"p2={r['p_two_sided']:.5g}, Holm={r['p_holm_family']:.5g}"
            )

        lines += ["", "5 DAY-MASTER ELEMENTS, sorted by enrichment:"]
        for _,r in elem.sort_values("enrichment",ascending=False).iterrows():
            lines.append(
                f"  {r['category']}: "
                f"obs={int(r['observed_n'])} ({100*r['observed_pct']:.2f}%), "
                f"exp={r['expected_n']:.1f} ({100*r['expected_pct']:.2f}%), "
                f"enrichment={r['enrichment']:.3f}, "
                f"p2={r['p_two_sided']:.5g}, Holm={r['p_holm_family']:.5g}"
            )

        lines += ["", "GLOBAL TESTS:"]
        for _,r in glob.iterrows():
            lines.append(
                f"  {r['family']}: Pearson={r['pearson_stat']:.3f}, "
                f"MonteCarlo p={r['mc_p']:.6g} ({int(r['mc_reps'])} reps)"
            )
        lines.append("")

    lines += [
        "Important:",
        "  1986-1989 are exploratory/discovery for this Day-Master question.",
        "  1990-1992 should remain untouched until hypotheses are frozen/preregistered.",
        "",
        "Scope interpretation:",
        "  full  = all Music people.",
        "  known = only people with known P19/P625 latitude.",
        "  north = known latitude > 0.",
        "  Therefore known-vs-north is cleaner for testing sensitivity to Southern Hemisphere",
        "  than full-vs-north, because full-vs-north also removes unknown birthplaces.",
    ]

    p=outdir/"music_daymaster_summary.txt"
    p.write_text("\n".join(lines),encoding="utf-8")


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--years",nargs="+",type=int,default=[1986,1987,1988,1989])
    ap.add_argument("--outdir",default="music_daymaster_results")
    ap.add_argument("--mc-reps",type=int,default=100000)
    ap.add_argument("--seed",type=int,default=20260926)
    args=ap.parse_args()

    root=Path(".").resolve()
    outdir=root/args.outdir
    outdir.mkdir(parents=True,exist_ok=True)

    music=load_music_people(root,args.years)

    print(f"Loaded Music people: {len(music):,}")
    print("Building matched-calendar baseline...")
    baseline=build_calendar_baseline(music["birth_year"].tolist())

    results={}
    for scope in ["full","known","north"]:
        r=summarize_scope(
            music,baseline,scope,outdir,args.mc_reps,args.seed
        )
        if r is not None:
            results[scope]=r

    # Combined long outputs
    all_stem=[]
    all_elem=[]
    all_global=[]
    for scope,(stem,elem,glob,x) in results.items():
        all_stem.append(stem)
        all_elem.append(elem)
        all_global.append(glob)

    pd.concat(all_stem,ignore_index=True).to_csv(
        outdir/"all_scopes_daymaster_10stem.csv",
        index=False,encoding="utf-8-sig"
    )
    pd.concat(all_elem,ignore_index=True).to_csv(
        outdir/"all_scopes_daymaster_5element.csv",
        index=False,encoding="utf-8-sig"
    )
    pd.concat(all_global,ignore_index=True).to_csv(
        outdir/"all_scopes_global_tests.csv",
        index=False,encoding="utf-8-sig"
    )

    # Save individual Music rows with derived Day Master for audit.
    music.to_csv(
        outdir/"music_people_with_daymaster.csv",
        index=False,encoding="utf-8-sig"
    )

    write_human_summary(results,args.years,outdir)

    print(f"\nSaved under: {outdir}")
    print("Main file: music_daymaster_summary.txt")


if __name__=="__main__":
    main()
