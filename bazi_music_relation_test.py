#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Test whether "relational" BaZi structures are enriched among Music births.

Input
-----
1986_daily_category_stats.csv
Expected columns:
    date
    n_people
    Music__n
(optionally many other category columns)

Main idea
---------
One row = one calendar date, NOT one person.

For each date:
  * compute year/month/day pillars at local noon using lunar_python
  * flag dates whose year/month pillar changes during that civil date
    (solar-term boundary ambiguity because we do not know birth time)
  * create the six frozen features:

    1. DAY_STEM_COMBINE
       day stem combines with year stem OR month stem

    2. DAY_BRANCH_HALF_TRINE
       day branch and year/month branch are two distinct members of
       the same San-He trio

    3. DAY_BRANCH_LIUHE

    4. DAY_BRANCH_CHONG

    5. DAY_BRANCH_XING_HAI
       Xing OR Hai

    6. STEM_COMBINE_AND_HALF_TRINE

Secondary descriptive variables:
    DAY_BRANCH_XING
    DAY_BRANCH_HAI
    HARMONY_ANY
    CONFLICT_ANY
    HARMONY_AND_CONFLICT
    RELATION_SCORE

Statistics
----------
For each frozen feature:
  A) raw pooled Music rate + risk ratio
  B) day-level permutation test:
       shuffle the feature label across dates, preserving number of feature-days
       statistic = pooled Music-rate difference
     This keeps the calendar date as the unit being permuted.
  C) grouped-binomial GLM:
       Music count / total people
       ~ feature + Gregorian month + weekday
     with HC0 robust covariance.

The six frozen tests receive Benjamini-Hochberg FDR correction.

Two scopes are run automatically:
  * gregorian_YEAR
  * dominant_bazi_year_<pillar>
    (for 1986 this should normally be 丙寅; early-January/pre-Lichun dates
     are therefore not silently treated as 丙寅)

Outputs
-------
bazi_relation_music_YEAR/
    YEAR_bazi_feature_daily.csv
    YEAR_frozen_feature_tests.csv
    YEAR_glm_adjusted_tests.csv
    YEAR_relation_score_summary.csv
    YEAR_joint_glm_<scope>.txt
    YEAR_bazi_music_summary.txt

Install
-------
pip install pandas numpy scipy statsmodels lunar_python

Run
---
python bazi_music_relation_test.py --input 1986_daily_category_stats.csv --year 1986

For a faster first pass:
python bazi_music_relation_test.py --input 1986_daily_category_stats.csv --year 1986 --permutations 10000

