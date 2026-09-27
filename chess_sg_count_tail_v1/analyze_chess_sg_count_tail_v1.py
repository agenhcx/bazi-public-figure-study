#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
analyze_chess_sg_count_tail_v1.py

POST-REVEAL DIAGNOSTIC
======================

Question:
The first reveal found a nominal 伤官-exposure enrichment in 2013 male chess
players (total count higher than same-birth-year calendar null). Is that signal
caused by a heavier upper tail, e.g. more players with 2 or 3+ 伤官 positions?

This script keeps the analysis deliberately narrow.

Observed categories:
  SG_count = 0
  SG_count = 1
  SG_count = 2
  SG_count = 3+

Six known positions only:
  year stem
  year branch main qi
  month stem
  month branch main qi
  day stem
  day branch main qi

No birth hour.
No secondary hidden stems.
No 三合 / 三会 / 六合 / 刑冲 transformations.

For each cohort, it reports:
- observed counts and rates for 0 / 1 / 2 / 3+ 伤官
- same-birth-year exact calendar expected rates
- Monte Carlo expected counts / z / empirical p for:
    * SG_count == 0
    * SG_count == 1
    * SG_count == 2
    * SG_count >= 3
    * SG_count >= 2   (upper-tail summary)
- chi-square goodness-of-fit against the same-birth-year weighted expected
  distribution, reported descriptively because this is post-reveal diagnostic.

Reads:
  chess_first_reveal_v1/bazi_1994_M.csv
  chess_first_reveal_v1/bazi_1994_F.csv
  chess_first_reveal_v1/bazi_2013_M.csv
  chess_first_reveal_v1/bazi_2013_F.csv

Outputs:
  chess_sg_count_tail_v1/
