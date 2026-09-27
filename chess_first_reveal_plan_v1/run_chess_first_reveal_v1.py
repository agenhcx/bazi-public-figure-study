#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
run_chess_first_reveal_v1.py

FIRST CHESS BAZI REVEAL
=======================

This script is designed to be run only after:
  chess-preregister-v3-date-sanity

It freezes the first-reveal analysis plan in Git BEFORE calculating any BaZi,
then calculates the three known pillars for the four north-v3 cohorts, runs the
frozen confirmatory headline analyses, and separately reports pre-reveal
exploratory Water / Metal+Water metrics.

CONFIRMATORY (from the frozen chess preregistration)
-----------------------------------------------------
C1. Day-Master five-element distributions, 1994 vs 2013.
C2. Directional Metal-vs-Earth temporal gradient:
      Metal relatively more represented in 1994,
      Earth relatively more represented in 2013.
C3. Measurable three-pillar 伤官 / 偏印 exposures, including performance
    association with within-snapshot-sex standardized Elo.

EXPLORATORY — FROZEN IN THIS SCRIPT BEFORE FIRST REVEAL
--------------------------------------------------------
E1. Water Day-Master frequency.
E2. WaterCount across the six known stem/main-qi positions (0..6).
E3. MetalWaterCount across the same six positions (0..6).
These address the user's pre-existing "水主智 / 金水" idea, but they are NOT
retroactively promoted to confirmatory hypotheses.

BAZI ENGINE
-----------
Uses sxtwl. Three pillars only:
  year, month, day
No birth time is imputed.
No Southern-Hemisphere seasonal/month inversion is used because north-v3
contains confirmed Northern-Hemisphere births only.

Six known element positions:
  year stem
  year branch main qi
  month stem
  month branch main qi
  day stem
  day branch main qi

Calendar null
-------------
For selection/enrichment-style summaries, the default calendar null is:
  uniformly sample a Gregorian date within the SAME birth year for each player.
This preserves the exact empirical birth-year distribution of each cohort.

The null implementation is frozen in the analysis-plan commit before results
are calculated. It is NOT used to redefine the historical-period C1/C2 tests.

Git provenance
--------------
Before any BaZi calculation:
  plan directory: chess_first_reveal_plan_v1/
  plan tag:       chess-first-reveal-plan-v1

After results:
  result directory: chess_first_reveal_v1/
  result tag:       chess-first-reveal-results-v1
