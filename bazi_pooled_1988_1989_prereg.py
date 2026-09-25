#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse, math
from pathlib import Path
import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.stats.multitest import multipletests
from bazi_hour_marginal_analysis_v2_prereg import build_hour_marginal_features

PRIMARY = [
    ("H1", "YMD_DAY_HALF_TRINE", 1.0),
    ("H2", "P_HOUR_COMPLETES_DAY_SANHE", 1.0/12.0),
    ("H3", "YMD_STEM_COMBINE_AND_HALF_TRINE", 1.0),
]
EQUIV_LO = 1.0 / 1.10
EQUIV_HI = 1.10

def one_sided_positive(beta, p_two):
    return p_two/2 if beta >= 0 else 1-p_two/2

def design(d, feature):
    X = pd.DataFrame(index=d.index)
    X[feature] = pd.to_numeric(d[feature]).astype(float)
    yd = pd.get_dummies(d["source_year"].astype("category"), prefix="year", drop_first=True, dtype=float)
    md = pd.get_dummies(d["gregorian_month"].astype("category"), prefix="month", drop_first=True, dtype=float)
    wd = pd.get_dummies(d["weekday"].astype("category"), prefix="weekday", drop_first=True, dtype=float)
    X = pd.concat([X, yd, md, wd], axis=1)
    return sm.add_constant(X, has_constant="add").astype(float)

def fit_one(d, h, feature, delta):
    y = np.column_stack([d["Music__n"].to_numpy(float), (d["n_people"]-d["Music__n"]).to_numpy(float)])
    fit = sm.GLM(y, design(d, feature), family=sm.families.Binomial()).fit(cov_type="HC0", maxiter=200)
    beta = float(fit.params[feature]); se = float(fit.bse[feature]); p2 = float(fit.pvalues[feature])
    p1 = one_sided_positive(beta, p2)
    be = beta*delta; see = se*delta
    z90 = 1.6448536269514722
    ci90lo = math.exp(be-z90*see); ci90hi = math.exp(be+z90*see)
    return {
        "hypothesis": h, "feature": feature,
        "practical_or": math.exp(be),
        "ci95_low": math.exp(be-1.96*see),
        "ci95_high": math.exp(be+1.96*see),
        "one_sided_positive_p": p1,
        "ci90_low": ci90lo, "ci90_high": ci90hi,
        "equivalent_within_10pct": (ci90lo > EQUIV_LO and ci90hi < EQUIV_HI),
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-1988", default=r"occupation_scan_1988\1988_daily_category_stats.csv")
    ap.add_argument("--input-1989", default=r"occupation_scan_1989\1989_daily_category_stats.csv")
    ap.add_argument("--outdir", default="bazi_pooled_1988_1989")
    a = ap.parse_args()

    frames=[]
    for year, fn in [(1988,a.input_1988),(1989,a.input_1989)]:
        d=pd.read_csv(fn)
        d["date"]=pd.to_datetime(d["date"])
        d["n_people"]=pd.to_numeric(d["n_people"]).astype(int)
        d["Music__n"]=pd.to_numeric(d["Music__n"]).astype(int)
        d=d.loc[d["date"].dt.year==year].copy()
        f=build_hour_marginal_features(d)
        f["source_year"]=year
        frames.append(f)

    d=pd.concat(frames,ignore_index=True)
    d=d.loc[~d["pillar_transition_ambiguous"]].copy()

    rows=[fit_one(d,*x) for x in PRIMARY]
    res=pd.DataFrame(rows)
    res["global_bh_q"]=multipletests(res["one_sided_positive_p"],alpha=0.05,method="fdr_bh")[1]

    out=Path(a.outdir); out.mkdir(parents=True,exist_ok=True)
    res.to_csv(out/"1988_1989_primary_pooled.csv",index=False,encoding="utf-8-sig")

    lines=[
        "Preregistered pooled replication — 1988 + 1989","",
        f"Eligible dates: {len(d)}", f"People: {d['n_people'].sum():,}", f"Music: {d['Music__n'].sum():,}",""
    ]
    for _,r in res.iterrows():
        lines += [
            f"{r['hypothesis']} {r['feature']}:",
            f"  practical OR = {r['practical_or']:.4f}",
            f"  95% CI = [{r['ci95_low']:.4f}, {r['ci95_high']:.4f}]",
            f"  one-sided p = {r['one_sided_positive_p']:.6g}",
            f"  global BH q = {r['global_bh_q']:.6g}",
            f"  90% CI = [{r['ci90_low']:.4f}, {r['ci90_high']:.4f}]",
            f"  within +/-10% equivalence margin = {bool(r['equivalent_within_10pct'])}",""
        ]
    (out/"1988_1989_pooled_summary.txt").write_text("\n".join(lines),encoding="utf-8")
    print("\n".join(lines))

if __name__=="__main__":
    main()
