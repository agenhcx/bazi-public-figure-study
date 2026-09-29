#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Post-validation exact-combination diagnostic for Music × BaZi.

North-primary, 1986–1992.

Purpose
-------
Check whether two previously observed exploratory structures are broad
multi-combination patterns or are driven by one/few exact Day-Stem ×
Month-Branch combinations.

Family A — Earth-Day-Master matching-main-qi tomb-month:
    戊辰, 戊戌, 己丑, 己未

Family B — non-Fire month-order 伤官:
    甲午, 乙巳, 戊酉, 己申, 庚子, 辛亥, 壬卯, 癸寅

IMPORTANT
---------
1986–1992 outcomes have already been inspected.
Everything produced here is POST-VALIDATION EXPLORATORY.

Models
------
For each exact combination separately:

M0:
    Music/non-Music ~ exact_combo
                      + C(Gregorian year)
                      + C(Gregorian month)
                      + C(weekday)

M2:
    M0 + C(day_stem) + C(month_branch)

M2 is the key diagnostic: it estimates the specific Day-Stem ×
Month-Branch pairing beyond the marginal Day-Stem and Month-Branch
composition.

Outputs include:
- adjusted OR / 95% CI / two-sided p
- raw Music rate inside and outside the exact combo
- direction count: how many exact combinations have M2 OR > 1
- forest plot for M2 pooled effects
"""

import argparse
import math
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
import matplotlib.pyplot as plt
from lunar_python import Solar


EARTH_MATCH = ["戊辰","戊戌","己丑","己未"]
NONFIRE_SHANGGUAN = ["甲午","乙巳","戊酉","己申","庚子","辛亥","壬卯","癸寅"]

FAMILY_MAP = {
    **{x:"Earth_matching_tomb_month" for x in EARTH_MATCH},
    **{x:"NonFire_month_order_shangguan" for x in NONFIRE_SHANGGUAN},
}

ALL_COMBOS = EARTH_MATCH + NONFIRE_SHANGGUAN


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

    return {
        "day_stem":ds,
        "month_branch":mb,
        "combo":ds+mb,
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


def load_north(root, years):
    frames = []
    cache = {}

    for y in years:
        p = root / f"hemisphere_{y}" / f"{y}_people_with_hemisphere.csv"

        if not p.exists():
            raise FileNotFoundError(p)

        d = pd.read_csv(p,encoding="utf-8-sig")

        d = d.loc[d["hemisphere"].eq("north")].copy()
        d["_music"] = music_flag(d)

        d["dob"] = pd.to_datetime(
            d["_birth_date_norm"],errors="coerce"
        )

        d = d.loc[d["dob"].notna()].copy()
        d = d.loc[d["dob"].dt.year.eq(int(y))].copy()

        d["gregorian_year"] = d["dob"].dt.year.astype(int)
        d["gregorian_month"] = d["dob"].dt.month.astype(int)
        d["weekday"] = d["dob"].dt.day_name()

        keep = []
        feats = []

        for ts in d["dob"]:
            key = ts.date().isoformat()

            if key not in cache:
                if transition_ambiguous(ts.year,ts.month,ts.day):
                    cache[key] = None
                else:
                    cache[key] = date_features(ts)

            f = cache[key]
            keep.append(f is not None)
            feats.append(f)

        d = d.loc[keep].copy()
        feats = [f for f,k in zip(feats,keep) if k]

        d["day_stem"] = [f["day_stem"] for f in feats]
        d["month_branch"] = [f["month_branch"] for f in feats]
        d["combo"] = [f["combo"] for f in feats]

        frames.append(d)

    return pd.concat(frames,ignore_index=True)


def make_daily(d):
    return (
        d.groupby(
            [
                "dob",
                "gregorian_year",
                "gregorian_month",
                "weekday",
                "day_stem",
                "month_branch",
                "combo",
            ],
            as_index=False,
        )
        .agg(
            n_people=("_music","size"),
            music_n=("_music","sum"),
        )
    )


def design_matrix(d, feature_col, model):
    X = pd.DataFrame(
        {feature_col:d[feature_col].astype(float)},
        index=d.index,
    )

    cats = [
        "gregorian_year",
        "gregorian_month",
        "weekday",
    ]

    if model == "M2":
        cats += ["day_stem","month_branch"]

    for c in cats:
        dd = pd.get_dummies(
            d[c].astype("category"),
            prefix=c,
            drop_first=True,
            dtype=float,
        )
        X = pd.concat([X,dd],axis=1)

    return sm.add_constant(X,has_constant="add").astype(float)


def fit_exact_combo(daily, combo, model):
    x = daily.copy()
    feature = f"is_{combo}"
    x[feature] = x["combo"].eq(combo).astype(int)

    if x[feature].sum() == 0:
        return {
            "combo":combo,
            "family":FAMILY_MAP[combo],
            "model":model,
            "status":"no_target_dates",
        }

    y = np.column_stack([
        x["music_n"].to_numpy(float),
        (x["n_people"]-x["music_n"]).to_numpy(float),
    ])

    try:
        fit = sm.GLM(
            y,
            design_matrix(x,feature,model),
            family=sm.families.Binomial(),
        ).fit(cov_type="HC0",maxiter=200)

        b = float(fit.params[feature])
        se = float(fit.bse[feature])
        p2 = float(fit.pvalues[feature])

        mask = x[feature].astype(bool)

        n1 = int(x.loc[mask,"n_people"].sum())
        y1 = int(x.loc[mask,"music_n"].sum())
        n0 = int(x.loc[~mask,"n_people"].sum())
        y0 = int(x.loc[~mask,"music_n"].sum())

        return {
            "combo":combo,
            "family":FAMILY_MAP[combo],
            "model":model,
            "status":"ok",

            "beta":b,
            "se":se,
            "or":math.exp(b),
            "ci95_low":math.exp(b-1.96*se),
            "ci95_high":math.exp(b+1.96*se),
            "p_two_sided_exploratory":p2,

            "target_dates":int(mask.sum()),
            "target_people":n1,
            "target_music":y1,
            "target_music_rate":y1/n1 if n1 else np.nan,

            "other_people":n0,
            "other_music":y0,
            "other_music_rate":y0/n0 if n0 else np.nan,
        }

    except Exception as e:
        return {
            "combo":combo,
            "family":FAMILY_MAP[combo],
            "model":model,
            "status":f"fit_failed: {type(e).__name__}: {e}",
        }


def analyze_block(d,label):
    daily = make_daily(d)
    rows = []

    for combo in ALL_COMBOS:
        for model in ["M0","M2"]:
            rows.append({
                "cohort":label,
                **fit_exact_combo(daily,combo,model),
            })

    return daily,pd.DataFrame(rows)


def direction_summary(models):
    rows=[]

    for (cohort,family),g in models.groupby(["cohort","family"]):
        g = g.loc[
            g["model"].eq("M2") &
            g["status"].eq("ok")
        ].copy()

        n = len(g)
        n_pos = int((g["or"] > 1).sum())
        n_neg = int((g["or"] < 1).sum())
        n_eq = int((g["or"] == 1).sum())

        rows.append({
            "cohort":cohort,
            "family":family,
            "n_estimable_combos":n,
            "n_or_gt_1":n_pos,
            "n_or_lt_1":n_neg,
            "n_or_eq_1":n_eq,
            "fraction_or_gt_1":n_pos/n if n else np.nan,
            "median_or":float(g["or"].median()) if n else np.nan,
            "geomean_or":float(np.exp(np.log(g["or"]).mean())) if n else np.nan,
        })

    return pd.DataFrame(rows)


def make_forest_plot(models,outpath):
    d = models.loc[
        (models["cohort"]=="1986_1992_pooled_exploratory") &
        (models["model"]=="M2") &
        (models["status"]=="ok")
    ].copy()

    d["order"] = d["combo"].map(
        {c:i for i,c in enumerate(ALL_COMBOS)}
    )
    d = d.sort_values("order",ascending=False)

    fig,ax = plt.subplots(figsize=(8,7))

    y = np.arange(len(d))

    ax.errorbar(
        d["or"],
        y,
        xerr=[
            d["or"]-d["ci95_low"],
            d["ci95_high"]-d["or"],
        ],
        fmt="o",
        capsize=3,
    )

    ax.axvline(1.0,linestyle="--")
    ax.set_yticks(y)
    ax.set_yticklabels(
        [
            f"{r.combo}  ({'土四墓' if r.family=='Earth_matching_tomb_month' else '非火伤官'})"
            for r in d.itertuples()
        ]
    )

    ax.set_xscale("log")
    ax.set_xlabel("Adjusted OR (M2, log scale)")
    ax.set_title(
        "Post-validation exploratory exact-combination effects\n"
        "North-primary, pooled 1986–1992"
    )

    fig.tight_layout()
    fig.savefig(outpath,dpi=180,bbox_inches="tight")
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()

    ap.add_argument(
        "--years",
        nargs="+",
        type=int,
        default=[1986,1987,1988,1989,1990,1991,1992],
    )

    ap.add_argument(
        "--outdir",
        default="postvalidation_exact_combo_diagnostic_1986_1992",
    )

    args = ap.parse_args()

    root = Path(".").resolve()
    outdir = root / args.outdir
    outdir.mkdir(parents=True,exist_ok=True)

    people = load_north(root,args.years)

    blocks = [
        (
            "1986_1989_discovery",
            people.loc[
                people["gregorian_year"].between(1986,1989)
            ].copy(),
        ),
        (
            "1990_1992_validation_era",
            people.loc[
                people["gregorian_year"].between(1990,1992)
            ].copy(),
        ),
        (
            "1986_1992_pooled_exploratory",
            people.copy(),
        ),
    ]

    model_frames=[]
    daily_frames=[]

    for label,sub in blocks:
        daily,models = analyze_block(sub,label)
        daily["cohort"] = label

        model_frames.append(models)
        daily_frames.append(daily)

    all_models = pd.concat(model_frames,ignore_index=True)
    all_daily = pd.concat(daily_frames,ignore_index=True)

    directions = direction_summary(all_models)

    all_models.to_csv(
        outdir/"exact_combo_models.csv",
        index=False,
        encoding="utf-8-sig",
    )

    directions.to_csv(
        outdir/"exact_combo_direction_summary.csv",
        index=False,
        encoding="utf-8-sig",
    )

    all_daily.to_csv(
        outdir/"exact_combo_daily_analysis_table.csv",
        index=False,
        encoding="utf-8-sig",
    )

    make_forest_plot(
        all_models,
        outdir/"exact_combo_forest_M2_pooled.png",
    )

    lines = [
        "POST-VALIDATION EXACT-COMBO DIAGNOSTIC",
        "North-primary, 1986–1992",
        "",
        "Family A: 戊辰 / 戊戌 / 己丑 / 己未",
        "Family B: 甲午 / 乙巳 / 戊酉 / 己申 / 庚子 / 辛亥 / 壬卯 / 癸寅",
        "",
        "M2 = exact combo + Gregorian year + Gregorian month + weekday + Day Stem + Month Branch",
        "",
        "All results are exploratory.",
        "",
    ]

    for cohort in [
        "1986_1989_discovery",
        "1990_1992_validation_era",
        "1986_1992_pooled_exploratory",
    ]:
        lines.append("="*80)
        lines.append(cohort)

        g = all_models.loc[
            (all_models["cohort"]==cohort) &
            (all_models["model"]=="M2")
        ]

        for family in [
            "Earth_matching_tomb_month",
            "NonFire_month_order_shangguan",
        ]:
            lines.append("")
            lines.append(family)

            q = g.loc[g["family"]==family]

            for _,r in q.iterrows():
                if r["status"] == "ok":
                    lines.append(
                        f"  {r['combo']}: "
                        f"OR={r['or']:.4f}, "
                        f"95CI=[{r['ci95_low']:.4f},{r['ci95_high']:.4f}], "
                        f"p2={r['p_two_sided_exploratory']:.6g}, "
                        f"N={int(r['target_people'])}, "
                        f"Music={int(r['target_music'])}, "
                        f"rate={r['target_music_rate']:.4%}"
                    )
                else:
                    lines.append(
                        f"  {r['combo']}: {r['status']}"
                    )

            ds = directions.loc[
                (directions["cohort"]==cohort) &
                (directions["family"]==family)
            ]

            if not ds.empty:
                r=ds.iloc[0]
                lines.append(
                    f"  Direction count: "
                    f"{int(r['n_or_gt_1'])}/{int(r['n_estimable_combos'])} OR>1; "
                    f"median OR={r['median_or']:.4f}; "
                    f"geomean OR={r['geomean_or']:.4f}"
                )

        lines.append("")

    summary_path = outdir/"EXACT_COMBO_DIAGNOSTIC_SUMMARY.txt"
    summary_path.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )

    print("\n".join(lines))
    print()
    print("Saved:")
    print(summary_path)


if __name__=="__main__":
    main()