"""

from __future__ import annotations

import argparse
import calendar
import hashlib
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import chi2_contingency, fisher_exact, norm, spearmanr

try:
    import sxtwl
except ImportError as e:
    raise SystemExit(
        "Missing dependency: sxtwl\n"
        "Install it first with:\n"
        "  pip install sxtwl\n"
        f"Original error: {e}"
    )


STEMS = "甲乙丙丁戊己庚辛壬癸"
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
ELEMENTS = ["木", "火", "土", "金", "水"]
STEM_ELEMENT = ["木", "木", "火", "火", "土", "土", "金", "金", "水", "水"]
STEM_YANG = [True, False, True, False, True, False, True, False, True, False]

# Branch main-qi stem indices:
# 子癸 丑己 寅甲 卯乙 辰戊 巳丙 午丁 未己 申庚 酉辛 戌戊 亥壬
BRANCH_MAIN_STEM = [9, 5, 0, 1, 4, 2, 3, 5, 6, 7, 4, 8]

COHORTS = {
    "1994_M": "primary_north_top_1994_M.csv",
    "1994_F": "primary_north_top_1994_F.csv",
    "2013_M": "primary_north_top_2013_M.csv",
    "2013_F": "primary_north_top_2013_F.csv",
}

CONFIRMATORY_LABEL = "confirmatory_frozen_prereg"
EXPLORATORY_LABEL = "exploratory_pre_reveal_not_confirmatory"


def run(cmd: list[str], cwd: Path, check: bool = True) -> str:
    print("$", " ".join(cmd))
    p = subprocess.run(
        cmd,
        cwd=str(cwd),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if p.stdout:
        print(p.stdout.rstrip())
    if check and p.returncode != 0:
        raise RuntimeError(
            f"Command failed ({p.returncode}): {' '.join(cmd)}"
        )
    return p.stdout.strip()


def git_root(path: Path) -> Path:
    x = run(["git", "rev-parse", "--show-toplevel"], path)
    return Path(x.splitlines()[-1]).resolve()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def git_tag_exists(repo: Path, tag: str) -> bool:
    return bool(run(["git", "tag", "--list", tag], repo).strip())


def ensure_no_staged(repo: Path) -> None:
    staged = run(["git", "diff", "--cached", "--name-only"], repo).strip()
    if staged:
        raise RuntimeError(
            "Git index already has staged files. Clear/commit them first:\n"
            + staged
        )


def stage_exact(repo: Path, paths: list[Path]) -> None:
    rels = [str(p.relative_to(repo)) for p in paths]
    run(["git", "add", "--", *rels], repo)
    staged = {
        x.strip().replace("\\", "/")
        for x in run(
            ["git", "diff", "--cached", "--name-only"], repo
        ).splitlines()
        if x.strip()
    }
    expected = {Path(x).as_posix() for x in rels}
    if staged != expected:
        raise RuntimeError(
            "Staged-file safety mismatch.\n"
            f"Expected={sorted(expected)}\n"
            f"Actual={sorted(staged)}"
        )


def ten_god(day_stem: int, target_stem: int) -> str:
    de = STEM_ELEMENT[day_stem]
    te = STEM_ELEMENT[target_stem]
    same_pol = STEM_YANG[day_stem] == STEM_YANG[target_stem]

    generating = {
        "木": "火",
        "火": "土",
        "土": "金",
        "金": "水",
        "水": "木",
    }
    controlling = {
        "木": "土",
        "土": "水",
        "水": "火",
        "火": "金",
        "金": "木",
    }

    if te == de:
        return "比肩" if same_pol else "劫财"
    if generating[de] == te:
        return "食神" if same_pol else "伤官"
    if generating[te] == de:
        return "偏印" if same_pol else "正印"
    if controlling[de] == te:
        return "偏财" if same_pol else "正财"
    if controlling[te] == de:
        return "七杀" if same_pol else "正官"

    raise RuntimeError((day_stem, target_stem, de, te))


def pillar_str(gz: Any) -> str:
    return STEMS[gz.tg] + BRANCHES[gz.dz]


def bazi_features(y: int, m: int, d: int) -> dict[str, Any]:
    day = sxtwl.fromSolar(int(y), int(m), int(d))

    # sxtwl's default year pillar uses the traditional solar-term boundary
    # appropriate for BaZi; month pillar is solar-term based.
    ygz = day.getYearGZ()
    mgz = day.getMonthGZ()
    dgz = day.getDayGZ()

    positions_stem_idx = [
        ygz.tg,
        BRANCH_MAIN_STEM[ygz.dz],
        mgz.tg,
        BRANCH_MAIN_STEM[mgz.dz],
        dgz.tg,
        BRANCH_MAIN_STEM[dgz.dz],
    ]

    pos_elements = [STEM_ELEMENT[i] for i in positions_stem_idx]
    gods = [ten_god(dgz.tg, i) for i in positions_stem_idx]

    counts = {e: pos_elements.count(e) for e in ELEMENTS}

    return {
        "year_pillar": pillar_str(ygz),
        "month_pillar": pillar_str(mgz),
        "day_pillar": pillar_str(dgz),
        "year_stem": STEMS[ygz.tg],
        "year_branch": BRANCHES[ygz.dz],
        "month_stem": STEMS[mgz.tg],
        "month_branch": BRANCHES[mgz.dz],
        "day_stem": STEMS[dgz.tg],
        "day_branch": BRANCHES[dgz.dz],
        "day_master_element": STEM_ELEMENT[dgz.tg],
        "WoodCount": counts["木"],
        "FireCount": counts["火"],
        "EarthCount": counts["土"],
        "MetalCount": counts["金"],
        "WaterCount": counts["水"],
        "MetalWaterCount": counts["金"] + counts["水"],
        "shangguan_count_6pos": gods.count("伤官"),
        "pianyin_count_6pos": gods.count("偏印"),
        "six_position_elements": "".join(pos_elements),
        "six_position_tengods": "|".join(gods),
    }


def load_cohorts(source: Path) -> dict[str, pd.DataFrame]:
    out = {}
    for key, fname in COHORTS.items():
        p = source / fname
        if not p.exists():
            raise FileNotFoundError(p)
        d = pd.read_csv(p)
        req = {"fide_id", "name", "rating", "exact_dob_frozen"}
        missing = req - set(d.columns)
        if missing:
            raise RuntimeError(f"{fname}: missing {sorted(missing)}")

        dob = pd.to_datetime(d["exact_dob_frozen"], errors="coerce")
        if dob.isna().any():
            raise RuntimeError(f"{fname}: unparseable exact_dob_frozen")
        snapshot = pd.Timestamp("1994-01-01" if key.startswith("1994") else "2013-01-01")
        if (dob > snapshot).any():
            bad = d.loc[dob > snapshot, ["fide_id", "name", "exact_dob_frozen"]]
            raise RuntimeError(
                f"{fname}: future DOB survived v3 sanitation:\n"
                + bad.to_string(index=False)
            )
        out[key] = d.copy()
    return out


def enrich_bazi(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for s in df["exact_dob_frozen"].astype(str):
        y, m, d = map(int, s[:10].split("-"))
        rows.append(bazi_features(y, m, d))
    x = pd.concat(
        [df.reset_index(drop=True), pd.DataFrame(rows)],
        axis=1,
    )
    return x


def element_counts(df: pd.DataFrame) -> dict[str, int]:
    vc = df["day_master_element"].value_counts()
    return {e: int(vc.get(e, 0)) for e in ELEMENTS}


def h1_metal_earth_table(d94: pd.DataFrame, d13: pd.DataFrame) -> dict[str, Any]:
    m94 = int((d94["day_master_element"] == "金").sum())
    e94 = int((d94["day_master_element"] == "土").sum())
    m13 = int((d13["day_master_element"] == "金").sum())
    e13 = int((d13["day_master_element"] == "土").sum())

    table = np.array([[m94, e94], [m13, e13]], dtype=int)
    odds, p_two = fisher_exact(table, alternative="two-sided")
    _, p_dir = fisher_exact(table, alternative="greater")

    return {
        "table_rows": ["1994", "2013"],
        "table_cols": ["Metal_DM", "Earth_DM"],
        "table": table.tolist(),
        "odds_ratio_1994_vs_2013": float(odds),
        "fisher_two_sided_p": float(p_two),
        "fisher_directional_p_metal_earlier_earth_later": float(p_dir),
        "analysis_role": CONFIRMATORY_LABEL,
    }


def cmh_metal_earth(bysex: dict[str, pd.DataFrame]) -> dict[str, Any]:
    strata = []
    num_or = 0.0
    den_or = 0.0
    score = 0.0
    variance = 0.0

    for sex in ["M", "F"]:
        a = int((bysex[f"1994_{sex}"]["day_master_element"] == "金").sum())
        b = int((bysex[f"1994_{sex}"]["day_master_element"] == "土").sum())
        c = int((bysex[f"2013_{sex}"]["day_master_element"] == "金").sum())
        d = int((bysex[f"2013_{sex}"]["day_master_element"] == "土").sum())
        n = a + b + c + d

        if n <= 1:
            continue

        row1 = a + b
        row2 = c + d
        col1 = a + c
        col2 = b + d
        ea = row1 * col1 / n
        va = row1 * row2 * col1 * col2 / (n * n * (n - 1))

        score += a - ea
        variance += va
        num_or += a * d / n
        den_or += b * c / n

        strata.append({
            "sex": sex,
            "table": [[a, b], [c, d]],
        })

    z = score / math.sqrt(variance) if variance > 0 else float("nan")
    common_or = num_or / den_or if den_or > 0 else float("inf")

    return {
        "strata": strata,
        "mantel_haenszel_common_odds_ratio": float(common_or),
        "cmh_z_direction_metal_earlier": float(z),
        "cmh_one_sided_p": float(norm.sf(z)),
        "cmh_two_sided_p": float(2 * norm.sf(abs(z))),
        "analysis_role": CONFIRMATORY_LABEL,
    }


def h2_element_distribution(d94: pd.DataFrame, d13: pd.DataFrame) -> dict[str, Any]:
    tab = np.array([
        [element_counts(d94)[e] for e in ELEMENTS],
        [element_counts(d13)[e] for e in ELEMENTS],
    ], dtype=int)

    chi2, p, dof, exp = chi2_contingency(tab)

    return {
        "elements": ELEMENTS,
        "table": tab.tolist(),
        "chi2": float(chi2),
        "df": int(dof),
        "p": float(p),
        "expected": exp.tolist(),
        "analysis_role": CONFIRMATORY_LABEL,
    }


def spearman_metric(df: pd.DataFrame, metric: str) -> dict[str, Any]:
    x = pd.to_numeric(df[metric], errors="raise")
    y = pd.to_numeric(df["elo_z_within_snapshot_sex"], errors="raise")
    if x.nunique() < 2:
        return {"rho": None, "p": None, "n": int(len(df))}
    r = spearmanr(x, y)
    return {
        "rho": float(r.statistic),
        "p": float(r.pvalue),
        "n": int(len(df)),
    }


def build_calendar_feature_cache(years: list[int]) -> dict[int, pd.DataFrame]:
    cache = {}
    for y in sorted(set(years)):
        recs = []
        for m in range(1, 13):
            for d in range(1, calendar.monthrange(y, m)[1] + 1):
                f = bazi_features(y, m, d)
                recs.append({
                    "WaterDM": int(f["day_master_element"] == "水"),
                    "MetalDM": int(f["day_master_element"] == "金"),
                    "EarthDM": int(f["day_master_element"] == "土"),
                    "WaterCount": f["WaterCount"],
                    "MetalWaterCount": f["MetalWaterCount"],
                    "shangguan_count_6pos": f["shangguan_count_6pos"],
                    "pianyin_count_6pos": f["pianyin_count_6pos"],
                })
        cache[y] = pd.DataFrame(recs)
        print(f"[calendar cache] {y}: {len(recs)} dates")
    return cache


def monte_carlo_same_year(
    df: pd.DataFrame,
    cal: dict[int, pd.DataFrame],
    metrics: list[str],
    n_sims: int,
    rng: np.random.Generator,
) -> dict[str, Any]:
    years = pd.to_datetime(df["exact_dob_frozen"]).dt.year.astype(int)
    groups = years.value_counts().sort_index().to_dict()

    obs = {}
    for metric in metrics:
        if metric == "WaterDM":
            obs[metric] = float((df["day_master_element"] == "水").sum())
        elif metric == "MetalDM":
            obs[metric] = float((df["day_master_element"] == "金").sum())
        elif metric == "EarthDM":
            obs[metric] = float((df["day_master_element"] == "土").sum())
        else:
            obs[metric] = float(df[metric].sum())

    sims = {metric: np.zeros(n_sims, dtype=float) for metric in metrics}

    for y, n in groups.items():
        arr = cal[int(y)]
        for metric in metrics:
            values = arr[metric].to_numpy(dtype=float)
            idx = rng.integers(0, len(values), size=(n_sims, int(n)))
            sims[metric] += values[idx].sum(axis=1)

    out = {}
    n = len(df)

    for metric in metrics:
        s = sims[metric]
        o = obs[metric]
        mean = float(s.mean())
        sd = float(s.std(ddof=1))
        z = (o - mean) / sd if sd > 0 else None
        p_hi = (1 + int((s >= o).sum())) / (n_sims + 1)
        p_lo = (1 + int((s <= o).sum())) / (n_sims + 1)

        out[metric] = {
            "observed_sum": o,
            "observed_mean_per_player": o / n,
            "null_mean_sum": mean,
            "null_mean_per_player": mean / n,
            "null_sd_sum": sd,
            "z": float(z) if z is not None else None,
            "empirical_p_high": float(p_hi),
            "empirical_p_low": float(p_lo),
            "n_sims": int(n_sims),
            "null": "uniform Gregorian date within same birth year",
        }

    return out


def plan_markdown(seed: int, n_sims: int) -> str:
    return f"""# Chess BaZi First-Reveal Analysis Plan v1

