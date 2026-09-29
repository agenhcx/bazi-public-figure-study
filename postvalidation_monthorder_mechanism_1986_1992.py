#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Post-validation exploratory mechanism analysis:
Music × month-order structures, north-primary, 1986–1992.

IMPORTANT:
- 1986–1992 outcomes have already been inspected.
- Every analysis in this script is exploratory / mechanism-generating.
- Do NOT relabel any result here as confirmatory.
- Any future confirmation requires a new, non-overlapping cohort and preregistration.

Main questions
--------------
1) What drives the previously observed month-order 比肩 signal?
   - non-Earth 比肩 that is Jianlu-equivalent
   - Earth-Day-Master mixed-qi 比肩
   - classical Jianlu including 戊巳 / 己午

2) What is inside month-order 劫财?
   - overlap with strict Yangren for 甲/丙/庚/壬
   - Yin-stem same-element opposite-polarity cases
   - Earth mixed-qi cases
   - explicit strict Yangren including 戊午 (which is NOT month-order 劫财)

3) What drives month-order 伤官?
   - non-Fire single-branch cases
   - Fire-Day-Master Earth mixed-qi cases:
       丙丑 / 丙未
       丁辰 / 丁戌
   - test sensitivity after controlling Day Stem and Month Branch.

Models
------
Grouped-binomial daily Music vs non-Music.

M0: feature + C(year) + C(gregorian_month) + C(weekday)
M1: M0 + C(day_stem)
M2: M1 + C(month_branch)