Notes
-----
This is exploratory historical-data analysis, not evidence that BaZi causally
determines occupation. Gregorian-date-only data lack exact birth time/location.
"""

import argparse
import math
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.stats import fisher_exact
from statsmodels.stats.multitest import multipletests

try:
    from lunar_python import Solar
except ImportError:
    raise SystemExit(
        "Missing package lunar_python.\n"
        "Install with:\n"
        "    pip install lunar_python\n"
    )


# ============================================================
# Classical relationship definitions
# ============================================================

STEM_COMBINES = {
    frozenset(("甲", "己")),
    frozenset(("乙", "庚")),
    frozenset(("丙", "辛")),
    frozenset(("丁", "壬")),
    frozenset(("戊", "癸")),
}

LIUHE = {
    frozenset(("子", "丑")),
    frozenset(("寅", "亥")),
    frozenset(("卯", "戌")),
    frozenset(("辰", "酉")),
    frozenset(("巳", "申")),
    frozenset(("午", "未")),
}

CHONG = {
    frozenset(("子", "午")),
    frozenset(("丑", "未")),
    frozenset(("寅", "申")),
    frozenset(("卯", "酉")),
    frozenset(("辰", "戌")),
    frozenset(("巳", "亥")),
}

HAI = {
    frozenset(("子", "未")),
    frozenset(("丑", "午")),
    frozenset(("寅", "巳")),
    frozenset(("卯", "辰")),
    frozenset(("申", "亥")),
    frozenset(("酉", "戌")),
}

SANHE_GROUPS = [
    frozenset(("申", "子", "辰")),
    frozenset(("亥", "卯", "未")),
    frozenset(("寅", "午", "戌")),
    frozenset(("巳", "酉", "丑")),
]

# Pairwise interpretation of the two traditional 三刑 triads,
# plus 子卯相刑 and self-punishment 辰午酉亥.
XING_TRIADS = [
    frozenset(("寅", "巳", "申")),
    frozenset(("丑", "戌", "未")),
]
XING_PAIR = {frozenset(("子", "卯"))}
SELF_XING = {"辰", "午", "酉", "亥"}


FROZEN_FEATURES = [
    "DAY_STEM_COMBINE",
    "DAY_BRANCH_HALF_TRINE",
    "DAY_BRANCH_LIUHE",
    "DAY_BRANCH_CHONG",
    "DAY_BRANCH_XING_HAI",
    "STEM_COMBINE_AND_HALF_TRINE",
]


# ============================================================
# Relation helpers
# ============================================================

def stem_combine(a, b):
    return frozenset((a, b)) in STEM_COMBINES


def liuhe(a, b):
    return frozenset((a, b)) in LIUHE


def chong(a, b):
    return frozenset((a, b)) in CHONG


def hai(a, b):
    return frozenset((a, b)) in HAI


def half_trine(a, b):
    if a == b:
        return False
    pair = {a, b}
    return any(pair.issubset(group) for group in SANHE_GROUPS)


def xing(a, b):
    if a == b:
        return a in SELF_XING

    pair = {a, b}

    if frozenset(pair) in XING_PAIR:
        return True

    return any(pair.issubset(group) for group in XING_TRIADS)


def any_with_day(day_value, year_value, month_value, func):
    return func(day_value, year_value) or func(day_value, month_value)


def pair_targets(day_value, year_value, month_value, func):
    targets = []
    if func(day_value, year_value):
        targets.append("year")
    if func(day_value, month_value):
        targets.append("month")
    return "+".join(targets)


# ============================================================
# BaZi pillar calculation
# ============================================================

def pillars_at(y, m, d, hour, minute=0):
    solar = Solar.fromYmdHms(y, m, d, hour, minute, 0)
    ec = solar.getLunar().getEightChar()

    return {
        "year_pillar": ec.getYear(),
        "month_pillar": ec.getMonth(),
        "day_pillar": ec.getDay(),
    }


def add_bazi_features(df):
    records = []

    for _, row in df.iterrows():
        dt = pd.Timestamp(row["date"])
        y, m, d = dt.year, dt.month, dt.day

        # Use noon as the representative date-level pillar.
        p = pillars_at(y, m, d, 12, 0)

        # Flag civil dates during which YEAR or MONTH pillar changes.
        # This catches solar-term boundary dates for which birth time matters.
        p_early = pillars_at(y, m, d, 0, 30)
        p_late = pillars_at(y, m, d, 22, 30)

        transition_ambiguous = (
            p_early["year_pillar"] != p_late["year_pillar"]
            or p_early["month_pillar"] != p_late["month_pillar"]
        )

        yg, yz = p["year_pillar"][0], p["year_pillar"][1]
        mg, mz = p["month_pillar"][0], p["month_pillar"][1]
        dg, dz = p["day_pillar"][0], p["day_pillar"][1]

        stem_y = stem_combine(dg, yg)
        stem_m = stem_combine(dg, mg)
        stem_any = stem_y or stem_m

        half_y = half_trine(dz, yz)
        half_m = half_trine(dz, mz)
        half_any = half_y or half_m

        liuhe_y = liuhe(dz, yz)
        liuhe_m = liuhe(dz, mz)
        liuhe_any = liuhe_y or liuhe_m

        chong_y = chong(dz, yz)
        chong_m = chong(dz, mz)
        chong_any = chong_y or chong_m

        xing_y = xing(dz, yz)
        xing_m = xing(dz, mz)
        xing_any = xing_y or xing_m

        hai_y = hai(dz, yz)
        hai_m = hai(dz, mz)
        hai_any = hai_y or hai_m

        xing_hai = xing_any or hai_any

        harmony_any = stem_any or half_any or liuhe_any
        conflict_any = chong_any or xing_any or hai_any

        # Count relation TYPES, not number of pairwise hits.
        relation_score = sum([
            stem_any,
            half_any,
            liuhe_any,
            chong_any,
            xing_any,
            hai_any,
        ])

        rec = row.to_dict()
        rec.update({
            "year_pillar": p["year_pillar"],
            "month_pillar": p["month_pillar"],
            "day_pillar": p["day_pillar"],
            "year_stem": yg,
            "year_branch": yz,
            "month_stem": mg,
            "month_branch": mz,
            "day_stem": dg,
            "day_branch": dz,
            "pillar_transition_ambiguous": transition_ambiguous,

            "DAY_STEM_COMBINE_YEAR": stem_y,
            "DAY_STEM_COMBINE_MONTH": stem_m,
            "DAY_STEM_COMBINE": stem_any,
            "DAY_STEM_COMBINE_TARGET": pair_targets(dg, yg, mg, stem_combine),

            "DAY_BRANCH_HALF_TRINE_YEAR": half_y,
            "DAY_BRANCH_HALF_TRINE_MONTH": half_m,
            "DAY_BRANCH_HALF_TRINE": half_any,
            "DAY_BRANCH_HALF_TRINE_TARGET": pair_targets(dz, yz, mz, half_trine),

            "DAY_BRANCH_LIUHE_YEAR": liuhe_y,
            "DAY_BRANCH_LIUHE_MONTH": liuhe_m,
            "DAY_BRANCH_LIUHE": liuhe_any,
            "DAY_BRANCH_LIUHE_TARGET": pair_targets(dz, yz, mz, liuhe),

            "DAY_BRANCH_CHONG_YEAR": chong_y,
            "DAY_BRANCH_CHONG_MONTH": chong_m,
            "DAY_BRANCH_CHONG": chong_any,
            "DAY_BRANCH_CHONG_TARGET": pair_targets(dz, yz, mz, chong),

            "DAY_BRANCH_XING": xing_any,
            "DAY_BRANCH_XING_TARGET": pair_targets(dz, yz, mz, xing),

            "DAY_BRANCH_HAI": hai_any,
            "DAY_BRANCH_HAI_TARGET": pair_targets(dz, yz, mz, hai),

            "DAY_BRANCH_XING_HAI": xing_hai,

            "STEM_COMBINE_AND_HALF_TRINE": stem_any and half_any,

            "HARMONY_ANY": harmony_any,
            "CONFLICT_ANY": conflict_any,
            "HARMONY_AND_CONFLICT": harmony_any and conflict_any,
            "RELATION_SCORE": relation_score,

            "gregorian_month": m,
            "weekday": dt.day_name(),
        })
        records.append(rec)

    return pd.DataFrame(records)


# ============================================================
# Statistics helpers
# ============================================================

def bh_adjust(pvals):
    pvals = np.asarray(pvals, dtype=float)
    valid = np.isfinite(pvals)
    q = np.full(len(pvals), np.nan)
    reject = np.full(len(pvals), False)

    if valid.any():
        r, qq, _, _ = multipletests(
            pvals[valid],
            alpha=0.05,
            method="fdr_bh",
        )
        q[valid] = qq
        reject[valid] = r

    return reject, q


def pooled_feature_stats(data, feature):
    mask = data[feature].astype(bool).to_numpy()

    n1 = int(data.loc[mask, "n_people"].sum())
    y1 = int(data.loc[mask, "Music__n"].sum())
    n0 = int(data.loc[~mask, "n_people"].sum())
    y0 = int(data.loc[~mask, "Music__n"].sum())

    rate1 = y1 / n1 if n1 else np.nan
    rate0 = y0 / n0 if n0 else np.nan
    rr = rate1 / rate0 if rate0 > 0 else np.nan
    diff = rate1 - rate0

    table = [[y1, n1 - y1], [y0, n0 - y0]]
    _, fisher_p_greater = fisher_exact(table, alternative="greater")
    _, fisher_p_two = fisher_exact(table, alternative="two-sided")

    return {
        "feature": feature,
        "feature_days": int(mask.sum()),
        "nonfeature_days": int((~mask).sum()),
        "feature_people": n1,
        "feature_music": y1,
        "feature_music_rate": rate1,
        "nonfeature_people": n0,
        "nonfeature_music": y0,
        "nonfeature_music_rate": rate0,
        "risk_ratio": rr,
        "rate_difference": diff,
        "fisher_p_one_sided": fisher_p_greater,
        "fisher_p_two_sided": fisher_p_two,
    }


def day_level_permutation_p(data, feature, permutations=50000, seed=20260924):
    """
    Shuffle the feature label across calendar dates, preserving number of
    feature-positive dates. Statistic is pooled Music-rate difference.

    One-sided alternative: feature-positive dates have HIGHER Music rate.
    """
    rng = np.random.default_rng(seed)

    music = data["Music__n"].to_numpy(dtype=float)
    total = data["n_people"].to_numpy(dtype=float)
    mask = data[feature].astype(bool).to_numpy()

    k = int(mask.sum())
    D = len(mask)

    def stat(m):
        y1 = music[m].sum()
        n1 = total[m].sum()
        y0 = music[~m].sum()
        n0 = total[~m].sum()
        return (y1 / n1) - (y0 / n0)

    obs = stat(mask)

    ge = 0
    abs_ge = 0

    # Chunking keeps memory tiny.
    base = np.arange(D)
    for _ in range(permutations):
        idx = rng.choice(base, size=k, replace=False)
        pmask = np.zeros(D, dtype=bool)
        pmask[idx] = True
        s = stat(pmask)
        if s >= obs - 1e-15:
            ge += 1
        if abs(s) >= abs(obs) - 1e-15:
            abs_ge += 1

    p_one = (ge + 1) / (permutations + 1)
    p_two = (abs_ge + 1) / (permutations + 1)

    return obs, p_one, p_two


def build_design_matrix(data, features):
    X = pd.DataFrame(index=data.index)
    for f in features:
        X[f] = data[f].astype(int)

    month_d = pd.get_dummies(
        data["gregorian_month"].astype("category"),
        prefix="month",
        drop_first=True,
        dtype=float,
    )
    weekday_d = pd.get_dummies(
        data["weekday"].astype("category"),
        prefix="weekday",
        drop_first=True,
        dtype=float,
    )

    X = pd.concat([X, month_d, weekday_d], axis=1)
    X = sm.add_constant(X, has_constant="add")
    return X.astype(float)


def grouped_binomial_glm(data, features):
    """
    One row per date, grouped binomial endog:
        [Music successes, non-Music failures]

    HC0 robust covariance is used across date rows.
    """
    y = np.column_stack([
        data["Music__n"].to_numpy(dtype=float),
        (data["n_people"] - data["Music__n"]).to_numpy(dtype=float),
    ])
    X = build_design_matrix(data, features)

    model = sm.GLM(y, X, family=sm.families.Binomial())
    fit = model.fit(cov_type="HC0", maxiter=200)

    return fit, X


def single_feature_adjusted_tests(data):
    rows = []

    for feature in FROZEN_FEATURES:
        try:
            fit, X = grouped_binomial_glm(data, [feature])
            beta = float(fit.params[feature])
            se = float(fit.bse[feature])
            p = float(fit.pvalues[feature])

            rows.append({
                "feature": feature,
                "beta_log_odds": beta,
                "robust_se": se,
                "odds_ratio": math.exp(beta),
                "ci95_low_or": math.exp(beta - 1.96 * se),
                "ci95_high_or": math.exp(beta + 1.96 * se),
                "glm_p_two_sided": p,
                "n_dates": len(data),
            })
        except Exception as e:
            rows.append({
                "feature": feature,
                "beta_log_odds": np.nan,
                "robust_se": np.nan,
                "odds_ratio": np.nan,
                "ci95_low_or": np.nan,
                "ci95_high_or": np.nan,
                "glm_p_two_sided": np.nan,
                "n_dates": len(data),
                "error": str(e),
            })

    out = pd.DataFrame(rows)
    reject, q = bh_adjust(out["glm_p_two_sided"].to_numpy())
    out["glm_fdr_bh_q"] = q
    out["glm_fdr_reject_0_05"] = reject
    return out


def relation_score_summary(data):
    rows = []

    for score, g in data.groupby("RELATION_SCORE"):
        n = int(g["n_people"].sum())
        y = int(g["Music__n"].sum())
        rows.append({
            "relation_score": int(score),
            "n_dates": len(g),
            "n_people": n,
            "music": y,
            "music_rate": y / n if n else np.nan,
        })

    return pd.DataFrame(rows).sort_values("relation_score")


# ============================================================
# Scope analysis
# ============================================================

def analyze_scope(data, scope_name, permutations, seed):
    pooled_rows = []

    for i, feature in enumerate(FROZEN_FEATURES):
        row = pooled_feature_stats(data, feature)

        obs, pperm1, pperm2 = day_level_permutation_p(
            data,
            feature,
            permutations=permutations,
            seed=seed + i * 10007,
        )

        row["permutation_observed_rate_diff"] = obs
        row["permutation_p_one_sided"] = pperm1
        row["permutation_p_two_sided"] = pperm2
        row["scope"] = scope_name
        row["n_dates_scope"] = len(data)

        pooled_rows.append(row)

    pooled = pd.DataFrame(pooled_rows)

    rej, q = bh_adjust(pooled["permutation_p_one_sided"].to_numpy())
    pooled["permutation_fdr_bh_q_one_sided"] = q
    pooled["permutation_fdr_reject_0_05"] = rej

    glm = single_feature_adjusted_tests(data)
    glm.insert(0, "scope", scope_name)

    score = relation_score_summary(data)
    score.insert(0, "scope", scope_name)

    # Joint model is secondary because frozen features overlap.
    try:
        joint_fit, _ = grouped_binomial_glm(data, FROZEN_FEATURES)
        joint_text = joint_fit.summary().as_text()
    except Exception as e:
        joint_text = f"Joint GLM failed: {e}"

    return pooled, glm, score, joint_text


# ============================================================
# Main
# ============================================================

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--input",
        default="1986_daily_category_stats.csv",
    )
    ap.add_argument("--year", type=int, default=1986)
    ap.add_argument(
        "--permutations",
        type=int,
        default=50000,
        help="Day-level permutations per frozen feature (default 50000).",
    )
    ap.add_argument("--seed", type=int, default=20260924)
    ap.add_argument(
        "--outdir",
        default=None,
    )
    ap.add_argument(
        "--include-transition-days",
        action="store_true",
        help=(
            "Include dates where year/month pillar changes during the civil date. "
            "Default main analysis excludes them."
        ),
    )
    args = ap.parse_args()

    inpath = Path(args.input)
    if not inpath.exists():
        raise SystemExit(f"Input file not found: {inpath}")

    outdir = Path(
        args.outdir or f"bazi_relation_music_{args.year}"
    )
    outdir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(inpath)

    required = {"date", "n_people", "Music__n"}
    missing = required - set(df.columns)
    if missing:
        raise SystemExit(
            f"Input is missing columns: {sorted(missing)}\n"
            f"Found columns:\n{list(df.columns)}"
        )

    df["date"] = pd.to_datetime(df["date"])

    # Restrict to requested Gregorian year and make sure counts are numeric.
    df = df.loc[df["date"].dt.year == args.year].copy()
    df["n_people"] = pd.to_numeric(df["n_people"], errors="raise").astype(int)
    df["Music__n"] = pd.to_numeric(df["Music__n"], errors="raise").astype(int)

    if (df["Music__n"] > df["n_people"]).any():
        raise SystemExit("Found Music__n > n_people.")

    print(f"Input dates: {len(df)}")
    print(f"People represented: {df['n_people'].sum():,}")
    print(f"Music counts: {df['Music__n'].sum():,}")
    print()
    print("Calculating year/month/day pillars with lunar_python ...")

    feat = add_bazi_features(df)

    feature_out = outdir / f"{args.year}_bazi_feature_daily.csv"
    feat.to_csv(feature_out, index=False, encoding="utf-8-sig")

    # --------------------------------------------------------
    # Sanity check dates chosen BEFORE this code was run.
    # --------------------------------------------------------
    inspect_dates = [
        f"{args.year}-05-14",
        f"{args.year}-08-01",
        f"{args.year}-11-11",
        f"{args.year}-12-27",
    ]

    print()
    print("=== Sanity check / highlighted dates ===")
    cols = [
        "date",
        "year_pillar",
        "month_pillar",
        "day_pillar",
        "n_people",
        "Music__n",
        "DAY_STEM_COMBINE",
        "DAY_STEM_COMBINE_TARGET",
        "DAY_BRANCH_HALF_TRINE",
        "DAY_BRANCH_HALF_TRINE_TARGET",
        "DAY_BRANCH_LIUHE",
        "DAY_BRANCH_CHONG",
        "DAY_BRANCH_XING",
        "DAY_BRANCH_HAI",
        "RELATION_SCORE",
        "pillar_transition_ambiguous",
    ]

    check = feat.loc[
        feat["date"].dt.strftime("%Y-%m-%d").isin(inspect_dates),
        cols,
    ].copy()

    if len(check):
        print(check.to_string(index=False))
    else:
        print("No highlighted dates found in input.")

    # --------------------------------------------------------
    # Main eligible set
    # --------------------------------------------------------
    if args.include_transition_days:
        eligible = feat.copy()
        transition_note = "included"
    else:
        eligible = feat.loc[~feat["pillar_transition_ambiguous"]].copy()
        transition_note = "excluded"

    print()
    print(
        f"Solar-term transition-ambiguous dates {transition_note}. "
        f"Analysis dates: {len(eligible)}"
    )

    print()
    print("BaZi year-pillar distribution among analysis dates:")
    print(eligible["year_pillar"].value_counts().to_string())

    dominant_year_pillar = eligible["year_pillar"].mode().iloc[0]

    scopes = {
        f"gregorian_{args.year}": eligible,
        f"bazi_year_{dominant_year_pillar}": eligible.loc[
            eligible["year_pillar"] == dominant_year_pillar
        ].copy(),
    }

    pooled_all = []
    glm_all = []
    score_all = []
    joint_paths = []

    for scope_name, dscope in scopes.items():
        print()
        print("=" * 72)
        print(f"SCOPE: {scope_name}")
        print(f"Dates: {len(dscope)}")
        print(
            f"People={dscope['n_people'].sum():,}, "
            f"Music={dscope['Music__n'].sum():,}, "
            f"Music rate={dscope['Music__n'].sum()/dscope['n_people'].sum():.4%}"
        )
        print(
            f"Running {args.permutations:,} day-level permutations "
            f"for each of {len(FROZEN_FEATURES)} frozen features ..."
        )

        pooled, glm, score, joint_text = analyze_scope(
            dscope,
            scope_name,
            permutations=args.permutations,
            seed=args.seed,
        )

        pooled_all.append(pooled)
        glm_all.append(glm)
        score_all.append(score)

        joint_path = outdir / f"{args.year}_joint_glm_{scope_name}.txt"
        joint_path.write_text(joint_text, encoding="utf-8")
        joint_paths.append(joint_path)

        show_cols = [
            "feature",
            "feature_days",
            "feature_music_rate",
            "nonfeature_music_rate",
            "risk_ratio",
            "permutation_p_one_sided",
            "permutation_fdr_bh_q_one_sided",
        ]
        print()
        print("Frozen-feature permutation results:")
        print(
            pooled[show_cols]
            .sort_values("permutation_p_one_sided")
            .to_string(index=False, float_format=lambda x: f"{x:.5g}")
        )

        print()
        print("Adjusted grouped-binomial GLM results:")
        show_glm = [
            "feature",
            "odds_ratio",
            "ci95_low_or",
            "ci95_high_or",
            "glm_p_two_sided",
            "glm_fdr_bh_q",
        ]
        print(
            glm[show_glm]
            .sort_values("glm_p_two_sided")
            .to_string(index=False, float_format=lambda x: f"{x:.5g}")
        )

    pooled_df = pd.concat(pooled_all, ignore_index=True)
    glm_df = pd.concat(glm_all, ignore_index=True)
    score_df = pd.concat(score_all, ignore_index=True)

    pooled_out = outdir / f"{args.year}_frozen_feature_tests.csv"
    glm_out = outdir / f"{args.year}_glm_adjusted_tests.csv"
    score_out = outdir / f"{args.year}_relation_score_summary.csv"

    pooled_df.to_csv(pooled_out, index=False, encoding="utf-8-sig")
    glm_df.to_csv(glm_out, index=False, encoding="utf-8-sig")
    score_df.to_csv(score_out, index=False, encoding="utf-8-sig")

    # --------------------------------------------------------
    # Human-readable summary
    # --------------------------------------------------------
    lines = [
        f"BaZi relational-feature Music test — Gregorian year {args.year}",
        "",
        f"Input dates: {len(df)}",
        f"Input people: {df['n_people'].sum():,}",
        f"Input Music count: {df['Music__n'].sum():,}",
        f"Solar-term transition ambiguous dates: "
        f"{int(feat['pillar_transition_ambiguous'].sum())}",
        f"Main analysis transition dates: {transition_note}",
        f"Dominant BaZi year pillar: {dominant_year_pillar}",
        "",
        "Frozen features:",
    ]

    for f in FROZEN_FEATURES:
        lines.append(f"  - {f}")

    lines += [
        "",
        "Highlighted-date pillars:",
        check.to_string(index=False) if len(check) else "(none)",
        "",
    ]

    for scope_name in scopes:
        lines += [
            "=" * 72,
            f"SCOPE: {scope_name}",
            "",
            "Permutation tests (one-sided hypothesis = higher Music rate):",
        ]

        tmp = pooled_df.loc[pooled_df["scope"] == scope_name].copy()
        for _, r in tmp.sort_values("permutation_p_one_sided").iterrows():
            lines.append(
                f"  {r['feature']}: "
                f"days={int(r['feature_days'])}, "
                f"MusicRate={100*r['feature_music_rate']:.2f}% vs "
                f"{100*r['nonfeature_music_rate']:.2f}%, "
                f"RR={r['risk_ratio']:.3f}, "
                f"perm_p={r['permutation_p_one_sided']:.6g}, "
                f"BH_q={r['permutation_fdr_bh_q_one_sided']:.6g}"
            )

        lines += [
            "",
            "Adjusted GLM (feature + Gregorian month + weekday):",
        ]

        tmpg = glm_df.loc[glm_df["scope"] == scope_name].copy()
        for _, r in tmpg.sort_values("glm_p_two_sided").iterrows():
            lines.append(
                f"  {r['feature']}: "
                f"OR={r['odds_ratio']:.3f} "
                f"[{r['ci95_low_or']:.3f}, {r['ci95_high_or']:.3f}], "
                f"p={r['glm_p_two_sided']:.6g}, "
                f"BH_q={r['glm_fdr_bh_q']:.6g}"
            )

        lines += [
            "",
            "Relation-score descriptive trend:",
        ]

        tmps = score_df.loc[score_df["scope"] == scope_name]
        for _, r in tmps.iterrows():
            lines.append(
                f"  score={int(r['relation_score'])}: "
                f"days={int(r['n_dates'])}, "
                f"people={int(r['n_people'])}, "
                f"Music={int(r['music'])}, "
                f"MusicRate={100*r['music_rate']:.2f}%"
            )

        lines.append("")

    lines += [
        "Interpretation guardrails:",
        "  * A low p-value here is association, not causation.",
        "  * We already inspected several high-Music dates before freezing these",
        "    hypotheses, so 1986 remains exploratory/discovery data.",
        "  * The real test is to freeze the definitions and replicate them in",
        "    an untouched year/cohort.",
        "  * Gregorian birth-date-only data cannot recover exact birth hour/location.",
        "  * Transition dates are excluded by default because month/year pillar can",
        "    depend on birth time on those dates.",
    ]

    summary = "\n".join(lines)
    summary_out = outdir / f"{args.year}_bazi_music_summary.txt"
    summary_out.write_text(summary, encoding="utf-8")

    print()
    print("=" * 72)
    print("Saved:")
    for p in [
        feature_out,
        pooled_out,
        glm_out,
        score_out,
        summary_out,
        *joint_paths,
    ]:
        print(f"  {p}")


if __name__ == "__main__":
    main()
