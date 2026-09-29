#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Post-validation exploratory analysis of 杂气月透干 for the Music × BaZi study.

Scope
-----
North-primary public figures, 1986–1992.

Target structures
-----------------
    戊辰, 戊戌, 己丑, 己未

These are the four combinations that generated the previously observed
"Earth Day Master + matching Earth main-qi tomb month" signal.

IMPORTANT
---------
1986–1992 Music outcomes have already been inspected.
Everything produced here is POST-VALIDATION EXPLORATORY analysis.
Do not describe p-values from this script as confirmatory.

Operational definition of 透干
------------------------------
For a hidden stem in the month branch:

1. Fixed transparency:
   Does that hidden stem appear in the YEAR stem or MONTH stem?

2. Hour-marginalized transparency:
   Enumerate the 12 representative double-hours:
       子 00:00, 丑 02:00, 寅 04:00, ... , 亥 22:00
   and determine whether the hidden stem appears in the hour stem.

3. Total marginal probability:
   If already exposed in year/month -> probability = 1.
   Otherwise -> fraction of the 12 hour pillars whose hour stem equals it.

The DAY STEM is intentionally NOT counted as "透干".
For these four target structures the month main qi is already identical
to the Day Master, so counting the Day Stem would make main-qi
"transparency" trivially 100% and would not represent the usual
格局 meaning of a hidden stem becoming visible elsewhere in the chart.

Four tomb branches contain THREE hidden stems, not two:
    辰: 戊 / 乙 / 癸
    戌: 戊 / 辛 / 丁
    丑: 己 / 癸 / 辛
    未: 己 / 丁 / 乙

We label them main / middle / residual here. This is only an ordering label;
the script does NOT force a single 格局 when multiple hidden stems are exposed.

Models
------
Within the four target structures only, fit grouped-binomial daily GLMs:

    Music/non-Music ~ feature
                      + C(Gregorian year)
                      + C(Gregorian month)
                      + C(weekday)
                      + C(exact combo)

Each transparency probability is tested separately.

