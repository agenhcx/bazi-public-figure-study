#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Post-validation exploratory specialization analysis within Music.

Question:
Does month-order 伤官 become stronger among creator-coded musicians
(songwriter/composer/singer-songwriter/producer/arranger) than among
other Music-coded public figures?

North-primary, 1986–1992.
All results are exploratory because outcomes have already been inspected.

Important interpretation:
- "creator-coded" means Wikidata P106 occupation labels explicitly contain
  one of the frozen creator-role patterns below.
- "other_music" does NOT mean proven non-creator. It means no creator role
  is explicitly coded in the available P106 labels.
- "solo artist" is NOT inferred here. Absence of band-membership metadata
  is not valid evidence of a solo career.

Creator role patterns (frozen in this script before running):
  singer-songwriter
  songwriter
  composer
  record producer
  music producer
  music arranger

Sensitivity:
  creator_plus_rapper additionally counts rapper as creator-coded.

Main predictors:
  1) month_order_shangguan
  2) nonfire_month_order_shangguan
  3) earth_matching_tomb_month

Main model:
  within Music only:
    creator-coded / other-Music counts
      ~ feature + C(year) + C(gregorian_month) + C(weekday)

Sensitivity model adds Day Stem and Month Branch:
    + C(day_stem) + C(month_branch)

