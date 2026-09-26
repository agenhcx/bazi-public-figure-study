#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
earth_branch_by_daymaster.py

Targeted follow-up to the table-tennis BaZi study.

Question
--------
Among 土日主 (戊/己) and 金日主 (庚/辛), are 辰戌丑未 / 土本气 branches
unusually common or unusual in TYPE, after conditioning on the observed
day-master stem and Gregorian birth year?

This is the correct targeted test for the proposed mechanism:
    土日主: 辰戌丑未本气土 -> 比劫 / 根
    金日主: 辰戌丑未本气土 -> 印

Why condition on exact day-master STEM?
---------------------------------------
The current sample has different 戊/己 and 庚/辛 counts.
Exact stem matters for 比肩/劫财 and 正印/偏印 polarity.
Therefore the null preserves, for EACH real player:
    - Gregorian birth year
    - exact day-master stem (戊 / 己 / 庚 / 辛)

and randomizes only the calendar date among dates in that year that have
the SAME day-master stem.

This avoids diluting the question by averaging over all five day-master
elements.

Known-data limitation
---------------------
Birth time is unavailable, so this script uses only the three known branches:
    年支, 月支, 日支
No 时支 is invented.

Metrics
-------
For each subgroup (土日主, 金日主, and 戊/己/庚/辛 separately):

1) Overall 土本气 branch share among year/month/day branches.
2) Position-specific:
       year branch is 土本气
       month branch is 土本气
       day branch is 土本气
3) Month-weighted 土本气 share for w = 1, 1.5, 2, 3 by default.
4) Exact storage-branch counts:
       辰, 戌, 丑, 未
5) Main-qi stem type:
       戊-main (辰/戌)
       己-main (丑/未)
6) Wet/dry traditional grouping:
       湿土 = 辰/丑
       燥土 = 戌/未
7) Exact ten-god relation among 土本气 branches:
       土日主: 比肩 / 劫财
       金日主: 正印 / 偏印
8) Known-three-branch storage clashes:
       辰戌俱见
       丑未俱见
       任一四库冲 pair
9) Direct 土日主 vs 金日主 difference for selected metrics.

The null automatically accounts for the fact that four of twelve branch
main-qi elements are 土.

Dependencies
------------
pip install pandas numpy lunar-python

Run
---
python earth_branch_by_daymaster.py ^
    --input tabletennis_reference_enriched.csv ^
    --month-weights 1 1.5 2 3 ^
    --permutations 200000 ^
    --output-prefix earth_branch_dm

PowerShell:
python earth_branch_by_daymaster.py `
  --input tabletennis_reference_enriched.csv `
  --month-weights 1 1.5 2 3 `
  --permutations 200000 `
  --output-prefix earth_branch_dm
