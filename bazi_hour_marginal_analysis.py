#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Hour-marginalized BaZi vs Music analysis.

Purpose
-------
We only know Gregorian birth DATE, not birth TIME.
Instead of inventing one birth hour, enumerate the 12 traditional double-hours
and marginalize over them with equal prior weight (1/12 each).

This lets us test questions such as:
  * Does the Y/M/D chart already contain a day-branch half-trine?
  * Given unknown hour, what is P(day branch participates in any half-trine)?
  * What is P(a complete San-He trio exists after adding the hour)?
  * What is P(a complete San-He trio involving the DAY branch exists)?
  * What is P(day stem combines with year/month/hour stem)?
  * What is P(full day-involving San-He AND day-stem combine)?

The 1986 cohort should be treated as discovery because its high-Music dates
were inspected before these hour-marginalized hypotheses were defined.
Use an untouched year such as 1987 as replication.

Input
-----
YEAR_daily_category_stats.csv
Required columns:
    date
    n_people
    Music__n

Install
-------
pip install pandas numpy scipy statsmodels lunar_python

Examples
--------
python bazi_hour_marginal_analysis.py ^
  --input 1986_daily_category_stats.csv --year 1986

python bazi_hour_marginal_analysis.py ^
  --input 1987_daily_category_stats.csv --year 1987

Optional faster permutation pass:
python bazi_hour_marginal_analysis.py ^
  --input 1986_daily_category_stats.csv --year 1986 --permutations 10000

Outputs
-------
bazi_hour_marginal_YEAR/
  YEAR_hour_marginal_daily.csv
  YEAR_binary_tests.csv
  YEAR_probability_glm.csv
  YEAR_probability_permutation.csv
  YEAR_hour_marginal_summary.txt

Important modeling assumptions
------------------------------
1) Equal prior probability for the 12 double-hours.
2) A representative clock time is used for each traditional hour branch:
      子 00:00, 丑 02:00, 寅 04:00, ..., 亥 22:00.
   This deliberately avoids the special late-Zi (23:00) day-boundary debate.
3) Gregorian dates on which year/month pillar changes during the civil date
   are excluded by default because exact birth time is unknown.
4) Association != causation.
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
        "Missing lunar_python.\nInstall with:\n"
        "    pip install lunar_python"
    )

# ============================================================
# Classical relations
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

XING_TRIADS = [
    frozenset(("寅", "巳", "申")),
    frozenset(("丑", "戌", "未")),
]
XING_PAIR = {frozenset(("子", "卯"))}
SELF_XING = {"辰", "午", "酉", "亥"}

# Representative local clock hours for 12 traditional double-hours.
HOUR_REPRESENTATIVES = [
    ("子", 0),
    ("丑", 2),
    ("寅", 4),
    ("卯", 6),
    ("辰", 8),
    ("巳", 10),
    ("午", 12),
    ("未", 14),
    ("申", 16),
    ("酉", 18),
    ("戌", 20),
    ("亥", 22),
]

# Frozen replication targets from 1986 discovery work.
BINARY_FROZEN = [
    "YMD_DAY_HALF_TRINE",
    "YMD_STEM_COMBINE_AND_HALF_TRINE",
]

# New hour-marginalized probability hypotheses.
PROBABILITY_FROZEN = [
    "P4_DAY_HALF_TRINE",
    "P4_FULL_SANHE_ANY",
    "P4_FULL_SANHE_INVOLVES_DAY",
    "P4_DAY_STEM_COMBINE",
    "P4_FULL_DAY_SANHE_AND_STEM_COMBINE",
]


def stem_combine(a, b):
    return frozenset((a, b)) in STEM_COMBINES


def half_trine(a, b):
    if a == b:
        return False
    pair = {a, b}
    return any(pair.issubset(g) for g in SANHE_GROUPS)


def liuhe(a, b):
    return frozenset((a, b)) in LIUHE


def chong(a, b):
    return frozenset((a, b)) in CHONG


def hai(a, b):
    return frozenset((a, b)) in HAI


def xing(a, b):
    if a == b:
        return a in SELF_XING
    pair = {a, b}
    if frozenset(pair) in XING_PAIR:
        return True
    return any(pair.issubset(g) for g in XING_TRIADS)


