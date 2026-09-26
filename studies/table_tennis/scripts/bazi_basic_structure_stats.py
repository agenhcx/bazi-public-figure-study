#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
bazi_basic_structure_stats.py

Basic, low-assumption BaZi structure statistics for the table-tennis cohort.

PRIMARY GOAL
------------
Step back from specific 十神 stories and first measure the most mechanical
features of the available charts.

IMPORTANT DATA LIMITATION
-------------------------
The table-tennis DOB dataset has dates but not reliable birth times.
Therefore the PRIMARY analysis uses only the three known pillars:

    年柱 + 月柱 + 日柱

That is 6 known characters, not a claimed full 8-character chart.

The script DOES NOT invent a 时柱.

WHAT IT TESTS
-------------
A) Day-master distribution
   - all 10 heavenly stems separately:
       甲 乙 丙 丁 戊 己 庚 辛 壬 癸
   - 5-element aggregation:
       木 火 土 金 水
   - within-element yin/yang pairs:
       甲 vs 乙
       丙 vs 丁
       戊 vs 己
       庚 vs 辛
       壬 vs 癸
   - explicit 土 vs 金 contrast

B) Raw element composition of the known 3 pillars
   Count:
       year stem
       month stem
       day stem
       year branch main qi
       month branch main qi
       day branch main qi

   Month-order (月令 = month branch main qi) weight is adjustable.

   Default sensitivity grid:
       1, 1.5, 2, 3

   Example:
       --month-weights 1 1.5 2 3

C) Branch-main-qi relation to the day master
   For each of the three known branches, classify the MAIN QI as:
       比劫 / 印 / 食伤 / 财 / 官杀

   Again, month branch can be weighted.

   This directly tests ideas such as:
       - are athletes high in "root" / 比劫-supporting branches?
       - are they low/high in 印?
       - does the result survive changing 月令 weight?

D) Calendar-matched null
   The naive baseline is NOT assumed to be exactly 10%/20%.

   For each real player, preserve Gregorian birth year and randomize the
   birthday uniformly within that same Gregorian year.

   This automatically preserves:
       - leap years
       - 立春 year-pillar transitions
       - monthly pillar structure
       - day-stem cycling
       - four-storage-branch asymmetries (辰戌丑未)
       - any structural dependence between day master and branch main qi

   Birth sex is irrelevant for these static 3-pillar features, so it is not
   used in the null.

HOLDOUT NOTE
------------
The currently observed 土 > 金 pattern was noticed AFTER looking at the
384-player cohort, so this sample is hypothesis-generating for that contrast.

Use the same code unchanged on future, non-overlapping players for a true
holdout replication.

DEPENDENCIES
------------
pip install pandas numpy scipy lunar-python

RECOMMENDED RUN
---------------
python bazi_basic_structure_stats.py ^
    --input tabletennis_reference_enriched.csv ^
    --month-weights 1 1.5 2 3 ^
    --permutations 200000 ^
    --output-prefix bazi_basic

PowerShell multiline:
python bazi_basic_structure_stats.py `
  --input tabletennis_reference_enriched.csv `
  --month-weights 1 1.5 2 3 `
  --permutations 200000 `
  --output-prefix bazi_basic

OUTPUTS
-------
< prefix >_daymaster_10stem.csv
< prefix >_daymaster_5element.csv
< prefix >_daymaster_pair_tests.csv
< prefix >_player_features.csv
< prefix >_structure_summary.csv
< prefix >_calendar_null_tests.csv
< prefix >_calendar_date_cache.csv