This is exploratory mechanism analysis, not a preregistered test.
"""

import argparse
import math
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from lunar_python import Solar


# ---------------------------------------------------------------------
# BaZi mappings
# ---------------------------------------------------------------------

STEM_ELEMENT = {
    "甲":"木","乙":"木","丙":"火","丁":"火","戊":"土",
    "己":"土","庚":"金","辛":"金","壬":"水","癸":"水",
}

STEM_POLARITY = {
    "甲":"阳","乙":"阴","丙":"阳","丁":"阴","戊":"阳",
    "己":"阴","庚":"阳","辛":"阴","壬":"阳","癸":"阴",
}

GENERATES = {"木":"火","火":"土","土":"金","金":"水","水":"木"}
CONTROLS  = {"木":"土","土":"水","水":"火","火":"金","金":"木"}

# main / middle / residual
MONTH_HIDDEN = {
    "辰": ("戊","乙","癸"),
    "戌": ("戊","辛","丁"),
    "丑": ("己","癸","辛"),
    "未": ("己","丁","乙"),
}

TARGET_COMBOS = {"戊辰","戊戌","己丑","己未"}

REPRESENTATIVE_HOURS = [0,2,4,6,8,10,12,14,16,18,20,22]


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


# ---------------------------------------------------------------------
# Pillars
# ---------------------------------------------------------------------

def eight_char_at(y,m,d,hour=12,minute=0):
    ec = Solar.fromYmdHms(
        int(y),int(m),int(d),int(hour),int(minute),0
    ).getLunar().getEightChar()

    return {
        "year": ec.getYear(),
        "month": ec.getMonth(),
        "day": ec.getDay(),
        "time": ec.getTime(),
    }


def transition_ambiguous(y,m,d):
    a = eight_char_at(y,m,d,0,30)
    b = eight_char_at(y,m,d,22,30)
    return a["year"] != b["year"] or a["month"] != b["month"]


# ---------------------------------------------------------------------
# Transparency marginalization
# ---------------------------------------------------------------------

def transparency_features(ts):
    """
    Return date-level transparency features for one target date.

    Day stem is excluded from the definition of 透干.
    """
    noon = eight_char_at(ts.year,ts.month,ts.day,12,0)

    yp = noon["year"]
    mp = noon["month"]
    dp = noon["day"]

    ys = yp[0]
    ms = mp[0]
    ds = dp[0]
    mb = mp[1]

    combo = ds + mb
    if combo not in TARGET_COMBOS:
        return None

    hidden = MONTH_HIDDEN[mb]
    main, middle, residual = hidden

    # Ten-God identity of each hidden stem relative to Day Master.
    tg_main = ten_god(ds, main)
    tg_middle = ten_god(ds, middle)
    tg_residual = ten_god(ds, residual)

    # Fixed visible stems excluding Day Stem.
    fixed_visible = {ys, ms}

    # 12 possible hour stems.
    hour_stems = []
    hour_pillars = []

    for h in REPRESENTATIVE_HOURS:
        ec = eight_char_at(ts.year,ts.month,ts.day,h,0)
        hp = ec["time"]
        hour_pillars.append(hp)
        hour_stems.append(hp[0])

    def stem_stats(stem):
        fixed = int(stem in fixed_visible)
        hour_hits = sum(int(hs == stem) for hs in hour_stems)
        p_hour = hour_hits / 12.0

        # Total probability that the stem is visible in Y/M/H.
        p_total = 1.0 if fixed else p_hour

        return fixed, hour_hits, p_hour, p_total

    main_fixed, main_hour_hits, p_main_hour, p_main_total = stem_stats(main)
    mid_fixed, mid_hour_hits, p_mid_hour, p_mid_total = stem_stats(middle)
    res_fixed, res_hour_hits, p_res_hour, p_res_total = stem_stats(residual)

    # Pattern probabilities across 12 possible hours.
    pattern_counts = Counter()

    for hs in hour_stems:
        visible = set(fixed_visible)
        visible.add(hs)

        exposed = tuple(
            name for name, stem in [
                ("main", main),
                ("middle", middle),
                ("residual", residual),
            ]
            if stem in visible
        )

        if not exposed:
            key = "none"
        elif len(exposed) >= 2:
            key = "multiple"
        else:
            key = exposed[0] + "_only"

        pattern_counts[key] += 1

    def pp(name):
        return pattern_counts[name] / 12.0

    # Any auxiliary hidden stem = middle or residual.
    p_any_aux = 0.0
    p_any_hidden = 0.0

    for hs in hour_stems:
        visible = set(fixed_visible)
        visible.add(hs)

        if middle in visible or residual in visible:
            p_any_aux += 1/12.0

        if main in visible or middle in visible or residual in visible:
            p_any_hidden += 1/12.0

    rec = {
        "year_pillar": yp,
        "month_pillar": mp,
        "day_pillar": dp,
        "day_stem": ds,
        "month_branch": mb,
        "combo": combo,

        "hidden_main": main,
        "hidden_middle": middle,
        "hidden_residual": residual,

        "tg_main": tg_main,
        "tg_middle": tg_middle,
        "tg_residual": tg_residual,

        "year_stem": ys,
        "month_stem": ms,

        "main_fixed_exposed": main_fixed,
        "middle_fixed_exposed": mid_fixed,
        "residual_fixed_exposed": res_fixed,

        "main_hour_hits_12": main_hour_hits,
        "middle_hour_hits_12": mid_hour_hits,
        "residual_hour_hits_12": res_hour_hits,

        "p_main_hour_add": p_main_hour,
        "p_middle_hour_add": p_mid_hour,
        "p_residual_hour_add": p_res_hour,

        "p_main_exposed_total": p_main_total,
        "p_middle_exposed_total": p_mid_total,
        "p_residual_exposed_total": p_res_total,

        "p_any_aux_exposed": p_any_aux,
        "p_any_hidden_exposed": p_any_hidden,

        "p_none_exposed": pp("none"),
        "p_main_only": pp("main_only"),
        "p_middle_only": pp("middle_only"),
        "p_residual_only": pp("residual_only"),
        "p_multiple_exposed": pp("multiple"),

        "hour_stems_12": ";".join(hour_stems),
        "hour_pillars_12": ";".join(hour_pillars),
    }

    # Convenience Ten-God-specific probability columns.
    # If the same Ten God somehow occurred twice, take the union probability
    # later via explicit hour enumeration. In these four structures the
    # three hidden stems have distinct Ten Gods.
    for tg in [
        "比肩","劫财","食神","伤官","偏财","正财",
        "七杀","正官","偏印","正印"
    ]:
        rec[f"p_tg_{tg}_exposed"] = 0.0

    for stem, tg in [
        (main,tg_main),
        (middle,tg_middle),
        (residual,tg_residual),
    ]:
        _, _, _, ptotal = stem_stats(stem)
        rec[f"p_tg_{tg}_exposed"] = ptotal

    return rec


# ---------------------------------------------------------------------
# Input
# ---------------------------------------------------------------------

def music_flag(df):
    if "_music" in df.columns:
        return (
            pd.to_numeric(df["_music"],errors="coerce")
            .fillna(0)
            .astype(int)
        )

    if "broad_categories" in df.columns:
        return (
            df["broad_categories"]
            .fillna("")
            .astype(str)
            .apply(
                lambda s: int(
                    "Music" in [x.strip() for x in s.split(";") if x.strip()]
                )
            )
        )

    raise ValueError("Need _music or broad_categories column.")


def load_target_people(root, years):
    frames = []
    date_cache = {}

    for y in years:
        p = root / f"hemisphere_{y}" / f"{y}_people_with_hemisphere.csv"

        if not p.exists():
            raise FileNotFoundError(p)

        d = pd.read_csv(p,encoding="utf-8-sig")

        required = {"hemisphere","_birth_date_norm"}
        missing = required - set(d.columns)
        if missing:
            raise ValueError(f"{p} missing columns: {sorted(missing)}")

        d = d.loc[d["hemisphere"].eq("north")].copy()
        d["_music"] = music_flag(d)

        d["dob"] = pd.to_datetime(
            d["_birth_date_norm"], errors="coerce"
        )

        d = d.loc[d["dob"].notna()].copy()
        d = d.loc[d["dob"].dt.year.eq(int(y))].copy()

        d["gregorian_year"] = d["dob"].dt.year.astype(int)
        d["gregorian_month"] = d["dob"].dt.month.astype(int)
        d["weekday"] = d["dob"].dt.day_name()

        keep = []
        feat_rows = []

        for ts in d["dob"]:
            key = ts.date().isoformat()

            if key not in date_cache:
                if transition_ambiguous(ts.year,ts.month,ts.day):
                    date_cache[key] = None
                else:
                    date_cache[key] = transparency_features(ts)

            feat = date_cache[key]
            keep.append(feat is not None)
            feat_rows.append(feat)

        d = d.loc[keep].copy()
        feat_rows = [
            f for f,k in zip(feat_rows,keep) if k
        ]

        if d.empty:
            continue

        for col in feat_rows[0].keys():
            d[col] = [f[col] for f in feat_rows]

        frames.append(d)

    if not frames:
        raise RuntimeError("No target people found.")

    return pd.concat(frames,ignore_index=True)


# ---------------------------------------------------------------------
# Daily grouped-binomial models
# ---------------------------------------------------------------------

MODEL_FEATURES = [
    "main_fixed_exposed",
    "middle_fixed_exposed",
    "residual_fixed_exposed",

    "p_main_hour_add",
    "p_middle_hour_add",
    "p_residual_hour_add",

    "p_main_exposed_total",
    "p_middle_exposed_total",
    "p_residual_exposed_total",

    "p_any_aux_exposed",
    "p_any_hidden_exposed",

    "p_none_exposed",
    "p_main_only",
    "p_middle_only",
    "p_residual_only",
    "p_multiple_exposed",

    "p_tg_伤官_exposed",
    "p_tg_食神_exposed",
    "p_tg_偏财_exposed",
    "p_tg_正财_exposed",
    "p_tg_七杀_exposed",
    "p_tg_正官_exposed",
    "p_tg_偏印_exposed",
    "p_tg_正印_exposed",
]


def make_daily(d):
    groupcols = [
        "dob",
        "gregorian_year",
        "gregorian_month",
        "weekday",
        "combo",
        "day_stem",
        "month_branch",
        "tg_main",
        "tg_middle",
        "tg_residual",
    ] + MODEL_FEATURES

    return (
        d.groupby(groupcols,as_index=False)
        .agg(
            n_people=("_music","size"),
            music_n=("_music","sum"),
        )
    )


def design_matrix(d, feature):
    X = pd.DataFrame(
        {feature: pd.to_numeric(d[feature],errors="raise").astype(float)},
        index=d.index,
    )

    for c in ["gregorian_year","gregorian_month","weekday","combo"]:
        dd = pd.get_dummies(
            d[c].astype("category"),
            prefix=c,
            drop_first=True,
            dtype=float,
        )
        X = pd.concat([X,dd],axis=1)

    return sm.add_constant(X,has_constant="add").astype(float)


def fit_feature(daily, feature):
    x = daily.copy()

    # No variation -> not estimable.
    vals = pd.to_numeric(x[feature],errors="coerce")
    if vals.nunique(dropna=True) < 2:
        return {
            "feature": feature,
            "status": "not_estimable_no_variation",
        }

    y = np.column_stack([
        x["music_n"].to_numpy(float),
        (x["n_people"]-x["music_n"]).to_numpy(float),
    ])

    try:
        fit = sm.GLM(
            y,
            design_matrix(x,feature),
            family=sm.families.Binomial(),
        ).fit(cov_type="HC0",maxiter=200)

        b = float(fit.params[feature])
        se = float(fit.bse[feature])
        p = float(fit.pvalues[feature])

        return {
            "feature":feature,
            "status":"ok",
            "beta":b,
            "se":se,
            "or_per_unit":math.exp(b),
            "ci95_low":math.exp(b-1.96*se),
            "ci95_high":math.exp(b+1.96*se),
            "p_two_sided_exploratory":p,
            "feature_min":float(vals.min()),
            "feature_max":float(vals.max()),
            "feature_mean_date_unweighted":float(vals.mean()),
        }

    except Exception as e:
        return {
            "feature":feature,
            "status":f"fit_failed: {type(e).__name__}: {e}",
        }


# ---------------------------------------------------------------------
# Descriptive summaries
# ---------------------------------------------------------------------

def combo_summary(d):
    rows = []

    for combo,g in d.groupby("combo"):
        n = len(g)
        music = int(g["_music"].sum())

        rec = {
            "combo":combo,
            "n_people":n,
            "music_n":music,
            "music_rate":music/n if n else np.nan,
            "n_dates":g["dob"].dt.date.nunique(),
            "tg_main":g["tg_main"].iloc[0],
            "tg_middle":g["tg_middle"].iloc[0],
            "tg_residual":g["tg_residual"].iloc[0],
        }

        for c in [
            "main_fixed_exposed",
            "middle_fixed_exposed",
            "residual_fixed_exposed",
            "p_main_exposed_total",
            "p_middle_exposed_total",
            "p_residual_exposed_total",
            "p_any_aux_exposed",
            "p_multiple_exposed",
        ]:
            rec[f"mean_{c}"] = float(g[c].mean())

        rows.append(rec)

    return pd.DataFrame(rows).sort_values("combo")


def era_label(y):
    if 1986 <= y <= 1989:
        return "1986_1989_discovery"
    if 1990 <= y <= 1992:
        return "1990_1992_validation_era"
    return "other"


def analyze_block(d,label):
    daily = make_daily(d)

    model_rows = []
    for f in MODEL_FEATURES:
        model_rows.append({
            "cohort":label,
            **fit_feature(daily,f),
        })

    csum = combo_summary(d)
    csum.insert(0,"cohort",label)

    return daily, pd.DataFrame(model_rows), csum


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------

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
        default="postvalidation_earth_zaqi_transparency_1986_1992",
    )

    args = ap.parse_args()

    root = Path(".").resolve()
    outdir = root / args.outdir
    outdir.mkdir(parents=True,exist_ok=True)

    people = load_target_people(root,args.years)

    blocks = [
        (
            "1986_1989_discovery",
            people.loc[
                people["gregorian_year"].between(1986,1989)
            ].copy()
        ),
        (
            "1990_1992_validation_era",
            people.loc[
                people["gregorian_year"].between(1990,1992)
            ].copy()
        ),
        (
            "1986_1992_pooled_exploratory",
            people.copy()
        ),
    ]

    all_models = []
    all_combos = []
    all_daily = []

    lines = [
        "POST-VALIDATION EXPLORATORY 杂气月透干 ANALYSIS",
        "North-primary, 1986–1992",
        "",
        "Target combos: 戊辰 / 戊戌 / 己丑 / 己未",
        "",
        "Definition:",
        "  透干 fixed = hidden stem appears in YEAR or MONTH stem.",
        "  DAY STEM is excluded from 透干.",
        "  Hour contribution is marginalized equally across 12 representative double-hours.",
        "",
        "Hidden stems:",
        "  辰 = 戊 / 乙 / 癸",
        "  戌 = 戊 / 辛 / 丁",
        "  丑 = 己 / 癸 / 辛",
        "  未 = 己 / 丁 / 乙",
        "",
        "All p-values below are exploratory because outcomes were already inspected.",
        "",
    ]

    for label,sub in blocks:
        if sub.empty:
            continue

        daily,models,csum = analyze_block(sub,label)

        all_daily.append(daily.assign(cohort=label))
        all_models.append(models)
        all_combos.append(csum)

        lines += [
            "="*80,
            label,
            f"People: {len(sub):,}",
            f"Music: {int(sub['_music'].sum()):,}",
            f"Dates: {sub['dob'].dt.date.nunique():,}",
            "",
            "Combo summary:",
        ]

        for _,r in csum.iterrows():
            lines.append(
                f"  {r['combo']}: "
                f"N={int(r['n_people'])}, "
                f"Music={int(r['music_n'])}, "
                f"rate={r['music_rate']:.4%}, "
                f"hidden TG={r['tg_main']}/{r['tg_middle']}/{r['tg_residual']}"
            )

        lines.append("")
        lines.append("Selected transparency models:")

        selected = [
            "p_main_exposed_total",
            "p_middle_exposed_total",
            "p_residual_exposed_total",
            "p_any_aux_exposed",
            "p_multiple_exposed",
        ]

        for f in selected:
            r = models.loc[models["feature"].eq(f)].iloc[0]

            if r["status"] == "ok":
                lines.append(
                    f"  {f}: "
                    f"OR/unit={r['or_per_unit']:.4f}, "
                    f"95CI=[{r['ci95_low']:.4f},{r['ci95_high']:.4f}], "
                    f"p2={r['p_two_sided_exploratory']:.6g}"
                )
            else:
                lines.append(
                    f"  {f}: {r['status']}"
                )

        lines.append("")

    # Outputs.
    people.to_csv(
        outdir/"earth_zaqi_people_with_transparency.csv",
        index=False,
        encoding="utf-8-sig",
    )

    pd.concat(all_daily,ignore_index=True).to_csv(
        outdir/"earth_zaqi_daily_analysis_table.csv",
        index=False,
        encoding="utf-8-sig",
    )

    pd.concat(all_models,ignore_index=True).to_csv(
        outdir/"earth_zaqi_transparency_models.csv",
        index=False,
        encoding="utf-8-sig",
    )

    pd.concat(all_combos,ignore_index=True).to_csv(
        outdir/"earth_zaqi_combo_summary.csv",
        index=False,
        encoding="utf-8-sig",
    )

    summary_path = outdir/"EARTH_ZAQI_TRANSPARENCY_SUMMARY.txt"
    summary_path.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )

    print("\n".join(lines))
    print()
    print("Saved:")
    print(summary_path)


if __name__ == "__main__":
    main()