Also reports creator-coded vs all non-creator-coded public figures as
a secondary descriptive occupational-selection model.
"""

import argparse
import math
import re
from pathlib import Path

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

CREATOR_PATTERNS = [
    r"\bsinger-songwriter\b",
    r"\bsongwriter\b",
    r"\bcomposer\b",
    r"\brecord producer\b",
    r"\bmusic producer\b",
    r"\bmusic arranger\b",
]

RAPPER_PATTERN = r"\brapper\b"

MUSIC_PERFORMER_PATTERNS = [
    r"\bsinger\b", r"\bvocalist\b", r"\bmusician\b", r"\brapper\b",
    r"\bguitarist\b", r"\bbassist\b", r"\bdrummer\b", r"\bpianist\b",
    r"\bkeyboardist\b", r"\bviolinist\b", r"\bviolist\b", r"\bcellist\b",
    r"\bdouble bassist\b", r"\bsaxophonist\b", r"\btrumpeter\b",
    r"\btrombonist\b", r"\bclarinetist\b", r"\bflutist\b", r"\boboist\b",
    r"\bpercussionist\b", r"\borganist\b", r"\bharpist\b",
]

EARTH_MATCH_COMBOS = {"戊辰","戊戌","己丑","己未"}


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
    ec = Solar.fromYmdHms(
        int(y),int(m),int(d),int(hour),int(minute),0
    ).getLunar().getEightChar()
    return {
        "year":ec.getYear(),
        "month":ec.getMonth(),
        "day":ec.getDay(),
    }


def transition_ambiguous(y,m,d):
    a = eight_char_at(y,m,d,0,30)
    b = eight_char_at(y,m,d,22,30)
    return a["year"] != b["year"] or a["month"] != b["month"]


def date_features(ts):
    ec = eight_char_at(ts.year,ts.month,ts.day,12,0)
    ds = ec["day"][0]
    mb = ec["month"][1]
    main = BRANCH_MAIN_STEM[mb]
    tg = ten_god(ds,main)
    combo = ds + mb

    return {
        "day_stem":ds,
        "month_branch":mb,
        "month_order_tengod":tg,
        "month_order_shangguan":int(tg=="伤官"),
        "nonfire_month_order_shangguan":int(
            tg=="伤官" and STEM_ELEMENT[ds] != "火"
        ),
        "earth_matching_tomb_month":int(combo in EARTH_MATCH_COMBOS),
        "combo":combo,
    }


def music_flag(df):
    if "_music" in df.columns:
        return (
            pd.to_numeric(df["_music"],errors="coerce")
            .fillna(0).astype(int)
        )

    if "broad_categories" in df.columns:
        return (
            df["broad_categories"].fillna("").astype(str)
            .apply(
                lambda s: int(
                    "Music" in [x.strip() for x in s.split(";") if x.strip()]
                )
            )
        )

    raise ValueError("Need _music or broad_categories column.")


def role_flags(label_text):
    txt = (label_text or "").lower()

    creator = int(any(re.search(p,txt,re.I) for p in CREATOR_PATTERNS))
    rapper = int(bool(re.search(RAPPER_PATTERN,txt,re.I)))
    performer = int(any(re.search(p,txt,re.I) for p in MUSIC_PERFORMER_PATTERNS))

    return {
        "creator_coded":creator,
        "creator_plus_rapper":int(creator or rapper),
        "performer_coded":performer,
        "rapper_coded":rapper,
    }


def load_data(root,years):
    frames=[]
    cache={}

    for y in years:
        p=root/f"hemisphere_{y}"/f"{y}_people_with_hemisphere.csv"
        if not p.exists():
            raise FileNotFoundError(p)

        d=pd.read_csv(p,encoding="utf-8-sig")

        required={"hemisphere","_birth_date_norm","occupation_labels"}
        missing=required-set(d.columns)
        if missing:
            raise ValueError(f"{p} missing {sorted(missing)}")

        d=d.loc[d["hemisphere"].eq("north")].copy()
        d["_music"]=music_flag(d)

        role_rows=[
            role_flags(x)
            for x in d["occupation_labels"].fillna("").astype(str)
        ]
        for c in role_rows[0].keys():
            d[c]=[r[c] for r in role_rows]

        d["dob"]=pd.to_datetime(d["_birth_date_norm"],errors="coerce")
        d=d.loc[d["dob"].notna()].copy()
        d=d.loc[d["dob"].dt.year.eq(y)].copy()

        d["gregorian_year"]=d["dob"].dt.year.astype(int)
        d["gregorian_month"]=d["dob"].dt.month.astype(int)
        d["weekday"]=d["dob"].dt.day_name()

        keep=[]
        feats=[]
        for ts in d["dob"]:
            key=ts.date().isoformat()
            if key not in cache:
                if transition_ambiguous(ts.year,ts.month,ts.day):
                    cache[key]=None
                else:
                    cache[key]=date_features(ts)
            f=cache[key]
            keep.append(f is not None)
            feats.append(f)

        d=d.loc[keep].copy()
        feats=[f for f,k in zip(feats,keep) if k]

        for c in feats[0].keys():
            d[c]=[f[c] for f in feats]

        frames.append(d)

    return pd.concat(frames,ignore_index=True)


PREDICTORS = [
    "month_order_shangguan",
    "nonfire_month_order_shangguan",
    "earth_matching_tomb_month",
]


def make_daily_specialization(d,outcome_col,within_music):
    x=d.loc[d["_music"].eq(1)].copy() if within_music else d.copy()

    groupcols=[
        "dob","gregorian_year","gregorian_month","weekday",
        "day_stem","month_branch","combo",
    ]+PREDICTORS

    return x.groupby(groupcols,as_index=False).agg(
        n_people=(outcome_col,"size"),
        success_n=(outcome_col,"sum"),
    )


def design_matrix(d,feature,model):
    X=pd.DataFrame({feature:d[feature].astype(float)},index=d.index)

    cats=["gregorian_year","gregorian_month","weekday"]
    if model=="M2":
        cats += ["day_stem","month_branch"]

    for c in cats:
        dd=pd.get_dummies(
            d[c].astype("category"),
            prefix=c,
            drop_first=True,
            dtype=float,
        )
        X=pd.concat([X,dd],axis=1)

    return sm.add_constant(X,has_constant="add").astype(float)


def fit_model(daily,feature,model):
    if daily[feature].nunique() < 2:
        return {"status":"not_estimable"}

    y=np.column_stack([
        daily["success_n"].to_numpy(float),
        (daily["n_people"]-daily["success_n"]).to_numpy(float),
    ])

    try:
        fit=sm.GLM(
            y,
            design_matrix(daily,feature,model),
            family=sm.families.Binomial(),
        ).fit(cov_type="HC0",maxiter=200)

        b=float(fit.params[feature])
        se=float(fit.bse[feature])

        mask=daily[feature].astype(bool)
        n1=int(daily.loc[mask,"n_people"].sum())
        y1=int(daily.loc[mask,"success_n"].sum())
        n0=int(daily.loc[~mask,"n_people"].sum())
        y0=int(daily.loc[~mask,"success_n"].sum())

        return {
            "status":"ok",
            "beta":b,
            "se":se,
            "or":math.exp(b),
            "ci95_low":math.exp(b-1.96*se),
            "ci95_high":math.exp(b+1.96*se),
            "p_two_sided_exploratory":float(fit.pvalues[feature]),
            "feature_people":n1,
            "feature_success":y1,
            "feature_rate":y1/n1 if n1 else np.nan,
            "nonfeature_people":n0,
            "nonfeature_success":y0,
            "nonfeature_rate":y0/n0 if n0 else np.nan,
        }

    except Exception as e:
        return {
            "status":f"fit_failed: {type(e).__name__}: {e}"
        }


def run_block(d,label):
    rows=[]

    specs=[
        # Main: creator coding among Music.
        ("creator_coded","within_music",True),
        # Sensitivity: rapper counted as creator.
        ("creator_plus_rapper","within_music",True),
        # Descriptive occupational selection against all public figures.
        ("creator_coded","all_people",False),
    ]

    for outcome,scope,within_music in specs:
        daily=make_daily_specialization(d,outcome,within_music)

        for feature in PREDICTORS:
            for model in ["M0","M2"]:
                rows.append({
                    "cohort":label,
                    "outcome":outcome,
                    "scope":scope,
                    "feature":feature,
                    "model":model,
                    **fit_model(daily,feature,model),
                })

    return pd.DataFrame(rows)


def audit_roles(d):
    music=d.loc[d["_music"].eq(1)].copy()

    rows=[
        {
            "metric":"Music people",
            "n":len(music),
            "pct_of_music":1.0,
        },
        {
            "metric":"creator_coded",
            "n":int(music["creator_coded"].sum()),
            "pct_of_music":float(music["creator_coded"].mean()),
        },
        {
            "metric":"creator_plus_rapper",
            "n":int(music["creator_plus_rapper"].sum()),
            "pct_of_music":float(music["creator_plus_rapper"].mean()),
        },
        {
            "metric":"performer_coded",
            "n":int(music["performer_coded"].sum()),
            "pct_of_music":float(music["performer_coded"].mean()),
        },
        {
            "metric":"music_without_creator_coded",
            "n":int((music["creator_coded"]==0).sum()),
            "pct_of_music":float((music["creator_coded"]==0).mean()),
        },
    ]

    return pd.DataFrame(rows)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument(
        "--years",nargs="+",type=int,
        default=[1986,1987,1988,1989,1990,1991,1992],
    )
    ap.add_argument(
        "--outdir",
        default="postvalidation_music_creator_specialization_1986_1992",
    )
    args=ap.parse_args()

    root=Path(".").resolve()
    outdir=root/args.outdir
    outdir.mkdir(parents=True,exist_ok=True)

    d=load_data(root,args.years)

    blocks=[
        (
            "1986_1989_discovery",
            d.loc[d["gregorian_year"].between(1986,1989)].copy(),
        ),
        (
            "1990_1992_validation_era",
            d.loc[d["gregorian_year"].between(1990,1992)].copy(),
        ),
        (
            "1986_1992_pooled_exploratory",
            d.copy(),
        ),
    ]

    model_frames=[]
    audit_frames=[]

    lines=[
        "POST-VALIDATION MUSIC CREATOR-SPECIALIZATION ANALYSIS",
        "North-primary, 1986–1992",
        "",
        "creator_coded patterns:",
        "  singer-songwriter / songwriter / composer / record producer / music producer / music arranger",
        "",
        "Main contrast:",
        "  within Music only: creator-coded vs other Music-coded people.",
        "",
        "Important:",
        "  other Music-coded does NOT mean proven non-creator.",
        "  solo artist is NOT inferred from absence of group metadata.",
        "  All results are exploratory.",
        "",
    ]

    for label,sub in blocks:
        m=run_block(sub,label)
        a=audit_roles(sub)
        a.insert(0,"cohort",label)

        model_frames.append(m)
        audit_frames.append(a)

        lines += [
            "="*80,
            label,
            f"All north people: {len(sub):,}",
            f"Music people: {int(sub['_music'].sum()):,}",
        ]

        aud={r.metric:r for r in a.itertuples()}
        lines.append(
            f"creator_coded: {aud['creator_coded'].n:,} "
            f"({aud['creator_coded'].pct_of_music:.2%} of Music)"
        )
        lines.append(
            f"creator_plus_rapper: {aud['creator_plus_rapper'].n:,} "
            f"({aud['creator_plus_rapper'].pct_of_music:.2%} of Music)"
        )
        lines.append("")

        sel=m.loc[
            (m["scope"]=="within_music") &
            (m["outcome"]=="creator_coded") &
            (m["model"]=="M2")
        ]

        lines.append("Within-Music creator-coded specialization, M2:")

        for _,r in sel.iterrows():
            if r["status"]=="ok":
                lines.append(
                    f"  {r['feature']}: "
                    f"OR={r['or']:.4f}, "
                    f"95CI=[{r['ci95_low']:.4f},{r['ci95_high']:.4f}], "
                    f"p2={r['p_two_sided_exploratory']:.6g}"
                )
            else:
                lines.append(
                    f"  {r['feature']}: {r['status']}"
                )

        lines.append("")

    models=pd.concat(model_frames,ignore_index=True)
    audits=pd.concat(audit_frames,ignore_index=True)

    models.to_csv(
        outdir/"creator_specialization_models.csv",
        index=False,encoding="utf-8-sig"
    )

    audits.to_csv(
        outdir/"creator_role_audit.csv",
        index=False,encoding="utf-8-sig"
    )

    # Person-level audit file for checking classification.
    keep_cols=[
        c for c in [
            "qid","name","occupation_labels","broad_categories",
            "_music","creator_coded","creator_plus_rapper",
            "performer_coded","rapper_coded",
            "dob","day_stem","month_branch","combo",
            "month_order_tengod",
            "month_order_shangguan",
            "nonfire_month_order_shangguan",
            "earth_matching_tomb_month",
        ]
        if c in d.columns
    ]

    d.loc[d["_music"].eq(1),keep_cols].to_csv(
        outdir/"music_people_creator_classification_audit.csv",
        index=False,encoding="utf-8-sig"
    )

    summary=outdir/"CREATOR_SPECIALIZATION_SUMMARY.txt"
    summary.write_text("\n".join(lines),encoding="utf-8")

    print("\n".join(lines))
    print()
    print("Saved:")
    print(summary)


if __name__=="__main__":
    main()