"""

import argparse
import calendar
import math
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from lunar_python import Solar
except Exception as e:
    raise SystemExit(
        "Install lunar-python first:\n"
        "  pip install lunar-python\n"
        f"Original error: {e}"
    )


GAN_ELEMENT = {
    "甲": "木", "乙": "木",
    "丙": "火", "丁": "火",
    "戊": "土", "己": "土",
    "庚": "金", "辛": "金",
    "壬": "水", "癸": "水",
}

GAN_POLARITY = {
    "甲": "阳", "乙": "阴",
    "丙": "阳", "丁": "阴",
    "戊": "阳", "己": "阴",
    "庚": "阳", "辛": "阴",
    "壬": "阳", "癸": "阴",
}

BRANCH_MAIN_GAN = {
    "子": "癸",
    "丑": "己",
    "寅": "甲",
    "卯": "乙",
    "辰": "戊",
    "巳": "丙",
    "午": "丁",
    "未": "己",
    "申": "庚",
    "酉": "辛",
    "戌": "戊",
    "亥": "壬",
}

EARTH_BRANCHES = set("辰戌丑未")
WET_EARTH = set("辰丑")
DRY_EARTH = set("戌未")
WU_MAIN_BRANCHES = set("辰戌")
JI_MAIN_BRANCHES = set("丑未")
TARGET_STEMS = set("戊己庚辛")


def weight_tag(w):
    return f"{float(w):g}".replace(".", "p")


def exact_tengod(day_gan, target_gan):
    """
    Only needed here for same-element (比劫) and resource (印) relationships,
    but implement explicitly for the target stems.
    """
    de = GAN_ELEMENT[day_gan]
    te = GAN_ELEMENT[target_gan]
    same_pol = GAN_POLARITY[day_gan] == GAN_POLARITY[target_gan]

    if de == te:
        return "比肩" if same_pol else "劫财"

    # For 金 day masters, 土 generates 金 => 印.
    if de == "金" and te == "土":
        return "偏印" if same_pol else "正印"

    return ""


def parse_three_pillars(year_pillar, month_pillar, day_pillar):
    yp = str(year_pillar).strip()
    mp = str(month_pillar).strip()
    dp = str(day_pillar).strip()

    if min(len(yp), len(mp), len(dp)) < 2:
        raise ValueError("Invalid pillar string.")

    return {
        "year_zhi": yp[1],
        "month_zhi": mp[1],
        "day_zhi": dp[1],
        "day_gan": dp[0],
    }


def date_chart_features(y, m, d):
    solar = Solar.fromYmdHms(
        int(y), int(m), int(d),
        12, 0, 0
    )
    ec = solar.getLunar().getEightChar()

    return parse_three_pillars(
        ec.getYear(),
        ec.getMonth(),
        ec.getDay(),
    )


def player_metrics(chart, weights):
    dg = chart["day_gan"]

    z = {
        "year": chart["year_zhi"],
        "month": chart["month_zhi"],
        "day": chart["day_zhi"],
    }

    out = {}

    # Basic position-specific indicators.
    for pos in ["year", "month", "day"]:
        out[f"{pos}_earth_branch"] = float(z[pos] in EARTH_BRANCHES)

    earth_count = sum(
        z[pos] in EARTH_BRANCHES
        for pos in ["year", "month", "day"]
    )

    out["earth_branch_count"] = float(earth_count)
    out["earth_branch_share"] = float(earth_count / 3.0)

    # Exact branch types.
    for b in ["辰", "戌", "丑", "未"]:
        out[f"branch_count_{b}"] = float(
            sum(
                z[pos] == b
                for pos in ["year", "month", "day"]
            )
        )

    # Main-qi type.
    out["earth_main_wu_count"] = float(
        sum(
            z[pos] in WU_MAIN_BRANCHES
            for pos in ["year", "month", "day"]
        )
    )
    out["earth_main_ji_count"] = float(
        sum(
            z[pos] in JI_MAIN_BRANCHES
            for pos in ["year", "month", "day"]
        )
    )

    # Wet / dry.
    out["wet_earth_count"] = float(
        sum(
            z[pos] in WET_EARTH
            for pos in ["year", "month", "day"]
        )
    )
    out["dry_earth_count"] = float(
        sum(
            z[pos] in DRY_EARTH
            for pos in ["year", "month", "day"]
        )
    )

    # Exact ten-god type among Earth-main branches.
    rel_counts = Counter()

    for pos in ["year", "month", "day"]:
        b = z[pos]

        if b in EARTH_BRANCHES:
            tg = exact_tengod(
                dg,
                BRANCH_MAIN_GAN[b],
            )
            if tg:
                rel_counts[tg] += 1

    for tg in ["比肩", "劫财", "正印", "偏印"]:
        out[f"earth_branch_{tg}_count"] = float(
            rel_counts[tg]
        )

    # Storage clash pairs among the known three branches.
    branches_present = set(z.values())

    out["has_辰戌_pair"] = float(
        "辰" in branches_present
        and "戌" in branches_present
    )
    out["has_丑未_pair"] = float(
        "丑" in branches_present
        and "未" in branches_present
    )
    out["has_any_storage_clash_pair"] = float(
        out["has_辰戌_pair"] > 0
        or out["has_丑未_pair"] > 0
    )

    # Tunable month weight.
    for w in weights:
        tag = weight_tag(w)
        numerator = (
            float(z["year"] in EARTH_BRANCHES)
            + float(w) * float(z["month"] in EARTH_BRANCHES)
            + float(z["day"] in EARTH_BRANCHES)
        )
        denominator = 2.0 + float(w)

        out[f"earth_branch_share_w{tag}"] = (
            numerator / denominator
        )

    return out


def load_actual(path, weights):
    df = pd.read_csv(
        path,
        encoding="utf-8-sig",
    )

    need = [
        "name",
        "dob",
        "birth_year",
        "year_pillar",
        "month_pillar",
        "day_pillar",
    ]

    missing = [c for c in need if c not in df.columns]
    if missing:
        raise SystemExit(
            f"Missing input columns: {missing}"
        )

    rows = []

    for _, r in df.iterrows():
        chart = parse_three_pillars(
            r["year_pillar"],
            r["month_pillar"],
            r["day_pillar"],
        )

        dg = chart["day_gan"]

        if dg not in TARGET_STEMS:
            continue

        m = player_metrics(
            chart,
            weights,
        )

        m.update({
            "name": r["name"],
            "dob": r["dob"],
            "birth_year": int(r["birth_year"]),
            "day_master": dg,
            "day_master_element": GAN_ELEMENT[dg],
            "year_branch": chart["year_zhi"],
            "month_branch": chart["month_zhi"],
            "day_branch": chart["day_zhi"],
        })

        if "qid" in df.columns:
            m["qid"] = r["qid"]

        rows.append(m)

    return pd.DataFrame(rows)


def metric_list(weights):
    out = [
        "year_earth_branch",
        "month_earth_branch",
        "day_earth_branch",
        "earth_branch_count",
        "earth_branch_share",
        "branch_count_辰",
        "branch_count_戌",
        "branch_count_丑",
        "branch_count_未",
        "earth_main_wu_count",
        "earth_main_ji_count",
        "wet_earth_count",
        "dry_earth_count",
        "earth_branch_比肩_count",
        "earth_branch_劫财_count",
        "earth_branch_正印_count",
        "earth_branch_偏印_count",
        "has_辰戌_pair",
        "has_丑未_pair",
        "has_any_storage_clash_pair",
    ]

    for w in weights:
        out.append(
            f"earth_branch_share_w{weight_tag(w)}"
        )

    return out


def calendar_rows_for_year(year, weights):
    y = int(year)
    n = 366 if calendar.isleap(y) else 365
    start = pd.Timestamp(
        year=y,
        month=1,
        day=1,
    )

    rows = []

    for i in range(n):
        dt = (
            start
            + pd.Timedelta(days=i)
        )

        chart = date_chart_features(
            dt.year,
            dt.month,
            dt.day,
        )

        dg = chart["day_gan"]

        if dg not in TARGET_STEMS:
            continue

        m = player_metrics(
            chart,
            weights,
        )

        m.update({
            "birth_year": y,
            "dob": dt.strftime("%Y-%m-%d"),
            "day_master": dg,
            "day_master_element": GAN_ELEMENT[dg],
        })

        rows.append(m)

    return rows


def build_cache(
    years,
    weights,
    cache_path,
    rebuild=False,
):
    cache_path = Path(cache_path)

    if rebuild and cache_path.exists():
        cache_path.unlink()

    sig = ",".join(
        f"{float(w):g}"
        for w in weights
    )

    if cache_path.exists():
        old = pd.read_csv(
            cache_path,
            encoding="utf-8-sig",
        )

        if (
            "weights_signature" in old.columns
            and set(
                old["weights_signature"]
                .astype(str)
                .unique()
            ) == {sig}
        ):
            have = set(
                old["birth_year"]
                .astype(int)
                .unique()
            )
            need = set(
                int(x)
                for x in years
            )

            if need.issubset(have):
                print(
                    f"Loaded reusable cache: "
                    f"{cache_path} "
                    f"({len(old):,} rows)"
                )
                return old[
                    old["birth_year"]
                    .astype(int)
                    .isin(need)
                ].copy()

    rows = []

    ys = sorted(
        set(int(x) for x in years)
    )

    for pos, y in enumerate(ys, 1):
        print(
            f"[{pos:02d}/{len(ys):02d}] "
            f"calendar year {y}"
        )

        yr = calendar_rows_for_year(
            y,
            weights,
        )

        for r in yr:
            r["weights_signature"] = sig

        rows.extend(yr)

        pd.DataFrame(
            rows
        ).to_csv(
            cache_path,
            index=False,
            encoding="utf-8-sig",
        )

    return pd.DataFrame(rows)


def subgroup_name(row):
    return row["day_master_element"]


def make_observed_summary(actual, metrics):
    rows = []

    subgroups = {
        "土日主": actual[
            actual["day_master_element"] == "土"
        ],
        "金日主": actual[
            actual["day_master_element"] == "金"
        ],
        "戊": actual[
            actual["day_master"] == "戊"
        ],
        "己": actual[
            actual["day_master"] == "己"
        ],
        "庚": actual[
            actual["day_master"] == "庚"
        ],
        "辛": actual[
            actual["day_master"] == "辛"
        ],
    }

    for name, g in subgroups.items():
        for metric in metrics:
            x = g[metric].astype(float)

            rows.append({
                "subgroup": name,
                "metric": metric,
                "n_players": len(g),
                "observed_sum": float(x.sum()),
                "observed_mean": float(x.mean()),
                "observed_sd": float(
                    x.std(ddof=1)
                ) if len(g) > 1 else np.nan,
            })

    return pd.DataFrame(rows)


def build_candidate_arrays(
    cache,
    metrics,
):
    """
    Keyed by (birth_year, exact day-master stem).
    """
    out = {}

    for (y, g), x in cache.groupby(
        ["birth_year", "day_master"],
        sort=True,
    ):
        out[
            (int(y), str(g))
        ] = x[
            metrics
        ].astype(float).to_numpy()

    return out


def actual_groups(actual):
    """
    For simulation efficiency: count real players by exact
    (birth_year, day-master stem).
    """
    counts = (
        actual.groupby(
            ["birth_year", "day_master"]
        )
        .size()
    )

    return {
        (int(y), str(g)): int(n)
        for (y, g), n in counts.items()
    }


def exact_expected_by_subgroup(
    actual,
    arrays,
    metrics,
):
    """
    Exact calendar expectation, preserving each real player's
    year + exact day-master stem.
    """
    k = len(metrics)

    sums = {
        "土日主": np.zeros(k),
        "金日主": np.zeros(k),
        "戊": np.zeros(k),
        "己": np.zeros(k),
        "庚": np.zeros(k),
        "辛": np.zeros(k),
    }

    n = {
        "土日主": 0,
        "金日主": 0,
        "戊": 0,
        "己": 0,
        "庚": 0,
        "辛": 0,
    }

    for _, r in actual.iterrows():
        key = (
            int(r["birth_year"]),
            str(r["day_master"]),
        )

        a = arrays[key]
        mu = a.mean(axis=0)

        stem = str(r["day_master"])
        elem_group = (
            "土日主"
            if r["day_master_element"] == "土"
            else "金日主"
        )

        sums[stem] += mu
        sums[elem_group] += mu

        n[stem] += 1
        n[elem_group] += 1

    return sums, n


def observed_sums_by_subgroup(
    actual,
    metrics,
):
    k = len(metrics)

    out = {}

    masks = {
        "土日主": (
            actual["day_master_element"] == "土"
        ),
        "金日主": (
            actual["day_master_element"] == "金"
        ),
        "戊": (
            actual["day_master"] == "戊"
        ),
        "己": (
            actual["day_master"] == "己"
        ),
        "庚": (
            actual["day_master"] == "庚"
        ),
        "辛": (
            actual["day_master"] == "辛"
        ),
    }

    for name, mask in masks.items():
        out[name] = (
            actual.loc[
                mask,
                metrics,
            ]
            .astype(float)
            .sum(axis=0)
            .to_numpy()
        )

    return out


def simulate(
    actual,
    arrays,
    metrics,
    observed_sums,
    expected_sums,
    permutations,
    batch_size,
    seed,
):
    rng = np.random.default_rng(seed)
    k = len(metrics)

    stem_to_elemgroup = {
        "戊": "土日主",
        "己": "土日主",
        "庚": "金日主",
        "辛": "金日主",
    }

    groups = [
        "土日主",
        "金日主",
        "戊",
        "己",
        "庚",
        "辛",
    ]

    acc_sum = {
        g: np.zeros(k)
        for g in groups
    }
    acc_sq = {
        g: np.zeros(k)
        for g in groups
    }
    ge = {
        g: np.zeros(k, dtype=np.int64)
        for g in groups
    }
    le = {
        g: np.zeros(k, dtype=np.int64)
        for g in groups
    }
    abs_ge = {
        g: np.zeros(k, dtype=np.int64)
        for g in groups
    }

    # For direct 土-vs-金 difference in subgroup MEANS.
    diff_metrics = [
        "earth_branch_share",
        "month_earth_branch",
    ] + [
        m for m in metrics
        if m.startswith("earth_branch_share_w")
    ]

    diff_idx = [
        metrics.index(m)
        for m in diff_metrics
    ]

    obs_n = {
        "土日主": int(
            (actual["day_master_element"] == "土").sum()
        ),
        "金日主": int(
            (actual["day_master_element"] == "金").sum()
        ),
    }

    obs_diff = (
        observed_sums["土日主"][diff_idx]
        / obs_n["土日主"]
        - observed_sums["金日主"][diff_idx]
        / obs_n["金日主"]
    )

    exp_diff = (
        expected_sums["土日主"][diff_idx]
        / obs_n["土日主"]
        - expected_sums["金日主"][diff_idx]
        / obs_n["金日主"]
    )

    diff_sum = np.zeros(len(diff_idx))
    diff_sq = np.zeros(len(diff_idx))
    diff_ge = np.zeros(
        len(diff_idx),
        dtype=np.int64,
    )
    diff_abs_ge = np.zeros(
        len(diff_idx),
        dtype=np.int64,
    )

    counts = actual_groups(actual)

    done = 0

    while done < permutations:
        b = min(
            batch_size,
            permutations - done,
        )

        sim = {
            g: np.zeros(
                (b, k),
                dtype=float,
            )
            for g in groups
        }

        for (year, stem), n_players in counts.items():
            a = arrays[
                (year, stem)
            ]

            idx = rng.integers(
                0,
                len(a),
                size=(b, n_players),
            )

            contribution = (
                a[idx]
                .sum(axis=1)
            )

            sim[stem] += contribution
            sim[
                stem_to_elemgroup[stem]
            ] += contribution

        for g in groups:
            x = sim[g]

            acc_sum[g] += x.sum(axis=0)
            acc_sq[g] += np.square(
                x
            ).sum(axis=0)

            ge[g] += np.count_nonzero(
                x
                >= (
                    observed_sums[g]
                    - 1e-12
                ),
                axis=0,
            )

            le[g] += np.count_nonzero(
                x
                <= (
                    observed_sums[g]
                    + 1e-12
                ),
                axis=0,
            )

            abs_ge[g] += np.count_nonzero(
                np.abs(
                    x
                    - expected_sums[g]
                )
                >= (
                    np.abs(
                        observed_sums[g]
                        - expected_sums[g]
                    )
                    - 1e-12
                ),
                axis=0,
            )

        # Direct difference in means.
        d = (
            sim["土日主"][:, diff_idx]
            / obs_n["土日主"]
            - sim["金日主"][:, diff_idx]
            / obs_n["金日主"]
        )

        diff_sum += d.sum(axis=0)
        diff_sq += np.square(
            d
        ).sum(axis=0)

        diff_ge += np.count_nonzero(
            d
            >= (
                obs_diff
                - 1e-12
            ),
            axis=0,
        )

        diff_abs_ge += np.count_nonzero(
            np.abs(
                d - exp_diff
            )
            >= (
                np.abs(
                    obs_diff - exp_diff
                )
                - 1e-12
            ),
            axis=0,
        )

        done += b

        if (
            done == permutations
            or done % (
                batch_size * 5
            ) == 0
        ):
            print(
                f"Permutation progress: "
                f"{done:,}/{permutations:,}"
            )

    rows = []

    for g in groups:
        mean = (
            acc_sum[g]
            / permutations
        )
        var = (
            acc_sq[g]
            / permutations
            - mean ** 2
        )
        sd = np.sqrt(
            np.maximum(
                var,
                0.0,
            )
        )

        n_g = (
            obs_n[g]
            if g in obs_n
            else int(
                (actual["day_master"] == g).sum()
            )
        )

        for j, metric in enumerate(metrics):
            z = (
                (
                    observed_sums[g][j]
                    - expected_sums[g][j]
                )
                / sd[j]
                if sd[j] > 0
                else np.nan
            )

            rows.append({
                "analysis": "within_subgroup",
                "subgroup": g,
                "metric": metric,
                "n_players": n_g,
                "observed_sum": float(
                    observed_sums[g][j]
                ),
                "observed_mean": float(
                    observed_sums[g][j]
                    / n_g
                ),
                "exact_calendar_expected_sum": float(
                    expected_sums[g][j]
                ),
                "calendar_expected_mean": float(
                    expected_sums[g][j]
                    / n_g
                ),
                "observed_minus_expected": float(
                    observed_sums[g][j]
                    - expected_sums[g][j]
                ),
                "z_vs_conditional_null": float(z),
                "p_one_sided_enrichment": float(
                    (ge[g][j] + 1)
                    / (permutations + 1)
                ),
                "p_one_sided_depletion": float(
                    (le[g][j] + 1)
                    / (permutations + 1)
                ),
                "p_two_sided": float(
                    (abs_ge[g][j] + 1)
                    / (permutations + 1)
                ),
                "permutations": permutations,
            })

    diff_mean = (
        diff_sum
        / permutations
    )
    diff_var = (
        diff_sq
        / permutations
        - diff_mean ** 2
    )
    diff_sd = np.sqrt(
        np.maximum(
            diff_var,
            0.0,
        )
    )

    for q, metric in enumerate(diff_metrics):
        z = (
            (
                obs_diff[q]
                - exp_diff[q]
            )
            / diff_sd[q]
            if diff_sd[q] > 0
            else np.nan
        )

        rows.append({
            "analysis": "earth_minus_metal_direct_difference",
            "subgroup": "土日主 - 金日主",
            "metric": metric,
            "n_players": (
                obs_n["土日主"]
                + obs_n["金日主"]
            ),
            "observed_sum": np.nan,
            "observed_mean": float(
                obs_diff[q]
            ),
            "exact_calendar_expected_sum": np.nan,
            "calendar_expected_mean": float(
                exp_diff[q]
            ),
            "observed_minus_expected": float(
                obs_diff[q]
                - exp_diff[q]
            ),
            "z_vs_conditional_null": float(z),
            "p_one_sided_enrichment": float(
                (diff_ge[q] + 1)
                / (permutations + 1)
            ),
            "p_one_sided_depletion": np.nan,
            "p_two_sided": float(
                (diff_abs_ge[q] + 1)
                / (permutations + 1)
            ),
            "permutations": permutations,
        })

    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()

    ap.add_argument(
        "--input",
        required=True,
    )

    ap.add_argument(
        "--month-weights",
        nargs="+",
        type=float,
        default=[
            1.0,
            1.5,
            2.0,
            3.0,
        ],
    )

    ap.add_argument(
        "--permutations",
        type=int,
        default=200000,
    )

    ap.add_argument(
        "--batch-size",
        type=int,
        default=5000,
    )

    ap.add_argument(
        "--seed",
        type=int,
        default=20260926,
    )

    ap.add_argument(
        "--output-prefix",
        default="earth_branch_dm",
    )

    ap.add_argument(
        "--calendar-cache",
        default=None,
    )

    ap.add_argument(
        "--rebuild-cache",
        action="store_true",
    )

    args = ap.parse_args()

    weights = sorted(
        set(
            float(w)
            for w in args.month_weights
        )
    )

    prefix = args.output_prefix

    cache_path = (
        args.calendar_cache
        if args.calendar_cache
        else (
            f"{prefix}"
            "_conditional_calendar_cache.csv"
        )
    )

    actual = load_actual(
        args.input,
        weights,
    )

    print()
    print(
        f"Target players: {len(actual)} "
        f"(土日主="
        f"{(actual['day_master_element']=='土').sum()}, "
        f"金日主="
        f"{(actual['day_master_element']=='金').sum()})"
    )

    print(
        "Exact stems: "
        + ", ".join(
            f"{g}={int((actual['day_master']==g).sum())}"
            for g in ["戊", "己", "庚", "辛"]
        )
    )

    metrics = metric_list(
        weights
    )

    observed_summary = (
        make_observed_summary(
            actual,
            metrics,
        )
    )

    observed_summary.to_csv(
        f"{prefix}_observed_summary.csv",
        index=False,
        encoding="utf-8-sig",
    )

    actual.to_csv(
        f"{prefix}_player_features.csv",
        index=False,
        encoding="utf-8-sig",
    )

    cache = build_cache(
        actual["birth_year"]
        .astype(int)
        .unique(),
        weights,
        cache_path,
        rebuild=args.rebuild_cache,
    )

    arrays = build_candidate_arrays(
        cache,
        metrics,
    )

    # Verify every real year+stem has candidates.
    missing = []

    for _, r in actual.iterrows():
        key = (
            int(r["birth_year"]),
            str(r["day_master"]),
        )

        if key not in arrays:
            missing.append(key)

    if missing:
        raise RuntimeError(
            "Missing conditional-null candidate groups: "
            + str(
                sorted(set(missing))
            )
        )

    obs_sums = (
        observed_sums_by_subgroup(
            actual,
            metrics,
        )
    )

    exp_sums, subgroup_ns = (
        exact_expected_by_subgroup(
            actual,
            arrays,
            metrics,
        )
    )

    print()
    print(
        f"Running {args.permutations:,} "
        f"conditional calendar permutations..."
    )

    tests = simulate(
        actual,
        arrays,
        metrics,
        obs_sums,
        exp_sums,
        permutations=args.permutations,
        batch_size=args.batch_size,
        seed=args.seed,
    )

    tests.to_csv(
        f"{prefix}_conditional_null_tests.csv",
        index=False,
        encoding="utf-8-sig",
    )

    print()
    print("=" * 100)
    print("KEY RESULTS")
    print("=" * 100)

    key_metrics = [
        "earth_branch_share",
        "year_earth_branch",
        "month_earth_branch",
        "day_earth_branch",
        "branch_count_辰",
        "branch_count_戌",
        "branch_count_丑",
        "branch_count_未",
        "earth_main_wu_count",
        "earth_main_ji_count",
        "wet_earth_count",
        "dry_earth_count",
        "earth_branch_比肩_count",
        "earth_branch_劫财_count",
        "earth_branch_正印_count",
        "earth_branch_偏印_count",
        "has_any_storage_clash_pair",
    ] + [
        f"earth_branch_share_w{weight_tag(w)}"
        for w in weights
    ]

    show = tests[
        (
            tests["subgroup"]
            .isin(
                [
                    "土日主",
                    "金日主",
                    "土日主 - 金日主",
                ]
            )
        )
        & (
            tests["metric"]
            .isin(key_metrics)
        )
    ][
        [
            "analysis",
            "subgroup",
            "metric",
            "n_players",
            "observed_mean",
            "calendar_expected_mean",
            "observed_minus_expected",
            "z_vs_conditional_null",
            "p_one_sided_enrichment",
            "p_one_sided_depletion",
            "p_two_sided",
        ]
    ]

    print(
        show.to_string(
            index=False,
            float_format=lambda x: f"{x:.6f}",
        )
    )

    print()
    print("Saved:")
    for fn in [
        f"{prefix}_player_features.csv",
        f"{prefix}_observed_summary.csv",
        f"{prefix}_conditional_null_tests.csv",
        cache_path,
    ]:
        print(f"  {fn}")


if __name__ == "__main__":
    main()
