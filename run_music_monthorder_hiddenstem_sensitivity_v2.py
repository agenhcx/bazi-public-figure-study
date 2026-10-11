#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Music month-order hidden-stem/hour sensitivity V2
=================================================

This version reproduces the ORIGINAL Music validation cohort construction:
- Reads hemisphere_YEAR/YEAR_people_with_hemisphere.csv directly.
- Uses lunar_python (same as frozen Music validation pipelines).
- Uses _birth_date_norm and _music.
- Excludes dates whose Year or Month pillar differs between 00:30 and 22:30.
- Uses 12:00 civil time for Y/M/D pillars.
- Primary scope = hemisphere == "north".

Targets:
M5  1990-1992: broad month-order Shangguan positive
M10 1993-1995: non-Fire month-order Shangguan positive

Sensitivity coding:
M0: original month-branch main qi.
M1: exposure-aware using Year+Month stems (Day stem excluded from 透干).
M2: same, with Hour stem marginalized across all 12 double-hours.

Exposure rules:
priority = highest-priority exposed hidden stem (main > middle > residual), fallback main.
share    = fraction of exposed hidden stems that are Shangguan, fallback main.
any      = 1 if any exposed hidden stem is Shangguan, fallback main.

IMPORTANT:
- M0 remains the frozen original result.
- All new models are post-validation method sensitivities.
- All prespecified sensitivity rules are reported.

Run:
    python .\run_music_monthorder_hiddenstem_sensitivity_v2.py --repo .

Expected M0 sanity:
- M5 OR ~= 1.067784, p_one ~= 0.15669989
- M10 OR ~= 1.019834, p_one ~= 0.42987605
- M10 north N = 33034, Music = 1792, dates = 1062

Dependencies:
    pip install pandas numpy statsmodels lunar_python
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from lunar_python import Solar


STEMS = list("甲乙丙丁戊己庚辛壬癸")
BRANCHES = list("子丑寅卯辰巳午未申酉戌亥")

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

# Traditional order frozen as main > middle > residual.
HIDDEN_STEMS = {
    "子":["癸"],
    "丑":["己","癸","辛"],
    "寅":["甲","丙","戊"],
    "卯":["乙"],
    "辰":["戊","乙","癸"],
    "巳":["丙","戊","庚"],
    "午":["丁","己"],
    "未":["己","丁","乙"],
    "申":["庚","壬","戊"],
    "酉":["辛"],
    "戌":["戊","辛","丁"],
    "亥":["壬","甲"],
}
BRANCH_MAIN_STEM = {b: hs[0] for b, hs in HIDDEN_STEMS.items()}


def ten_god(day_stem: str, target_stem: str) -> str:
    de, te = STEM_ELEMENT[day_stem], STEM_ELEMENT[target_stem]
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


def is_sg(day_stem: str, target_stem: str) -> float:
    return 1.0 if ten_god(day_stem, target_stem) == "伤官" else 0.0


def ec_at(y, m, d, h=12, minute=0):
    ec = Solar.fromYmdHms(
        int(y), int(m), int(d), int(h), int(minute), 0
    ).getLunar().getEightChar()
    return ec.getYear(), ec.getMonth(), ec.getDay(), ec.getTime()


def transition_ambiguous(ts: pd.Timestamp) -> bool:
    y1, m1, _, _ = ec_at(ts.year, ts.month, ts.day, 0, 30)
    y2, m2, _, _ = ec_at(ts.year, ts.month, ts.day, 22, 30)
    return y1 != y2 or m1 != m2


def hour_stem_for_branch(day_stem: str, hour_branch: str) -> str:
    """
    Exact Five-Rat rule, equivalent to deriving the hour pillar directly.
    """
    ds_idx = STEMS.index(day_stem)
    hb_idx = BRANCHES.index(hour_branch)
    zi_start = 2 * (ds_idx % 5)
    return STEMS[(zi_start + hb_idx) % 10]


def branch_sg_score(day_stem: str, branch: str, visible_stems: set[str], rule: str) -> float:
    hidden = HIDDEN_STEMS[branch]
    exposed = [s for s in hidden if s in visible_stems]

    if rule == "main":
        return is_sg(day_stem, hidden[0])

    if not exposed:
        return is_sg(day_stem, hidden[0])

    if rule == "priority":
        return is_sg(day_stem, exposed[0])

    if rule == "share":
        return float(np.mean([is_sg(day_stem, s) for s in exposed]))

    if rule == "any":
        return float(any(is_sg(day_stem, s) > 0 for s in exposed))

    raise ValueError(rule)


