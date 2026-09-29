#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Exploratory 1986 Music × Ten-God analysis (v2)

New in v2:
- Reports P(Music | Ten-God)
- Reports Ten-God share among Music:
      P(Ten-God | Music)
- Reports Ten-God share in the full eligible sample:
      P(Ten-God)
- Reports enrichment ratio:
      P(Ten-God | Music) / P(Ten-God)
- Runs one-vs-rest exploratory GLMs for all 10 Ten-Gods at:
      1) month stem 月干
      2) month-order main qi 月令本气
- BH-FDR across all 20 all-Ten-God exploratory tests
- Keeps the six targeted 食神/伤官/食伤 tests separately.

Install:
    pip install pandas numpy scipy statsmodels lunar_python

Run:
    python bazi_music_tengod_1986_v2.py --input occupation_scan_1986\\1986_daily_category_stats.csv --year 1986
"""

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

# 月支本气
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
    return {
        "year": ec.getYear(),
        "month": ec.getMonth(),
        "day": ec.getDay(),
        "hour": ec.getTime(),
    }


def add_features(df):
    rows = []

    for _, r in df.iterrows():
        dt = pd.Timestamp(r["date"])
        y, m, d = dt.year, dt.month, dt.day

        noon = eight_char_at(y, m, d, 12)
        early = eight_char_at(y, m, d, 0, 30)
        late = eight_char_at(y, m, d, 22, 30)

        transition = (
            early["year"] != late["year"]
            or early["month"] != late["month"]
        )

        mp = noon["month"]
        dp = noon["day"]

        month_stem = mp[0]
        month_branch = mp[1]
        day_stem = dp[0]
        month_main_stem = BRANCH_MAIN_STEM[month_branch]

        rec = r.to_dict()
        rec.update({
            "year_pillar": noon["year"],
            "month_pillar": mp,
            "day_pillar": dp,
            "day_stem": day_stem,
            "month_stem": month_stem,
            "month_branch": month_branch,
            "month_main_stem": month_main_stem,
            "month_stem_tengod": ten_god(day_stem, month_stem),
            "month_order_tengod": ten_god(day_stem, month_main_stem),
            "pillar_transition_ambiguous": transition,
            "gregorian_month": m,
            "weekday": dt.day_name(),
        })

        rec["month_stem_shangguan"] = int(rec["month_stem_tengod"] == "伤官")
        rec["month_stem_shishen"] = int(rec["month_stem_tengod"] == "食神")
        rec["month_stem_shishang"] = int(rec["month_stem_tengod"] in {"食神", "伤官"})

        rec["month_order_shangguan"] = int(rec["month_order_tengod"] == "伤官")
        rec["month_order_shishen"] = int(rec["month_order_tengod"] == "食神")
        rec["month_order_shishang"] = int(rec["month_order_tengod"] in {"食神", "伤官"})

        rows.append(rec)

    return pd.DataFrame(rows)


def design_matrix(d, feature):
    X = pd.DataFrame(index=d.index)
    X[feature] = pd.to_numeric(d[feature]).astype(float)

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

    X = pd.concat([X, month_d, weekday_d], axis=1)
    X = sm.add_constant(X, has_constant="add")
    return X.astype(float)


def fit_binary(d, feature):
    mask = d[feature].astype(bool)

    n1 = int(d.loc[mask, "n_people"].sum())
    y1 = int(d.loc[mask, "Music__n"].sum())
    n0 = int(d.loc[~mask, "n_people"].sum())
    y0 = int(d.loc[~mask, "Music__n"].sum())

    r1 = y1 / n1
    r0 = y0 / n0

    _, fisher_p = fisher_exact(
        [[y1, n1-y1], [y0, n0-y0]],
        alternative="greater",
    )

    y = np.column_stack([
        d["Music__n"].to_numpy(float),
        (d["n_people"] - d["Music__n"]).to_numpy(float),
    ])

    fit = sm.GLM(
        y,
        design_matrix(d, feature),
        family=sm.families.Binomial(),
    ).fit(cov_type="HC0", maxiter=200)

    beta = float(fit.params[feature])
    se = float(fit.bse[feature])
    p_two = float(fit.pvalues[feature])
    p_one = p_two / 2 if beta >= 0 else 1 - p_two / 2

    return {
        "feature": feature,
        "feature_days": int(mask.sum()),
        "feature_people": n1,
        "feature_music": y1,
        "feature_music_rate": r1,
        "nonfeature_people": n0,
        "nonfeature_music": y0,
        "nonfeature_music_rate": r0,
        "risk_ratio": r1 / r0,
        "fisher_one_sided_p": fisher_p,
        "adjusted_or": math.exp(beta),
        "ci95_low": math.exp(beta - 1.96*se),
        "ci95_high": math.exp(beta + 1.96*se),
        "glm_one_sided_p": p_one,
        "glm_two_sided_p": p_two,
    }


def make_descriptive_table(d, col, location_name):
    total_people = int(d["n_people"].sum())
    total_music = int(d["Music__n"].sum())

    rows = []

    for tg in TEN_GODS:
        g = d.loc[d[col] == tg]

        n = int(g["n_people"].sum())
        music = int(g["Music__n"].sum())

        p_music_given_tg = music / n if n else np.nan
        share_music = music / total_music if total_music else np.nan
        share_all = n / total_people if total_people else np.nan
        enrichment = share_music / share_all if share_all else np.nan

        rows.append({
            "location": location_name,
            "ten_god": tg,
            "dates": len(g),
            "people": n,
            "music": music,
            "p_music_given_tengod": p_music_given_tg,
            "share_among_music": share_music,
            "share_among_all": share_all,
            "enrichment_ratio": enrichment,
        })

    return pd.DataFrame(rows)


def add_all_tengod_tests(d):
    results = []

    for location, col in [
        ("month_stem", "month_stem_tengod"),
        ("month_order", "month_order_tengod"),
    ]:
        for tg in TEN_GODS:
            feature = f"tmp_{location}_{tg}"
            d = d.copy()
            d[feature] = (d[col] == tg).astype(int)

            r = fit_binary(d, feature)
            r["location"] = location
            r["ten_god"] = tg
            results.append(r)

    out = pd.DataFrame(results)
    out["bh_q_all20"] = multipletests(
        out["glm_one_sided_p"],
        alpha=0.05,
        method="fdr_bh",
    )[1]

    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--year", type=int, default=1986)
    ap.add_argument("--outdir", default=None)
    args = ap.parse_args()

    inpath = Path(args.input)
    if not inpath.exists():
        raise SystemExit(f"Input not found: {inpath}")

    d = pd.read_csv(inpath)
    d["date"] = pd.to_datetime(d["date"])
    d = d.loc[d["date"].dt.year == args.year].copy()
    d["n_people"] = pd.to_numeric(d["n_people"]).astype(int)
    d["Music__n"] = pd.to_numeric(d["Music__n"]).astype(int)

    feat = add_features(d)
    eligible = feat.loc[~feat["pillar_transition_ambiguous"]].copy()

    outdir = Path(args.outdir or f"bazi_tengod_music_{args.year}_v2")
    outdir.mkdir(parents=True, exist_ok=True)

    stemtab = make_descriptive_table(
        eligible,
        "month_stem_tengod",
        "month_stem",
    )
    ordertab = make_descriptive_table(
        eligible,
        "month_order_tengod",
        "month_order",
    )

    # Targeted 食神/伤官/食伤 tests.
    targeted = [
        "month_stem_shangguan",
        "month_stem_shishen",
        "month_stem_shishang",
        "month_order_shangguan",
        "month_order_shishen",
        "month_order_shishang",
    ]
    targeted_tests = pd.DataFrame(
        [fit_binary(eligible, f) for f in targeted]
    )
    targeted_tests["bh_q_target6"] = multipletests(
        targeted_tests["glm_one_sided_p"],
        alpha=0.05,
        method="fdr_bh",
    )[1]

    # All 20 exploratory one-vs-rest tests.
    all_tests = add_all_tengod_tests(eligible)

    # Save CSV outputs.
    stemtab.to_csv(
        outdir / f"{args.year}_month_stem_tengod_enrichment.csv",
        index=False,
        encoding="utf-8-sig",
    )
    ordertab.to_csv(
        outdir / f"{args.year}_month_order_tengod_enrichment.csv",
        index=False,
        encoding="utf-8-sig",
    )
    targeted_tests.to_csv(
        outdir / f"{args.year}_targeted_tengod_tests.csv",
        index=False,
        encoding="utf-8-sig",
    )
    all_tests.to_csv(
        outdir / f"{args.year}_all20_tengod_tests.csv",
        index=False,
        encoding="utf-8-sig",
    )
    eligible.to_csv(
        outdir / f"{args.year}_daily_tengod_features.csv",
        index=False,
        encoding="utf-8-sig",
    )

    total_people = int(eligible["n_people"].sum())
    total_music = int(eligible["Music__n"].sum())

    lines = [
        f"Exploratory Music × Ten-God analysis v2 — {args.year}",
        "",
        f"Eligible dates: {len(eligible)}",
        f"People: {total_people:,}",
        f"Music: {total_music:,}",
        f"Overall Music rate: {100*total_music/total_people:.2f}%",
        f"Excluded pillar-transition dates: {int(feat['pillar_transition_ambiguous'].sum())}",
        "",
        "Metrics:",
        "  P(Music|TG) = Music rate within that Ten-God group.",
        "  Share among Music = P(TG|Music). These 10 shares sum to 100%.",
        "  Share among all = P(TG) in all eligible people. These 10 shares sum to 100%.",
        "  Enrichment = P(TG|Music) / P(TG). >1 means overrepresented among Music.",
        "",
        "MONTH STEM / 月干 — sorted by enrichment:",
    ]

    stem_sorted = stemtab.sort_values(
        ["enrichment_ratio", "p_music_given_tengod"],
        ascending=False,
    )
    for _, r in stem_sorted.iterrows():
        lines.append(
            f"  {r['ten_god']}: "
            f"Music={int(r['music'])}/{int(r['people'])}, "
            f"P(Music|TG)={100*r['p_music_given_tengod']:.2f}%, "
            f"share among Music={100*r['share_among_music']:.2f}%, "
            f"share among all={100*r['share_among_all']:.2f}%, "
            f"enrichment={r['enrichment_ratio']:.3f}"
        )

    lines += [
        "",
        "MONTH ORDER / 月令本气 — sorted by enrichment:",
    ]

    order_sorted = ordertab.sort_values(
        ["enrichment_ratio", "p_music_given_tengod"],
        ascending=False,
    )
    for _, r in order_sorted.iterrows():
        lines.append(
            f"  {r['ten_god']}: "
            f"Music={int(r['music'])}/{int(r['people'])}, "
            f"P(Music|TG)={100*r['p_music_given_tengod']:.2f}%, "
            f"share among Music={100*r['share_among_music']:.2f}%, "
            f"share among all={100*r['share_among_all']:.2f}%, "
            f"enrichment={r['enrichment_ratio']:.3f}"
        )

    lines += [
        "",
        "TARGETED 食神/伤官/食伤 exploratory tests:",
    ]

    for _, r in targeted_tests.iterrows():
        lines.append(
            f"  {r['feature']}: "
            f"rate={100*r['feature_music_rate']:.2f}% vs "
            f"{100*r['nonfeature_music_rate']:.2f}%, "
            f"RR={r['risk_ratio']:.3f}, "
            f"adjusted OR={r['adjusted_or']:.3f} "
            f"[{r['ci95_low']:.3f},{r['ci95_high']:.3f}], "
            f"one-sided p={r['glm_one_sided_p']:.6g}, "
            f"BH q={r['bh_q_target6']:.6g}"
        )

    lines += [
        "",
        "ALL 20 one-vs-rest exploratory tests — sorted by one-sided p:",
    ]

    for _, r in all_tests.sort_values("glm_one_sided_p").iterrows():
        lines.append(
            f"  {r['location']} {r['ten_god']}: "
            f"OR={r['adjusted_or']:.3f} "
            f"[{r['ci95_low']:.3f},{r['ci95_high']:.3f}], "
            f"one-sided p={r['glm_one_sided_p']:.6g}, "
            f"BH q(all20)={r['bh_q_all20']:.6g}"
        )

    lines += [
        "",
        "Interpretation guardrail:",
        "  1986 is exploratory/discovery only.",
        "  A high enrichment or nominal p-value here is hypothesis-generating.",
        "  It should be frozen and tested in an untouched cohort before confirmatory use.",
    ]

    summary = outdir / f"{args.year}_tengod_music_summary_v2.txt"
    summary.write_text("\n".join(lines), encoding="utf-8")

    print("\n".join(lines))
    print(f"\nSaved to: {outdir}")


if __name__ == "__main__":
    main()