**Frozen before any chess BaZi calculation/reveal.**

Source cohort tag expected:
`chess-preregister-v3-date-sanity`

## Confirmatory analyses

### C1 — Day-Master five-element distribution
Report 木火土金水 counts and proportions for 1994 vs 2013, separately by sex
and pooled.

### C2 — Metal/Earth temporal gradient
Predefined direction:
- Metal Day Masters relatively more represented in 1994;
- Earth Day Masters relatively more represented in 2013.

Tests:
- Fisher exact test within sex;
- sex-stratified Mantel-Haenszel directional test.

### C3 — Three-pillar 伤官 / 偏印 exposure
Operationalization:
count occurrences across the six known stem/main-qi positions:
year stem, year branch main qi, month stem, month branch main qi,
day stem, day branch main qi.

Report:
- cohort distributions / means;
- Spearman association with `elo_z_within_snapshot_sex`;
- same-birth-year calendar-null enrichment summaries.

## Exploratory analyses fixed before first reveal

These are **not confirmatory hypotheses**.

### E1 — Water Day Master
Report Water-DM frequency and same-birth-year calendar-null comparison.

### E2 — WaterCount
Count Water among the six known stem/main-qi positions, range 0–6.

### E3 — MetalWaterCount
Count Metal + Water among those six positions, range 0–6.