def date_features(ts: pd.Timestamp, hour_weights: np.ndarray) -> dict:
    yp, mp, dp, _ = ec_at(ts.year, ts.month, ts.day, 12, 0)
    ys, ms, ds = yp[0], mp[0], dp[0]
    mb = mp[1]

    visible6 = {ys, ms}

    m0 = branch_sg_score(ds, mb, visible6, "main")
    p6 = branch_sg_score(ds, mb, visible6, "priority")
    s6 = branch_sg_score(ds, mb, visible6, "share")
    a6 = branch_sg_score(ds, mb, visible6, "any")

    p8 = s8 = a8 = 0.0
    for hb, w in zip(BRANCHES, hour_weights):
        hs = hour_stem_for_branch(ds, hb)
        visible8 = {ys, ms, hs}
        p8 += float(w) * branch_sg_score(ds, mb, visible8, "priority")
        s8 += float(w) * branch_sg_score(ds, mb, visible8, "share")
        a8 += float(w) * branch_sg_score(ds, mb, visible8, "any")

    nonfire = 1.0 if STEM_ELEMENT[ds] != "火" else 0.0

    return {
        "gregorian_year": int(ts.year),
        "gregorian_month": int(ts.month),
        "weekday": ts.day_name(),
        "year_pillar": yp,
        "month_pillar": mp,
        "day_pillar": dp,
        "year_stem": ys,
        "month_stem": ms,
        "day_stem": ds,
        "month_branch": mb,

        "M5_M0_mainqi": float(m0),
        "M5_M1_priority_6": float(p6),
        "M5_M1_share_6": float(s6),
        "M5_M1_any_6": float(a6),
        "M5_M2_priority_8": float(p8),
        "M5_M2_share_8": float(s8),
        "M5_M2_any_8": float(a8),

        "M10_M0_mainqi_nonfire": float(m0 * nonfire),
        "M10_M1_priority_6_nonfire": float(p6 * nonfire),
        "M10_M1_share_6_nonfire": float(s6 * nonfire),
        "M10_M1_any_6_nonfire": float(a6 * nonfire),
        "M10_M2_priority_8_nonfire": float(p8 * nonfire),
        "M10_M2_share_8_nonfire": float(s8 * nonfire),
        "M10_M2_any_8_nonfire": float(a8 * nonfire),

        "mainqi_is_sg": int(m0 > 0.5),
        "priority6_is_sg": int(p6 > 0.5),
    }


def parse_hour_weights(s: str) -> np.ndarray:
    if s.strip().lower() == "uniform":
        return np.ones(12, dtype=float) / 12.0
    vals = np.array([float(x.strip()) for x in s.split(",")], dtype=float)
    if len(vals) != 12:
        raise SystemExit("--hour-weights requires 12 values in 子..亥 order")
    if np.any(vals < 0) or vals.sum() <= 0:
        raise SystemExit("Hour weights must be nonnegative and sum to >0")
    return vals / vals.sum()


def load_window(root: Path, years: list[int], hour_weights: np.ndarray) -> tuple[pd.DataFrame, pd.DataFrame]:
    frames = []
    qa = []
    cache = {}

    for y in years:
        p = root / f"hemisphere_{y}" / f"{y}_people_with_hemisphere.csv"
        if not p.exists():
            raise FileNotFoundError(p)

        d = pd.read_csv(p, encoding="utf-8-sig")
        required = {"_birth_date_norm", "_music", "hemisphere"}
        missing = required - set(d.columns)
        if missing:
            raise RuntimeError(f"{p} missing: {sorted(missing)}")

        d["_music_eval"] = pd.to_numeric(d["_music"], errors="raise").astype(int)
        d["dob"] = pd.to_datetime(d["_birth_date_norm"], errors="raise")

        # Same year QA as frozen pipelines.
        d = d.loc[d["dob"].dt.year.eq(y)].copy()

        # Compute date features once per unique DOB, and drop transition-ambiguous dates.
        unique_dates = d["dob"].drop_duplicates().sort_values()
        fmap = {}
        ambiguous_dates = set()

        for ts in unique_dates:
            key = ts.date().isoformat()
            if key in cache:
                f = cache[key]
            else:
                if transition_ambiguous(ts):
                    f = None
                else:
                    f = date_features(ts, hour_weights)
                cache[key] = f

            if f is None:
                ambiguous_dates.add(key)
            else:
                fmap[pd.Timestamp(ts)] = f

        n_before = len(d)
        d = d.loc[~d["dob"].dt.date.astype(str).isin(ambiguous_dates)].copy()

        feat = pd.DataFrame(
            [{"dob": k, **v} for k, v in fmap.items()]
        )
        d = d.merge(feat, on="dob", how="left", validate="many_to_one")

        # Primary scope.
        dn = d.loc[d["hemisphere"].eq("north")].copy()

        qa.append({
            "year": y,
            "input_rows": n_before,
            "ambiguous_dates_excluded": len(ambiguous_dates),
            "post_ambiguity_rows_all_scopes": len(d),
            "north_people": len(dn),
            "north_music": int(dn["_music_eval"].sum()),
            "north_dates": int(dn["dob"].nunique()),
        })
        frames.append(dn)

    return pd.concat(frames, ignore_index=True), pd.DataFrame(qa)


