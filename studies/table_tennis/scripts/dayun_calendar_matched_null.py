#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
dayun_calendar_matched_null.py

Calendar-matched null test for the table-tennis 大运 hypothesis.

PRIMARY HYPOTHESIS (locked before this script):
    At chronological age 12, the 大运 STEM ten-god is 食神 or 七杀
    more often than expected from calendar structure.

SECONDARY:
    1) 大运 branch 本气 ten-god is 食神 or 七杀
    2) stem OR branch-main-qi is 食神 or 七杀
    3) 食神 and 七杀 separately

Why this null is needed
-----------------------
We do NOT compare everything to a naive 10% / 20% baseline.

For each real player we preserve:
    - Gregorian birth year
    - gender

Then, under the null, we replace the exact birthday by a random
calendar day in that same year. Because birth time is unknown, each
candidate calendar day is evaluated over the same 24-hour grid used
for the real players (HH:30 for 00..23).

Therefore the null automatically preserves / reproduces:
    - day-master distribution induced by the calendar
    - month-pillar structure
    - year-pillar transitions around 立春
    - 阳男阴女顺 / 阴男阳女逆
    - 起运 timing
    - 天干/地支 dependence
    - 火日主遇四库时地支本气食伤机会较高
    - leap years

This script imports the already-audited:
    dayun_audit_scanner_v2.py

Put both .py files in the same directory.

Recommended run
---------------
python dayun_calendar_matched_null.py ^
    --input tabletennis_reference_enriched.csv ^
    --observed dayun_hour_sensitivity.csv ^
    --age 12 ^
    --permutations 200000 ^
    --cache dayun_calendar_daylevel_cache.csv