def has_full_sanhe(branches):
    s = set(branches)
    return any(g.issubset(s) for g in SANHE_GROUPS)


def has_full_sanhe_involving_day(year_b, month_b, day_b, hour_b):
    s = {year_b, month_b, day_b, hour_b}
    for g in SANHE_GROUPS:
        if day_b in g and g.issubset(s):
            return True
    return False


def day_has_half_trine(year_b, month_b, day_b, hour_b=None):
    partners = [year_b, month_b]
    if hour_b is not None:
        partners.append(hour_b)
    return any(half_trine(day_b, b) for b in partners)


def day_stem_combines(year_s, month_s, day_s, hour_s=None):
    targets = [year_s, month_s]
    if hour_s is not None:
        targets.append(hour_s)
    return any(stem_combine(day_s, s) for s in targets)


# ============================================================
# Pillars
# ============================================================

def eight_char_at(y, m, d, hour, minute=0):
    solar = Solar.fromYmdHms(y, m, d, hour, minute, 0)
    ec = solar.getLunar().getEightChar()
    return {
        "year": ec.getYear(),
        "month": ec.getMonth(),
        "day": ec.getDay(),
        "hour": ec.getTime(),
    }


def build_hour_marginal_features(df):
    rows = []

    for _, row in df.iterrows():
        dt = pd.Timestamp(row["date"])
        y, m, d = dt.year, dt.month, dt.day

        # Noon chart for Y/M/D.
        noon = eight_char_at(y, m, d, 12)

        # Detect year/month transition dates.
        early = eight_char_at(y, m, d, 0, 30)
        late = eight_char_at(y, m, d, 22, 30)
        transition_ambiguous = (
            early["year"] != late["year"]
            or early["month"] != late["month"]
        )

        yp, mp, dp = noon["year"], noon["month"], noon["day"]
        ys, yb = yp[0], yp[1]
        ms, mb = mp[0], mp[1]
        ds, db = dp[0], dp[1]

        # Replication features based only on Y/M/D.
        ymd_half = half_trine(db, yb) or half_trine(db, mb)
        ymd_stem_combine = stem_combine(ds, ys) or stem_combine(ds, ms)
        ymd_combo = ymd_half and ymd_stem_combine

        hour_records = []

        for expected_branch, hour in HOUR_REPRESENTATIVES:
            p = eight_char_at(y, m, d, hour)
            hp = p["hour"]
            hs, hb = hp[0], hp[1]

            # Sanity check package hour branch against representative table.
            if hb != expected_branch:
                raise RuntimeError(
                    f"Unexpected hour branch on {dt.date()} at {hour:02d}:00: "
                    f"got {hp}, expected branch {expected_branch}"
                )

            branches = [yb, mb, db, hb]

            day_half_4 = day_has_half_trine(yb, mb, db, hb)
            full_any = has_full_sanhe(branches)
            full_day = has_full_sanhe_involving_day(yb, mb, db, hb)
            stem_comb_4 = day_stem_combines(ys, ms, ds, hs)
            full_day_and_stem = full_day and stem_comb_4

            # Did the hour specifically CREATE a new day half-trine?
            hour_adds_day_half = (not ymd_half) and half_trine(db, hb)

            # Did the hour specifically COMPLETE a full San-He involving day?
            ymd_full_day = has_full_sanhe_involving_day(yb, mb, db, "__NONE__")
            hour_completes_day_sanhe = (not ymd_full_day) and full_day

            hour_records.append({
                "hour_branch": hb,
                "hour_pillar": hp,
                "day_half_4": day_half_4,
                "full_any": full_any,
                "full_day": full_day,
                "stem_comb_4": stem_comb_4,
                "full_day_and_stem": full_day_and_stem,
                "hour_adds_day_half": hour_adds_day_half,
                "hour_completes_day_sanhe": hour_completes_day_sanhe,
            })

        def prob(key):
            return sum(int(h[key]) for h in hour_records) / 12.0

        rec = row.to_dict()
        rec.update({
            "year_pillar": yp,
            "month_pillar": mp,
            "day_pillar": dp,
            "year_stem": ys,
            "year_branch": yb,
            "month_stem": ms,
            "month_branch": mb,
            "day_stem": ds,
            "day_branch": db,
            "pillar_transition_ambiguous": transition_ambiguous,

            "YMD_DAY_HALF_TRINE": int(ymd_half),
            "YMD_DAY_STEM_COMBINE": int(ymd_stem_combine),
            "YMD_STEM_COMBINE_AND_HALF_TRINE": int(ymd_combo),

            # Hour-marginalized probabilities.
            "P4_DAY_HALF_TRINE": prob("day_half_4"),
            "P4_FULL_SANHE_ANY": prob("full_any"),
            "P4_FULL_SANHE_INVOLVES_DAY": prob("full_day"),
            "P4_DAY_STEM_COMBINE": prob("stem_comb_4"),
            "P4_FULL_DAY_SANHE_AND_STEM_COMBINE": prob("full_day_and_stem"),

            # Mechanistic diagnostic probabilities.
            "P_HOUR_ADDS_NEW_DAY_HALF_TRINE": prob("hour_adds_day_half"),
            "P_HOUR_COMPLETES_DAY_SANHE": prob("hour_completes_day_sanhe"),

            "gregorian_month": m,
            "weekday": dt.day_name(),
        })

        rows.append(rec)

    return pd.DataFrame(rows)


