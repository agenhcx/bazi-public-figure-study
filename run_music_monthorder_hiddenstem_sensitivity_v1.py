#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Music month-order hidden-stem / hour-pillar sensitivity
=======================================================

Targets
-------
M5  (1990–1992 North-primary):
    Month-order Shangguan -> Music +
    Original model:
      grouped-binomial daily GLM
      H + C(gregorian_year) + C(gregorian_month) + C(weekday)

M10 (1993–1995 North-primary):
    Non-Fire month-order Shangguan -> Music +
    Original model:
      grouped-binomial daily GLM
      H + C(gregorian_year) + C(gregorian_month) + C(weekday)
        + C(day_stem) + C(month_branch)

This script DOES NOT replace the frozen original analyses. It is a
post-validation method-sensitivity analysis.

Input
-----
Use the exact already-filtered North-primary eligible PERSON-LEVEL cohorts
from the original validation pipelines.

Required logical fields:
  - DOB
  - binary Music outcome

The script auto-detects common column names, or specify:
  --dob-col ...
  --music-col ...

Examples:
  python .\run_music_monthorder_hiddenstem_sensitivity_v1.py --input-1990-1992 .\music_1990_1992_north_primary_people.csv --input-1993-1995 .\music_1993_1995_north_primary_people.csv

  python .\run_music_monthorder_hiddenstem_sensitivity_v1.py --input-1990-1992 .\a.csv --input-1993-1995 .\b.csv --dob-col exact_dob_frozen --music-col is_music

Dependencies
------------
  pip install pandas numpy statsmodels patsy sxtwl

Feature models
--------------
M0_mainqi:
    Original month-branch main-qi Ten-God.

M1_priority_6:
    Exposure-aware month branch using YEAR + MONTH stems only.
    DAY stem is excluded from 透干.
    If hidden stems are exposed, choose highest priority:
        main > middle > residual
    If none exposed, fall back to main qi.

M1_share_6:
    If hidden stems are exposed, contribution = fraction of exposed
    hidden stems that are Shangguan; if none exposed, fallback main qi.

M1_any_6:
    If hidden stems are exposed, feature=1 if ANY exposed hidden stem is
    Shangguan; if none exposed, fallback main qi.

M2_priority_8 / M2_share_8 / M2_any_8:
    Same rules, but YEAR + MONTH + HOUR stems can activate hidden stems.
    Unknown hour is exactly marginalized over all 12 double-hours.

For M10 each Shangguan exposure score is multiplied by:
    I(Day-Master element != Fire)

Outputs
-------
music_monthorder_hiddenstem_sensitivity_v1/
  music_monthorder_hiddenstem_sensitivity_results.csv
  music_monthorder_hiddenstem_sensitivity_summary.txt
  music_monthorder_hiddenstem_transition_audit.csv

Important
---------
This script also outputs a transition audit for the month branch:
  mainqi_SG -> exposure_nonSG
  mainqi_nonSG -> exposure_SG
under the six-position PRIORITY rule, allowing direct diagnosis of whether
auxiliary Shangguan activations offset losses of main-qi Shangguan.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import patsy
import statsmodels.api as sm
import sxtwl


STEMS = list("甲乙丙丁戊己庚辛壬癸")
BRANCHES = list("子丑寅卯辰巳午未申酉戌亥")
STEM_ELEMENT = ["木","木","火","火","土","土","金","金","水","水"]
STEM_YANG = [1,0,1,0,1,0,1,0,1,0]

# Traditional hidden-stem order: main > middle > residual.
HIDDEN_STEMS = {
    0: [9],          # 子 癸
    1: [5,9,7],      # 丑 己癸辛
    2: [0,2,4],      # 寅 甲丙戊
    3: [1],          # 卯 乙
    4: [4,1,9],      # 辰 戊乙癸
    5: [2,4,6],      # 巳 丙戊庚
    6: [3,5],        # 午 丁己
    7: [5,3,1],      # 未 己丁乙
    8: [6,8,4],      # 申 庚壬戊
    9: [7],          # 酉 辛
    10:[4,7,3],      # 戌 戊辛丁
    11:[8,0],        # 亥 壬甲
}
BRANCH_MAIN_STEM = [HIDDEN_STEMS[i][0] for i in range(12)]