def make_daily(df: pd.DataFrame, feature: str, include_relational_covars: bool) -> pd.DataFrame:
    group_cols = [
        "dob","gregorian_year","gregorian_month","weekday",feature
    ]
    if include_relational_covars:
        group_cols += ["day_stem","month_branch"]

    return (
        df.groupby(group_cols, as_index=False, dropna=False)
          .agg(n_people=("_music_eval","size"), music_n=("_music_eval","sum"))
    )


def design_matrix(d: pd.DataFrame, feature: str, include_relational_covars: bool) -> pd.DataFrame:
    X = pd.DataFrame({feature: d[feature].astype(float)}, index=d.index)
    cats = ["gregorian_year","gregorian_month","weekday"]
    if include_relational_covars:
        cats += ["day_stem","month_branch"]

    for c in cats:
        dd = pd.get_dummies(
            d[c].astype("category"),
            prefix=c,
            drop_first=True,
            dtype=float,
        )
        X = pd.concat([X, dd], axis=1)

    return sm.add_constant(X, has_constant="add").astype(float)


def fit_feature(df: pd.DataFrame, feature: str, include_relational_covars: bool) -> dict:
    daily = make_daily(df, feature, include_relational_covars)

    y = np.column_stack([
        daily["music_n"].to_numpy(float),
        (daily["n_people"] - daily["music_n"]).to_numpy(float),
    ])
    X = design_matrix(daily, feature, include_relational_covars)

    fit = sm.GLM(y, X, family=sm.families.Binomial()).fit(cov_type="HC0", maxiter=200)

    b = float(fit.params[feature])
    se = float(fit.bse[feature])
    z = b / se
    p1 = 0.5 * math.erfc(z / math.sqrt(2.0))
    p2 = float(fit.pvalues[feature])

    return {
        "feature": feature,
        "n_people": int(daily["n_people"].sum()),
        "n_music": int(daily["music_n"].sum()),
        "n_dates": int(len(daily)),
        "feature_mean_people": float(np.average(
            daily[feature].astype(float),
            weights=daily["n_people"].astype(float),
        )),
        "beta": b,
        "se": se,
        "OR_per_unit": float(math.exp(b)),
        "CI95_low": float(math.exp(b - 1.96 * se)),
        "CI95_high": float(math.exp(b + 1.96 * se)),
        "z": z,
        "p_one_positive": p1,
        "p_two_sided": p2,
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
    for cohort, sub in [
        ("ALL", x),
        ("MUSIC", x.loc[x["_music_eval"].eq(1)]),
        ("NONMUSIC", x.loc[x["_music_eval"].eq(0)]),
    ]:
        vc = sub["transition"].value_counts()
        n = len(sub)
        for tr in ["SG->SG","SG->nonSG","nonSG->SG","nonSG->nonSG"]:
            c = int(vc.get(tr, 0))
            rows.append({
                "analysis": label,
                "cohort": cohort,
                "transition": tr,
                "n": c,
                "denominator": n,
                "pct": (c / n if n else np.nan),
            })
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    ap.add_argument(
        "--output-dir",
        default="music_monthorder_hiddenstem_sensitivity_v2",
    )
    ap.add_argument(
        "--hour-weights",
        default="uniform",
        help="uniform OR 12 comma-separated weights in 子..亥 order",
    )
    args = ap.parse_args()

    root = Path(args.repo).resolve()
    outdir = root / args.output_dir
    outdir.mkdir(parents=True, exist_ok=True)

    hw = parse_hour_weights(args.hour_weights)

    d90, qa90 = load_window(root, [1990,1991,1992], hw)
    d93, qa93 = load_window(root, [1993,1994,1995], hw)
    qa = pd.concat([
        qa90.assign(block="1990_1992"),
        qa93.assign(block="1993_1995"),
    ], ignore_index=True)
    qa.to_csv(outdir / "cohort_qa.csv", index=False, encoding="utf-8-sig")

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

    rows = []
    for f in m5_features:
        r = fit_feature(d90, f, include_relational_covars=False)
        rows.append({"analysis":"M5_1990_1992", **r})

    for f in m10_features:
        r = fit_feature(d93, f, include_relational_covars=True)
        rows.append({"analysis":"M10_1993_1995", **r})

    res = pd.DataFrame(rows)

    for label in ["M5_1990_1992","M10_1993_1995"]:
        idx = res["analysis"].eq(label)
        b0 = float(res.loc[idx].iloc[0]["beta"])
        res.loc[idx, "logOR_ratio_vs_M0"] = (
            res.loc[idx, "beta"] / b0 if abs(b0) > 1e-12 else np.nan
        )

    res.to_csv(
        outdir / "music_monthorder_hiddenstem_sensitivity_results.csv",
        index=False,
        encoding="utf-8-sig",
    )

    ta = pd.concat([
        transition_audit(d90, "M5_1990_1992"),
        transition_audit(d93, "M10_1993_1995"),
    ], ignore_index=True)
    ta.to_csv(
        outdir / "music_monthorder_hiddenstem_transition_audit.csv",
        index=False,
        encoding="utf-8-sig",
    )

    lines = [
        "MUSIC MONTH-ORDER HIDDEN-STEM / HOUR SENSITIVITY V2",
        "=" * 78,
        "",
        "Cohort construction reproduces frozen Music pipelines:",
        "hemisphere files -> transition-ambiguous date exclusion -> north only.",
        "",
        "Hour weights: " + " ".join(
            f"{BRANCHES[i]}={hw[i]:.5f}" for i in range(12)
        ),
        "",
        "COHORT QA",
        "---------",
    ]
    for _, r in qa.iterrows():
        lines.append(
            f"{int(r['year'])}: north N={int(r['north_people'])}, "
            f"Music={int(r['north_music'])}, dates={int(r['north_dates'])}, "
            f"ambiguous_dates_excluded={int(r['ambiguous_dates_excluded'])}"
        )

    lines += [
        "",
        f"1990-1992 pooled north: N={len(d90)}, Music={int(d90['_music_eval'].sum())}, dates={d90['dob'].nunique()}",
        f"1993-1995 pooled north: N={len(d93)}, Music={int(d93['_music_eval'].sum())}, dates={d93['dob'].nunique()}",
        "",
        "SANITY CHECK TARGETS",
        "--------------------",
        "M5 M0: OR ~= 1.067784, p_one ~= 0.15669989",
        "M10 M0: OR ~= 1.019834, p_one ~= 0.42987605",
        "M10 cohort: N=33034, Music=1792, dates=1062",
        "",
    ]

    for label in ["M5_1990_1992","M10_1993_1995"]:
        lines += ["-" * 78, label, "-" * 78]
        for _, r in res.loc[res["analysis"].eq(label)].iterrows():
            lines.append(
                f"{r['feature']}: mean={r['feature_mean_people']:.6f} "
                f"OR={r['OR_per_unit']:.6f} "
                f"CI=[{r['CI95_low']:.6f},{r['CI95_high']:.6f}] "
                f"p_one={r['p_one_positive']:.8g} "
                f"logOR_ratio_vs_M0={r['logOR_ratio_vs_M0']:.4f}"
            )
        lines.append("")

    lines += [
        "TRANSITION AUDIT — six-position PRIORITY rule",
        "---------------------------------------------",
    ]
    for label in ["M5_1990_1992","M10_1993_1995"]:
        lines.append(label)
        z = ta.loc[(ta["analysis"].eq(label)) & (ta["cohort"].eq("ALL"))]
        for _, r in z.iterrows():
            lines.append(
                f"  {r['transition']}: {int(r['n'])}/{int(r['denominator'])} = {r['pct']:.4%}"
            )
        lines.append("")

    lines += [
        "INTERPRETATION",
        "--------------",
        "1) Do not interpret sensitivities unless M0 reproduces the frozen original result.",
        "2) Priority is primary exposure-aware sensitivity; Share/Any are required secondary sensitivities.",
        "3) Direction and effect-size attenuation/amplification matter more than p<0.05.",
        "4) Transition audit directly separates loss of main-qi Shangguan from gain of auxiliary Shangguan.",
        "5) M0 remains the original inferential result; these analyses are method sensitivities.",
    ]

    (outdir / "music_monthorder_hiddenstem_sensitivity_summary.txt").write_text(
        "\n".join(lines), encoding="utf-8"
    )

    meta = {
        "analysis_role": "post-validation method sensitivity",
        "cohort_source": "hemisphere_YEAR/YEAR_people_with_hemisphere.csv",
        "transition_rule": "exclude if Year or Month pillar differs between 00:30 and 22:30",
        "pillar_time_for_features": "12:00 civil time",
        "primary_scope": "hemisphere == north",
        "day_stem_excluded_from_transparency": True,
        "fallback": "main qi when no hidden stem exposed",
        "priority_order": "main > middle > residual",
        "hour_weights": {BRANCHES[i]: float(hw[i]) for i in range(12)},
    }
    (outdir / "metadata.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print("\n".join(lines))
    print("\nSaved:", outdir)


if __name__ == "__main__":
    main()