M2 asks whether the feature behaves like an interaction beyond the
marginal Day-Stem and Month-Branch composition.
"""

import argparse
import math
from pathlib import Path
from collections import Counter

import numpy as np
import pandas as pd
import statsmodels.api as sm
from lunar_python import Solar

STEM_ELEMENT = {
    "甲":"木","乙":"木","丙":"火","丁":"火","戊":"土",
    "己":"土","庚":"金","辛":"金","壬":"水","癸":"水",
}
STEM_POLARITY = {
    "甲":"阳","乙":"阴","丙":"阳","丁":"阴","戊":"阳",
    "己":"阴","庚":"阳","辛":"阴","壬":"阳","癸":"阴",
}
GENERATES = {"木":"火","火":"土","土":"金","金":"水","水":"木"}
CONTROLS = {"木":"土","土":"水","水":"火","火":"金","金":"木"}

BRANCH_MAIN_STEM = {
    "子":"癸","丑":"己","寅":"甲","卯":"乙","辰":"戊","巳":"丙",
    "午":"丁","未":"己","申":"庚","酉":"辛","戌":"戊","亥":"壬",
}

# Classical Lu branch for each Day Stem.
LU_BRANCH = {
    "甲":"寅","乙":"卯","丙":"巳","丁":"午","戊":"巳",
    "己":"午","庚":"申","辛":"酉","壬":"亥","癸":"子",
}

# Strict standard Yang-Ren mapping for the five Yang Day Stems.
# This intentionally does not define a Yin-stem "刃".
YANGREN_STRICT = {
    "甲":"卯","丙":"午","戊":"午","庚":"酉","壬":"子",
}


def ten_god(day_stem, target_stem):
    de = STEM_ELEMENT[day_stem]
    te = STEM_ELEMENT[target_stem]
    same = STEM_POLARITY[day_stem] == STEM_POLARITY[target_stem]

    if de == te:
        return "比肩" if same else "劫财"
    if GENERATES[de] == te:
        return "食神" if same else "伤官"
    if CONTROLS[de] == te:
        return "偏财" if same else "正财"
    if CONTROLS[te] == de:
        return "七杀" if same else "正官"
    if GENERATES[te] == de:
        return "偏印" if same else "正印"
    raise ValueError((day_stem, target_stem))


def eight_char_at(y,m,d,hour=12,minute=0):
    ec = Solar.fromYmdHms(int(y),int(m),int(d),int(hour),int(minute),0).getLunar().getEightChar()
    return {"year":ec.getYear(),"month":ec.getMonth(),"day":ec.getDay()}


def transition_ambiguous(y,m,d):
    a = eight_char_at(y,m,d,0,30)
    b = eight_char_at(y,m,d,22,30)
    return a["year"] != b["year"] or a["month"] != b["month"]


def date_features(ts):
    y,m,d = ts.year,ts.month,ts.day
    ec = eight_char_at(y,m,d,12,0)
    dp = ec["day"]
    mp = ec["month"]
    ds, mb = dp[0], mp[1]
    main = BRANCH_MAIN_STEM[mb]
    tg = ten_god(ds, main)

    # Exact operational decomposition of month-order 比肩.
    month_order_bijian = int(tg == "比肩")
    bijian_non_earth_jianlu_equiv = int(
        month_order_bijian and STEM_ELEMENT[ds] != "土" and LU_BRANCH[ds] == mb
    )
    bijian_earth_zaqi = int(
        month_order_bijian and STEM_ELEMENT[ds] == "土"
    )

    # Classical Jianlu: includes 戊巳 and 己午.
    jianlu_classical = int(LU_BRANCH[ds] == mb)

    # Month-order 劫财 decomposition.
    month_order_jiecai = int(tg == "劫财")
    yangren_strict = int(ds in YANGREN_STRICT and YANGREN_STRICT[ds] == mb)
    jiecai_yangren_overlap = int(month_order_jiecai and yangren_strict)
    jiecai_yin_non_yangren = int(
        month_order_jiecai and STEM_POLARITY[ds] == "阴" and STEM_ELEMENT[ds] != "土"
    )
    jiecai_earth_zaqi = int(month_order_jiecai and STEM_ELEMENT[ds] == "土")

    # Month-order 伤官 decomposition.
    month_order_shangguan = int(tg == "伤官")
    shangguan_fire_earth_zaqi = int(
        month_order_shangguan and STEM_ELEMENT[ds] == "火"
    )
    shangguan_nonfire = int(
        month_order_shangguan and STEM_ELEMENT[ds] != "火"
    )

    return {
        "day_stem":ds,
        "month_branch":mb,
        "month_order_tengod":tg,
        "month_order_bijian":month_order_bijian,
        "bijian_non_earth_jianlu_equiv":bijian_non_earth_jianlu_equiv,
        "bijian_earth_zaqi":bijian_earth_zaqi,
        "jianlu_classical":jianlu_classical,
        "month_order_jiecai":month_order_jiecai,
        "yangren_strict":yangren_strict,
        "jiecai_yangren_overlap":jiecai_yangren_overlap,
        "jiecai_yin_non_yangren":jiecai_yin_non_yangren,
        "jiecai_earth_zaqi":jiecai_earth_zaqi,
        "month_order_shangguan":month_order_shangguan,
        "shangguan_fire_earth_zaqi":shangguan_fire_earth_zaqi,
        "shangguan_nonfire":shangguan_nonfire,
        "combo":ds+mb,
    }


FEATURES = [
    "month_order_bijian",
    "bijian_non_earth_jianlu_equiv",
    "bijian_earth_zaqi",
    "jianlu_classical",
    "month_order_jiecai",
    "yangren_strict",
    "jiecai_yangren_overlap",
    "jiecai_yin_non_yangren",
    "jiecai_earth_zaqi",
    "month_order_shangguan",
    "shangguan_fire_earth_zaqi",
    "shangguan_nonfire",
]


def music_flag(df):
    if "_music" in df.columns:
        return pd.to_numeric(df["_music"],errors="coerce").fillna(0).astype(int)
    if "broad_categories" in df.columns:
        return df["broad_categories"].fillna("").astype(str).str.split("; ").apply(
            lambda xs: int("Music" in xs)
        )
    raise ValueError("Need _music or broad_categories column.")


def load_north(root, years):
    out=[]
    cache={}
    for y in years:
        p=root/f"hemisphere_{y}"/f"{y}_people_with_hemisphere.csv"
        if not p.exists():
            raise FileNotFoundError(p)
        d=pd.read_csv(p,encoding="utf-8-sig")
        d=d.loc[d["hemisphere"].eq("north")].copy()
        d["_music"]=music_flag(d)
        d["dob"]=pd.to_datetime(d["_birth_date_norm"],errors="coerce")
        d=d.loc[d["dob"].notna()].copy()
        d=d.loc[d["dob"].dt.year.eq(y)].copy()
        d["gregorian_year"]=d["dob"].dt.year.astype(int)
        d["gregorian_month"]=d["dob"].dt.month.astype(int)
        d["weekday"]=d["dob"].dt.day_name()

        rows=[]
        keep=[]
        for ts in d["dob"]:
            key=ts.date().isoformat()
            if key not in cache:
                if transition_ambiguous(ts.year,ts.month,ts.day):
                    cache[key]=None
                else:
                    cache[key]=date_features(ts)
            if cache[key] is None:
                keep.append(False); rows.append(None)
            else:
                keep.append(True); rows.append(cache[key])
        d=d.loc[keep].copy()
        rows=[r for r,k in zip(rows,keep) if k]
        for c in ["day_stem","month_branch","month_order_tengod","combo"]+FEATURES:
            d[c]=[r[c] for r in rows]
        out.append(d)
    return pd.concat(out,ignore_index=True)


def make_daily(d):
    groupcols=[
        "dob","gregorian_year","gregorian_month","weekday",
        "day_stem","month_branch","month_order_tengod","combo",
    ]+FEATURES
    return d.groupby(groupcols,as_index=False).agg(
        n_people=("_music","size"),
        music_n=("_music","sum"),
    )


def make_X(d, feature, model):
    X=pd.DataFrame({feature:d[feature].astype(float)},index=d.index)
    cats=["gregorian_year","gregorian_month","weekday"]
    if model in ("M1","M2"):
        cats.append("day_stem")
    if model=="M2":
        cats.append("month_branch")
    for c in cats:
        dd=pd.get_dummies(d[c].astype("category"),prefix=c,drop_first=True,dtype=float)
        X=pd.concat([X,dd],axis=1)
    return sm.add_constant(X,has_constant="add").astype(float)


def fit_feature(daily, feature, model):
    y=np.column_stack([
        daily["music_n"].to_numpy(float),
        (daily["n_people"]-daily["music_n"]).to_numpy(float),
    ])
    fit=sm.GLM(y,make_X(daily,feature,model),family=sm.families.Binomial()).fit(
        cov_type="HC0",maxiter=200
    )
    b=float(fit.params[feature]); se=float(fit.bse[feature]); p=float(fit.pvalues[feature])
    mask=daily[feature].astype(bool)
    n1=int(daily.loc[mask,"n_people"].sum()); y1=int(daily.loc[mask,"music_n"].sum())
    n0=int(daily.loc[~mask,"n_people"].sum()); y0=int(daily.loc[~mask,"music_n"].sum())
    return {
        "feature":feature,"model":model,
        "or":math.exp(b),"ci95_low":math.exp(b-1.96*se),"ci95_high":math.exp(b+1.96*se),
        "p_two_sided":p,
        "feature_people":n1,"feature_music":y1,"feature_music_rate":y1/n1 if n1 else np.nan,
        "nonfeature_people":n0,"nonfeature_music":y0,"nonfeature_music_rate":y0/n0 if n0 else np.nan,
    }


def combo_descriptives(d):
    rows=[]
    for combo,g in d.groupby("combo"):
        ds=combo[0]; mb=combo[1]
        tg=ten_god(ds,BRANCH_MAIN_STEM[mb])
        n=len(g); ym=int(g["_music"].sum())
        rows.append({
            "combo":combo,"day_stem":ds,"month_branch":mb,
            "month_order_tengod":tg,
            "n_people":n,"music_n":ym,"music_rate":ym/n if n else np.nan,
            "is_classical_jianlu":int(LU_BRANCH[ds]==mb),
            "is_strict_yangren":int(ds in YANGREN_STRICT and YANGREN_STRICT[ds]==mb),
        })
    return pd.DataFrame(rows).sort_values(["month_order_tengod","combo"])


def run_block(d, label):
    daily=make_daily(d)
    rows=[]
    for f in FEATURES:
        for m in ["M0","M1","M2"]:
            rows.append({"cohort":label,**fit_feature(daily,f,m)})
    return pd.DataFrame(rows),combo_descriptives(d)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--years",nargs="+",type=int,default=[1986,1987,1988,1989,1990,1991,1992])
    ap.add_argument("--outdir",default="postvalidation_monthorder_mechanism_1986_1992")
    args=ap.parse_args()

    root=Path(".").resolve()
    outdir=root/args.outdir
    outdir.mkdir(parents=True,exist_ok=True)

    d=load_north(root,args.years)

    blocks=[
        ("1986_1989_discovery",d[d["gregorian_year"].between(1986,1989)].copy()),
        ("1990_1992_validation_era",d[d["gregorian_year"].between(1990,1992)].copy()),
        ("1986_1992_pooled_exploratory",d.copy()),
    ]

    all_models=[]
    all_combos=[]
    summary=[]

    summary.append("POST-VALIDATION EXPLORATORY MECHANISM ANALYSIS")
    summary.append("North-primary; 1986–1992 outcomes already revealed.")
    summary.append("Nothing here is confirmatory.")
    summary.append("")

    for label,sub in blocks:
        models,combos=run_block(sub,label)
        combos.insert(0,"cohort",label)
        all_models.append(models); all_combos.append(combos)

        summary.append("="*80)
        summary.append(label)
        summary.append(f"People: {len(sub):,}; Music: {int(sub['_music'].sum()):,}")
        for f in [
            "month_order_bijian","bijian_non_earth_jianlu_equiv","bijian_earth_zaqi","jianlu_classical",
            "month_order_shangguan","shangguan_fire_earth_zaqi","shangguan_nonfire",
            "month_order_jiecai","yangren_strict",
        ]:
            r=models[(models["feature"]==f)&(models["model"]=="M2")].iloc[0]
            summary.append(
                f"{f}: M2 OR={r['or']:.4f}, 95CI=[{r['ci95_low']:.4f},{r['ci95_high']:.4f}], p2={r['p_two_sided']:.6g}"
            )
        summary.append("")

    pd.concat(all_models,ignore_index=True).to_csv(
        outdir/"mechanism_models.csv",index=False,encoding="utf-8-sig"
    )
    pd.concat(all_combos,ignore_index=True).to_csv(
        outdir/"exact_daystem_monthbranch_combo_descriptives.csv",index=False,encoding="utf-8-sig"
    )
    d.to_csv(outdir/"north_people_with_mechanism_features.csv",index=False,encoding="utf-8-sig")
    (outdir/"MECHANISM_SUMMARY.txt").write_text("\n".join(summary),encoding="utf-8")

    print("\n".join(summary))
    print("Saved:",outdir)


if __name__=="__main__":
    main()