# ============================================================
# Statistics
# ============================================================

def bh_adjust(pvals):
    pvals = np.asarray(pvals, dtype=float)
    ok = np.isfinite(pvals)
    q = np.full(len(pvals), np.nan)
    reject = np.full(len(pvals), False)

    if ok.any():
        r, qq, _, _ = multipletests(
            pvals[ok], alpha=0.05, method="fdr_bh"
        )
        q[ok] = qq
        reject[ok] = r

    return reject, q


def design_matrix(data, feature):
    X = pd.DataFrame(index=data.index)
    X[feature] = pd.to_numeric(data[feature], errors="raise").astype(float)

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


def grouped_glm(data, feature):
    y = np.column_stack([
        data["Music__n"].to_numpy(dtype=float),
        (data["n_people"] - data["Music__n"]).to_numpy(dtype=float),
    ])
    X = design_matrix(data, feature)
    model = sm.GLM(y, X, family=sm.families.Binomial())
    fit = model.fit(cov_type="HC0", maxiter=200)
    return fit


def binary_test_table(data):
    rows = []

    for feature in BINARY_FROZEN:
        mask = data[feature].astype(bool)

        n1 = int(data.loc[mask, "n_people"].sum())
        y1 = int(data.loc[mask, "Music__n"].sum())
        n0 = int(data.loc[~mask, "n_people"].sum())
        y0 = int(data.loc[~mask, "Music__n"].sum())

        r1 = y1 / n1
        r0 = y0 / n0
        rr = r1 / r0

        _, p_one = fisher_exact(
            [[y1, n1-y1], [y0, n0-y0]],
            alternative="greater",
        )

        fit = grouped_glm(data, feature)
        beta = float(fit.params[feature])
        se = float(fit.bse[feature])
        p_glm = float(fit.pvalues[feature])

        rows.append({
            "feature": feature,
            "feature_days": int(mask.sum()),
            "feature_people": n1,
            "feature_music": y1,
            "feature_music_rate": r1,
            "nonfeature_people": n0,
            "nonfeature_music": y0,
            "nonfeature_music_rate": r0,
            "risk_ratio": rr,
            "fisher_one_sided_p": p_one,
            "glm_or": math.exp(beta),
            "glm_ci95_low": math.exp(beta - 1.96*se),
            "glm_ci95_high": math.exp(beta + 1.96*se),
            "glm_p": p_glm,
        })

    out = pd.DataFrame(rows)
    _, q = bh_adjust(out["glm_p"])
    out["glm_bh_q"] = q
    return out


def exposure_contrast(data, feature):
    """
    Intuitive continuous-exposure contrast:
      mean feature exposure among Music person-counts
      minus mean feature exposure among non-Music person-counts.
    """
    x = data[feature].to_numpy(dtype=float)
    y = data["Music__n"].to_numpy(dtype=float)
    n = data["n_people"].to_numpy(dtype=float)
    non = n - y

    mean_music = np.sum(x*y) / np.sum(y)
    mean_non = np.sum(x*non) / np.sum(non)
    return mean_music - mean_non, mean_music, mean_non


