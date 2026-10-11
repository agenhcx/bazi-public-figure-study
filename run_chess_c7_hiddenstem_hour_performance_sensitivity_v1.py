#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
C7 hidden-stem / hour-pillar performance sensitivity V1
========================================================

Target
------
Chess C7:
    Six-position Shangguan / Pianyin counts vs Elo within elite Chess.

Original frozen finding:
    2023 FULL:       SG rho ~ +0.006 ; PY rho ~ -0.059
    2023 NEW_TARGET: SG rho ~ +0.031 ; PY rho ~ +0.059

This script is a POST-VALIDATION METHOD SENSITIVITY.
It does not replace the frozen C7 result.

Cohorts
-------
Reads:
  chess_2023_cohorts_v1/primary_2023_M_FULL.csv
  chess_2023_cohorts_v1/primary_2023_F_FULL.csv
  chess_2023_cohorts_v1/validation_2023_M_NEW_TARGET.csv
  chess_2023_cohorts_v1/validation_2023_F_NEW_TARGET.csv

The original C7 pooled performance analysis is reconstructed by:
  - z-standardizing rating within sex (M/F) inside each analysis population;
  - pooling sexes;
  - Spearman correlation of Ten-God count vs Elo-z.

Because Spearman is invariant to positive affine scaling, sex-specific descriptive
correlations are also reported.

Coding
------
M0_mainqi_6pos:
  Original six known Y/M/D positions.

M1_*_6pos:
  Hidden-stem exposure sensitivity on Y/M/D branches.
  Visible stems = Year + Month stems.
  Day stem is excluded from 透干.
  No hidden stem exposed -> fallback to main qi.

M2_mainqi_8pos_expected:
  Add Hour stem + Hour branch main qi and exactly average the feature over 12 hours.

M3_*_8pos_expected:
  Full exposure-aware feature, exactly averaged over 12 hours.
  Visible stems = Year + Month + Hour stems.
  Day stem excluded from 透干.

Exposure rules:
  priority : highest-priority exposed hidden stem, main > middle > residual.
  share    : fraction of exposed hidden stems having the target Ten God.
  any      : 1 if any exposed hidden stem has the target Ten God.
  All rules fallback to main qi when none is exposed.

Nonlinearity check
------------------
Correlation is nonlinear, so Corr(E[X_hour], Elo) is not identical to
E[Corr(X_hour, Elo)]. Therefore the script additionally performs Monte Carlo
hour assignment:
  - independently draw one of 12 hours for every player;
  - recompute pooled Spearman rho;
  - repeat --hour-mc times;
  - report median, 2.5/97.5 percentiles, mean, and P(rho>0).

Primary hour distribution:
  uniform over 12 traditional double-hours.

Dependencies:
  pip install numpy pandas scipy sxtwl

Run:
  python .\run_chess_c7_hiddenstem_hour_performance_sensitivity_v1.py --repo . --hour-mc 10000

Outputs:
  chess_c7_hiddenstem_hour_sensitivity_v1/
    c7_sensitivity_summary.txt
    c7_sensitivity_results.csv
    c7_hour_mc_results.csv
    c7_player_expected_features.csv
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import sxtwl
from scipy.stats import spearmanr


STEMS = list("甲乙丙丁戊己庚辛壬癸")
BRANCHES = list("子丑寅卯辰巳午未申酉戌亥")

STEM_ELEMENT = ["木","木","火","火","土","土","金","金","水","水"]
STEM_YANG = [1,0,1,0,1,0,1,0,1,0]

# main > middle > residual
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


def tg_score(dm: int, target: int, tg: str) -> float:
    return 1.0 if ten_god(dm, target) == tg else 0.0


def ymd_gz(y: int, m: int, d: int):
    x = sxtwl.fromSolar(int(y), int(m), int(d))
    return x.getYearGZ(), x.getMonthGZ(), x.getDayGZ()


def hour_stem_index(day_stem_idx: int, hour_branch_idx: int) -> int:
    zi_start = 2 * (int(day_stem_idx) % 5)
    return (zi_start + int(hour_branch_idx)) % 10