def ten_god(dm: int, target: int) -> str:
    de, te = STEM_ELEMENT[dm], STEM_ELEMENT[target]
    same = STEM_YANG[dm] == STEM_YANG[target]
    gen = {"木":"火","火":"土","土":"金","金":"水","水":"木"}
    ctl = {"木":"土","土":"水","水":"火","火":"金","金":"木"}

    if te == de:
        return "比肩" if same else "劫财"
    if gen[de] == te:
        return "食神" if same else "伤官"
    if gen[te] == de:
        return "偏印" if same else "正印"
    if ctl[de] == te:
        return "偏财" if same else "正财"
    if ctl[te] == de:
        return "七杀" if same else "正官"
    raise RuntimeError((dm, target))


def is_sg(dm: int, stem_idx: int) -> float:
    return 1.0 if ten_god(dm, stem_idx) == "伤官" else 0.0


def hour_stem_index(day_stem_idx: int, hour_branch_idx: int) -> int:
    # 甲己甲子、乙庚丙子、丙辛戊子、丁壬庚子、戊癸壬子
    zi_start = 2 * (int(day_stem_idx) % 5)
    return (zi_start + int(hour_branch_idx)) % 10


def ymd_gz(y: int, m: int, d: int):
    x = sxtwl.fromSolar(int(y), int(m), int(d))
    return x.getYearGZ(), x.getMonthGZ(), x.getDayGZ()


def branch_sg_score(dm: int, branch_idx: int, visible_stems: set[int], rule: str) -> float:
    hidden = HIDDEN_STEMS[int(branch_idx)]
    exposed = [s for s in hidden if s in visible_stems]

    if rule == "main":
        return is_sg(dm, hidden[0])

    if not exposed:
        return is_sg(dm, hidden[0])

    if rule == "priority":
        return is_sg(dm, exposed[0])

    if rule == "share":
        return float(np.mean([is_sg(dm, s) for s in exposed]))

    if rule == "any":
        return float(any(is_sg(dm, s) > 0 for s in exposed))

    raise ValueError(rule)


def date_monthorder_features(y: int, m: int, d: int, hour_weights: np.ndarray) -> dict:
    yg, mg, dg = ymd_gz(y, m, d)
    dm = int(dg.tg)
    mb = int(mg.dz)

    visible6 = {int(yg.tg), int(mg.tg)}

    main = branch_sg_score(dm, mb, visible6, "main")
    pri6 = branch_sg_score(dm, mb, visible6, "priority")
    shr6 = branch_sg_score(dm, mb, visible6, "share")
    any6 = branch_sg_score(dm, mb, visible6, "any")

    pri8 = shr8 = any8 = 0.0
    for hb, w in enumerate(hour_weights):
        hs = hour_stem_index(dm, hb)
        visible8 = {int(yg.tg), int(mg.tg), int(hs)}
        pri8 += float(w) * branch_sg_score(dm, mb, visible8, "priority")
        shr8 += float(w) * branch_sg_score(dm, mb, visible8, "share")
        any8 += float(w) * branch_sg_score(dm, mb, visible8, "any")

    nonfire = 1.0 if STEM_ELEMENT[dm] != "火" else 0.0

    return {
        "gregorian_year": int(y),
        "gregorian_month": int(m),
        "weekday": int(pd.Timestamp(y, m, d).weekday()),
        "day_stem": STEMS[dm],
        "day_stem_idx": dm,
        "day_element": STEM_ELEMENT[dm],
        "month_branch": BRANCHES[mb],
        "month_branch_idx": mb,

        # M5 features
        "M5_M0_mainqi": float(main),
        "M5_M1_priority_6": float(pri6),
        "M5_M1_share_6": float(shr6),
        "M5_M1_any_6": float(any6),
        "M5_M2_priority_8": float(pri8),
        "M5_M2_share_8": float(shr8),
        "M5_M2_any_8": float(any8),

        # M10: same exposure score restricted to non-Fire Day Masters
        "M10_M0_mainqi_nonfire": float(main * nonfire),
        "M10_M1_priority_6_nonfire": float(pri6 * nonfire),
        "M10_M1_share_6_nonfire": float(shr6 * nonfire),
        "M10_M1_any_6_nonfire": float(any6 * nonfire),
        "M10_M2_priority_8_nonfire": float(pri8 * nonfire),
        "M10_M2_share_8_nonfire": float(shr8 * nonfire),
        "M10_M2_any_8_nonfire": float(any8 * nonfire),

        # Transition audit under six-position PRIORITY rule
        "mainqi_is_sg": int(main > 0.5),
        "priority6_is_sg": int(pri6 > 0.5),
    }


