#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import math
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.stats import fisher_exact
from statsmodels.stats.multitest import multipletests
from lunar_python import Solar

STEM_ELEMENT = {
    "甲":"木","乙":"木","丙":"火","丁":"火","戊":"土","己":"土",
    "庚":"金","辛":"金","壬":"水","癸":"水",
}
STEM_POLARITY = {
    "甲":"阳","乙":"阴","丙":"阳","丁":"阴","戊":"阳","己":"阴",
    "庚":"阳","辛":"阴","壬":"阳","癸":"阴",
}
GENERATES = {"木":"火","火":"土","土":"金","金":"水","水":"木"}
CONTROLS = {"木":"土","土":"水","水":"火","火":"金","金":"木"}

BRANCH_MAIN_STEM = {
    "子":"癸","丑":"己","寅":"甲","卯":"乙","辰":"戊","巳":"丙",
    "午":"丁","未":"己","申":"庚","酉":"辛","戌":"戊","亥":"壬",
}

TEN_GODS = ["比肩","劫财","食神","伤官","偏财","正财","七杀","正官","偏印","正印"]

def ten_god(day_stem, other_stem):
    de, oe = STEM_ELEMENT[day_stem], STEM_ELEMENT[other_stem]
    same = STEM_POLARITY[day_stem] == STEM_POLARITY[other_stem]
    if oe == de:
        return "比肩" if same else "劫财"
    if GENERATES[de] == oe:
        return "食神" if same else "伤官"
    if CONTROLS[de] == oe:
        return "偏财" if same else "正财"
    if CONTROLS[oe] == de:
        return "七杀" if same else "正官"
    if GENERATES[oe] == de:
        return "偏印" if same else "正印"
    raise ValueError((day_stem, other_stem))

def eight_char_at(y, m, d, hour=12, minute=0):
    ec = Solar.fromYmdHms(y, m, d, hour, minute, 0).getLunar().getEightChar()
    return {"year":ec.getYear(),"month":ec.getMonth(),"day":ec.getDay(),"hour":ec.getTime()}

def add_features(df):
    rows=[]
    for _,r in df.iterrows():
        dt=pd.Timestamp(r["date"])
        y,m,d=dt.year,dt.month,dt.day
        noon=eight_char_at(y,m,d,12)
        early=eight_char_at(y,m,d,0,30)
        late=eight_char_at(y,m,d,22,30)
        transition=(early["year"]!=late["year"] or early["month"]!=late["month"])

        mp,dp=noon["month"],noon["day"]
        ms,mb=mp[0],mp[1]
        ds=dp[0]
        main=BRANCH_MAIN_STEM[mb]

        rec=r.to_dict()
        rec.update({
            "year_pillar":noon["year"],
            "month_pillar":mp,
            "day_pillar":dp,
            "day_stem":ds,
            "month_stem":ms,
            "month_branch":mb,
            "month_main_stem":main,
            "month_stem_tengod":ten_god(ds,ms),
            "month_order_tengod":ten_god(ds,main),
            "pillar_transition_ambiguous":transition,
            "gregorian_month":m,
            "weekday":dt.day_name(),
        })
        rec["month_stem_shangguan"]=int(rec["month_stem_tengod"]=="伤官")
        rec["month_stem_shishen"]=int(rec["month_stem_tengod"]=="食神")
        rec["month_stem_shishang"]=int(rec["month_stem_tengod"] in {"食神","伤官"})
        rec["month_order_shangguan"]=int(rec["month_order_tengod"]=="伤官")
        rec["month_order_shishen"]=int(rec["month_order_tengod"]=="食神")
        rec["month_order_shishang"]=int(rec["month_order_tengod"] in {"食神","伤官"})
        rows.append(rec)
    return pd.DataFrame(rows)

def design_matrix(d, feature):
    X=pd.DataFrame(index=d.index)
    X[feature]=pd.to_numeric(d[feature]).astype(float)
    md=pd.get_dummies(d["gregorian_month"].astype("category"),prefix="month",drop_first=True,dtype=float)
    wd=pd.get_dummies(d["weekday"].astype("category"),prefix="weekday",drop_first=True,dtype=float)
    X=pd.concat([X,md,wd],axis=1)
    return sm.add_constant(X,has_constant="add").astype(float)

def fit_binary(d,feature):
    mask=d[feature].astype(bool)
    n1=int(d.loc[mask,"n_people"].sum()); y1=int(d.loc[mask,"Music__n"].sum())
    n0=int(d.loc[~mask,"n_people"].sum()); y0=int(d.loc[~mask,"Music__n"].sum())
    r1=y1/n1; r0=y0/n0
    _,pf=fisher_exact([[y1,n1-y1],[y0,n0-y0]],alternative="greater")

    y=np.column_stack([d["Music__n"].to_numpy(float),(d["n_people"]-d["Music__n"]).to_numpy(float)])
    fit=sm.GLM(y,design_matrix(d,feature),family=sm.families.Binomial()).fit(cov_type="HC0",maxiter=200)
    beta=float(fit.params[feature]); se=float(fit.bse[feature]); p2=float(fit.pvalues[feature])
    p1=p2/2 if beta>=0 else 1-p2/2

    return {
        "feature":feature,
        "feature_days":int(mask.sum()),
        "feature_people":n1,
        "feature_music":y1,
        "feature_music_rate":r1,
        "nonfeature_people":n0,
        "nonfeature_music":y0,
        "nonfeature_music_rate":r0,
        "risk_ratio":r1/r0,
        "fisher_one_sided_p":pf,
        "adjusted_or":math.exp(beta),
        "ci95_low":math.exp(beta-1.96*se),
        "ci95_high":math.exp(beta+1.96*se),
        "glm_one_sided_p":p1,
    }

