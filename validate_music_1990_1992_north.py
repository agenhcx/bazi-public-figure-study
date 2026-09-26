#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Frozen validation pipeline: Music × BaZi, 1990–1992, north-primary.

Frozen preregistration anchor
-----------------------------
Git tag:
    prereg-music-1990-1992-north-v1

Freeze commit:
    7b0de85

Primary H1:
    month-order 伤官 positively associated with Music.

Secondary S1:
    overall six-component Y/M/D Water is lower than matched-calendar expectation.

Secondary S2:
    month-order 劫财 negatively associated with Music.

Secondary S3:
    month-order 比肩 positively associated with Music.

Multiplicity:
    H1 is the sole primary test.
    S1–S3 are adjusted jointly with BH-FDR across exactly 3 p-values.

Primary sample:
    birth latitude > 0 (north)

Sensitivity samples:
    known coordinates
    full sample

No hypothesis selection or stopping by individual year.
The confirmatory target is pooled 1990+1991+1992.
"""

import argparse
import math
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.stats.multitest import multipletests
from lunar_python import Solar


FREEZE_TAG = "prereg-music-1990-1992-north-v1"
FREEZE_COMMIT = "7b0de85"

ELEMENTS = ["木", "火", "土", "金", "水"]

STEM_ELEMENT = {
    "甲":"木","乙":"木",
    "丙":"火","丁":"火",
    "戊":"土","己":"土",
    "庚":"金","辛":"金",
    "壬":"水","癸":"水",
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


def all_dates_in_year(y):
    d = date(int(y),1,1)
    end = date(int(y),12,31)
    while d <= end:
        yield d
        d += timedelta(days=1)


def eight_char_at(y,m,d,hour=12,minute=0):
    ec = Solar.fromYmdHms(
        int(y),int(m),int(d),int(hour),int(minute),0
    ).getLunar().getEightChar()

    return {
        "year": ec.getYear(),
        "month": ec.getMonth(),
        "day": ec.getDay(),
    }


def transition_ambiguous(y,m,d):
    early = eight_char_at(y,m,d,0,30)
    late = eight_char_at(y,m,d,22,30)

    return (
        early["year"] != late["year"]
        or early["month"] != late["month"]
    )


def date_features(y,m,d):
    noon = eight_char_at(y,m,d,12,0)

    yp = noon["year"]
    mp = noon["month"]
    dp = noon["day"]

    ys,yb = yp[0],yp[1]
    ms,mb = mp[0],mp[1]
    ds,db = dp[0],dp[1]

    month_main = BRANCH_MAIN_STEM[mb]

    components = [
        STEM_ELEMENT[ys],
        STEM_ELEMENT[BRANCH_MAIN_STEM[yb]],
        STEM_ELEMENT[ms],
        STEM_ELEMENT[BRANCH_MAIN_STEM[mb]],
        STEM_ELEMENT[ds],
        STEM_ELEMENT[BRANCH_MAIN_STEM[db]],
    ]

    cnt = Counter(components)

    return {
        "year_pillar": yp,
        "month_pillar": mp,
        "day_pillar": dp,
        "day_stem": ds,
        "month_order_tengod": ten_god(ds, month_main),
        **{f"n_{e}": int(cnt[e]) for e in ELEMENTS},
    }


def load_people(root, years):
    frames = []

    for y in years:
        p = root / f"hemisphere_{y}" / f"{y}_people_with_hemisphere.csv"

        if not p.exists():
            raise SystemExit(
                f"\nMissing required hemisphere-enriched file:\n{p}\n\n"
                f"Create it before validation. Do NOT replace the north rule "
                f"with nationality/country inference."
            )

        d = pd.read_csv(p, encoding="utf-8-sig")

        needed = ["_music","_birth_date_norm","hemisphere"]
        missing = [c for c in needed if c not in d.columns]
        if missing:
            raise SystemExit(f"{p} missing columns: {missing}")

        d["_music"] = (
            pd.to_numeric(d["_music"],errors="coerce")
            .fillna(0).astype(int)
        )

        d["dob"] = pd.to_datetime(
            d["_birth_date_norm"], errors="coerce"
        )
        d = d.loc[d["dob"].notna()].copy()
        d["gregorian_year"] = d["dob"].dt.year.astype(int)
        d["gregorian_month"] = d["dob"].dt.month.astype(int)
        d["weekday"] = d["dob"].dt.day_name()
        d["source_year"] = int(y)

        # Compute ambiguity + frozen date-derived features.
        amb = []
        feats = []

        for dt in d["dob"]:
            a = transition_ambiguous(dt.year,dt.month,dt.day)
            amb.append(a)
            feats.append(
                None if a else date_features(dt.year,dt.month,dt.day)
            )

        d["pillar_transition_ambiguous"] = amb

        keep = ~d["pillar_transition_ambiguous"]
        d = d.loc[keep].copy()
        feats = [f for f,a in zip(feats,amb) if not a]

        for col in [
            "year_pillar",
            "month_pillar",
            "day_pillar",
            "day_stem",
            "month_order_tengod",
        ] + [f"n_{e}" for e in ELEMENTS]:
            d[col] = [f[col] for f in feats]

        frames.append(d)

    if not frames:
        raise SystemExit("No people loaded.")

    return pd.concat(frames,ignore_index=True)


def filter_scope(d, scope):
    if scope == "north":
        return d.loc[d["hemisphere"]=="north"].copy()
    if scope == "known":
        return d.loc[
            d["hemisphere"].isin(["north","south","equator"])
        ].copy()
    if scope == "full":
        return d.copy()
    raise ValueError(scope)


def make_daily(people):
    return (
        people
        .groupby(
            [
                "dob",
                "gregorian_year",
                "gregorian_month",
                "weekday",
                "month_order_tengod",
            ],
            as_index=False,
        )
        .agg(
            n_people=("_music","size"),
            Music__n=("_music","sum"),
        )
    )


def design_matrix(d, feature_col):
    X = pd.DataFrame(index=d.index)
    X[feature_col] = pd.to_numeric(
        d[feature_col], errors="raise"
    ).astype(float)

    year_d = pd.get_dummies(
        d["gregorian_year"].astype("category"),
        prefix="year",
        drop_first=True,
        dtype=float,
    )

    month_d = pd.get_dummies(
        d["gregorian_month"].astype("category"),
        prefix="month",
        drop_first=True,
        dtype=float,
    )

    weekday_d = pd.get_dummies(
        d["weekday"].astype("category"),
        prefix="weekday",
        drop_first=True,
        dtype=float,
    )

    X = pd.concat(
        [X,year_d,month_d,weekday_d],
        axis=1,
    )

    return sm.add_constant(X,has_constant="add").astype(float)


def fit_directional_glm(daily, tg, direction):
    x = daily.copy()

    feature = f"feature__month_order__{tg}"
    x[feature] = (
        x["month_order_tengod"] == tg
    ).astype(int)

    y = np.column_stack([
        x["Music__n"].to_numpy(float),
        (x["n_people"]-x["Music__n"]).to_numpy(float),
    ])

    fit = sm.GLM(
        y,
        design_matrix(x,feature),
        family=sm.families.Binomial(),
    ).fit(cov_type="HC0",maxiter=200)

    beta = float(fit.params[feature])
    se = float(fit.bse[feature])
    p2 = float(fit.pvalues[feature])

    if direction == "positive":
        p1 = p2/2 if beta >= 0 else 1-p2/2
    elif direction == "negative":
        p1 = p2/2 if beta <= 0 else 1-p2/2
    else:
        raise ValueError(direction)

    mask = x[feature].astype(bool)

    n1 = int(x.loc[mask,"n_people"].sum())
    y1 = int(x.loc[mask,"Music__n"].sum())
    n0 = int(x.loc[~mask,"n_people"].sum())
    y0 = int(x.loc[~mask,"Music__n"].sum())

    return {
        "ten_god": tg,
        "direction": direction,
        "beta": beta,
        "se": se,
        "adjusted_or": math.exp(beta),
        "ci95_low": math.exp(beta-1.96*se),
        "ci95_high": math.exp(beta+1.96*se),
        "p_one_sided_frozen": p1,
        "p_two_sided": p2,
        "feature_people": n1,
        "feature_music": y1,
        "feature_music_rate": y1/n1 if n1 else np.nan,
        "nonfeature_people": n0,
        "nonfeature_music": y0,
        "nonfeature_music_rate": y0/n0 if n0 else np.nan,
    }


def build_water_calendar_baseline(years):
    baseline = {}

    for y in sorted(set(map(int,years))):
        vals = []

        for dt in all_dates_in_year(y):
            if transition_ambiguous(
                dt.year,dt.month,dt.day
            ):
                continue

            f = date_features(
                dt.year,dt.month,dt.day
            )
            vals.append(f["n_水"])

        baseline[y] = np.asarray(vals,dtype=np.int8)

    return baseline


def observed_music_water(people):
    m = people.loc[people["_music"]==1].copy()
    return int(m["n_水"].sum()), m


def expected_music_water(music_people, baseline):
    yc = Counter(
        int(y) for y in music_people["gregorian_year"]
    )

    exp = 0.0

    for y,n in yc.items():
        exp += n * float(baseline[y].mean())

    return exp


def simulate_music_water(
    music_people,
    baseline,
    reps,
    seed,
):
    rng = np.random.default_rng(seed)

    yc = Counter(
        int(y) for y in music_people["gregorian_year"]
    )

    totals = np.zeros(reps,dtype=np.int32)

    for y,n in sorted(yc.items()):
        vals = baseline[y]
        n_dates = len(vals)

        remaining = n

        while remaining > 0:
            k = min(512,remaining)

            idx = rng.integers(
                0,n_dates,size=(reps,k)
            )

            totals += vals[idx].sum(axis=1,dtype=np.int32)
            remaining -= k

    return totals


def test_water_lower(
    people,
    baseline,
    reps,
    seed,
):
    obs,music = observed_music_water(people)
    exp = expected_music_water(music,baseline)

    sims = simulate_music_water(
        music,baseline,reps,seed
    )

    # frozen direction: lower Water
    p_lower = (
        np.sum(sims <= obs) + 1
    ) / (reps + 1)

    p_upper = (
        np.sum(sims >= obs) + 1
    ) / (reps + 1)

    p2 = min(1.0,2.0*min(p_lower,p_upper))

    n = len(music)
    slots = 6*n

    return {
        "music_people_n": n,
        "observed_water_count": obs,
        "observed_water_share": obs/slots if slots else np.nan,
        "observed_water_mean_per_person": obs/n if n else np.nan,
        "expected_water_count": exp,
        "expected_water_share": exp/slots if slots else np.nan,
        "expected_water_mean_per_person": exp/n if n else np.nan,
        "enrichment": obs/exp if exp else np.nan,
        "p_one_sided_lower_frozen": p_lower,
        "p_two_sided": p2,
        "mc_reps": reps,
    }


def per_year_descriptives(people, baseline, reps, seed):
    rows = []

    for y in sorted(people["gregorian_year"].unique()):
        py = people.loc[
            people["gregorian_year"]==y
        ].copy()

        daily = make_daily(py)

        h1 = fit_directional_glm(
            daily,"伤官","positive"
        )
        s2 = fit_directional_glm(
            daily,"劫财","negative"
        )
        s3 = fit_directional_glm(
            daily,"比肩","positive"
        )
        s1 = test_water_lower(
            py,baseline,reps,seed+int(y)
        )

        rows += [
            {
                "year":int(y),
                "hypothesis":"H1_month_order_shangguan_positive",
                "effect":h1["adjusted_or"],
                "p_directional":h1["p_one_sided_frozen"],
            },
            {
                "year":int(y),
                "hypothesis":"S1_water_lower",
                "effect":s1["enrichment"],
                "p_directional":s1["p_one_sided_lower_frozen"],
            },
            {
                "year":int(y),
                "hypothesis":"S2_month_order_jiecai_negative",
                "effect":s2["adjusted_or"],
                "p_directional":s2["p_one_sided_frozen"],
            },
            {
                "year":int(y),
                "hypothesis":"S3_month_order_bijian_positive",
                "effect":s3["adjusted_or"],
                "p_directional":s3["p_one_sided_frozen"],
            },
        ]

    return pd.DataFrame(rows)


def analyze_scope(
    all_people,
    scope,
    water_baseline,
    reps,
    seed,
):
    people = filter_scope(
        all_people,scope
    )

    daily = make_daily(people)

    h1 = fit_directional_glm(
        daily,"伤官","positive"
    )

    s2 = fit_directional_glm(
        daily,"劫财","negative"
    )

    s3 = fit_directional_glm(
        daily,"比肩","positive"
    )

    s1 = test_water_lower(
        people,
        water_baseline,
        reps,
        seed,
    )

    primary = pd.DataFrame([{
        "scope":scope,
        "hypothesis":"H1_month_order_shangguan_positive",
        **h1,
    }])

    secondary = pd.DataFrame([
        {
            "scope":scope,
            "hypothesis":"S1_water_lower",
            "effect_type":"water_enrichment",
            "effect":s1["enrichment"],
            "raw_p_frozen_direction":s1["p_one_sided_lower_frozen"],
            "details":(
                f"obs={s1['observed_water_count']};"
                f"exp={s1['expected_water_count']:.3f};"
                f"N_music={s1['music_people_n']}"
            ),
        },
        {
            "scope":scope,
            "hypothesis":"S2_month_order_jiecai_negative",
            "effect_type":"adjusted_or",
            "effect":s2["adjusted_or"],
            "raw_p_frozen_direction":s2["p_one_sided_frozen"],
            "details":(
                f"95CI=[{s2['ci95_low']:.4f},{s2['ci95_high']:.4f}]"
            ),
        },
        {
            "scope":scope,
            "hypothesis":"S3_month_order_bijian_positive",
            "effect_type":"adjusted_or",
            "effect":s3["adjusted_or"],
            "raw_p_frozen_direction":s3["p_one_sided_frozen"],
            "details":(
                f"95CI=[{s3['ci95_low']:.4f},{s3['ci95_high']:.4f}]"
            ),
        },
    ])

    secondary["bh_q_secondary_3"] = multipletests(
        secondary["raw_p_frozen_direction"].to_numpy(float),
        alpha=0.05,
        method="fdr_bh",
    )[1]

    peryear = per_year_descriptives(
        people,
        water_baseline,
        reps=min(20000,reps),
        seed=seed+1000,
    )
    peryear["scope"] = scope

    return {
        "people":people,
        "daily":daily,
        "primary":primary,
        "secondary":secondary,
        "peryear":peryear,
        "water_detail":pd.DataFrame([{
            "scope":scope,
            **s1,
        }]),
        "s2_detail":pd.DataFrame([{
            "scope":scope,
            **s2,
        }]),
        "s3_detail":pd.DataFrame([{
            "scope":scope,
            **s3,
        }]),
    }


def write_summary(results,outdir,reps):
    north = results["north"]
    h1 = north["primary"].iloc[0]
    sec = north["secondary"]

    lines = [
        "FROZEN VALIDATION RESULT",
        "Music × BaZi, 1990–1992",
        "",
        f"Freeze tag: {FREEZE_TAG}",
        f"Freeze commit: {FREEZE_COMMIT}",
        "",
        "PRIMARY SAMPLE: NORTH ONLY",
        f"Eligible people: {len(north['people']):,}",
        f"Eligible dates represented: {len(north['daily']):,}",
        "",
        "PRIMARY HYPOTHESIS",
        "H1: month-order 伤官 positive",
        f"Adjusted OR = {h1['adjusted_or']:.6f}",
        f"95% CI = [{h1['ci95_low']:.6f}, {h1['ci95_high']:.6f}]",
        f"Frozen one-sided p = {h1['p_one_sided_frozen']:.8g}",
        f"Two-sided p = {h1['p_two_sided']:.8g}",
        "",
        "SECONDARY FAMILY (BH-FDR across exactly 3 tests)",
    ]

    for _,r in sec.iterrows():
        lines.append(
            f"{r['hypothesis']}: "
            f"effect={r['effect']:.6f}, "
            f"raw directional p={r['raw_p_frozen_direction']:.8g}, "
            f"BH q={r['bh_q_secondary_3']:.8g}"
        )

    lines += [
        "",
        "Sensitivity samples were computed only after applying the same frozen",
        "hypothesis definitions:",
    ]

    for scope in ["known","full"]:
        x = results[scope]
        ph = x["primary"].iloc[0]
        lines.append(
            f"{scope}: H1 OR={ph['adjusted_or']:.4f}, "
            f"p1={ph['p_one_sided_frozen']:.5g}, "
            f"N={len(x['people']):,}"
        )

    lines += [
        "",
        "Per-year estimates are descriptive only; pooled 1990–1992 is confirmatory.",
        f"Water Monte Carlo reps (pooled): {reps}",
        "",
        "Interpretation rule:",
        "Do not promote any newly noticed 1990–1992 feature to confirmatory status.",
    ]

    (outdir/"VALIDATION_RESULT_MUSIC_1990_1992_NORTH.txt").write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def main():
    ap = argparse.ArgumentParser()

    ap.add_argument(
        "--years",
        nargs="+",
        type=int,
        default=[1990,1991,1992],
    )

    ap.add_argument(
        "--outdir",
        default="validation_music_1990_1992_north",
    )

    ap.add_argument(
        "--mc-reps",
        type=int,
        default=100000,
    )

    ap.add_argument(
        "--seed",
        type=int,
        default=20260926,
    )

    args = ap.parse_args()

    if args.years != [1990,1991,1992]:
        raise SystemExit(
            "Frozen validation expects exactly: --years 1990 1991 1992"
        )

    root = Path(".").resolve()
    outdir = root / args.outdir
    outdir.mkdir(parents=True,exist_ok=True)

    print("="*72)
    print("FROZEN VALIDATION PIPELINE")
    print(f"Tag:    {FREEZE_TAG}")
    print(f"Commit: {FREEZE_COMMIT}")
    print("="*72)

    people = load_people(
        root,args.years
    )

    print(
        f"\nLoaded eligible pre-hemisphere-filter people: {len(people):,}"
    )

    water_baseline = build_water_calendar_baseline(
        args.years
    )

    results = {}

    # North is intentionally run first.
    for i,scope in enumerate(
        ["north","known","full"]
    ):
        print(f"\nRunning scope: {scope}")

        results[scope] = analyze_scope(
            people,
            scope,
            water_baseline,
            reps=args.mc_reps,
            seed=args.seed + i*10000,
        )

        r = results[scope]

        r["primary"].to_csv(
            outdir/f"{scope}_primary_H1.csv",
            index=False,
            encoding="utf-8-sig",
        )

        r["secondary"].to_csv(
            outdir/f"{scope}_secondary_S1_S3.csv",
            index=False,
            encoding="utf-8-sig",
        )

        r["peryear"].to_csv(
            outdir/f"{scope}_per_year_descriptive.csv",
            index=False,
            encoding="utf-8-sig",
        )

        r["water_detail"].to_csv(
            outdir/f"{scope}_S1_water_detail.csv",
            index=False,
            encoding="utf-8-sig",
        )

        r["daily"].to_csv(
            outdir/f"{scope}_daily_analysis_table.csv",
            index=False,
            encoding="utf-8-sig",
        )

    pd.concat(
        [results[s]["primary"] for s in ["north","known","full"]],
        ignore_index=True,
    ).to_csv(
        outdir/"all_scopes_primary_H1.csv",
        index=False,
        encoding="utf-8-sig",
    )

    pd.concat(
        [results[s]["secondary"] for s in ["north","known","full"]],
        ignore_index=True,
    ).to_csv(
        outdir/"all_scopes_secondary_S1_S3.csv",
        index=False,
        encoding="utf-8-sig",
    )

    write_summary(
        results,
        outdir,
        args.mc_reps,
    )

    print("\nDONE")
    print(
        f"Main result:\n"
        f"{outdir/'VALIDATION_RESULT_MUSIC_1990_1992_NORTH.txt'}"
    )


if __name__=="__main__":
    main()