def parse_hour_weights(s: str) -> np.ndarray:
    if s.strip().lower() == "uniform":
        return np.ones(12, dtype=float) / 12.0
    vals = np.array([float(x.strip()) for x in s.split(",")], dtype=float)
    if len(vals) != 12:
        raise SystemExit("--hour-weights must contain 12 comma-separated values in 子..亥 order")
    if np.any(vals < 0) or vals.sum() <= 0:
        raise SystemExit("Hour weights must be nonnegative and sum to >0")
    return vals / vals.sum()


def detect_col(df: pd.DataFrame, explicit: str | None, candidates: list[str], logical_name: str) -> str:
    if explicit:
        if explicit not in df.columns:
            raise RuntimeError(f"{logical_name}: requested column '{explicit}' not found")
        return explicit
    lower_map = {c.lower(): c for c in df.columns}
    for cand in candidates:
        if cand.lower() in lower_map:
            return lower_map[cand.lower()]
    raise RuntimeError(
        f"Could not auto-detect {logical_name}. Columns are:\n{list(df.columns)}\n"
        f"Use the corresponding --*-col option."
    )


def coerce_music(s: pd.Series) -> pd.Series:
    # Numeric/bool first.
    if pd.api.types.is_bool_dtype(s):
        return s.astype(int)
    if pd.api.types.is_numeric_dtype(s):
        vals = s.astype(float)
        if set(vals.dropna().unique()).issubset({0.0,1.0}):
            return vals.astype(int)

    # String binary.
    ss = s.fillna("").astype(str).str.strip()
    low = ss.str.lower()
    true_vals = {"1","true","yes","y","music","musician"}
    false_vals = {"0","false","no","n","non-music","nonmusic",""}

    if set(low.unique()).issubset(true_vals | false_vals):
        return low.map(lambda x: 1 if x in true_vals else 0).astype(int)

    # Broad-category field: detect token Music.
    return ss.str.contains(r"(^|[;,|/\[\]'\"])\s*Music\s*($|[;,|/\[\]'\"])", case=False, regex=True).astype(int)


def load_people(path: Path, dob_col: str | None, music_col: str | None) -> pd.DataFrame:
    df = pd.read_csv(path)

    dc = detect_col(
        df, dob_col,
        ["exact_dob_frozen","dob","birth_date","date_of_birth","birthdate","date"],
        "DOB",
    )
    mc = detect_col(
        df, music_col,
        ["is_music","music","music_flag","broad_categories","broad_category","categories"],
        "Music outcome",
    )

    out = df.copy()
    out["_dob"] = pd.to_datetime(out[dc].astype(str).str[:10], errors="coerce")
    out["_music"] = coerce_music(out[mc])

    bad = out["_dob"].isna()
    if bad.any():
        raise RuntimeError(f"{path}: {bad.sum()} rows have invalid DOB in column {dc}")

    return out