def permutation_continuous(
    data, feature, permutations=50000, seed=20260924
):
    rng = np.random.default_rng(seed)
    x = data[feature].to_numpy(dtype=float)
    y = data["Music__n"].to_numpy(dtype=float)
    n = data["n_people"].to_numpy(dtype=float)
    non = n - y

    obs, mm, mn = exposure_contrast(data, feature)

    ge = 0
    abs_ge = 0

    for _ in range(permutations):
        xp = rng.permutation(x)
        s = (
            np.sum(xp*y) / np.sum(y)
            - np.sum(xp*non) / np.sum(non)
        )
        if s >= obs - 1e-15:
            ge += 1
        if abs(s) >= abs(obs) - 1e-15:
            abs_ge += 1

    return {
        "feature": feature,
        "mean_exposure_music": mm,
        "mean_exposure_nonmusic": mn,
        "exposure_difference": obs,
        "perm_p_one_sided": (ge+1)/(permutations+1),
        "perm_p_two_sided": (abs_ge+1)/(permutations+1),
    }


def probability_glm_table(data):
    rows = []

    for feature in PROBABILITY_FROZEN:
        fit = grouped_glm(data, feature)
        beta = float(fit.params[feature])
        se = float(fit.bse[feature])
        p = float(fit.pvalues[feature])

        # OR for a full 0 -> 1 change in probability exposure.
        rows.append({
            "feature": feature,
            "feature_min": float(data[feature].min()),
            "feature_max": float(data[feature].max()),
            "feature_mean": float(data[feature].mean()),
            "glm_beta_per_1_0": beta,
            "glm_or_per_1_0": math.exp(beta),
            "glm_ci95_low": math.exp(beta - 1.96*se),
            "glm_ci95_high": math.exp(beta + 1.96*se),
            "glm_p": p,
        })

    out = pd.DataFrame(rows)
    _, q = bh_adjust(out["glm_p"])
    out["glm_bh_q"] = q
    return out


def probability_permutation_table(
    data, permutations=50000, seed=20260924
):
    rows = []
    for i, feature in enumerate(PROBABILITY_FROZEN):
        r = permutation_continuous(
            data,
            feature,
            permutations=permutations,
            seed=seed + 1009*i,
        )
        rows.append(r)

    out = pd.DataFrame(rows)
    _, q = bh_adjust(out["perm_p_one_sided"])
    out["perm_bh_q_one_sided"] = q
    return out


def summarize_probability_levels(data, feature):
    tmp = data.groupby(feature).agg(
        n_dates=("date", "count"),
        n_people=("n_people", "sum"),
        music=("Music__n", "sum"),
    ).reset_index()

    tmp["music_rate"] = tmp["music"] / tmp["n_people"]
    return tmp.sort_values(feature)