def descriptive_table(d,col):
    rows=[]
    for tg in TEN_GODS:
        g=d.loc[d[col]==tg]
        n=int(g["n_people"].sum()); y=int(g["Music__n"].sum())
        rows.append({"ten_god":tg,"dates":len(g),"people":n,"music":y,"music_rate":y/n if n else np.nan})
    return pd.DataFrame(rows).sort_values("music_rate",ascending=False)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--input",required=True)
    ap.add_argument("--year",type=int,default=1986)
    ap.add_argument("--outdir",default=None)
    a=ap.parse_args()

    d=pd.read_csv(a.input)
    d["date"]=pd.to_datetime(d["date"])
    d=d.loc[d["date"].dt.year==a.year].copy()
    d["n_people"]=pd.to_numeric(d["n_people"]).astype(int)
    d["Music__n"]=pd.to_numeric(d["Music__n"]).astype(int)

    feat=add_features(d)
    eligible=feat.loc[~feat["pillar_transition_ambiguous"]].copy()

    outdir=Path(a.outdir or f"bazi_tengod_music_{a.year}")
    outdir.mkdir(parents=True,exist_ok=True)

    stemtab=descriptive_table(eligible,"month_stem_tengod")
    ordertab=descriptive_table(eligible,"month_order_tengod")

    targets=[
        "month_stem_shangguan","month_stem_shishen","month_stem_shishang",
        "month_order_shangguan","month_order_shishen","month_order_shishang"
    ]
    tests=pd.DataFrame([fit_binary(eligible,f) for f in targets])
    tests["bh_q"]=multipletests(tests["glm_one_sided_p"],alpha=0.05,method="fdr_bh")[1]

    stemtab.to_csv(outdir/f"{a.year}_month_stem_tengod.csv",index=False,encoding="utf-8-sig")
    ordertab.to_csv(outdir/f"{a.year}_month_order_tengod.csv",index=False,encoding="utf-8-sig")
    tests.to_csv(outdir/f"{a.year}_targeted_tengod_tests.csv",index=False,encoding="utf-8-sig")
    eligible.to_csv(outdir/f"{a.year}_daily_tengod_features.csv",index=False,encoding="utf-8-sig")

    lines=[
        f"Exploratory Music × Ten-God analysis — {a.year}",
        "",
        f"Eligible dates: {len(eligible)}",
        f"People: {eligible['n_people'].sum():,}",
        f"Music: {eligible['Music__n'].sum():,}",
        f"Excluded pillar-transition dates: {int(feat['pillar_transition_ambiguous'].sum())}",
        "",
        "Definition:",
        "  Month stem Ten-God = 月干 relative to 日主.",
        "  Month-order Ten-God = 月支本气藏干 relative to 日主.",
        "",
        "MONTH STEM — all ten gods:",
    ]
    for _,r in stemtab.iterrows():
        lines.append(f"  {r['ten_god']}: dates={int(r['dates'])}, people={int(r['people'])}, Music={int(r['music'])}, rate={100*r['music_rate']:.2f}%")
    lines += ["","MONTH ORDER / 月令本气 — all ten gods:"]
    for _,r in ordertab.iterrows():
        lines.append(f"  {r['ten_god']}: dates={int(r['dates'])}, people={int(r['people'])}, Music={int(r['music'])}, rate={100*r['music_rate']:.2f}%")
    lines += ["","TARGETED exploratory tests (adjusted for Gregorian month + weekday):"]
    for _,r in tests.iterrows():
        lines.append(
            f"  {r['feature']}: rate={100*r['feature_music_rate']:.2f}% vs {100*r['nonfeature_music_rate']:.2f}%, "
            f"RR={r['risk_ratio']:.3f}, adjusted OR={r['adjusted_or']:.3f} "
            f"[{r['ci95_low']:.3f},{r['ci95_high']:.3f}], "
            f"one-sided p={r['glm_one_sided_p']:.6g}, BH q={r['bh_q']:.6g}"
        )
    lines += [
        "",
        "Interpretation note:",
        "  1986 is exploratory/discovery only.",
        "  Positive patterns found here should be frozen and tested in an untouched cohort."
    ]

    summary=outdir/f"{a.year}_tengod_music_summary.txt"
    summary.write_text("\n".join(lines),encoding="utf-8")
    print("\n".join(lines))
    print(f"\nSaved to: {outdir}")

if __name__=="__main__":
    main()