def attach_features(df: pd.DataFrame, hour_weights: np.ndarray) -> pd.DataFrame:
    # Compute once per unique date.
    dates = (
        df[["_dob"]]
        .drop_duplicates()
        .sort_values("_dob")
        .reset_index(drop=True)
    )
    feat_rows = []
    for dt in dates["_dob"]:
        f = date_monthorder_features(dt.year, dt.month, dt.day, hour_weights)
        f["_dob"] = dt
        feat_rows.append(f)
    feat = pd.DataFrame(feat_rows)
    return df.merge(feat, on="_dob", how="left", validate="many_to_one")


def grouped_daily(df: pd.DataFrame, feature: str) -> pd.DataFrame:
    g = (
        df.groupby(
            ["_dob","gregorian_year","gregorian_month","weekday","day_stem","month_branch",feature],
            dropna=False,
            as_index=False,
        )
        .agg(n=("_music","size"), music=("_music","sum"))
    )
    g["nonmusic"] = g["n"] - g["music"]
    return g


def fit_grouped_binomial(df: pd.DataFrame, feature: str, extra_covars: bool) -> dict:
    d = grouped_daily(df, feature)

    rhs = feature + " + C(gregorian_year) + C(gregorian_month) + C(weekday)"
    if extra_covars:
        rhs += " + C(day_stem) + C(month_branch)"

    # Use a two-column grouped-binomial response, matching the original daily-count logic.
    X = patsy.dmatrix(rhs, data=d, return_type="dataframe")
    endog = np.column_stack([d["music"].to_numpy(float), d["nonmusic"].to_numpy(float)])

    fit = sm.GLM(endog, X, family=sm.families.Binomial()).fit(cov_type="HC0")

    beta = float(fit.params[feature])
    se = float(fit.bse[feature])
    z = beta / se
    p2 = float(math.erfc(abs(z) / math.sqrt(2.0)))
    p_pos = float(0.5 * math.erfc(z / math.sqrt(2.0)))

    lo = beta - 1.959963984540054 * se
    hi = beta + 1.959963984540054 * se

    return {
        "feature": feature,
        "n_people": int(df.shape[0]),
        "music_people": int(df["_music"].sum()),
        "n_dates": int(d.shape[0]),
        "feature_mean_people": float(df[feature].mean()),
        "beta": beta,
        "se_hc0": se,
        "OR_per_unit": float(math.exp(beta)),
        "CI95_low": float(math.exp(lo)),
        "CI95_high": float(math.exp(hi)),
        "z": float(z),
        "p_one_positive": p_pos,
        "p_two_sided": p2,
        "formula_rhs": rhs,
    }


def transition_audit(df: pd.DataFrame, label: str) -> pd.DataFrame:
    x = df.copy()
    x["transition"] = np.select(
        [
            (x["mainqi_is_sg"] == 1) & (x["priority6_is_sg"] == 1),
            (x["mainqi_is_sg"] == 1) & (x["priority6_is_sg"] == 0),
            (x["mainqi_is_sg"] == 0) & (x["priority6_is_sg"] == 1),
            (x["mainqi_is_sg"] == 0) & (x["priority6_is_sg"] == 0),
        ],
        ["SG->SG","SG->nonSG","nonSG->SG","nonSG->nonSG"],
        default="other",
    )

    rows = []
    for cohort, sub in [("ALL", x), ("MUSIC", x[x["_music"] == 1]), ("NONMUSIC", x[x["_music"] == 0])]:
        counts = sub["transition"].value_counts()
        n = len(sub)
        for tr in ["SG->SG","SG->nonSG","nonSG->SG","nonSG->nonSG"]:
            c = int(counts.get(tr, 0))
            rows.append({
                "analysis": label,
                "cohort": cohort,
                "transition": tr,
                "n": c,
                "denominator": n,
                "pct": (c / n if n else np.nan),
            })
    return pd.DataFrame(rows)