# ============================================================
# Main
# ============================================================

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--permutations", type=int, default=50000)
    ap.add_argument("--seed", type=int, default=20260924)
    ap.add_argument("--outdir", default=None)
    ap.add_argument(
        "--include-transition-days",
        action="store_true",
        help="Include civil dates on which year/month pillar changes.",
    )
    args = ap.parse_args()

    inpath = Path(args.input)
    if not inpath.exists():
        raise SystemExit(f"Input not found: {inpath}")

    outdir = Path(
        args.outdir or f"bazi_hour_marginal_{args.year}"
    )
    outdir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(inpath)
    required = {"date", "n_people", "Music__n"}
    missing = required - set(df.columns)
    if missing:
        raise SystemExit(f"Missing columns: {sorted(missing)}")

    df["date"] = pd.to_datetime(df["date"])
    df = df.loc[df["date"].dt.year == args.year].copy()
    df["n_people"] = pd.to_numeric(df["n_people"]).astype(int)
    df["Music__n"] = pd.to_numeric(df["Music__n"]).astype(int)

    print(f"Input dates: {len(df)}")
    print(f"People: {df['n_people'].sum():,}")
    print(f"Music: {df['Music__n'].sum():,}")
    print("Enumerating 12 possible hour pillars for every date ...")

    feat = build_hour_marginal_features(df)

    daily_out = outdir / f"{args.year}_hour_marginal_daily.csv"
    feat.to_csv(daily_out, index=False, encoding="utf-8-sig")

    # Main eligibility.
    if args.include_transition_days:
        eligible = feat.copy()
        transition_note = "included"
    else:
        eligible = feat.loc[
            ~feat["pillar_transition_ambiguous"]
        ].copy()
        transition_note = "excluded"

    # Analyze both Gregorian year and dominant BaZi year.
    dominant_year = eligible["year_pillar"].mode().iloc[0]
    scopes = {
        f"gregorian_{args.year}": eligible,
        f"bazi_year_{dominant_year}": eligible.loc[
            eligible["year_pillar"] == dominant_year
        ].copy(),
    }

    binary_all = []
    pglm_all = []
    pperm_all = []
    summary_lines = [
        f"Hour-marginalized BaZi Music analysis — {args.year}",
        "",
        f"Input dates: {len(df)}",
        f"People: {df['n_people'].sum():,}",
        f"Music: {df['Music__n'].sum():,}",
        f"Transition ambiguous dates: "
        f"{int(feat['pillar_transition_ambiguous'].sum())}",
        f"Transition dates in main analysis: {transition_note}",
        f"Dominant BaZi year pillar: {dominant_year}",
        "",
        "Equal-hour prior: each of 12 traditional double-hours has weight 1/12.",
        "",
    ]

    # Highlight same four 1986 dates if applicable.
    if args.year == 1986:
        focus_dates = [
            "1986-05-14",
            "1986-08-01",
            "1986-11-11",
            "1986-12-27",
        ]
        cols = [
            "date", "year_pillar", "month_pillar", "day_pillar",
            "n_people", "Music__n",
            "YMD_DAY_HALF_TRINE",
            "YMD_DAY_STEM_COMBINE",
            "P4_DAY_HALF_TRINE",
            "P4_FULL_SANHE_ANY",
            "P4_FULL_SANHE_INVOLVES_DAY",
            "P4_DAY_STEM_COMBINE",
            "P4_FULL_DAY_SANHE_AND_STEM_COMBINE",
            "P_HOUR_COMPLETES_DAY_SANHE",
        ]
        chk = feat.loc[
            feat["date"].dt.strftime("%Y-%m-%d").isin(focus_dates),
            cols,
        ]
        print("\n=== 1986 focus dates ===")
        print(chk.to_string(index=False))
        summary_lines += [
            "1986 focus dates:",
            chk.to_string(index=False),
            "",
        ]

    for scope_name, d in scopes.items():
        print("\n" + "="*80)
        print(f"SCOPE: {scope_name}")
        print(
            f"dates={len(d)}, people={d['n_people'].sum():,}, "
            f"Music={d['Music__n'].sum():,}"
        )

        b = binary_test_table(d)
        b.insert(0, "scope", scope_name)
        binary_all.append(b)

        pg = probability_glm_table(d)
        pg.insert(0, "scope", scope_name)
        pglm_all.append(pg)

        pp = probability_permutation_table(
            d,
            permutations=args.permutations,
            seed=args.seed,
        )
        pp.insert(0, "scope", scope_name)
        pperm_all.append(pp)

        print("\nFrozen Y/M/D replication features:")
        print(
            b[
                [
                    "feature",
                    "feature_days",
                    "feature_music_rate",
                    "nonfeature_music_rate",
                    "risk_ratio",
                    "glm_or",
                    "glm_p",
                    "glm_bh_q",
                ]
            ].to_string(
                index=False,
                float_format=lambda x: f"{x:.5g}",
            )
        )

        print("\nHour-marginalized probability features — adjusted GLM:")
        print(
            pg[
                [
                    "feature",
                    "feature_min",
                    "feature_max",
                    "feature_mean",
                    "glm_or_per_1_0",
                    "glm_p",
                    "glm_bh_q",
                ]
            ].to_string(
                index=False,
                float_format=lambda x: f"{x:.5g}",
            )
        )

        print("\nHour-marginalized probability features — day permutation:")
        print(
            pp[
                [
                    "feature",
                    "mean_exposure_music",
                    "mean_exposure_nonmusic",
                    "exposure_difference",
                    "perm_p_one_sided",
                    "perm_bh_q_one_sided",
                ]
            ].to_string(
                index=False,
                float_format=lambda x: f"{x:.5g}",
            )
        )

        summary_lines += [
            "="*80,
            f"SCOPE: {scope_name}",
            "",
            "Y/M/D frozen replication:",
        ]
        for _, r in b.iterrows():
            summary_lines.append(
                f"  {r['feature']}: "
                f"MusicRate={100*r['feature_music_rate']:.2f}% vs "
                f"{100*r['nonfeature_music_rate']:.2f}%, "
                f"RR={r['risk_ratio']:.3f}, "
                f"adjusted OR={r['glm_or']:.3f}, "
                f"p={r['glm_p']:.6g}, q={r['glm_bh_q']:.6g}"
            )

        summary_lines += [
            "",
            "Hour-marginalized probability GLM:",
        ]
        for _, r in pg.iterrows():
            summary_lines.append(
                f"  {r['feature']}: "
                f"range={r['feature_min']:.3f}..{r['feature_max']:.3f}, "
                f"OR(0->1)={r['glm_or_per_1_0']:.3f}, "
                f"p={r['glm_p']:.6g}, q={r['glm_bh_q']:.6g}"
            )

        summary_lines += [
            "",
            "Hour-marginalized probability permutation:",
        ]
        for _, r in pp.iterrows():
            summary_lines.append(
                f"  {r['feature']}: "
                f"mean exposure Music={r['mean_exposure_music']:.4f}, "
                f"non-Music={r['mean_exposure_nonmusic']:.4f}, "
                f"delta={r['exposure_difference']:.5f}, "
                f"p={r['perm_p_one_sided']:.6g}, "
                f"q={r['perm_bh_q_one_sided']:.6g}"
            )

        # A few useful probability-level breakdowns.
        summary_lines += ["", "Selected exposure level summaries:"]
        for f in [
            "P4_FULL_SANHE_INVOLVES_DAY",
            "P4_DAY_STEM_COMBINE",
            "P4_FULL_DAY_SANHE_AND_STEM_COMBINE",
        ]:
            lev = summarize_probability_levels(d, f)
            summary_lines.append(f"  {f}:")
            for _, r in lev.iterrows():
                summary_lines.append(
                    f"    x={r[f]:.3f}: dates={int(r['n_dates'])}, "
                    f"people={int(r['n_people'])}, "
                    f"MusicRate={100*r['music_rate']:.2f}%"
                )

        summary_lines.append("")

    binary_df = pd.concat(binary_all, ignore_index=True)
    pglm_df = pd.concat(pglm_all, ignore_index=True)
    pperm_df = pd.concat(pperm_all, ignore_index=True)

    binary_out = outdir / f"{args.year}_binary_tests.csv"
    pglm_out = outdir / f"{args.year}_probability_glm.csv"
    pperm_out = outdir / f"{args.year}_probability_permutation.csv"
    summary_out = outdir / f"{args.year}_hour_marginal_summary.txt"

    binary_df.to_csv(binary_out, index=False, encoding="utf-8-sig")
    pglm_df.to_csv(pglm_out, index=False, encoding="utf-8-sig")
    pperm_df.to_csv(pperm_out, index=False, encoding="utf-8-sig")

    summary_lines += [
        "="*80,
        "Interpretation guardrails:",
        "  * 1986 is discovery, not clean replication.",
        "  * 1987 (or another untouched year) should be analyzed without first",
        "    inspecting high-Music dates.",
        "  * Equal 1/12 hour weights are a sensitivity model, not a claim that",
        "    real birth hours are uniformly distributed.",
        "  * A stronger future sensitivity analysis can substitute empirical",
        "    birth-hour weights if a suitable population dataset is available.",
        "  * The late-Zi (23:00) day-boundary convention is intentionally not",
        "    modeled in this version.",
    ]

    summary_out.write_text(
        "\n".join(summary_lines),
        encoding="utf-8",
    )

    print("\nSaved:")
    for p in [daily_out, binary_out, pglm_out, pperm_out, summary_out]:
        print(f"  {p}")


if __name__ == "__main__":
    main()