PowerShell multiline:
python dayun_calendar_matched_null.py `
  --input tabletennis_reference_enriched.csv `
  --observed dayun_hour_sensitivity.csv `
  --age 12 `
  --permutations 200000 `
  --cache dayun_calendar_daylevel_cache.csv

Outputs
-------
dayun_calendar_null_tests.csv
dayun_calendar_null_group_baselines.csv
dayun_calendar_daylevel_cache.csv   (large-ish, resumable)

Interpretation
--------------
For all_weighted:
    Each real DOB contributes its 24-hour grid fraction.
    Each null DOB does the same.
    This is the cleanest primary analysis because it does not throw
    away time-sensitive or boundary-sensitive real dates.

For robust_nonboundary:
    The same QC rule is applied BOTH to real dates and randomized dates.
    So selection is reproduced in the null rather than conditioning on
    the observed selected sample only.

One-sided p-values test ENRICHMENT:
    P(null >= observed)

No multiple-testing correction is applied here because only one
pre-registered primary endpoint exists:
    age 12 stem 食神-or-七杀.
Secondary rows are exploratory.
"""

import argparse
import calendar
import json
import math
import os
from pathlib import Path

import numpy as np
import pandas as pd

try:
    import dayun_audit_scanner_v2 as ds
except Exception as e:
    raise SystemExit(
        "Could not import dayun_audit_scanner_v2.py.\n"
        "Put dayun_calendar_matched_null.py and "
        "dayun_audit_scanner_v2.py in the same folder.\n"
        f"Original error: {type(e).__name__}: {e}"
    )


DEFAULT_SEED = 20260925


def norm_gender(x):
    """Normalize to 男 / 女, using the same convention as the scanner."""
    g = ds.parse_gender(x)
    return "男" if g == 1 else "女"


def days_in_year(y):
    return 366 if calendar.isleap(int(y)) else 365


def all_dates_in_year(y):
    y = int(y)
    start = pd.Timestamp(year=y, month=1, day=1)
    end = pd.Timestamp(year=y, month=12, day=31)
    return [
        d.strftime("%Y-%m-%d")
        for d in pd.date_range(start, end, freq="D")
    ]


def endpoint_columns(age):
    a = int(age)
    return {
        # Stem
        "stem_foodgod":
            f"age{a}_foodgod_grid_fraction",
        "stem_sevenkill":
            f"age{a}_sevenkill_grid_fraction",
        "stem_foodgod_or_sevenkill":
            f"age{a}_foodgod_or_sevenkill_grid_fraction",

        # Branch main qi
        "branch_foodgod":
            f"age{a}_branch_main_foodgod_grid_fraction",
        "branch_sevenkill":
            f"age{a}_branch_main_sevenkill_grid_fraction",
        "branch_foodgod_or_sevenkill":
            f"age{a}_branch_main_foodgod_or_sevenkill_grid_fraction",

        # Stem OR branch main qi
        "stem_or_branch_foodgod_or_sevenkill":
            f"age{a}_stem_or_branch_main_foodgod_or_sevenkill_grid_fraction",

        # Both stem AND branch main qi
        "stem_and_branch_foodgod_or_sevenkill":
            f"age{a}_stem_and_branch_main_foodgod_or_sevenkill_grid_fraction",
    }


def qc_columns(age):
    a = int(age)
    return {
        "stem_unique":
            f"age{a}_unique_tengod",
        "branch_unique":
            f"age{a}_branch_main_unique_tengod",
        "boundary":
            "boundary_sensitive",
    }


def validate_observed(obs, age):
    cols = endpoint_columns(age)
    qc = qc_columns(age)

    required = (
        ["name", "dob", "gender"]
        + list(cols.values())
        + list(qc.values())
    )

    missing = [
        c for c in required
        if c not in obs.columns
    ]

    if missing:
        raise SystemExit(
            "Observed sensitivity CSV is missing columns:\n"
            + "\n".join(missing)
        )


def validate_input(inp):
    required = [
        "name",
        "dob",
        "birth_year",
        "gender",
    ]

    missing = [
        c for c in required
        if c not in inp.columns
    ]

    if missing:
        raise SystemExit(
            "Input CSV is missing columns:\n"
            + "\n".join(missing)
        )


def verify_alignment(inp, obs):
    """
    Require exact one-to-one matching by name + dob + normalized gender.
    """
    a = inp[
        ["name", "dob", "gender", "birth_year"]
    ].copy()

    b = obs[
        ["name", "dob", "gender"]
    ].copy()

    a["gender_norm"] = a["gender"].map(norm_gender)
    b["gender_norm"] = b["gender"].map(norm_gender)

    key = ["name", "dob", "gender_norm"]

    if a.duplicated(key).any():
        raise SystemExit(
            "Input has duplicate name+dob+gender keys."
        )

    if b.duplicated(key).any():
        raise SystemExit(
            "Observed file has duplicate name+dob+gender keys."
        )

    m = a.merge(
        b,
        on=key,
        how="outer",
        indicator=True,
        suffixes=("_input", "_observed"),
    )

    bad = m[m["_merge"] != "both"]

    if len(bad):
        raise SystemExit(
            "Input and observed files do not align exactly.\n"
            f"Mismatched rows: {len(bad)}\n"
            + bad.head(20).to_string(index=False)
        )

    return a


def cache_group_complete(cache, year, gender):
    if cache is None or len(cache) == 0:
        return False

    sub = cache[
        (cache["birth_year"] == int(year))
        & (cache["gender"] == gender)
    ]

    return (
        len(sub) == days_in_year(year)
        and sub["dob"].nunique() == days_in_year(year)
    )


def build_one_calendar_day(
    dob,
    gender,
    age,
    yun_sect,
    zi_sect,
):
    """
    Evaluate one calendar DATE by scanning all 24 assumed clock hours.
    Returns one row of date-level fractional exposures.
    """
    sens, boundary = ds.sensitivity_one_date(
        dob,
        gender,
        yun_sect=yun_sect,
        zi_sect=zi_sect,
        ages=(int(age),),
        dayun_count=6,
    )

    s = ds.summarize_sensitivity(
        sens,
        boundary,
        ages=(int(age),),
    )

    row = {
        "dob": dob,
        "gender": norm_gender(gender),
        "birth_year": int(dob[:4]),
    }

    cols = endpoint_columns(age)
    qc = qc_columns(age)

    for c in cols.values():
        row[c] = float(s[c])

    row[qc["stem_unique"]] = int(s[qc["stem_unique"]])
    row[qc["branch_unique"]] = int(s[qc["branch_unique"]])
    row[qc["boundary"]] = int(s[qc["boundary"]])

    return row


def build_or_resume_cache(
    inp,
    cache_path,
    age,
    yun_sect,
    zi_sect,
    rebuild=False,
):
    cache_path = Path(cache_path)

    if rebuild and cache_path.exists():
        cache_path.unlink()

    if cache_path.exists():
        cache = pd.read_csv(
            cache_path,
            encoding="utf-8-sig",
        )
        print(
            f"Loaded existing cache: {cache_path} "
            f"({len(cache):,} date rows)"
        )
    else:
        cache = pd.DataFrame()

    groups = (
        inp.assign(
            gender_norm=inp["gender"].map(norm_gender)
        )
        [["birth_year", "gender_norm"]]
        .drop_duplicates()
        .sort_values(["birth_year", "gender_norm"])
    )

    all_rows = []

    if len(cache):
        all_rows.append(cache)

    for pos, r in enumerate(groups.itertuples(index=False), 1):
        year = int(r.birth_year)
        gender = str(r.gender_norm)

        if cache_group_complete(cache, year, gender):
            print(
                f"[{pos:02d}/{len(groups):02d}] "
                f"{year} {gender}: cache complete, skip"
            )
            continue

        # If an interrupted partial group exists, discard that group
        # and rebuild it cleanly.
        if len(cache):
            cache = cache[
                ~(
                    (cache["birth_year"] == year)
                    & (cache["gender"] == gender)
                )
            ].copy()

            all_rows = [cache] if len(cache) else []

        dates = all_dates_in_year(year)
        rows = []

        print(
            f"[{pos:02d}/{len(groups):02d}] "
            f"{year} {gender}: building {len(dates)} dates "
            f"x 24 hours ..."
        )

        for j, dob in enumerate(dates, 1):
            try:
                row = build_one_calendar_day(
                    dob,
                    gender,
                    age=age,
                    yun_sect=yun_sect,
                    zi_sect=zi_sect,
                )
                rows.append(row)
            except Exception as e:
                raise RuntimeError(
                    f"Calendar cache failed at "
                    f"{dob} {gender}: "
                    f"{type(e).__name__}: {e}"
                ) from e

            if (
                j == 1
                or j % 50 == 0
                or j == len(dates)
            ):
                print(
                    f"    {j:3d}/{len(dates):3d}"
                )

        group_df = pd.DataFrame(rows)

        if len(group_df) != len(dates):
            raise RuntimeError(
                f"Internal error: group {year} {gender} "
                f"has {len(group_df)} rows, expected {len(dates)}."
            )

        # Reconstruct current cache and save after EACH year-gender group.
        pieces = []

        if len(cache):
            pieces.append(cache)

        pieces.append(group_df)

        cache = pd.concat(
            pieces,
            ignore_index=True,
        )

        cache = cache.sort_values(
            ["birth_year", "gender", "dob"]
        ).reset_index(drop=True)

        cache.to_csv(
            cache_path,
            index=False,
            encoding="utf-8-sig",
        )

        print(
            f"    saved cache -> {cache_path} "
            f"({len(cache):,} rows)"
        )

    # Final completeness check
    for r in groups.itertuples(index=False):
        year = int(r.birth_year)
        gender = str(r.gender_norm)

        if not cache_group_complete(cache, year, gender):
            raise RuntimeError(
                f"Cache incomplete for {year} {gender}"
            )

    return cache


def make_group_arrays(
    cache,
    age,
):
    """
    Store date-level matrices for each (year, gender).
    """
    cols = endpoint_columns(age)
    qc = qc_columns(age)

    endpoint_names = list(cols.keys())
    endpoint_cols = [
        cols[k] for k in endpoint_names
    ]

    out = {}

    for (year, gender), g in cache.groupby(
        ["birth_year", "gender"],
        sort=True,
    ):
        g = g.sort_values("dob")

        values = (
            g[endpoint_cols]
            .astype(float)
            .to_numpy()
        )

        stem_clean = (
            (g[qc["boundary"]].astype(int).to_numpy() == 0)
            & (g[qc["stem_unique"]].astype(int).to_numpy() == 1)
        )

        branch_clean = (
            (g[qc["boundary"]].astype(int).to_numpy() == 0)
            & (g[qc["branch_unique"]].astype(int).to_numpy() == 1)
        )

        either_clean = (
            stem_clean
            & branch_clean
        )

        out[(int(year), str(gender))] = {
            "values": values,
            "endpoint_names": endpoint_names,
            "stem_clean": stem_clean,
            "branch_clean": branch_clean,
            "either_clean": either_clean,
            "dates": g["dob"].to_numpy(),
        }

    return out


def group_counts(inp):
    x = inp.copy()

    x["gender_norm"] = x["gender"].map(norm_gender)

    counts = (
        x.groupby(
            ["birth_year", "gender_norm"]
        )
        .size()
        .reset_index(name="n_players")
    )

    return {
        (int(r.birth_year), str(r.gender_norm)): int(r.n_players)
        for r in counts.itertuples(index=False)
    }


def observed_stats(obs, age):
    cols = endpoint_columns(age)
    qc = qc_columns(age)

    obs = obs.copy()
    obs["gender"] = obs["gender"].map(norm_gender)

    results = {}

    # All weighted analysis: no exclusions.
    for name, col in cols.items():
        vals = pd.to_numeric(
            obs[col],
            errors="coerce",
        )

        if vals.isna().any():
            raise SystemExit(
                f"Observed column {col} contains NaN."
            )

        results[("all_weighted", name)] = {
            "observed_sum": float(vals.sum()),
            "observed_n": int(len(vals)),
            "observed_rate": float(vals.mean()),
        }

    # Same QC rule that will be applied to randomized calendar dates.
    stem_clean = (
        pd.to_numeric(
            obs[qc["boundary"]],
            errors="raise",
        ).astype(int).eq(0)
        & pd.to_numeric(
            obs[qc["stem_unique"]],
            errors="raise",
        ).astype(int).eq(1)
    )

    branch_clean = (
        pd.to_numeric(
            obs[qc["boundary"]],
            errors="raise",
        ).astype(int).eq(0)
        & pd.to_numeric(
            obs[qc["branch_unique"]],
            errors="raise",
        ).astype(int).eq(1)
    )

    either_clean = (
        stem_clean
        & branch_clean
    )

    for name, col in cols.items():
        if name.startswith("stem_or_branch") or name.startswith("stem_and_branch"):
            mask = either_clean
        elif name.startswith("branch_"):
            mask = branch_clean
        else:
            mask = stem_clean

        vals = pd.to_numeric(
            obs.loc[mask, col],
            errors="coerce",
        )

        results[("robust_nonboundary", name)] = {
            "observed_sum": float(vals.sum()),
            "observed_n": int(mask.sum()),
            "observed_rate": float(vals.mean()) if mask.sum() else np.nan,
        }

    return results


def exact_all_weighted_expectation(
    arrays,
    counts,
):
    """
    Exact expectation for date-level weighted endpoints.
    """
    endpoint_names = next(iter(arrays.values()))[
        "endpoint_names"
    ]

    expected_sum = np.zeros(
        len(endpoint_names),
        dtype=float,
    )

    for key, m in counts.items():
        vals = arrays[key]["values"]

        expected_sum += (
            int(m)
            * vals.mean(axis=0)
        )

    n = sum(counts.values())

    return {
        name: {
            "expected_sum_exact": float(expected_sum[j]),
            "expected_rate_exact": float(expected_sum[j] / n),
        }
        for j, name in enumerate(endpoint_names)
    }


def clean_mask_for_endpoint(
    data,
    endpoint_name,
):
    if endpoint_name.startswith("stem_or_branch") or endpoint_name.startswith("stem_and_branch"):
        return data["either_clean"]

    if endpoint_name.startswith("branch_"):
        return data["branch_clean"]

    return data["stem_clean"]


def simulate_null(
    arrays,
    counts,
    observed,
    permutations,
    seed,
    batch_size,
):
    """
    Randomize birthday within birth-year + gender, preserving group counts.

    For each person/date draw:
      - all_weighted uses the 24-hour averaged date-level endpoint.
      - robust_nonboundary applies the same QC rule as observed data.

    Returns one test row per analysis x endpoint.
    """
    rng = np.random.default_rng(seed)

    endpoint_names = next(iter(arrays.values()))[
        "endpoint_names"
    ]

    k = len(endpoint_names)

    # Accumulators for null summaries.
    all_sum_total = np.zeros(k)
    all_sum_sq = np.zeros(k)
    all_ge = np.zeros(k, dtype=np.int64)

    clean_rate_total = np.zeros(k)
    clean_rate_sq = np.zeros(k)
    clean_n_total = np.zeros(k)
    clean_ge = np.zeros(k, dtype=np.int64)
    clean_valid_perm = np.zeros(k, dtype=np.int64)

    n_done = 0

    while n_done < permutations:
        b = min(
            int(batch_size),
            int(permutations - n_done),
        )

        all_sums = np.zeros(
            (b, k),
            dtype=float,
        )

        clean_num = np.zeros(
            (b, k),
            dtype=float,
        )

        clean_den = np.zeros(
            (b, k),
            dtype=np.int32,
        )

        # Sampling by year+gender groups is faster than looping 384 persons.
        for key, m in counts.items():
            data = arrays[key]
            vals = data["values"]
            n_days = len(vals)

            idx = rng.integers(
                0,
                n_days,
                size=(b, int(m)),
                endpoint=False,
            )

            # b x m x k
            chosen_vals = vals[idx]

            all_sums += chosen_vals.sum(axis=1)

            # Endpoint-specific QC masks.
            for j, name in enumerate(endpoint_names):
                mask = clean_mask_for_endpoint(
                    data,
                    name,
                )

                chosen_ok = mask[idx]

                clean_num[:, j] += (
                    chosen_vals[:, :, j]
                    * chosen_ok
                ).sum(axis=1)

                clean_den[:, j] += (
                    chosen_ok.sum(axis=1)
                )

        # all_weighted comparison is based on summed fractional exposure.
        for j, name in enumerate(endpoint_names):
            x = all_sums[:, j]

            all_sum_total[j] += x.sum()
            all_sum_sq[j] += np.square(x).sum()

            obs_sum = observed[
                ("all_weighted", name)
            ]["observed_sum"]

            all_ge[j] += np.count_nonzero(
                x >= obs_sum - 1e-12
            )

            den = clean_den[:, j]
            valid = den > 0

            if np.any(valid):
                rate = (
                    clean_num[valid, j]
                    / den[valid]
                )

                clean_rate_total[j] += rate.sum()
                clean_rate_sq[j] += np.square(rate).sum()
                clean_n_total[j] += den[valid].sum()

                obs_rate = observed[
                    ("robust_nonboundary", name)
                ]["observed_rate"]

                clean_ge[j] += np.count_nonzero(
                    rate >= obs_rate - 1e-12
                )

                clean_valid_perm[j] += int(
                    valid.sum()
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

    rows = []

    n_players = sum(counts.values())

    for j, name in enumerate(endpoint_names):
        # all weighted
        null_mean_sum = (
            all_sum_total[j] / permutations
        )

        null_var_sum = (
            all_sum_sq[j] / permutations
            - null_mean_sum ** 2
        )

        null_sd_sum = math.sqrt(
            max(
                null_var_sum,
                0.0,
            )
        )

        obs0 = observed[
            ("all_weighted", name)
        ]

        z0 = (
            (obs0["observed_sum"] - null_mean_sum)
            / null_sd_sum
            if null_sd_sum > 0
            else np.nan
        )

        p0 = (
            int(all_ge[j]) + 1
        ) / (
            int(permutations) + 1
        )

        rows.append({
            "analysis": "all_weighted",
            "endpoint": name,
            "age": None,
            "observed_n": obs0["observed_n"],
            "observed_sum": obs0["observed_sum"],
            "observed_rate": obs0["observed_rate"],
            "null_mean_sum": null_mean_sum,
            "null_mean_rate": null_mean_sum / n_players,
            "null_sd_sum": null_sd_sum,
            "enrichment_observed_over_null": (
                obs0["observed_rate"]
                / (null_mean_sum / n_players)
                if null_mean_sum > 0
                else np.nan
            ),
            "z_vs_null": z0,
            "p_one_sided_enrichment": p0,
            "permutations": permutations,
        })

        # robust + nonboundary
        valid_n = int(clean_valid_perm[j])

        null_mean_rate = (
            clean_rate_total[j] / valid_n
            if valid_n
            else np.nan
        )

        null_var_rate = (
            clean_rate_sq[j] / valid_n
            - null_mean_rate ** 2
            if valid_n
            else np.nan
        )

        null_sd_rate = (
            math.sqrt(max(null_var_rate, 0.0))
            if valid_n
            else np.nan
        )

        null_mean_n = (
            clean_n_total[j] / valid_n
            if valid_n
            else np.nan
        )

        obs1 = observed[
            ("robust_nonboundary", name)
        ]

        z1 = (
            (obs1["observed_rate"] - null_mean_rate)
            / null_sd_rate
            if null_sd_rate and null_sd_rate > 0
            else np.nan
        )

        p1 = (
            int(clean_ge[j]) + 1
        ) / (
            valid_n + 1
        ) if valid_n else np.nan

        rows.append({
            "analysis": "robust_nonboundary",
            "endpoint": name,
            "age": None,
            "observed_n": obs1["observed_n"],
            "observed_sum": obs1["observed_sum"],
            "observed_rate": obs1["observed_rate"],
            "null_mean_sum": np.nan,
            "null_mean_rate": null_mean_rate,
            "null_sd_sum": np.nan,
            "null_mean_eligible_n": null_mean_n,
            "enrichment_observed_over_null": (
                obs1["observed_rate"]
                / null_mean_rate
                if null_mean_rate and null_mean_rate > 0
                else np.nan
            ),
            "z_vs_null": z1,
            "p_one_sided_enrichment": p1,
            "permutations": valid_n,
        })

    return pd.DataFrame(rows)


def group_baselines(
    cache,
    inp,
    age,
):
    """
    Human-readable calendar baseline for each birth-year + gender group.
    """
    cols = endpoint_columns(age)
    qc = qc_columns(age)

    inp2 = inp.copy()
    inp2["gender_norm"] = inp2["gender"].map(norm_gender)

    real_counts = (
        inp2.groupby(
            ["birth_year", "gender_norm"]
        )
        .size()
        .rename("real_players")
        .reset_index()
    )

    rows = []

    for (year, gender), g in cache.groupby(
        ["birth_year", "gender"],
        sort=True,
    ):
        row = {
            "birth_year": int(year),
            "gender": str(gender),
            "calendar_days": len(g),
        }

        for name, col in cols.items():
            row[
                f"{name}_calendar_mean"
            ] = float(
                pd.to_numeric(
                    g[col],
                    errors="raise",
                ).mean()
            )

        stem_clean = (
            pd.to_numeric(
                g[qc["boundary"]],
                errors="raise",
            ).astype(int).eq(0)
            & pd.to_numeric(
                g[qc["stem_unique"]],
                errors="raise",
            ).astype(int).eq(1)
        )

        branch_clean = (
            pd.to_numeric(
                g[qc["boundary"]],
                errors="raise",
            ).astype(int).eq(0)
            & pd.to_numeric(
                g[qc["branch_unique"]],
                errors="raise",
            ).astype(int).eq(1)
        )

        row["stem_clean_calendar_fraction"] = float(
            stem_clean.mean()
        )
        row["branch_clean_calendar_fraction"] = float(
            branch_clean.mean()
        )
        row["both_clean_calendar_fraction"] = float(
            (stem_clean & branch_clean).mean()
        )

        rows.append(row)

    out = pd.DataFrame(rows)

    out = out.merge(
        real_counts,
        left_on=["birth_year", "gender"],
        right_on=["birth_year", "gender_norm"],
        how="left",
    ).drop(columns=["gender_norm"])

    return out


def mark_primary(df, age):
    df = df.copy()

    df["primary"] = (
        (df["analysis"] == "all_weighted")
        & (df["endpoint"] == "stem_foodgod_or_sevenkill")
        & (int(age) == 12)
    ).astype(int)

    df["age"] = int(age)

    return df


def main():
    ap = argparse.ArgumentParser()

    ap.add_argument(
        "--input",
        required=True,
        help="Original enriched player CSV.",
    )

    ap.add_argument(
        "--observed",
        required=True,
        help="dayun_hour_sensitivity.csv produced by v2 scanner.",
    )

    ap.add_argument(
        "--age",
        type=int,
        default=12,
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
        default=DEFAULT_SEED,
    )

    ap.add_argument(
        "--cache",
        default="dayun_calendar_daylevel_cache.csv",
    )

    ap.add_argument(
        "--rebuild-cache",
        action="store_true",
    )

    ap.add_argument(
        "--yun-sect",
        type=int,
        choices=[1, 2],
        default=1,
    )

    ap.add_argument(
        "--zi-sect",
        type=int,
        choices=[1, 2],
        default=2,
    )

    ap.add_argument(
        "--tests-output",
        default="dayun_calendar_null_tests.csv",
    )

    ap.add_argument(
        "--group-output",
        default="dayun_calendar_null_group_baselines.csv",
    )

    args = ap.parse_args()

    inp = pd.read_csv(
        args.input,
        encoding="utf-8-sig",
    )

    obs = pd.read_csv(
        args.observed,
        encoding="utf-8-sig",
    )

    validate_input(inp)
    validate_observed(obs, args.age)

    verify_alignment(inp, obs)

    print()
    print("=" * 90)
    print("CALENDAR-MATCHED DAYUN NULL")
    print("=" * 90)
    print(f"players       : {len(inp)}")
    print(f"age           : {args.age}")
    print(f"permutations  : {args.permutations:,}")
    print(f"yun sect      : {args.yun_sect}")
    print(f"zi sect       : {args.zi_sect}")
    print(f"seed          : {args.seed}")
    print()

    cache = build_or_resume_cache(
        inp,
        args.cache,
        age=args.age,
        yun_sect=args.yun_sect,
        zi_sect=args.zi_sect,
        rebuild=args.rebuild_cache,
    )

    arrays = make_group_arrays(
        cache,
        age=args.age,
    )

    counts = group_counts(inp)

    missing_groups = [
        key for key in counts
        if key not in arrays
    ]

    if missing_groups:
        raise SystemExit(
            f"Cache missing groups: {missing_groups}"
        )

    obs_stats = observed_stats(
        obs,
        age=args.age,
    )

    exact_exp = exact_all_weighted_expectation(
        arrays,
        counts,
    )

    print()
    print("Observed all-weighted age-{}:".format(args.age))
    for name in [
        "stem_foodgod",
        "stem_sevenkill",
        "stem_foodgod_or_sevenkill",
        "branch_foodgod",
        "branch_sevenkill",
        "branch_foodgod_or_sevenkill",
        "stem_or_branch_foodgod_or_sevenkill",
    ]:
        x = obs_stats[
            ("all_weighted", name)
        ]

        e = exact_exp[name]

        print(
            f"  {name:42s} "
            f"obs={x['observed_rate']:.4%} "
            f"calendar_expected={e['expected_rate_exact']:.4%}"
        )

    print()
    print(
        "Now running randomization test. "
        "The cache is already built, so future reruns are much faster."
    )

    tests = simulate_null(
        arrays,
        counts,
        obs_stats,
        permutations=args.permutations,
        seed=args.seed,
        batch_size=args.batch_size,
    )

    tests = mark_primary(
        tests,
        age=args.age,
    )

    # Replace Monte Carlo all-weighted mean with exact expectation columns too.
    tests["exact_expected_sum"] = np.nan
    tests["exact_expected_rate"] = np.nan

    for name, v in exact_exp.items():
        mask = (
            (tests["analysis"] == "all_weighted")
            & (tests["endpoint"] == name)
        )

        tests.loc[
            mask,
            "exact_expected_sum"
        ] = v["expected_sum_exact"]

        tests.loc[
            mask,
            "exact_expected_rate"
        ] = v["expected_rate_exact"]

    tests = tests.sort_values(
        ["primary", "analysis", "endpoint"],
        ascending=[False, True, True],
    ).reset_index(drop=True)

    tests.to_csv(
        args.tests_output,
        index=False,
        encoding="utf-8-sig",
    )

    groups = group_baselines(
        cache,
        inp,
        age=args.age,
    )

    groups.to_csv(
        args.group_output,
        index=False,
        encoding="utf-8-sig",
    )

    print()
    print("=" * 90)
    print("RESULTS")
    print("=" * 90)

    display_cols = [
        "primary",
        "analysis",
        "endpoint",
        "observed_n",
        "observed_rate",
        "null_mean_rate",
        "exact_expected_rate",
        "enrichment_observed_over_null",
        "z_vs_null",
        "p_one_sided_enrichment",
    ]

    print(
        tests[
            display_cols
        ].to_string(
            index=False
        )
    )

    primary = tests[
        tests["primary"] == 1
    ]

    if len(primary) == 1:
        r = primary.iloc[0]

        print()
        print("PRIMARY:")
        print(
            "  age 12 大运天干 = 食神 or 七杀"
        )
        print(
            f"  observed = {r['observed_rate']:.4%}"
        )
        print(
            f"  expected = {r['exact_expected_rate']:.4%}"
        )
        print(
            f"  enrichment = "
            f"{r['enrichment_observed_over_null']:.4f}x"
        )
        print(
            f"  one-sided permutation p = "
            f"{r['p_one_sided_enrichment']:.6g}"
        )

    print()
    print(f"Saved tests : {args.tests_output}")
    print(f"Saved groups: {args.group_output}")
    print(f"Saved cache : {args.cache}")


if __name__ == "__main__":
    main()