def analyze_window(
    df: pd.DataFrame,
    label: str,
    features: list[str],
    extra_covars: bool,
) -> list[dict]:
    out = []
    for f in features:
        r = fit_grouped_binomial(df, f, extra_covars=extra_covars)
        r["analysis"] = label
        out.append(r)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-1990-1992", required=True)
    ap.add_argument("--input-1993-1995", required=True)
    ap.add_argument("--dob-col", default=None)
    ap.add_argument("--music-col", default=None)
    ap.add_argument(
        "--hour-weights",
        default="uniform",
        help="uniform OR 12 comma-separated weights in 子,丑,...亥 order",
    )
    ap.add_argument(
        "--output-dir",
        default="music_monthorder_hiddenstem_sensitivity_v1",
    )
    args = ap.parse_args()

    outdir = Path(args.output_dir)
    outdir.mkdir(parents=True, exist_ok=True)
    hour_weights = parse_hour_weights(args.hour_weights)

    d90 = attach_features(
        load_people(Path(args.input_1990_1992), args.dob_col, args.music_col),
        hour_weights,
    )
    d93 = attach_features(
        load_people(Path(args.input_1993_1995), args.dob_col, args.music_col),
        hour_weights,
    )

    # Hard year-window checks so the wrong cohort file cannot be used silently.
    y90 = set(d90["gregorian_year"].unique().tolist())
    y93 = set(d93["gregorian_year"].unique().tolist())
    if not y90.issubset({1990,1991,1992}):
        raise RuntimeError(f"1990–1992 input contains unexpected years: {sorted(y90)}")
    if not y93.issubset({1993,1994,1995}):
        raise RuntimeError(f"1993–1995 input contains unexpected years: {sorted(y93)}")

    m5_features = [
        "M5_M0_mainqi",
        "M5_M1_priority_6",
        "M5_M1_share_6",
        "M5_M1_any_6",
        "M5_M2_priority_8",
        "M5_M2_share_8",
        "M5_M2_any_8",
    ]
    m10_features = [
        "M10_M0_mainqi_nonfire",
        "M10_M1_priority_6_nonfire",
        "M10_M1_share_6_nonfire",
        "M10_M1_any_6_nonfire",
        "M10_M2_priority_8_nonfire",
        "M10_M2_share_8_nonfire",
        "M10_M2_any_8_nonfire",
    ]

    results = []
    results += analyze_window(d90, "M5_1990_1992", m5_features, extra_covars=False)
    results += analyze_window(d93, "M10_1993_1995", m10_features, extra_covars=True)
    res = pd.DataFrame(results)

    # Ratios versus original M0 log-OR / excess feature prevalence are descriptive.
    res["logOR_ratio_vs_M0"] = np.nan
    for label in ["M5_1990_1992","M10_1993_1995"]:
        idx = res["analysis"] == label
        m0_beta = float(res.loc[idx].iloc[0]["beta"])
        if abs(m0_beta) > 1e-12:
            res.loc[idx, "logOR_ratio_vs_M0"] = res.loc[idx, "beta"] / m0_beta

    res.to_csv(
        outdir / "music_monthorder_hiddenstem_sensitivity_results.csv",
        index=False,
        encoding="utf-8-sig",
    )

    # Transition audit answers the user's C2-style conceptual question for Music:
    # how often main-qi Shangguan is lost vs auxiliary Shangguan is gained.
    ta = pd.concat([
        transition_audit(d90, "M5_1990_1992"),
        transition_audit(d93, "M10_1993_1995"),
    ], ignore_index=True)
    ta.to_csv(
        outdir / "music_monthorder_hiddenstem_transition_audit.csv",
        index=False,
        encoding="utf-8-sig",
    )

    # Export date-level feature table for audit, not full personal metadata.
    date_cols = [
        "_dob","gregorian_year","gregorian_month","weekday",
        "day_stem","day_element","month_branch",
        *m5_features,*m10_features,
        "mainqi_is_sg","priority6_is_sg",
    ]
    pd.concat([
        d90[date_cols].drop_duplicates(),
        d93[date_cols].drop_duplicates(),
    ], ignore_index=True).sort_values("_dob").to_csv(
        outdir / "music_monthorder_hiddenstem_date_features.csv",
        index=False,
        encoding="utf-8-sig",
    )

    lines = []
    lines.append("MUSIC MONTH-ORDER HIDDEN-STEM / HOUR SENSITIVITY V1")
    lines.append("=" * 78)
    lines.append("")
    lines.append("Hour weights: " + " ".join(
        f"{BRANCHES[i]}={hour_weights[i]:.5f}" for i in range(12)
    ))
    lines.append("")
    lines.append("SANITY CHECKS")
    lines.append("-------------")
    lines.append("M5 M0 should approximately reproduce: OR=1.067784, p_one=0.15669989")
    lines.append("M10 M0 should approximately reproduce: OR=1.019834, p_one=0.42987605")
    lines.append("If M0 does not reproduce, STOP: input cohort or model does not match frozen validation.")
    lines.append("")

    for label in ["M5_1990_1992","M10_1993_1995"]:
        lines.append("-" * 78)
        lines.append(label)
        lines.append("-" * 78)
        for _, r in res[res["analysis"] == label].iterrows():
            lines.append(
                f"{r['feature']}: "
                f"mean={r['feature_mean_people']:.6f} "
                f"OR={r['OR_per_unit']:.6f} "
                f"CI=[{r['CI95_low']:.6f},{r['CI95_high']:.6f}] "
                f"p_one={r['p_one_positive']:.8g} "
                f"logOR_ratio_vs_M0={r['logOR_ratio_vs_M0']:.4f}"
            )
        lines.append("")

    lines.append("TRANSITION AUDIT (six-position priority rule)")
    lines.append("----------------------------------------------")
    for label in ["M5_1990_1992","M10_1993_1995"]:
        lines.append(label)
        z = ta[(ta["analysis"] == label) & (ta["cohort"] == "ALL")]
        for _, r in z.iterrows():
            lines.append(f"  {r['transition']}: {int(r['n'])}/{int(r['denominator'])} = {r['pct']:.4%}")
        lines.append("")

    lines += [
        "INTERPRETATION GUARDRAILS",
        "-------------------------",
        "1) M0 is the frozen original result; sensitivity models do not replace it.",
        "2) Priority is the cleanest exposure-aware model; Share and Any form a sensitivity envelope.",
        "3) For M5/M10, focus first on OR direction and effect attenuation/amplification, not p<0.05 alone.",
        "4) The transition audit separates main-qi Shangguan losses (SG->nonSG) from auxiliary",
        "   Shangguan gains (nonSG->SG).",
        "5) Because Share/M2 models can be fractional, ORs are per +1 unit of expected Shangguan exposure.",
    ]

    (outdir / "music_monthorder_hiddenstem_sensitivity_summary.txt").write_text(
        "\n".join(lines), encoding="utf-8"
    )

    meta = {
        "analysis_role": "post-validation_method_sensitivity",
        "hour_weights": {BRANCHES[i]: float(hour_weights[i]) for i in range(12)},
        "day_stem_excluded_from_transparency": True,
        "fallback_if_no_hidden_stem_exposed": "main_qi",
        "priority_order": "main>middle>residual",
        "M5_original_target": {"OR": 1.067784, "p_one": 0.15669989},
        "M10_original_target": {"OR": 1.019834, "p_one": 0.42987605},
    }
    (outdir / "music_monthorder_hiddenstem_sensitivity_metadata.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print("\n=== RESULTS ===")
    print(res[["analysis","feature","OR_per_unit","p_one_positive","logOR_ratio_vs_M0"]].to_string(index=False))
    print("\nSaved:", outdir)


if __name__ == "__main__":
    main()