def branch_tg_contribution(
    dm: int,
    branch_idx: int,
    visible_stems: set[int],
    target_tg: str,
    rule: str,
) -> float:
    hidden = HIDDEN_STEMS[int(branch_idx)]
    exposed = [s for s in hidden if s in visible_stems]

    if rule == "main":
        return tg_score(dm, hidden[0], target_tg)

    if not exposed:
        return tg_score(dm, hidden[0], target_tg)

    if rule == "priority":
        return tg_score(dm, exposed[0], target_tg)

    if rule == "share":
        return float(np.mean([tg_score(dm, s, target_tg) for s in exposed]))

    if rule == "any":
        return float(any(tg_score(dm, s, target_tg) > 0 for s in exposed))

    raise ValueError(rule)


def date_feature_bundle(y: int, m: int, d: int) -> dict:
    yg, mg, dg = ymd_gz(y, m, d)
    dm = int(dg.tg)

    yb, mb, db = int(yg.dz), int(mg.dz), int(dg.dz)
    ys, ms, ds = int(yg.tg), int(mg.tg), int(dg.tg)

    visible6 = {ys, ms}  # Day stem excluded from transparency.

    out = {
        "year_pillar": STEMS[ys] + BRANCHES[yb],
        "month_pillar": STEMS[ms] + BRANCHES[mb],
        "day_pillar": STEMS[ds] + BRANCHES[db],
        "day_stem": STEMS[dm],
    }

    for tg, short in [("伤官","SG"), ("偏印","PY")]:
        stem6 = tg_score(dm, ys, tg) + tg_score(dm, ms, tg) + tg_score(dm, ds, tg)

        out[f"{short}_M0_mainqi_6"] = float(
            stem6
            + branch_tg_contribution(dm, yb, visible6, tg, "main")
            + branch_tg_contribution(dm, mb, visible6, tg, "main")
            + branch_tg_contribution(dm, db, visible6, tg, "main")
        )

        for rule in ["priority","share","any"]:
            out[f"{short}_M1_{rule}_6"] = float(
                stem6
                + branch_tg_contribution(dm, yb, visible6, tg, rule)
                + branch_tg_contribution(dm, mb, visible6, tg, rule)
                + branch_tg_contribution(dm, db, visible6, tg, rule)
            )

        # Exact expected feature over 12 hours, plus all 12 hour-specific values.
        for model, rule in [("M2_mainqi", "main"),
                            ("M3_priority", "priority"),
                            ("M3_share", "share"),
                            ("M3_any", "any")]:
            vals = []
            for hb in range(12):
                hs = hour_stem_index(dm, hb)
                visible8 = {ys, ms, hs}
                stem8 = stem6 + tg_score(dm, hs, tg)
                v = (
                    stem8
                    + branch_tg_contribution(dm, yb, visible8, tg, rule)
                    + branch_tg_contribution(dm, mb, visible8, tg, rule)
                    + branch_tg_contribution(dm, db, visible8, tg, rule)
                    + branch_tg_contribution(dm, hb, visible8, tg, rule)
                )
                vals.append(float(v))
            out[f"{short}_{model}_8_expected"] = float(np.mean(vals))
            out[f"__{short}_{model}_8_hours"] = vals

    return out


def detect_rating_col(df: pd.DataFrame) -> str:
    candidates = [
        "rating", "elo", "rating_std", "fide_rating",
        "standard_rating", "rating_standard",
    ]
    low = {c.lower(): c for c in df.columns}
    for x in candidates:
        if x.lower() in low:
            return low[x.lower()]
    raise RuntimeError(
        "Could not detect rating column. Columns:\n" + repr(list(df.columns))
    )


def load_one(path: Path, sex: str, group: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)

    d = pd.read_csv(path)
    if "exact_dob_frozen" not in d.columns:
        raise RuntimeError(f"{path}: missing exact_dob_frozen")

    rc = detect_rating_col(d)
    d = d.copy()
    d["_rating"] = pd.to_numeric(d[rc], errors="raise")
    d["_sex"] = sex
    d["_group"] = group

    # Within-sex z-standardization, preserving original pooled-performance logic.
    sd = float(d["_rating"].std(ddof=0))
    if sd <= 0:
        raise RuntimeError(f"{path}: rating SD <= 0")
    d["_elo_z"] = (d["_rating"] - float(d["_rating"].mean())) / sd

    rows = []
    cache = {}
    for _, r in d.iterrows():
        dt = pd.Timestamp(str(r["exact_dob_frozen"])[:10])
        key = dt.date().isoformat()
        if key not in cache:
            cache[key] = date_feature_bundle(dt.year, dt.month, dt.day)
        rows.append(cache[key])

    feat = pd.DataFrame(rows)
    return pd.concat([d.reset_index(drop=True), feat], axis=1)