These are exploratory operationalizations of the pre-existing "水主智 / 金水"
idea and must remain labeled exploratory regardless of result.

## Calendar null

For each player independently, sample a Gregorian date uniformly from the
same birth year. This preserves the exact empirical birth-year distribution.

Monte Carlo replicates: **{n_sims}**
Random seed: **{seed}**

The null is used for selection/enrichment-style summaries, not to redefine
the historical-period C1/C2 tests.

## BaZi calculation

Engine: `sxtwl`

Known pillars only:
- year
- month
- day

No birth time is imputed.

No Southern-Hemisphere inversion is used because the source population is the
confirmed-Northern-Hemisphere v3 cohort.

## Multiple testing / interpretation

- C1/C2/C3 are reported as the frozen confirmatory family.
- E1/E2/E3 are reported separately as exploratory.
- Exploratory p-values are descriptive and are not promoted to confirmation.
- Newly noticed patterns after this first reveal remain exploratory.
"""


def markdown_results(
    cohorts: dict[str, pd.DataFrame],
    results: dict[str, Any],
) -> str:
    lines = [
        "# Chess BaZi First Reveal v1",
        "",
        "Confirmatory and exploratory sections are deliberately separated.",
        "",
        "## Confirmatory — Day Master distributions",
        "",
    ]

    for key in ["1994_M", "1994_F", "2013_M", "2013_F"]:
        c = element_counts(cohorts[key])
        n = len(cohorts[key])
        lines.append(
            f"- **{key}** n={n}: "
            + ", ".join(f"{e} {c[e]} ({c[e]/n:.1%})" for e in ELEMENTS)
        )

    lines += [
        "",
        "## Confirmatory — Metal/Earth temporal gradient",
        "",
        "```json",
        json.dumps(results["confirmatory"]["C2_metal_earth"], ensure_ascii=False, indent=2),
        "```",
        "",
        "## Confirmatory — five-element 1994 vs 2013",
        "",
        "```json",
        json.dumps(results["confirmatory"]["C1_day_master_distribution"], ensure_ascii=False, indent=2),
        "```",
        "",
        "## Confirmatory — 伤官 / 偏印 performance",
        "",
        "```json",
        json.dumps(results["confirmatory"]["C3_tengod_performance"], ensure_ascii=False, indent=2),
        "```",
        "",
        "## Exploratory — Water / Metal+Water",
        "",
        "**These analyses are not confirmatory.**",
        "",
    ]

    for key in ["1994_M", "1994_F", "2013_M", "2013_F"]:
        d = cohorts[key]
        lines.append(
            f"- **{key}**: Water DM={(d['day_master_element']=='水').mean():.1%}; "
            f"mean WaterCount={d['WaterCount'].mean():.3f}; "
            f"mean MetalWaterCount={d['MetalWaterCount'].mean():.3f}"
        )

    lines += [
        "",
        "```json",
        json.dumps(results["exploratory"], ensure_ascii=False, indent=2),
        "```",
        "",
    ]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=r"..\1986wiki")
    ap.add_argument("--source-subdir", default="chess_north_v3")
    ap.add_argument("--plan-subdir", default="chess_first_reveal_plan_v1")
    ap.add_argument("--result-subdir", default="chess_first_reveal_v1")
    ap.add_argument("--plan-tag", default="chess-first-reveal-plan-v1")
    ap.add_argument("--result-tag", default="chess-first-reveal-results-v1")
    ap.add_argument("--remote", default="origin")
    ap.add_argument("--seed", type=int, default=20260927)
    ap.add_argument("--null-sims", type=int, default=5000)
    ap.add_argument(
        "--check-only",
        action="store_true",
        help="check dependencies/source files only; does not calculate BaZi",
    )
    args = ap.parse_args()

    repo = git_root(Path(args.repo).resolve())
    source = repo / args.source_subdir
    plan_dir = repo / args.plan_subdir
    result_dir = repo / args.result_subdir

    print("Repo:   ", repo)
    print("Source: ", source)

    cohorts_raw = load_cohorts(source)
    print("Source cohorts passed DOB temporal sanity checks.")

    if args.check_only:
        print("sxtwl import OK.")
        print("--check-only: no BaZi was calculated.")
        return

    if git_tag_exists(repo, args.result_tag):
        raise RuntimeError(
            f"Result tag already exists: {args.result_tag}. "
            "Refusing to overwrite first reveal."
        )

    # ------------------------------------------------------------------
    # PHASE 1: freeze plan BEFORE first BaZi calculation.
    # ------------------------------------------------------------------
    if not git_tag_exists(repo, args.plan_tag):
        ensure_no_staged(repo)
        plan_dir.mkdir(parents=True, exist_ok=True)

        plan_path = plan_dir / "CHESS_ANALYSIS_PLAN_V1.md"
        plan_path.write_text(
            plan_markdown(args.seed, args.null_sims),
            encoding="utf-8",
        )

        script_copy = plan_dir / "run_chess_first_reveal_v1.py"
        shutil.copy2(Path(__file__).resolve(), script_copy)

        source_manifest = {}
        for key, fname in COHORTS.items():
            p = source / fname
            source_manifest[key] = {
                "path": str(p.relative_to(repo)),
                "sha256": sha256(p),
                "n": int(len(cohorts_raw[key])),
            }

        manifest_path = plan_dir / "SOURCE_MANIFEST.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "source_tag": "chess-preregister-v3-date-sanity",
                    "source_files": source_manifest,
                    "seed": args.seed,
                    "null_sims": args.null_sims,
                    "confirmatory": [
                        "C1 Day-Master five-element distribution 1994 vs 2013",
                        "C2 Metal-vs-Earth temporal gradient",
                        "C3 伤官/偏印 six-position exposure and Elo association",
                    ],
                    "exploratory_not_confirmatory": [
                        "E1 Water Day Master",
                        "E2 WaterCount 0..6",
                        "E3 MetalWaterCount 0..6",
                    ],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        stage_exact(repo, [plan_path, script_copy, manifest_path])

        run(
            [
                "git", "commit", "-m",
                "Freeze chess first-reveal analysis plan before BaZi calculation",
            ],
            repo,
        )
        run(
            [
                "git", "tag", "-a", args.plan_tag,
                "-m", "Freeze chess first-reveal analysis plan before BaZi calculation",
            ],
            repo,
        )

        branch = run(["git", "branch", "--show-current"], repo).splitlines()[-1].strip()
        if not branch:
            raise RuntimeError("Detached HEAD; refusing push")
        run(["git", "push", args.remote, branch], repo)
        run(["git", "push", args.remote, args.plan_tag], repo)

        print("\n=== ANALYSIS PLAN FROZEN; FIRST BAZI REVEAL STARTS NOW ===\n")
    else:
        print(
            f"Plan tag {args.plan_tag} already exists; "
            "continuing under the frozen plan."
        )

    # ------------------------------------------------------------------
    # PHASE 2: FIRST BAZI CALCULATION / REVEAL.
    # ------------------------------------------------------------------
    cohorts = {}
    for key in ["1994_M", "1994_F", "2013_M", "2013_F"]:
        print(f"[BaZi] calculating {key} ({len(cohorts_raw[key])} players)")
        cohorts[key] = enrich_bazi(cohorts_raw[key])

    pooled94 = pd.concat([cohorts["1994_M"], cohorts["1994_F"]], ignore_index=True)
    pooled13 = pd.concat([cohorts["2013_M"], cohorts["2013_F"]], ignore_index=True)

    c1 = {
        "M": h2_element_distribution(cohorts["1994_M"], cohorts["2013_M"]),
        "F": h2_element_distribution(cohorts["1994_F"], cohorts["2013_F"]),
        "pooled": h2_element_distribution(pooled94, pooled13),
    }

    c2 = {
        "M": h1_metal_earth_table(cohorts["1994_M"], cohorts["2013_M"]),
        "F": h1_metal_earth_table(cohorts["1994_F"], cohorts["2013_F"]),
        "sex_stratified_CMH": cmh_metal_earth(cohorts),
    }

    c3_perf = {}
    for metric in ["shangguan_count_6pos", "pianyin_count_6pos"]:
        c3_perf[metric] = {}
        for key in ["1994_M", "1994_F", "2013_M", "2013_F"]:
            c3_perf[metric][key] = spearman_metric(cohorts[key], metric)

        all_std = pd.concat(
            [cohorts[k] for k in ["1994_M", "1994_F", "2013_M", "2013_F"]],
            ignore_index=True,
        )
        c3_perf[metric]["pooled_standardized_elo"] = spearman_metric(all_std, metric)

    # Calendar cache only after all actual BaZi values are calculated.
    all_years = []
    for d in cohorts.values():
        all_years += pd.to_datetime(d["exact_dob_frozen"]).dt.year.astype(int).tolist()
    cal = build_calendar_feature_cache(sorted(set(all_years)))

    rng = np.random.default_rng(args.seed)
    null_metrics = [
        "WaterDM",
        "MetalDM",
        "EarthDM",
        "WaterCount",
        "MetalWaterCount",
        "shangguan_count_6pos",
        "pianyin_count_6pos",
    ]

    calendar_null = {}
    for key in ["1994_M", "1994_F", "2013_M", "2013_F"]:
        print(f"[null] {key}: {args.null_sims} same-birth-year simulations")
        calendar_null[key] = monte_carlo_same_year(
            cohorts[key],
            cal,
            metrics=null_metrics,
            n_sims=args.null_sims,
            rng=rng,
        )

    confirmatory = {
        "C1_day_master_distribution": c1,
        "C2_metal_earth": c2,
        "C3_tengod_performance": c3_perf,
        "C3_calendar_null": {
            key: {
                "shangguan_count_6pos": calendar_null[key]["shangguan_count_6pos"],
                "pianyin_count_6pos": calendar_null[key]["pianyin_count_6pos"],
            }
            for key in calendar_null
        },
    }

    exploratory = {
        "analysis_role": EXPLORATORY_LABEL,
        "water_intelligence_proxy_note": (
            "Water-DM, WaterCount, and MetalWaterCount were fixed before first "
            "chess BaZi reveal in this analysis plan but were not part of the "
            "original confirmatory preregistration."
        ),
        "by_cohort": {
            key: {
                "WaterDM_count": int((cohorts[key]["day_master_element"] == "水").sum()),
                "WaterDM_share": float((cohorts[key]["day_master_element"] == "水").mean()),
                "WaterCount_mean": float(cohorts[key]["WaterCount"].mean()),
                "MetalCount_mean": float(cohorts[key]["MetalCount"].mean()),
                "MetalWaterCount_mean": float(cohorts[key]["MetalWaterCount"].mean()),
                "calendar_null": {
                    "WaterDM": calendar_null[key]["WaterDM"],
                    "WaterCount": calendar_null[key]["WaterCount"],
                    "MetalWaterCount": calendar_null[key]["MetalWaterCount"],
                },
            }
            for key in cohorts
        },
    }

    results = {
        "source_tag": "chess-preregister-v3-date-sanity",
        "plan_tag": args.plan_tag,
        "random_seed": args.seed,
        "null_sims": args.null_sims,
        "confirmatory": confirmatory,
        "exploratory": exploratory,
    }

    result_dir.mkdir(parents=True, exist_ok=True)
    generated = []

    for key, d in cohorts.items():
        p = result_dir / f"bazi_{key}.csv"
        d.to_csv(p, index=False, encoding="utf-8-sig")
        generated.append(p)

    counts_rows = []
    for key, d in cohorts.items():
        c = element_counts(d)
        n = len(d)
        for e in ELEMENTS:
            counts_rows.append({
                "cohort": key,
                "element": e,
                "count": c[e],
                "share": c[e] / n,
                "analysis_role": CONFIRMATORY_LABEL,
            })
    counts_path = result_dir / "day_master_element_counts.csv"
    pd.DataFrame(counts_rows).to_csv(
        counts_path, index=False, encoding="utf-8-sig"
    )
    generated.append(counts_path)

    result_json = result_dir / "first_reveal_results.json"
    result_json.write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    generated.append(result_json)

    summary_md = result_dir / "FIRST_REVEAL_SUMMARY.md"
    summary_md.write_text(
        markdown_results(cohorts, results),
        encoding="utf-8",
    )
    generated.append(summary_md)

    ensure_no_staged(repo)
    stage_exact(repo, generated)

    run(
        ["git", "commit", "-m", "Record first chess BaZi preregistered analysis results"],
        repo,
    )
    run(
        [
            "git", "tag", "-a", args.result_tag,
            "-m", "Record immutable first chess BaZi reveal results",
        ],
        repo,
    )

    branch = run(["git", "branch", "--show-current"], repo).splitlines()[-1].strip()
    run(["git", "push", args.remote, branch], repo)
    run(["git", "push", args.remote, args.result_tag], repo)
    commit = run(["git", "rev-parse", "HEAD"], repo).splitlines()[-1]

    # Console headline, deliberately compact so user can paste it back.
    print("\n=== FIRST REVEAL HEADLINE ===")
    for key in ["1994_M", "1994_F", "2013_M", "2013_F"]:
        c = element_counts(cohorts[key])
        d = cohorts[key]
        print(
            f"{key}: n={len(d)} | "
            + " ".join(f"{e}={c[e]}" for e in ELEMENTS)
            + f" | WaterDM={(d['day_master_element']=='水').mean():.3%}"
            + f" | WaterCount={d['WaterCount'].mean():.3f}"
            + f" | MetalWaterCount={d['MetalWaterCount'].mean():.3f}"
        )

    print("\nC2 Metal/Earth sex-stratified CMH:")
    print(json.dumps(c2["sex_stratified_CMH"], ensure_ascii=False, indent=2))

    print("\nExploratory Water/MetalWater same-year null:")
    for key in ["1994_M", "1994_F", "2013_M", "2013_F"]:
        x = exploratory["by_cohort"][key]["calendar_null"]
        print(key)
        print(
            "  WaterDM:",
            json.dumps(x["WaterDM"], ensure_ascii=False),
        )
        print(
            "  WaterCount:",
            json.dumps(x["WaterCount"], ensure_ascii=False),
        )
        print(
            "  MetalWaterCount:",
            json.dumps(x["MetalWaterCount"], ensure_ascii=False),
        )

    print("\n=== DONE ===")
    print("Commit:", commit)
    print("Plan tag:  ", args.plan_tag)
    print("Result tag:", args.result_tag)
    print("Results:", result_dir)


if __name__ == "__main__":
    main()