The cache is resumable/reusable for the same year range and weight list.
"""

import argparse
import calendar
import math
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from scipy.stats import binomtest, chisquare
except Exception as e:
    raise SystemExit(
        "scipy is required.\n"
        "Install with: pip install scipy\n"
        f"Original error: {e}"
    )

try:
    from lunar_python import Solar
except Exception as e:
    raise SystemExit(
        "lunar-python is required.\n"
        "Install with: pip install lunar-python\n"
        f"Original error: {e}"
    )


GAN_ORDER = list("甲乙丙丁戊己庚辛壬癸")
ELEMENT_ORDER = ["木", "火", "土", "金", "水"]
REL5_ORDER = ["比劫", "印", "食伤", "财", "官杀"]

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

GENERATES = {
    "木": "火",
    "火": "土",
    "土": "金",
    "金": "水",
    "水": "木",
}

CONTROLS = {
    "木": "土",
    "土": "水",
    "水": "火",
    "火": "金",
    "金": "木",
}

PAIR_ORDER = [
    ("木", "甲", "乙"),
    ("火", "丙", "丁"),
    ("土", "戊", "己"),
    ("金", "庚", "辛"),
    ("水", "壬", "癸"),
]


def weight_tag(w):
    s = f"{float(w):g}"
    return s.replace(".", "p")


def pillar_parts(p):
    p = str(p).strip()
    if len(p) < 2:
        raise ValueError(f"Invalid pillar: {p!r}")
    gan, zhi = p[0], p[1]
    if gan not in GAN_ELEMENT:
        raise ValueError(f"Invalid stem in pillar: {p!r}")
    if zhi not in BRANCH_MAIN_GAN:
        raise ValueError(f"Invalid branch in pillar: {p!r}")
    return gan, zhi


def relation5(day_gan, target_gan):
    """
    Five broad relation groups of target relative to day master.
    """
    de = GAN_ELEMENT[day_gan]
    te = GAN_ELEMENT[target_gan]

    if te == de:
        return "比劫"

    # target generates day => 印
    if GENERATES[te] == de:
        return "印"

    # day generates target => 食伤
    if GENERATES[de] == te:
        return "食伤"

    # day controls target => 财
    if CONTROLS[de] == te:
        return "财"

    # target controls day => 官杀
    if CONTROLS[te] == de:
        return "官杀"

    raise RuntimeError(
        f"Unclassified relation: day={day_gan}, target={target_gan}"
    )


def ten_god(day_gan, target_gan):
    """
    Exact ten-god label, useful for player-level auditing.
    """
    de = GAN_ELEMENT[day_gan]
    te = GAN_ELEMENT[target_gan]
    same_pol = GAN_POLARITY[day_gan] == GAN_POLARITY[target_gan]

    if te == de:
        return "比肩" if same_pol else "劫财"

    if GENERATES[te] == de:
        return "偏印" if same_pol else "正印"

    if GENERATES[de] == te:
        return "食神" if same_pol else "伤官"

    if CONTROLS[de] == te:
        return "偏财" if same_pol else "正财"

    if CONTROLS[te] == de:
        return "七杀" if same_pol else "正官"

    raise RuntimeError(
        f"Unclassified ten-god: day={day_gan}, target={target_gan}"
    )


def chart_from_pillars(year_pillar, month_pillar, day_pillar):
    yg, yz = pillar_parts(year_pillar)
    mg, mz = pillar_parts(month_pillar)
    dg, dz = pillar_parts(day_pillar)

    return {
        "year_gan": yg,
        "year_zhi": yz,
        "month_gan": mg,
        "month_zhi": mz,
        "day_gan": dg,
        "day_zhi": dz,
    }


def feature_dict(chart, weights):
    """
    Features from the three KNOWN pillars only.

    Element composition:
      year/month/day stems +
      year/month/day branch main qi.
      Month branch gets weight w.

    Branch relation composition:
      only branch main qi, relative to day master.
      Month branch gets weight w.
    """
    dg = chart["day_gan"]

    year_main = BRANCH_MAIN_GAN[chart["year_zhi"]]
    month_main = BRANCH_MAIN_GAN[chart["month_zhi"]]
    day_main = BRANCH_MAIN_GAN[chart["day_zhi"]]

    out = {
        "day_master": dg,
        "day_master_element": GAN_ELEMENT[dg],
        "year_branch_main_gan": year_main,
        "month_branch_main_gan": month_main,
        "day_branch_main_gan": day_main,
        "year_branch_main_tengod": ten_god(dg, year_main),
        "month_branch_main_tengod": ten_god(dg, month_main),
        "day_branch_main_tengod": ten_god(dg, day_main),
        "year_branch_relation5": relation5(dg, year_main),
        "month_branch_relation5": relation5(dg, month_main),
        "day_branch_relation5": relation5(dg, day_main),
    }

    stems = [
        chart["year_gan"],
        chart["month_gan"],
        chart["day_gan"],
    ]

    for w in weights:
        tag = weight_tag(w)

        elem_counts = {e: 0.0 for e in ELEMENT_ORDER}

        # Three known heavenly stems: each weight 1.
        for g in stems:
            elem_counts[GAN_ELEMENT[g]] += 1.0

        # Three branch main qi; 月令 gets tunable weight.
        elem_counts[GAN_ELEMENT[year_main]] += 1.0
        elem_counts[GAN_ELEMENT[month_main]] += float(w)
        elem_counts[GAN_ELEMENT[day_main]] += 1.0

        elem_total = 5.0 + float(w)

        for e in ELEMENT_ORDER:
            out[f"element_count_w{tag}_{e}"] = elem_counts[e]
            out[f"element_share_w{tag}_{e}"] = elem_counts[e] / elem_total

        # Branch-only relation composition.
        rel_counts = {r: 0.0 for r in REL5_ORDER}

        rel_counts[relation5(dg, year_main)] += 1.0
        rel_counts[relation5(dg, month_main)] += float(w)
        rel_counts[relation5(dg, day_main)] += 1.0

        rel_total = 2.0 + float(w)

        for r in REL5_ORDER:
            out[f"branch_rel_count_w{tag}_{r}"] = rel_counts[r]
            out[f"branch_rel_share_w{tag}_{r}"] = rel_counts[r] / rel_total

    return out


def load_actual(path, weights):
    df = pd.read_csv(path, encoding="utf-8-sig")

    required = [
        "name",
        "dob",
        "birth_year",
        "gender",
        "year_pillar",
        "month_pillar",
        "day_pillar",
    ]

    missing = [c for c in required if c not in df.columns]
    if missing:
        raise SystemExit(f"Missing required columns: {missing}")

    rows = []

    for i, r in df.iterrows():
        try:
            chart = chart_from_pillars(
                r["year_pillar"],
                r["month_pillar"],
                r["day_pillar"],
            )

            f = feature_dict(chart, weights)

            f.update({
                "name": r["name"],
                "dob": r["dob"],
                "birth_year": int(r["birth_year"]),
                "gender": r["gender"],
                "year_pillar": r["year_pillar"],
                "month_pillar": r["month_pillar"],
                "day_pillar": r["day_pillar"],
            })

            if "qid" in df.columns:
                f["qid"] = r["qid"]

            # Optional cross-check against existing month_main_stem column.
            if "month_main_stem" in df.columns:
                f["existing_month_main_stem"] = r["month_main_stem"]
                f["month_main_stem_matches"] = int(
                    str(r["month_main_stem"])
                    == str(f["month_branch_main_gan"])
                )

            rows.append(f)

        except Exception as e:
            raise RuntimeError(
                f"Failed row {i}, name={r.get('name')}, dob={r.get('dob')}: "
                f"{type(e).__name__}: {e}"
            ) from e

    out = pd.DataFrame(rows)

    if "month_main_stem_matches" in out.columns:
        bad = out[out["month_main_stem_matches"] != 1]
        if len(bad):
            raise RuntimeError(
                "month_main_stem cross-check failed for "
                f"{len(bad)} rows.\n"
                + bad[
                    [
                        "name",
                        "dob",
                        "month_pillar",
                        "existing_month_main_stem",
                        "month_branch_main_gan",
                    ]
                ].head(20).to_string(index=False)
            )

    return df, out


def daymaster_tables(player):
    n = len(player)

    stem_counts = (
        player["day_master"]
        .value_counts()
        .reindex(GAN_ORDER, fill_value=0)
    )

    stem_rows = []
    for g in GAN_ORDER:
        c = int(stem_counts[g])
        stem_rows.append({
            "day_master": g,
            "element": GAN_ELEMENT[g],
            "count": c,
            "rate": c / n,
            "naive_expected_rate": 0.10,
            "binom_p_enrichment_vs_10pct": binomtest(
                c, n, 0.10, alternative="greater"
            ).pvalue,
            "binom_p_depletion_vs_10pct": binomtest(
                c, n, 0.10, alternative="less"
            ).pvalue,
            "binom_p_two_sided_vs_10pct": binomtest(
                c, n, 0.10, alternative="two-sided"
            ).pvalue,
        })

    stem_df = pd.DataFrame(stem_rows)

    elem_counts = (
        player["day_master_element"]
        .value_counts()
        .reindex(ELEMENT_ORDER, fill_value=0)
    )

    elem_rows = []
    for e in ELEMENT_ORDER:
        c = int(elem_counts[e])
        elem_rows.append({
            "element": e,
            "count": c,
            "rate": c / n,
            "naive_expected_rate": 0.20,
            "binom_p_enrichment_vs_20pct": binomtest(
                c, n, 0.20, alternative="greater"
            ).pvalue,
            "binom_p_depletion_vs_20pct": binomtest(
                c, n, 0.20, alternative="less"
            ).pvalue,
            "binom_p_two_sided_vs_20pct": binomtest(
                c, n, 0.20, alternative="two-sided"
            ).pvalue,
        })

    elem_df = pd.DataFrame(elem_rows)

    pair_rows = []
    for e, g1, g2 in PAIR_ORDER:
        n1 = int(stem_counts[g1])
        n2 = int(stem_counts[g2])
        m = n1 + n2

        pair_rows.append({
            "element": e,
            "stem_1": g1,
            "stem_2": g2,
            "count_1": n1,
            "count_2": n2,
            "pair_total": m,
            "ratio_1_over_2": n1 / n2 if n2 else np.inf,
            "difference_1_minus_2": n1 - n2,
            "exact_binom_p_two_sided_50_50": (
                binomtest(
                    n1,
                    m,
                    0.5,
                    alternative="two-sided",
                ).pvalue
                if m else np.nan
            ),
        })

    pair_df = pd.DataFrame(pair_rows)

    # Add explicit Earth-vs-Metal row.
    earth = int(elem_counts["土"])
    metal = int(elem_counts["金"])
    em_total = earth + metal

    pair_df = pd.concat(
        [
            pair_df,
            pd.DataFrame([{
                "element": "土vs金",
                "stem_1": "土日主",
                "stem_2": "金日主",
                "count_1": earth,
                "count_2": metal,
                "pair_total": em_total,
                "ratio_1_over_2": earth / metal if metal else np.inf,
                "difference_1_minus_2": earth - metal,
                "exact_binom_p_two_sided_50_50": (
                    binomtest(
                        earth,
                        em_total,
                        0.5,
                        alternative="two-sided",
                    ).pvalue
                    if em_total else np.nan
                ),
                "exact_binom_p_one_sided_stem1_greater": (
                    binomtest(
                        earth,
                        em_total,
                        0.5,
                        alternative="greater",
                    ).pvalue
                    if em_total else np.nan
                ),
            }])
        ],
        ignore_index=True,
    )

    return stem_df, elem_df, pair_df


def structure_summary(player, weights):
    rows = []

    for w in weights:
        tag = weight_tag(w)

        for e in ELEMENT_ORDER:
            col = f"element_share_w{tag}_{e}"
            x = player[col].astype(float)

            rows.append({
                "family": "known_3pillar_element_share",
                "month_weight": float(w),
                "feature": e,
                "n": len(x),
                "mean": float(x.mean()),
                "sd": float(x.std(ddof=1)),
                "median": float(x.median()),
            })

        for rel in REL5_ORDER:
            col = f"branch_rel_share_w{tag}_{rel}"
            x = player[col].astype(float)

            rows.append({
                "family": "branch_main_qi_relation_share",
                "month_weight": float(w),
                "feature": rel,
                "n": len(x),
                "mean": float(x.mean()),
                "sd": float(x.std(ddof=1)),
                "median": float(x.median()),
            })

    return pd.DataFrame(rows)


def solar_chart(y, m, d):
    solar = Solar.fromYmdHms(
        int(y),
        int(m),
        int(d),
        12,
        0,
        0,
    )

    ec = solar.getLunar().getEightChar()

    return chart_from_pillars(
        ec.getYear(),
        ec.getMonth(),
        ec.getDay(),
    )


def dates_in_year(y):
    y = int(y)
    n = 366 if calendar.isleap(y) else 365
    start = pd.Timestamp(year=y, month=1, day=1)
    return [
        (start + pd.Timedelta(days=i)).date()
        for i in range(n)
    ]


def metric_names(weights):
    names = []

    for g in GAN_ORDER:
        names.append(f"dm_stem_{g}")

    for e in ELEMENT_ORDER:
        names.append(f"dm_element_{e}")

    names.append("dm_contrast_土_minus_金")

    for e, g1, g2 in PAIR_ORDER:
        names.append(f"dm_pair_{g1}_minus_{g2}")

    for w in weights:
        tag = weight_tag(w)

        for e in ELEMENT_ORDER:
            names.append(f"element_share_w{tag}_{e}")

        for rel in REL5_ORDER:
            names.append(f"branch_rel_share_w{tag}_{rel}")

    return names


def metric_vector_from_feature(f, weights, names):
    d = {}

    dm = f["day_master"]
    dme = f["day_master_element"]

    for g in GAN_ORDER:
        d[f"dm_stem_{g}"] = 1.0 if dm == g else 0.0

    for e in ELEMENT_ORDER:
        d[f"dm_element_{e}"] = 1.0 if dme == e else 0.0

    d["dm_contrast_土_minus_金"] = (
        1.0 if dme == "土"
        else -1.0 if dme == "金"
        else 0.0
    )

    for e, g1, g2 in PAIR_ORDER:
        d[f"dm_pair_{g1}_minus_{g2}"] = (
            1.0 if dm == g1
            else -1.0 if dm == g2
            else 0.0
        )

    for w in weights:
        tag = weight_tag(w)

        for e in ELEMENT_ORDER:
            d[f"element_share_w{tag}_{e}"] = float(
                f[f"element_share_w{tag}_{e}"]
            )

        for rel in REL5_ORDER:
            d[f"branch_rel_share_w{tag}_{rel}"] = float(
                f[f"branch_rel_share_w{tag}_{rel}"]
            )

    return np.array([d[n] for n in names], dtype=float)


def cache_signature(weights):
    return ",".join(f"{float(w):g}" for w in weights)


def build_calendar_cache(
    birth_years,
    weights,
    cache_path,
    rebuild=False,
):
    """
    One row per Gregorian calendar date for the years present in the sample.
    Only ~8.8k rows for 24 years, so this is cheap and exact.
    """
    cache_path = Path(cache_path)
    sig = cache_signature(weights)

    if rebuild and cache_path.exists():
        cache_path.unlink()

    if cache_path.exists():
        old = pd.read_csv(cache_path, encoding="utf-8-sig")

        if (
            "weights_signature" in old.columns
            and set(old["weights_signature"].astype(str).unique()) == {sig}
        ):
            have_years = set(old["birth_year"].astype(int).unique())
            need_years = set(int(x) for x in birth_years)

            if need_years.issubset(have_years):
                print(
                    f"Loaded reusable calendar cache: {cache_path} "
                    f"({len(old):,} dates)"
                )
                return old[
                    old["birth_year"].astype(int).isin(need_years)
                ].copy()

        print("Existing cache is incompatible; rebuilding.")

    names = metric_names(weights)
    rows = []

    years = sorted(set(int(x) for x in birth_years))

    for pos, y in enumerate(years, 1):
        dates = dates_in_year(y)

        print(
            f"[{pos:02d}/{len(years):02d}] "
            f"calendar year {y}: {len(dates)} dates"
        )

        for dt in dates:
            chart = solar_chart(
                dt.year,
                dt.month,
                dt.day,
            )

            f = feature_dict(
                chart,
                weights,
            )

            vec = metric_vector_from_feature(
                f,
                weights,
                names,
            )

            row = {
                "birth_year": y,
                "dob": dt.isoformat(),
                "weights_signature": sig,
            }

            row.update({
                name: float(vec[j])
                for j, name in enumerate(names)
            })

            rows.append(row)

        # Save incrementally by year.
        pd.DataFrame(rows).to_csv(
            cache_path,
            index=False,
            encoding="utf-8-sig",
        )

    out = pd.DataFrame(rows)
    return out


def observed_metric_sums(player, weights, names):
    sums = np.zeros(len(names), dtype=float)

    for _, r in player.iterrows():
        f = r.to_dict()
        sums += metric_vector_from_feature(
            f,
            weights,
            names,
        )

    return sums


def null_arrays(cache, names):
    out = {}

    for y, g in cache.groupby("birth_year", sort=True):
        out[int(y)] = g[names].astype(float).to_numpy()

    return out


def year_counts(input_df):
    return {
        int(y): int(n)
        for y, n in input_df.groupby("birth_year").size().items()
    }


def exact_null_expectation(arrays, counts, k):
    s = np.zeros(k, dtype=float)

    for y, n in counts.items():
        s += n * arrays[y].mean(axis=0)

    return s


def simulate_null(
    arrays,
    counts,
    observed_sums,
    exact_expected,
    names,
    permutations,
    batch_size,
    seed,
):
    rng = np.random.default_rng(seed)
    k = len(names)

    total = np.zeros(k, dtype=float)
    total_sq = np.zeros(k, dtype=float)

    ge_obs = np.zeros(k, dtype=np.int64)
    le_obs = np.zeros(k, dtype=np.int64)
    abs_dev_ge = np.zeros(k, dtype=np.int64)

    n_done = 0

    while n_done < permutations:
        b = min(batch_size, permutations - n_done)

        sim = np.zeros((b, k), dtype=float)

        for y, n_players in counts.items():
            a = arrays[y]
            idx = rng.integers(
                0,
                len(a),
                size=(b, n_players),
            )

            sim += a[idx].sum(axis=1)

        total += sim.sum(axis=0)
        total_sq += np.square(sim).sum(axis=0)

        ge_obs += np.count_nonzero(
            sim >= (observed_sums - 1e-12),
            axis=0,
        )

        le_obs += np.count_nonzero(
            sim <= (observed_sums + 1e-12),
            axis=0,
        )

        abs_dev_ge += np.count_nonzero(
            np.abs(sim - exact_expected)
            >= (np.abs(observed_sums - exact_expected) - 1e-12),
            axis=0,
        )

        n_done += b

        if (
            n_done == permutations
            or n_done % max(batch_size * 5, 1) == 0
        ):
            print(
                f"Permutation progress: "
                f"{n_done:,}/{permutations:,}"
            )

    mean = total / permutations
    var = total_sq / permutations - mean ** 2
    sd = np.sqrt(np.maximum(var, 0.0))

    p_enrich = (ge_obs + 1) / (permutations + 1)
    p_deplete = (le_obs + 1) / (permutations + 1)
    p_two = (abs_dev_ge + 1) / (permutations + 1)

    rows = []

    for j, name in enumerate(names):
        z = (
            (observed_sums[j] - exact_expected[j]) / sd[j]
            if sd[j] > 0
            else np.nan
        )

        rows.append({
            "metric": name,
            "observed_sum": float(observed_sums[j]),
            "exact_calendar_expected_sum": float(exact_expected[j]),
            "null_mc_mean_sum": float(mean[j]),
            "null_mc_sd_sum": float(sd[j]),
            "observed_minus_expected": float(
                observed_sums[j] - exact_expected[j]
            ),
            "z_vs_calendar_null": float(z),
            "p_one_sided_enrichment": float(p_enrich[j]),
            "p_one_sided_depletion": float(p_deplete[j]),
            "p_two_sided": float(p_two[j]),
            "permutations": int(permutations),
        })

    return pd.DataFrame(rows)


def add_human_readable_rates(
    tests,
    n_players,
):
    out = tests.copy()

    # For indicator metrics this is a rate; for share metrics it is the
    # cohort mean share. Both are sum / N.
    out["observed_mean_or_rate"] = (
        out["observed_sum"] / n_players
    )

    out["calendar_expected_mean_or_rate"] = (
        out["exact_calendar_expected_sum"] / n_players
    )

    out["observed_over_expected"] = (
        out["observed_mean_or_rate"]
        / out["calendar_expected_mean_or_rate"]
    )

    return out


def holm_adjust(pvals):
    p = np.asarray(pvals, dtype=float)
    m = len(p)
    order = np.argsort(p)
    adj = np.empty(m, dtype=float)

    running = 0.0

    for rank, idx in enumerate(order):
        val = (m - rank) * p[idx]
        running = max(running, val)
        adj[idx] = min(running, 1.0)

    return adj


def add_family_and_holm(tests):
    out = tests.copy()

    families = []

    for m in out["metric"]:
        if m.startswith("dm_stem_"):
            fam = "daymaster_10stem"
        elif m.startswith("dm_element_"):
            fam = "daymaster_5element"
        elif m == "dm_contrast_土_minus_金":
            fam = "daymaster_earth_vs_metal"
        elif m.startswith("dm_pair_"):
            fam = "daymaster_within_element_pairs"
        elif m.startswith("element_share_"):
            # Separate weight families to avoid mixing sensitivity settings.
            parts = m.split("_")
            fam = "element_share_" + parts[2]
        elif m.startswith("branch_rel_share_"):
            parts = m.split("_")
            fam = "branch_relation_" + parts[3]
        else:
            fam = "other"

        families.append(fam)

    out["family"] = families
    out["holm_p_two_sided_within_family"] = np.nan

    for fam, idx in out.groupby("family").groups.items():
        loc = list(idx)
        out.loc[
            loc,
            "holm_p_two_sided_within_family"
        ] = holm_adjust(
            out.loc[loc, "p_two_sided"].to_numpy()
        )

    return out


def print_key_results(
    stem_df,
    elem_df,
    pair_df,
    tests,
    weights,
):
    print()
    print("=" * 100)
    print("DAY MASTER: 10 STEMS")
    print("=" * 100)
    print(
        stem_df[
            ["day_master", "element", "count", "rate"]
        ].to_string(index=False)
    )

    print()
    print("=" * 100)
    print("DAY MASTER: 5 ELEMENTS")
    print("=" * 100)
    print(
        elem_df[
            ["element", "count", "rate"]
        ].to_string(index=False)
    )

    print()
    print("=" * 100)
    print("WITHIN-ELEMENT STEM PAIRS + EARTH VS METAL")
    print("=" * 100)
    print(
        pair_df.to_string(index=False)
    )

    print()
    print("=" * 100)
    print("CALENDAR-MATCHED KEY TESTS")
    print("=" * 100)

    key_metrics = (
        [f"dm_stem_{g}" for g in GAN_ORDER]
        + [f"dm_element_{e}" for e in ELEMENT_ORDER]
        + ["dm_contrast_土_minus_金"]
        + [f"dm_pair_{g1}_minus_{g2}" for _, g1, g2 in PAIR_ORDER]
    )

    x = tests[
        tests["metric"].isin(key_metrics)
    ][
        [
            "metric",
            "observed_mean_or_rate",
            "calendar_expected_mean_or_rate",
            "observed_minus_expected",
            "z_vs_calendar_null",
            "p_one_sided_enrichment",
            "p_one_sided_depletion",
            "p_two_sided",
        ]
    ]

    print(
        x.to_string(
            index=False,
            float_format=lambda v: f"{v:.6f}",
        )
    )

    print()
    print("Month-weight sensitivity summaries are in:")
    print("  *_structure_summary.csv")
    print("  *_calendar_null_tests.csv")


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
        default=[1.0, 1.5, 2.0, 3.0],
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
        default="bazi_basic",
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

    weights = sorted(set(float(x) for x in args.month_weights))

    if any(w <= 0 for w in weights):
        raise SystemExit("All month weights must be > 0.")

    prefix = args.output_prefix

    if args.calendar_cache is None:
        cache_path = f"{prefix}_calendar_date_cache.csv"
    else:
        cache_path = args.calendar_cache

    raw, player = load_actual(
        args.input,
        weights,
    )

    print(
        f"Loaded {len(player)} players. "
        f"Known pillars only: 年/月/日. "
        f"No invented 时柱."
    )

    stem_df, elem_df, pair_df = daymaster_tables(player)

    summary = structure_summary(
        player,
        weights,
    )

    stem_df.to_csv(
        f"{prefix}_daymaster_10stem.csv",
        index=False,
        encoding="utf-8-sig",
    )

    elem_df.to_csv(
        f"{prefix}_daymaster_5element.csv",
        index=False,
        encoding="utf-8-sig",
    )

    pair_df.to_csv(
        f"{prefix}_daymaster_pair_tests.csv",
        index=False,
        encoding="utf-8-sig",
    )

    player.to_csv(
        f"{prefix}_player_features.csv",
        index=False,
        encoding="utf-8-sig",
    )

    summary.to_csv(
        f"{prefix}_structure_summary.csv",
        index=False,
        encoding="utf-8-sig",
    )

    print()
    print("Building/loading calendar-matched date cache...")

    cache = build_calendar_cache(
        raw["birth_year"].astype(int).unique(),
        weights,
        cache_path,
        rebuild=args.rebuild_cache,
    )

    names = metric_names(weights)
    arrays = null_arrays(cache, names)
    counts = year_counts(raw)

    missing_years = [
        y for y in counts
        if y not in arrays
    ]

    if missing_years:
        raise RuntimeError(
            f"Calendar cache missing years: {missing_years}"
        )

    obs_sums = observed_metric_sums(
        player,
        weights,
        names,
    )

    exp_sums = exact_null_expectation(
        arrays,
        counts,
        len(names),
    )

    print()
    print(
        f"Running {args.permutations:,} calendar-matched permutations..."
    )

    tests = simulate_null(
        arrays,
        counts,
        obs_sums,
        exp_sums,
        names,
        permutations=args.permutations,
        batch_size=args.batch_size,
        seed=args.seed,
    )

    tests = add_human_readable_rates(
        tests,
        len(player),
    )

    tests = add_family_and_holm(tests)

    tests.to_csv(
        f"{prefix}_calendar_null_tests.csv",
        index=False,
        encoding="utf-8-sig",
    )

    # Add calendar expected rates back into day-master summary files.
    stem_expected = {}
    elem_expected = {}

    for _, r in tests.iterrows():
        m = r["metric"]

        if m.startswith("dm_stem_"):
            stem_expected[
                m.replace("dm_stem_", "")
            ] = r

        elif m.startswith("dm_element_"):
            elem_expected[
                m.replace("dm_element_", "")
            ] = r

    stem_df2 = stem_df.copy()
    stem_df2["calendar_expected_rate"] = stem_df2["day_master"].map(
        lambda g: stem_expected[g]["calendar_expected_mean_or_rate"]
    )
    stem_df2["calendar_p_enrichment"] = stem_df2["day_master"].map(
        lambda g: stem_expected[g]["p_one_sided_enrichment"]
    )
    stem_df2["calendar_p_depletion"] = stem_df2["day_master"].map(
        lambda g: stem_expected[g]["p_one_sided_depletion"]
    )
    stem_df2["calendar_p_two_sided"] = stem_df2["day_master"].map(
        lambda g: stem_expected[g]["p_two_sided"]
    )

    elem_df2 = elem_df.copy()
    elem_df2["calendar_expected_rate"] = elem_df2["element"].map(
        lambda e: elem_expected[e]["calendar_expected_mean_or_rate"]
    )
    elem_df2["calendar_p_enrichment"] = elem_df2["element"].map(
        lambda e: elem_expected[e]["p_one_sided_enrichment"]
    )
    elem_df2["calendar_p_depletion"] = elem_df2["element"].map(
        lambda e: elem_expected[e]["p_one_sided_depletion"]
    )
    elem_df2["calendar_p_two_sided"] = elem_df2["element"].map(
        lambda e: elem_expected[e]["p_two_sided"]
    )

    stem_df2.to_csv(
        f"{prefix}_daymaster_10stem.csv",
        index=False,
        encoding="utf-8-sig",
    )

    elem_df2.to_csv(
        f"{prefix}_daymaster_5element.csv",
        index=False,
        encoding="utf-8-sig",
    )

    print_key_results(
        stem_df2,
        elem_df2,
        pair_df,
        tests,
        weights,
    )

    print()
    print("Saved:")
    for fn in [
        f"{prefix}_daymaster_10stem.csv",
        f"{prefix}_daymaster_5element.csv",
        f"{prefix}_daymaster_pair_tests.csv",
        f"{prefix}_player_features.csv",
        f"{prefix}_structure_summary.csv",
        f"{prefix}_calendar_null_tests.csv",
        str(cache_path),
    ]:
        print(f"  {fn}")


if __name__ == "__main__":
    main()
