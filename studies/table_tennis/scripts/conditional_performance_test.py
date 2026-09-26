#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
conditional_performance_test.py

LOCKED exploratory/training-set tests:

H1. 辛金：偏印支数量（丑/未，本气己土）越多，peak Elo 越高
H2. 辛金：偏印支数量越多，official career-best rank 越小（更强）
H3. 土日主：土支/root 数量（辰戌丑未）越多，peak Elo 越高
H4. 土日主：土支/root 数量越多，official career-best rank 越小（更强）

Only known 年/月/日 branches are used. No birth-hour branch is invented.

Primary statistic: Spearman rho
Primary p-value: one-sided permutation test in the pre-specified direction.
No subgroup splitting by sex/era/stem after this point.

Secondary descriptive columns:
- 土日主劫财支 count
- 辛金正印支 count
These are written per player but are NOT part of the four locked primary tests.

Dependencies:
    pip install pandas numpy scipy

Run:
python conditional_performance_test.py --ranking tabletennis_reference_enriched.csv --elo ttr_elo_player_summary.csv --permutations 200000 --prefix conditional_perf
"""

import argparse
import numpy as np
import pandas as pd
from scipy.stats import rankdata, spearmanr


EARTH_BRANCHES = set("辰戌丑未")
JI_EARTH_BRANCHES = set("丑未")  # main qi 己
WU_EARTH_BRANCHES = set("辰戌")  # main qi 戊


def add_bazi_features(df):
    x = df.copy()
    x["day_master"] = x["day_pillar"].astype(str).str[0]
    x["year_branch"] = x["year_pillar"].astype(str).str[1]
    x["month_branch"] = x["month_pillar"].astype(str).str[1]
    x["day_branch"] = x["day_pillar"].astype(str).str[1]

    def count_in(row, branch_set):
        return sum(
            b in branch_set
            for b in [row["year_branch"], row["month_branch"], row["day_branch"]]
        )

    x["earth_root_count"] = x.apply(
        lambda r: count_in(r, EARTH_BRANCHES), axis=1
    )

    # 辛金: 己土(丑未) = 偏印；戊土(辰戌) = 正印
    x["xin_partial_seal_count"] = x.apply(
        lambda r: count_in(r, JI_EARTH_BRANCHES), axis=1
    )
    x["xin_direct_seal_count"] = x.apply(
        lambda r: count_in(r, WU_EARTH_BRANCHES), axis=1
    )

    # 土日主劫财:
    # 戊 -> 己土(丑未)
    # 己 -> 戊土(辰戌)
    def earth_robwealth(row):
        if row["day_master"] == "戊":
            return count_in(row, JI_EARTH_BRANCHES)
        if row["day_master"] == "己":
            return count_in(row, WU_EARTH_BRANCHES)
        return np.nan

    x["earth_robwealth_count"] = x.apply(earth_robwealth, axis=1)
    return x


def spearman_perm(x, y, alternative, permutations, rng):
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)

    ok = np.isfinite(x) & np.isfinite(y)
    x = x[ok]
    y = y[ok]

    n = len(x)
    if n < 4:
        return {
            "n": n,
            "rho": np.nan,
            "p_perm_one_sided": np.nan,
            "p_scipy_two_sided": np.nan,
        }

    rho, p2 = spearmanr(x, y)

    # Spearman = Pearson correlation of ranks.
    xr = rankdata(x, method="average").astype(float)
    yr = rankdata(y, method="average").astype(float)

    xr -= xr.mean()
    yr -= yr.mean()

    denom = np.sqrt(np.sum(xr * xr) * np.sum(yr * yr))
    obs = float(np.sum(xr * yr) / denom)

    extreme = 0
    batch = 5000
    done = 0

    while done < permutations:
        b = min(batch, permutations - done)

        # n is small (~26-79), so this is cheap.
        sims = np.empty(b, dtype=float)
        for i in range(b):
            yp = rng.permutation(yr)
            sims[i] = np.sum(xr * yp) / denom

        if alternative == "greater":
            extreme += int(np.count_nonzero(sims >= obs - 1e-15))
        elif alternative == "less":
            extreme += int(np.count_nonzero(sims <= obs + 1e-15))
        else:
            extreme += int(np.count_nonzero(np.abs(sims) >= abs(obs) - 1e-15))

        done += b

    p_perm = (extreme + 1) / (permutations + 1)

    return {
        "n": n,
        "rho": float(rho),
        "p_perm_one_sided": float(p_perm),
        "p_scipy_two_sided": float(p2),
    }


def describe_x(sub, xcol):
    vc = sub[xcol].value_counts().sort_index()
    return "; ".join(f"{int(k)}:{int(v)}" for k, v in vc.items())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ranking", required=True)
    ap.add_argument("--elo", required=True)
    ap.add_argument("--permutations", type=int, default=200000)
    ap.add_argument("--seed", type=int, default=20260926)
    ap.add_argument("--prefix", default="conditional_perf")
    args = ap.parse_args()

    rank = pd.read_csv(args.ranking, encoding="utf-8-sig")
    elo = pd.read_csv(args.elo, encoding="utf-8-sig")

    required_rank = [
        "qid", "name", "year_pillar", "month_pillar", "day_pillar", "highest_rank"
    ]
    missing = [c for c in required_rank if c not in rank.columns]
    if missing:
        raise SystemExit(f"Ranking file missing columns: {missing}")

    rank = add_bazi_features(rank)
    rank["highest_rank"] = pd.to_numeric(rank["highest_rank"], errors="coerce")

    # Merge Elo by QID. Use gender-standardized peak Elo.
    need_elo = ["qid", "peak_elo_gender_z", "internal_matches"]
    missing = [c for c in need_elo if c not in elo.columns]
    if missing:
        raise SystemExit(f"Elo file missing columns: {missing}")

    elo2 = elo[need_elo].copy()
    elo2["peak_elo_gender_z"] = pd.to_numeric(
        elo2["peak_elo_gender_z"], errors="coerce"
    )
    elo2["internal_matches"] = pd.to_numeric(
        elo2["internal_matches"], errors="coerce"
    )

    df = rank.merge(elo2, on="qid", how="left")
    # Match the original dynamic-Elo definition: require >=10 internal matches.
    df.loc[df["internal_matches"] < 10, "peak_elo_gender_z"] = np.nan

    # Save player-level audit file.
    audit_cols = [
        "qid", "name", "day_master",
        "year_branch", "month_branch", "day_branch",
        "xin_partial_seal_count", "xin_direct_seal_count",
        "earth_root_count", "earth_robwealth_count",
        "highest_rank", "peak_elo_gender_z", "internal_matches",
    ]
    df[audit_cols].to_csv(
        f"{args.prefix}_player_audit.csv",
        index=False,
        encoding="utf-8-sig",
    )

    tests = [
        {
            "test_id": "H1",
            "subgroup": "辛",
            "x": "xin_partial_seal_count",
            "y": "peak_elo_gender_z",
            "expected_direction": "positive",
            "alternative": "greater",
            "interpretation": "辛金偏印越多 -> Elo越高",
        },
        {
            "test_id": "H2",
            "subgroup": "辛",
            "x": "xin_partial_seal_count",
            "y": "highest_rank",
            "expected_direction": "negative",
            "alternative": "less",
            "interpretation": "辛金偏印越多 -> official rank越小",
        },
        {
            "test_id": "H3",
            "subgroup": "土",
            "x": "earth_root_count",
            "y": "peak_elo_gender_z",
            "expected_direction": "positive",
            "alternative": "greater",
            "interpretation": "土日主土根越多 -> Elo越高",
        },
        {
            "test_id": "H4",
            "subgroup": "土",
            "x": "earth_root_count",
            "y": "highest_rank",
            "expected_direction": "negative",
            "alternative": "less",
            "interpretation": "土日主土根越多 -> official rank越小",
        },
    ]

    rng = np.random.default_rng(args.seed)
    rows = []

    for t in tests:
        if t["subgroup"] == "辛":
            sub = df[df["day_master"] == "辛"].copy()
        else:
            sub = df[df["day_master"].isin(["戊", "己"])].copy()

        x = pd.to_numeric(sub[t["x"]], errors="coerce")
        y = pd.to_numeric(sub[t["y"]], errors="coerce")
        ok = x.notna() & y.notna()

        res = spearman_perm(
            x[ok].to_numpy(),
            y[ok].to_numpy(),
            t["alternative"],
            args.permutations,
            rng,
        )

        rows.append({
            "test_id": t["test_id"],
            "subgroup": t["subgroup"],
            "x": t["x"],
            "y": t["y"],
            "expected_direction": t["expected_direction"],
            "n": res["n"],
            "rho_spearman": res["rho"],
            "p_perm_one_sided": res["p_perm_one_sided"],
            "p_scipy_two_sided": res["p_scipy_two_sided"],
            "x_distribution_count:value": describe_x(sub.loc[ok], t["x"]),
            "interpretation": t["interpretation"],
            "permutations": args.permutations,
        })

    out = pd.DataFrame(rows)
    out.to_csv(
        f"{args.prefix}_locked_tests.csv",
        index=False,
        encoding="utf-8-sig",
    )

    print("\nLOCKED TRAINING-SET TESTS")
    print(out.to_string(index=False))
    print("\nSaved:")
    print(f"  {args.prefix}_locked_tests.csv")
    print(f"  {args.prefix}_player_audit.csv")


if __name__ == "__main__":
    main()