def corr_result(x: np.ndarray, y: np.ndarray) -> tuple[float,float]:
    r = spearmanr(x, y)
    return float(r.statistic), float(r.pvalue)


def deterministic_results(df: pd.DataFrame, group: str) -> list[dict]:
    rows = []
    cols = []
    for short, tg in [("SG","伤官"), ("PY","偏印")]:
        cols += [
            (tg, f"{short}_M0_mainqi_6"),
            (tg, f"{short}_M1_priority_6"),
            (tg, f"{short}_M1_share_6"),
            (tg, f"{short}_M1_any_6"),
            (tg, f"{short}_M2_mainqi_8_expected"),
            (tg, f"{short}_M3_priority_8_expected"),
            (tg, f"{short}_M3_share_8_expected"),
            (tg, f"{short}_M3_any_8_expected"),
        ]

    for tg, col in cols:
        rho, p2 = corr_result(df[col].to_numpy(float), df["_elo_z"].to_numpy(float))
        rows.append({
            "group": group,
            "scope": "POOLED_SEX_Z",
            "ten_god": tg,
            "feature": col,
            "n": len(df),
            "rho": rho,
            "p_two_sided": p2,
        })

        # Descriptive sex strata.
        for sex in ["M","F"]:
            z = df.loc[df["_sex"].eq(sex)]
            if len(z) >= 3:
                rr, pp = corr_result(z[col].to_numpy(float), z["_rating"].to_numpy(float))
                rows.append({
                    "group": group,
                    "scope": sex,
                    "ten_god": tg,
                    "feature": col,
                    "n": len(z),
                    "rho": rr,
                    "p_two_sided": pp,
                })

    return rows