"""

from __future__ import annotations

import argparse
import calendar
import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import chisquare
import sxtwl


STEM_ELEMENT = ["木","木","火","火","土","土","金","金","水","水"]
STEM_YANG = [1,0,1,0,1,0,1,0,1,0]
BRANCH_MAIN_STEM = [9,5,0,1,4,2,3,5,6,7,4,8]

FILES = {
    "1994_M": "bazi_1994_M.csv",
    "1994_F": "bazi_1994_F.csv",
    "2013_M": "bazi_2013_M.csv",
    "2013_F": "bazi_2013_F.csv",
}

CATS = ["0", "1", "2", "3+"]


def run(cmd, cwd, check=True):
    print("$", " ".join(cmd))
    p = subprocess.run(
        cmd, cwd=str(cwd), text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT
    )
    if p.stdout:
        print(p.stdout.rstrip())
    if check and p.returncode != 0:
        raise RuntimeError(
            f"Command failed ({p.returncode}): {' '.join(cmd)}"
        )
    return p.stdout.strip()


def git_root(path):
    out = run(["git","rev-parse","--show-toplevel"], path)
    return Path(out.splitlines()[-1]).resolve()


def tengod(dm, target):
    de = STEM_ELEMENT[dm]
    te = STEM_ELEMENT[target]
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


def six_gods(y, m, d):
    x = sxtwl.fromSolar(int(y), int(m), int(d))
    yg, mg, dg = x.getYearGZ(), x.getMonthGZ(), x.getDayGZ()

    stems = [
        yg.tg,
        BRANCH_MAIN_STEM[yg.dz],
        mg.tg,
        BRANCH_MAIN_STEM[mg.dz],
        dg.tg,
        BRANCH_MAIN_STEM[dg.dz],
    ]
    return [tengod(dg.tg, s) for s in stems]


def sg_count_from_row(row):
    raw = str(row.get("six_position_tengods", "")).strip()
    gods = raw.split("|") if raw else []

    if len(gods) != 6:
        dt = pd.Timestamp(str(row["exact_dob_frozen"])[:10])
        gods = six_gods(dt.year, dt.month, dt.day)

    return sum(g == "伤官" for g in gods)


def cat_from_count(n):
    if n <= 0:
        return "0"
    if n == 1:
        return "1"
    if n == 2:
        return "2"
    return "3+"


def year_table(year):
    rows = []
    for m in range(1, 13):
        for d in range(1, calendar.monthrange(year, m)[1] + 1):
            sg = sum(
                g == "伤官"
                for g in six_gods(year, m, d)
            )
            rows.append({
                "SG_count": sg,
                "SG_cat": cat_from_count(sg),
                "SG_ge2": int(sg >= 2),
                "SG_ge3": int(sg >= 3),
            })
    return pd.DataFrame(rows)


def weighted_expected_probs(years, cache):
    probs = {c: [] for c in CATS}
    ge2 = []
    ge3 = []

    for y in years.astype(int):
        t = cache[int(y)]
        for c in CATS:
            probs[c].append(float((t["SG_cat"] == c).mean()))
        ge2.append(float(t["SG_ge2"].mean()))
        ge3.append(float(t["SG_ge3"].mean()))

    return {
        "cat_probs": {c: float(np.mean(probs[c])) for c in CATS},
        "ge2": float(np.mean(ge2)),
        "ge3": float(np.mean(ge3)),
    }


def monte_carlo(years, cache, n_sims, rng):
    counts = {c: np.zeros(n_sims, dtype=int) for c in CATS}
    ge2 = np.zeros(n_sims, dtype=int)
    ge3 = np.zeros(n_sims, dtype=int)

    by_year = years.value_counts().sort_index().to_dict()

    for y, n in by_year.items():
        t = cache[int(y)]
        vals = t["SG_count"].to_numpy(dtype=int)
        idx = rng.integers(
            0, len(vals),
            size=(n_sims, int(n)),
        )
        sampled = vals[idx]

        counts["0"] += (sampled == 0).sum(axis=1)
        counts["1"] += (sampled == 1).sum(axis=1)
        counts["2"] += (sampled == 2).sum(axis=1)
        counts["3+"] += (sampled >= 3).sum(axis=1)
        ge2 += (sampled >= 2).sum(axis=1)
        ge3 += (sampled >= 3).sum(axis=1)

    return counts, ge2, ge3


def stat_from_sims(obs, sims, n):
    mean = float(sims.mean())
    sd = float(sims.std(ddof=1))
    return {
        "observed_count": int(obs),
        "observed_rate": float(obs / n),
        "null_mean_count": mean,
        "null_mean_rate": float(mean / n),
        "null_sd_count": sd,
        "z": float((obs - mean) / sd) if sd > 0 else None,
        "empirical_p_high": float(
            (1 + int((sims >= obs).sum())) / (len(sims) + 1)
        ),
        "empirical_p_low": float(
            (1 + int((sims <= obs).sum())) / (len(sims) + 1)
        ),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=r"..\1986wiki")
    ap.add_argument(
        "--source-subdir",
        default="chess_first_reveal_v1"
    )
    ap.add_argument(
        "--output-subdir",
        default="chess_sg_count_tail_v1"
    )
    ap.add_argument(
        "--tag",
        default="chess-postreveal-sg-count-tail-v1"
    )
    ap.add_argument("--remote", default="origin")
    ap.add_argument("--seed", type=int, default=20260927)
    ap.add_argument("--null-sims", type=int, default=20000)
    ap.add_argument("--no-git", action="store_true")
    a = ap.parse_args()

    repo = git_root(Path(a.repo).resolve())
    src = repo / a.source_subdir
    out = repo / a.output_subdir
    out.mkdir(parents=True, exist_ok=True)

    cohorts = {}
    all_years = []

    for key, fname in FILES.items():
        p = src / fname
        if not p.exists():
            raise FileNotFoundError(p)

        d = pd.read_csv(p)
        need = {
            "fide_id","name","rating",
            "exact_dob_frozen",
            "elo_z_within_snapshot_sex",
        }
        miss = need - set(d.columns)
        if miss:
            raise RuntimeError(
                f"{fname}: missing {sorted(miss)}"
            )

        d["SG_count_diag"] = d.apply(
            sg_count_from_row, axis=1
        )
        d["SG_cat_diag"] = d["SG_count_diag"].map(
            cat_from_count
        )
        d["SG_ge2_diag"] = d["SG_count_diag"] >= 2
        d["SG_ge3_diag"] = d["SG_count_diag"] >= 3

        cohorts[key] = d
        all_years += (
            pd.to_datetime(d["exact_dob_frozen"])
            .dt.year.astype(int).tolist()
        )

    cache = {}
    for y in sorted(set(all_years)):
        cache[y] = year_table(y)
        print(f"[calendar] {y}: {len(cache[y])} dates")

    rng = np.random.default_rng(a.seed)

    rows = []
    result = {
        "analysis_role": "post_reveal_exploratory_diagnostic",
        "question": "Is the 2013M SG exposure signal driven by a heavier SG-count upper tail?",
        "categories": CATS,
        "null_sims": a.null_sims,
        "seed": a.seed,
        "cohorts": {},
    }

    for key in ["1994_M","1994_F","2013_M","2013_F"]:
        d = cohorts[key]
        n = len(d)
        years = pd.to_datetime(
            d["exact_dob_frozen"]
        ).dt.year.astype(int)

        obs_counts = {
            c: int((d["SG_cat_diag"] == c).sum())
            for c in CATS
        }
        obs_ge2 = int(d["SG_ge2_diag"].sum())
        obs_ge3 = int(d["SG_ge3_diag"].sum())

        weighted = weighted_expected_probs(years, cache)
        sims, sims_ge2, sims_ge3 = monte_carlo(
            years, cache, a.null_sims, rng
        )

        cres = {
            "n": n,
            "observed_categories": {
                c: {
                    "count": obs_counts[c],
                    "rate": obs_counts[c] / n,
                }
                for c in CATS
            },
            "weighted_exact_expected_categories": weighted["cat_probs"],
            "monte_carlo": {
                c: stat_from_sims(
                    obs_counts[c], sims[c], n
                )
                for c in CATS
            },
            "upper_tail_ge2": stat_from_sims(
                obs_ge2, sims_ge2, n
            ),
            "upper_tail_ge3": stat_from_sims(
                obs_ge3, sims_ge3, n
            ),
        }

        # Descriptive GOF vs weighted expected category probabilities.
        exp_counts = np.array(
            [weighted["cat_probs"][c] * n for c in CATS],
            dtype=float,
        )
        obs_vec = np.array(
            [obs_counts[c] for c in CATS],
            dtype=float,
        )

        # Ensure exact equal total despite floating rounding.
        exp_counts *= obs_vec.sum() / exp_counts.sum()

        gof = chisquare(
            f_obs=obs_vec,
            f_exp=exp_counts,
        )
        cres["chi_square_gof_descriptive"] = {
            "chi2": float(gof.statistic),
            "df": 3,
            "p": float(gof.pvalue),
            "note": "post-reveal descriptive diagnostic",
        }

        result["cohorts"][key] = cres

        for c in CATS:
            rows.append({
                "cohort": key,
                "category": c,
                "observed_count": obs_counts[c],
                "observed_rate": obs_counts[c] / n,
                "expected_rate": weighted["cat_probs"][c],
                "expected_count": weighted["cat_probs"][c] * n,
                "z": cres["monte_carlo"][c]["z"],
                "p_high": cres["monte_carlo"][c]["empirical_p_high"],
                "p_low": cres["monte_carlo"][c]["empirical_p_low"],
            })

    out_csv = out / "sg_count_distribution_by_cohort.csv"
    pd.DataFrame(rows).to_csv(
        out_csv, index=False, encoding="utf-8-sig"
    )

    out_json = out / "sg_count_tail_results.json"
    out_json.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    md = [
        "# Chess SG-count Tail Diagnostic v1",
        "",
        "**Post-reveal exploratory diagnostic.**",
        "",
        "Categories: 0 / 1 / 2 / 3+ 伤官 across the six known positions.",
        "",
        "No birth hour, no secondary hidden stems, no 三合/三会/六合 transformations.",
        "",
    ]

    for key in ["1994_M","1994_F","2013_M","2013_F"]:
        x = result["cohorts"][key]
        md.append(f"## {key}")
        md.append("")
        for c in CATS:
            o = x["observed_categories"][c]
            e = x["weighted_exact_expected_categories"][c]
            z = x["monte_carlo"][c]["z"]
            ph = x["monte_carlo"][c]["empirical_p_high"]
            md.append(
                f"- SG={c}: observed {o['count']}/{x['n']} "
                f"({o['rate']:.1%}), expected {e:.1%}, "
                f"z={z:.3f}, p_high={ph:.4f}"
            )
        u = x["upper_tail_ge2"]
        md.append(
            f"- **SG>=2:** observed {u['observed_count']}/{x['n']} "
            f"({u['observed_rate']:.1%}), null {u['null_mean_rate']:.1%}, "
            f"z={u['z']:.3f}, p_high={u['empirical_p_high']:.4f}"
        )
        md.append("")

    out_md = out / "SG_COUNT_TAIL_DIAGNOSTIC.md"
    out_md.write_text(
        "\n".join(md),
        encoding="utf-8"
    )

    script_copy = out / "analyze_chess_sg_count_tail_v1.py"
    shutil.copy2(Path(__file__).resolve(), script_copy)

    generated = [
        out_csv, out_json, out_md, script_copy
    ]

    print("\n=== SG COUNT TAIL DIAGNOSTIC ===")
    for key in ["1994_M","1994_F","2013_M","2013_F"]:
        x = result["cohorts"][key]
        parts = []
        for c in CATS:
            o = x["observed_categories"][c]
            e = x["weighted_exact_expected_categories"][c]
            parts.append(
                f"{c}:{o['rate']:.2%} vs {e:.2%}"
            )
        u = x["upper_tail_ge2"]
        print(
            f"{key}: "
            + " | ".join(parts)
            + f" | SG>=2 {u['observed_rate']:.2%} "
              f"vs {u['null_mean_rate']:.2%}, "
              f"z={u['z']:.3f}, "
              f"p_high={u['empirical_p_high']:.4f}"
        )

    if a.no_git:
        print("\n--no-git: generated results; Git untouched.")
        return

    staged = run(
        ["git","diff","--cached","--name-only"],
        repo
    ).strip()
    if staged:
        raise RuntimeError(
            "Git index already has staged files:\n" + staged
        )

    if run(
        ["git","tag","--list",a.tag],
        repo
    ).strip():
        raise RuntimeError(
            f"Tag already exists: {a.tag}"
        )

    rels = [str(p.relative_to(repo)) for p in generated]
    run(["git","add","--",*rels], repo)
    run(
        [
            "git","commit","-m",
            "Add post-reveal chess SG-count tail diagnostic"
        ],
        repo
    )
    run(
        [
            "git","tag","-a",a.tag,
            "-m","Record post-reveal SG-count tail diagnostic"
        ],
        repo
    )

    branch = run(
        ["git","branch","--show-current"],
        repo
    ).splitlines()[-1].strip()

    run(["git","push",a.remote,branch], repo)
    run(["git","push",a.remote,a.tag], repo)

    commit = run(
        ["git","rev-parse","HEAD"],
        repo
    ).splitlines()[-1]

    print("\n=== DONE ===")
    print("Commit:", commit)
    print("Tag:   ", a.tag)
    print("Output:", out)


if __name__ == "__main__":
    main()
