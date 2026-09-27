#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Frozen validation: Music × BaZi, 1993–1995, north-primary.

Anchored to preregistration:
  tag: prereg-music-1993-1995-north-v1
  freeze commit: e2071c8

H1 PRIMARY:
  Earth-Day-Master matching-main-qi tomb-month positive:
    戊日+辰月, 戊日+戌月, 己日+丑月, 己日+未月

H2 SECONDARY:
  Non-Fire month-order 伤官 positive:
    甲午, 乙巳, 戊酉, 己申, 庚子, 辛亥, 壬卯, 癸寅

Primary model for both:
  grouped-binomial daily GLM
  ~ feature + C(gregorian_year) + C(gregorian_month) + C(weekday)
            + C(day_stem) + C(month_branch)
  HC0 robust covariance
  one-sided positive test

Primary scope:
  north only (hemisphere == "north")

Sensitivity:
  known, then full, using identical frozen definitions.

QA gate:
  P106 coverage must be >=95% in EACH annual cohort before association results
  are computed. Missing P106 remains non-Music under the frozen project rule.

IMPORTANT:
  Do not run this script until the preregistration tag has been pushed.
"""

import argparse
import math
import platform
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels
import statsmodels.api as sm
from lunar_python import Solar

FREEZE_TAG = "prereg-music-1993-1995-north-v1"
FREEZE_COMMIT = "e2071c8"
YEARS = [1993, 1994, 1995]

H1_COMBOS = {"戊辰", "戊戌", "己丑", "己未"}
H2_COMBOS = {"甲午", "乙巳", "戊酉", "己申", "庚子", "辛亥", "壬卯", "癸寅"}

BRANCH_MAIN_STEM = {
    "子":"癸","丑":"己","寅":"甲","卯":"乙","辰":"戊","巳":"丙",
    "午":"丁","未":"己","申":"庚","酉":"辛","戌":"戊","亥":"壬",
}
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


def eight_char_at(y, m, d, hour=12, minute=0):
    ec = Solar.fromYmdHms(
        int(y), int(m), int(d), int(hour), int(minute), 0
    ).getLunar().getEightChar()
    return {
        "year": ec.getYear(),
        "month": ec.getMonth(),
        "day": ec.getDay(),
    }


def transition_ambiguous(y, m, d):
    a = eight_char_at(y, m, d, 0, 30)
    b = eight_char_at(y, m, d, 22, 30)
    return a["year"] != b["year"] or a["month"] != b["month"]


def date_features(ts):
    ec = eight_char_at(ts.year, ts.month, ts.day, 12, 0)
    ds = ec["day"][0]
    mb = ec["month"][1]
    combo = ds + mb
    main = BRANCH_MAIN_STEM[mb]
    tg = ten_god(ds, main)

    h1 = int(combo in H1_COMBOS)
    h2 = int(combo in H2_COMBOS)

    # Internal consistency checks against the textual frozen definitions.
    if h1:
        assert ds in {"戊", "己"}
        assert mb in {"辰", "戌", "丑", "未"}
        assert main == ds
    if h2:
        assert STEM_ELEMENT[ds] != "火"
        assert tg == "伤官"

    return {
        "day_stem": ds,
        "month_branch": mb,
        "combo": combo,
        "month_order_tengod": tg,
        "H1_earth_matching_tomb": h1,
        "H2_nonfire_shangguan": h2,
    }


def infer_music(df):
    if "_music" in df.columns:
        s = pd.to_numeric(df["_music"], errors="coerce")
        if s.isna().any():
            raise ValueError("_music contains non-numeric/missing values.")
        return s.astype(int)

    if "broad_categories" in df.columns:
        return (
            df["broad_categories"].fillna("").astype(str)
            .apply(lambda s: int("Music" in [x.strip() for x in s.split(";") if x.strip()]))
        )

    raise ValueError("Need _music or broad_categories to derive Music outcome.")


def p106_coverage(df):
    if "has_p106" in df.columns:
        x = (
            df["has_p106"].astype(str).str.lower()
            .map({"true": True, "false": False, "1": True, "0": False})
        )
        if x.isna().any():
            raise ValueError("Could not parse some has_p106 values.")
        return float(x.mean()), int(x.sum()), len(x)

    if "occupation_qids" in df.columns:
        x = df["occupation_qids"].fillna("").astype(str).str.strip().ne("")
        return float(x.mean()), int(x.sum()), len(x)

    raise ValueError(
        "Cannot verify frozen P106 coverage gate: need has_p106 or occupation_qids column."
    )


def load_and_qa(root):
    raw_by_year = {}
    qa_rows = []

    # ----- QA FIRST: no association calculations here -----
    for y in YEARS:
        p = root / f"hemisphere_{y}" / f"{y}_people_with_hemisphere.csv"
        if not p.exists():
            raise FileNotFoundError(p)

        d = pd.read_csv(p, encoding="utf-8-sig")

        required = {"qid", "_birth_date_norm", "hemisphere"}
        missing = required - set(d.columns)
        if missing:
            raise ValueError(f"{p} missing required columns: {sorted(missing)}")

        n_input = len(d)
        duplicate_qids = int(d["qid"].duplicated().sum())
        if duplicate_qids:
            raise ValueError(f"{y}: duplicate QIDs found: {duplicate_qids}")

        dob = pd.to_datetime(d["_birth_date_norm"], errors="coerce")
        missing_dob = int(dob.isna().sum())
        wrong_year = int((dob.notna() & dob.dt.year.ne(y)).sum())

        if missing_dob or wrong_year:
            raise ValueError(
                f"{y}: DOB QA failed: missing/unparseable={missing_dob}, wrong_year={wrong_year}"
            )

        coverage, n_p106, n_total = p106_coverage(d)

        qa_rows.append({
            "year": y,
            "n_rows": n_input,
            "duplicate_qids": duplicate_qids,
            "missing_dob": missing_dob,
            "wrong_year": wrong_year,
            "p106_n": n_p106,
            "p106_total": n_total,
            "p106_coverage": coverage,
            "north_n_raw": int(d["hemisphere"].eq("north").sum()),
            "known_n_raw": int(d["hemisphere"].isin(["north","south","equator"]).sum()),
        })

        raw_by_year[y] = d

    qa = pd.DataFrame(qa_rows)

    print("=" * 88)
    print("PRE-ASSOCIATION DATA QA")
    print("=" * 88)
    for r in qa.itertuples():
        print(
            f"{r.year}: rows={r.n_rows:,}, P106={r.p106_n:,}/{r.p106_total:,} "
            f"({100*r.p106_coverage:.2f}%), north_raw={r.north_n_raw:,}"
        )

    bad = qa.loc[qa["p106_coverage"] < 0.95]
    if not bad.empty:
        print()
        print("STOP: frozen P106 coverage gate failed (<95%) in:")
        for r in bad.itertuples():
            print(f"  {r.year}: {100*r.p106_coverage:.2f}%")
        raise SystemExit(2)

    print("QA gate PASSED: every annual cohort has P106 coverage >=95%.")
    print()

    # Only after QA gate passes do we derive outcome + BaZi features.
    frames = []
    feature_cache = {}

    for y in YEARS:
        d = raw_by_year[y].copy()
        d["_music_eval"] = infer_music(d)
        d["dob"] = pd.to_datetime(d["_birth_date_norm"], errors="raise")
        d["gregorian_year"] = d["dob"].dt.year.astype(int)
        d["gregorian_month"] = d["dob"].dt.month.astype(int)
        d["weekday"] = d["dob"].dt.day_name()

        keep = []
        feats = []

        for ts in d["dob"]:
            key = ts.date().isoformat()
            if key not in feature_cache:
                if transition_ambiguous(ts.year, ts.month, ts.day):
                    feature_cache[key] = None
                else:
                    feature_cache[key] = date_features(ts)
            f = feature_cache[key]
            keep.append(f is not None)
            feats.append(f)

        d = d.loc[keep].copy()
        feats = [f for f, k in zip(feats, keep) if k]

        for c in feats[0].keys():
            d[c] = [f[c] for f in feats]

        frames.append(d)

    return pd.concat(frames, ignore_index=True), qa


def scope_filter(d, scope):
    if scope == "north":
        return d.loc[d["hemisphere"].eq("north")].copy()
    if scope == "known":
        return d.loc[d["hemisphere"].isin(["north","south","equator"])].copy()
    if scope == "full":
        return d.copy()
    raise ValueError(scope)


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
                "H1_earth_matching_tomb",
                "H2_nonfire_shangguan",
            ],
            as_index=False,
        )
        .agg(
            n_people=("_music_eval", "size"),
            music_n=("_music_eval", "sum"),
        )
    )


def design_matrix(d, feature):
    X = pd.DataFrame({feature: d[feature].astype(float)}, index=d.index)

    for c in [
        "gregorian_year",
        "gregorian_month",
        "weekday",
        "day_stem",
        "month_branch",
    ]:
        dd = pd.get_dummies(
            d[c].astype("category"),
            prefix=c,
            drop_first=True,
            dtype=float,
        )
        X = pd.concat([X, dd], axis=1)

    return sm.add_constant(X, has_constant="add").astype(float)


def one_sided_positive_from_z(z):
    return 0.5 * math.erfc(z / math.sqrt(2.0))


def fit_feature(daily, feature):
    y = np.column_stack([
        daily["music_n"].to_numpy(float),
        (daily["n_people"] - daily["music_n"]).to_numpy(float),
    ])

    fit = sm.GLM(
        y,
        design_matrix(daily, feature),
        family=sm.families.Binomial(),
    ).fit(cov_type="HC0", maxiter=200)

    b = float(fit.params[feature])
    se = float(fit.bse[feature])
    z = b / se
    p1 = one_sided_positive_from_z(z)
    p2 = float(fit.pvalues[feature])

    mask = daily[feature].astype(bool)

    return {
        "beta": b,
        "se": se,
        "or": math.exp(b),
        "ci95_low": math.exp(b - 1.96*se),
        "ci95_high": math.exp(b + 1.96*se),
        "z": z,
        "p_one_sided_positive": p1,
        "p_two_sided": p2,
        "feature_dates": int(mask.sum()),
        "feature_people": int(daily.loc[mask, "n_people"].sum()),
        "feature_music": int(daily.loc[mask, "music_n"].sum()),
    }


def fit_scope(d, scope):
    sub = scope_filter(d, scope)
    daily = make_daily(sub)

    rows = []
    for hypothesis, feature in [
        ("H1", "H1_earth_matching_tomb"),
        ("H2", "H2_nonfire_shangguan"),
    ]:
        rows.append({
            "scope": scope,
            "hypothesis": hypothesis,
            "feature": feature,
            "n_people": int(daily["n_people"].sum()),
            "n_music": int(daily["music_n"].sum()),
            "n_dates": len(daily),
            **fit_feature(daily, feature),
        })

    return pd.DataFrame(rows), daily


def fit_exact_combo(daily, combo):
    x = daily.copy()
    feature = "_exact_combo"
    x[feature] = x["combo"].eq(combo).astype(int)
    r = fit_feature(x, feature)
    return {"combo": combo, **r}


def exact_combo_diagnostics(d):
    sub = scope_filter(d, "north")
    daily = make_daily(sub)
    rows = []

    families = [
        ("H1_supportive", ["戊辰","戊戌","己丑","己未"]),
        ("H2_supportive", ["甲午","乙巳","戊酉","己申","庚子","辛亥","壬卯","癸寅"]),
    ]

    # pooled + per year, explicitly descriptive only
    blocks = [("pooled_1993_1995", daily)]
    for y in YEARS:
        blocks.append((f"{y}_descriptive", daily.loc[daily["gregorian_year"].eq(y)].copy()))

    for block, dd in blocks:
        for family, combos in families:
            for combo in combos:
                try:
                    r = fit_exact_combo(dd, combo)
                    status = "ok"
                except Exception as e:
                    r = {}
                    status = f"fit_failed: {type(e).__name__}: {e}"

                rows.append({
                    "block": block,
                    "family": family,
                    "combo": combo,
                    "status": status,
                    **r,
                })

    return pd.DataFrame(rows)


def per_year_hypothesis_descriptives(d):
    rows = []
    for y in YEARS:
        sub = d.loc[d["gregorian_year"].eq(y)].copy()
        for scope in ["north"]:
            daily = make_daily(scope_filter(sub, scope))
            for hypothesis, feature in [
                ("H1", "H1_earth_matching_tomb"),
                ("H2", "H2_nonfire_shangguan"),
            ]:
                try:
                    r = fit_feature(daily, feature)
                    status = "ok"
                except Exception as e:
                    r = {}
                    status = f"fit_failed: {type(e).__name__}: {e}"
                rows.append({
                    "year": y,
                    "scope": scope,
                    "hypothesis": hypothesis,
                    "status": status,
                    "n_people": int(daily["n_people"].sum()),
                    "n_music": int(daily["music_n"].sum()),
                    "n_dates": len(daily),
                    **r,
                })
    return pd.DataFrame(rows)


def versions_text():
    try:
        import lunar_python
        lunar_ver = getattr(lunar_python, "__version__", "unknown")
    except Exception:
        lunar_ver = "unknown"

    return [
        f"Python: {platform.python_version()}",
        f"pandas: {pd.__version__}",
        f"numpy: {np.__version__}",
        f"statsmodels: {statsmodels.__version__}",
        f"lunar_python: {lunar_ver}",
        f"platform: {platform.platform()}",
    ]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-dir", default=".")
    ap.add_argument(
        "--outdir",
        default="validation_music_1993_1995_north",
    )
    args = ap.parse_args()

    root = Path(args.project_dir).resolve()
    outdir = root / args.outdir
    outdir.mkdir(parents=True, exist_ok=True)

    d, qa = load_and_qa(root)
    qa.to_csv(outdir / "DATA_QA_1993_1995.csv", index=False, encoding="utf-8-sig")

    all_scope_rows = []
    daily_by_scope = {}
    for scope in ["north", "known", "full"]:
        results, daily = fit_scope(d, scope)
        all_scope_rows.append(results)
        daily_by_scope[scope] = daily

    results = pd.concat(all_scope_rows, ignore_index=True)
    results.to_csv(
        outdir / "frozen_H1_H2_scope_results.csv",
        index=False,
        encoding="utf-8-sig",
    )

    peryear = per_year_hypothesis_descriptives(d)
    peryear.to_csv(
        outdir / "north_per_year_descriptive.csv",
        index=False,
        encoding="utf-8-sig",
    )

    exact = exact_combo_diagnostics(d)
    exact.to_csv(
        outdir / "north_exact_combo_supportive_descriptive.csv",
        index=False,
        encoding="utf-8-sig",
    )

    north = results.loc[results["scope"].eq("north")].set_index("hypothesis")
    h1 = north.loc["H1"]
    h2 = north.loc["H2"]

    h1_supported = bool(h1["p_one_sided_positive"] < 0.05 and h1["or"] > 1)
    h2_supported = bool(h2["p_one_sided_positive"] < 0.05 and h2["or"] > 1)

    def status_line(supported, orv, p):
        if supported:
            return "SUPPORTED under the frozen one-sided alpha=0.05 rule."
        if orv > 1:
            return "Directionally positive but unsupported at the frozen threshold."
        return "Direction did not reproduce (OR <= 1)."

    lines = [
        "FROZEN VALIDATION RESULT",
        "Music × BaZi, 1993–1995",
        "",
        f"Freeze tag: {FREEZE_TAG}",
        f"Freeze commit: {FREEZE_COMMIT}",
        "",
        "PRIMARY SAMPLE: NORTH ONLY",
        f"Eligible people: {int(h1['n_people']):,}",
        f"Music people: {int(h1['n_music']):,}",
        f"Eligible dates represented: {int(h1['n_dates']):,}",
        "",
        "DATA QA",
    ]

    for r in qa.itertuples():
        lines.append(
            f"{r.year}: P106 coverage={100*r.p106_coverage:.2f}% "
            f"({r.p106_n:,}/{r.p106_total:,}), north_raw={r.north_n_raw:,}"
        )

    lines += [
        "",
        "PRIMARY HYPOTHESIS H1",
        "Earth-Day-Master matching-main-qi tomb-month positive",
        "Frozen exact set: 戊辰 / 戊戌 / 己丑 / 己未",
        f"Adjusted OR = {h1['or']:.6f}",
        f"95% CI = [{h1['ci95_low']:.6f}, {h1['ci95_high']:.6f}]",
        f"Frozen one-sided p = {h1['p_one_sided_positive']:.8g}",
        f"Two-sided p = {h1['p_two_sided']:.8g}",
        f"Result: {status_line(h1_supported, h1['or'], h1['p_one_sided_positive'])}",
        "",
        "SECONDARY HYPOTHESIS H2",
        "Non-Fire month-order 伤官 positive",
        "Frozen exact set: 甲午 / 乙巳 / 戊酉 / 己申 / 庚子 / 辛亥 / 壬卯 / 癸寅",
        f"Adjusted OR = {h2['or']:.6f}",
        f"95% CI = [{h2['ci95_low']:.6f}, {h2['ci95_high']:.6f}]",
        f"Frozen one-sided p = {h2['p_one_sided_positive']:.8g}",
        f"Two-sided p = {h2['p_two_sided']:.8g}",
        f"Result: {status_line(h2_supported, h2['or'], h2['p_one_sided_positive'])}",
        "",
        "SENSITIVITY (same frozen models)",
    ]

    for scope in ["known", "full"]:
        rr = results.loc[results["scope"].eq(scope)].set_index("hypothesis")
        lines.append(
            f"{scope}: H1 OR={rr.loc['H1','or']:.4f}, p1={rr.loc['H1','p_one_sided_positive']:.6g}; "
            f"H2 OR={rr.loc['H2','or']:.4f}, p1={rr.loc['H2','p_one_sided_positive']:.6g}"
        )

    pooled_exact = exact.loc[exact["block"].eq("pooled_1993_1995") & exact["status"].eq("ok")]
    lines += ["", "SUPPORTIVE EXACT-COMBO DIRECTION COUNTS (descriptive only)"]
    for family in ["H1_supportive", "H2_supportive"]:
        gg = pooled_exact.loc[pooled_exact["family"].eq(family)]
        lines.append(
            f"{family}: {(gg['or'] > 1).sum()}/{len(gg)} exact combinations have OR > 1"
        )

    lines += [
        "",
        "Per-year and exact-combination estimates are descriptive only.",
        "No newly noticed 1993–1995 feature may be promoted to confirmatory status.",
        "",
        "SOFTWARE",
        *versions_text(),
    ]

    result_path = outdir / "VALIDATION_RESULT_MUSIC_1993_1995_NORTH.txt"
    result_path.write_text("\n".join(lines), encoding="utf-8")

    print()
    print("\n".join(lines))
    print()
    print("DONE")
    print("Main result:")
    print(result_path)


if __name__ == "__main__":
    main()