def hour_mc_for_model(
    df: pd.DataFrame,
    short: str,
    model: str,
    n_mc: int,
    rng: np.random.Generator,
) -> dict:
    hour_col = f"__{short}_{model}_8_hours"
    H = np.array(df[hour_col].tolist(), dtype=float)  # N x 12
    y = df["_elo_z"].to_numpy(float)
    n = len(df)

    rhos = np.empty(n_mc, dtype=float)
    for i in range(n_mc):
        h = rng.integers(0, 12, size=n)
        x = H[np.arange(n), h]
        rhos[i] = float(spearmanr(x, y).statistic)

    return {
        "n_mc": int(n_mc),
        "rho_mean": float(np.mean(rhos)),
        "rho_median": float(np.median(rhos)),
        "rho_q025": float(np.quantile(rhos, 0.025)),
        "rho_q975": float(np.quantile(rhos, 0.975)),
        "p_rho_gt_0": float(np.mean(rhos > 0)),
        "p_rho_lt_0": float(np.mean(rhos < 0)),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    ap.add_argument("--source-subdir", default="chess_2023_cohorts_v1")
    ap.add_argument("--output-subdir", default="chess_c7_hiddenstem_hour_sensitivity_v1")
    ap.add_argument("--hour-mc", type=int, default=10000)
    ap.add_argument("--seed", type=int, default=20261006)
    args = ap.parse_args()

    root = Path(args.repo).resolve()
    src = root / args.source_subdir
    outdir = root / args.output_subdir
    outdir.mkdir(parents=True, exist_ok=True)

    paths = {
        ("FULL","M"): src / "primary_2023_M_FULL.csv",
        ("FULL","F"): src / "primary_2023_F_FULL.csv",
        ("NEW_TARGET","M"): src / "validation_2023_M_NEW_TARGET.csv",
        ("NEW_TARGET","F"): src / "validation_2023_F_NEW_TARGET.csv",
    }

    data = {}
    for group in ["FULL","NEW_TARGET"]:
        frames = []
        for sex in ["M","F"]:
            frames.append(load_one(paths[(group,sex)], sex, group))
        data[group] = pd.concat(frames, ignore_index=True)

    # Deterministic / expected-feature correlations.
    det_rows = []
    for group, df in data.items():
        det_rows += deterministic_results(df, group)
    det = pd.DataFrame(det_rows)
    det.to_csv(outdir / "c7_sensitivity_results.csv", index=False, encoding="utf-8-sig")

    # Nonlinear hour-assignment MC for mainqi and three exposure rules.
    mc_rows = []
    for gidx, group in enumerate(["FULL","NEW_TARGET"]):
        df = data[group]
        for sidx, (short, tg) in enumerate([("SG","伤官"),("PY","偏印")]):
            for midx, model in enumerate(["M2_mainqi","M3_priority","M3_share","M3_any"]):
                seed = args.seed + gidx*100000 + sidx*10000 + midx*1000
                rr = hour_mc_for_model(
                    df, short, model, args.hour_mc, np.random.default_rng(seed)
                )
                mc_rows.append({
                    "group": group,
                    "scope": "POOLED_SEX_Z",
                    "ten_god": tg,
                    "model": model,
                    **rr,
                })
    mc = pd.DataFrame(mc_rows)
    mc.to_csv(outdir / "c7_hour_mc_results.csv", index=False, encoding="utf-8-sig")

    # Player-level expected features only; do not export the internal 12-value arrays.
    exp_cols = [
        c for c in data["FULL"].columns
        if (c.startswith("SG_") or c.startswith("PY_")) and not c.startswith("__")
    ]
    export_frames = []
    for group, df in data.items():
        keep = [c for c in [
            "_group","_sex","fide_id","name","exact_dob_frozen","_rating","_elo_z",
            "year_pillar","month_pillar","day_pillar","day_stem",
            *exp_cols
        ] if c in df.columns]
        export_frames.append(df[keep])
    pd.concat(export_frames, ignore_index=True).to_csv(
        outdir / "c7_player_expected_features.csv",
        index=False,
        encoding="utf-8-sig",
    )

    # Summary.
    lines = [
        "C7 HIDDEN-STEM / HOUR-PILLAR PERFORMANCE SENSITIVITY V1",
        "="*78,
        "",
        "Original frozen C7 sanity targets (pooled sex-standardized Elo):",
        "FULL:       SG rho ~ +0.006 ; PY rho ~ -0.059",
        "NEW_TARGET: SG rho ~ +0.031 ; PY rho ~ +0.059",
        "",
        "DETERMINISTIC / EXPECTED-FEATURE CORRELATIONS",
        "---------------------------------------------",
    ]

    for group in ["FULL","NEW_TARGET"]:
        lines.append(group)
        z = det.loc[(det["group"].eq(group)) & (det["scope"].eq("POOLED_SEX_Z"))]
        for _, r in z.iterrows():
            lines.append(
                f"  {r['feature']}: {r['ten_god']} n={int(r['n'])} "
                f"rho={r['rho']:+.6f} p2={r['p_two_sided']:.6g}"
            )
        lines.append("")

    lines += [
        "RANDOM-HOUR MONTE CARLO (nonlinearity check)",
        "---------------------------------------------",
    ]
    for group in ["FULL","NEW_TARGET"]:
        lines.append(group)
        z = mc.loc[mc["group"].eq(group)]
        for _, r in z.iterrows():
            lines.append(
                f"  {r['ten_god']} {r['model']}: "
                f"rho_med={r['rho_median']:+.6f} "
                f"mean={r['rho_mean']:+.6f} "
                f"95%=[{r['rho_q025']:+.6f},{r['rho_q975']:+.6f}] "
                f"P(rho>0)={r['p_rho_gt_0']:.4f}"
            )
        lines.append("")

    lines += [
        "INTERPRETATION GUARDRAILS",
        "-------------------------",
        "1) First verify M0 reproduces the frozen C7 correlations approximately.",
        "2) C7 remains a negative performance finding if SG/PY correlations remain near zero",
        "   across priority/share/any and the random-hour distribution.",
        "3) Do not promote a nominal p-value from one sensitivity rule.",
        "4) If a full-chart exposure model produces a materially nonzero correlation in both",
        "   FULL and independent NEW_TARGET with consistent sign, C7 must be revised.",
        "5) This analysis concerns within-elite performance only; it does not change C2 elite-selection enrichment.",
    ]

    (outdir / "c7_sensitivity_summary.txt").write_text("\n".join(lines), encoding="utf-8")

    meta = {
        "analysis_role": "post-validation method sensitivity",
        "target": "C7 Shangguan/Pianyin count vs Elo",
        "hour_distribution": "uniform over 12 double-hours",
        "day_stem_excluded_from_transparency": True,
        "fallback": "main qi when no hidden stem exposed",
        "priority_order": "main > middle > residual",
        "hour_mc": int(args.hour_mc),
        "seed": int(args.seed),
    }
    (outdir / "metadata.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print("\n".join(lines))
    print("\nSaved:", outdir)


if __name__ == "__main__":
    main()
