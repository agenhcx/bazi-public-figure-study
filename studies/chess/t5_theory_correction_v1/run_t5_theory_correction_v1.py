#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import calendar
import json
from pathlib import Path

import numpy as np
import pandas as pd
import sxtwl

STEMS = list("甲乙丙丁戊己庚辛壬癸")
BRANCHES = list("子丑寅卯辰巳午未申酉戌亥")
STEM_ELEMENT = ["木","木","火","火","土","土","金","金","水","水"]
STEM_YANG = [1,0,1,0,1,0,1,0,1,0]
HIDDEN_STEMS = {
    0:[9], 1:[5,9,7], 2:[0,2,4], 3:[1], 4:[4,1,9], 5:[2,4,6],
    6:[3,5], 7:[5,3,1], 8:[6,8,4], 9:[7], 10:[4,7,3], 11:[8,0],
}
BRANCH_MAIN_STEM = [HIDDEN_STEMS[i][0] for i in range(12)]

COHORTS = {
    "2013_M_DISCOVERY": "chess_north_v3/primary_north_top_2013_M.csv",
    "2023_M_FULL": "chess_2023_cohorts_v1/primary_2023_M_FULL.csv",
    "2023_M_NEW_TARGET": "chess_2023_cohorts_v1/validation_2023_M_NEW_TARGET.csv",
}

B = 200_000
SEED = 20261010


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


def date_state(y: int, m: int, d: int) -> tuple[bool, bool, bool]:
    x = sxtwl.fromSolar(int(y), int(m), int(d))
    yg, mg, dg = x.getYearGZ(), x.getMonthGZ(), x.getDayGZ()
    dm = int(dg.tg)
    targets = [
        int(yg.tg), BRANCH_MAIN_STEM[int(yg.dz)],
        int(mg.tg), BRANCH_MAIN_STEM[int(mg.dz)],
        int(dg.tg), BRANCH_MAIN_STEM[int(dg.dz)],
    ]
    gods = [ten_god(dm, t) for t in targets]
    return ("伤官" in gods, "正官" in gods, dm == 6)


def year_profile(y: int) -> dict:
    rows = []
    for m in range(1, 13):
        for d in range(1, calendar.monthrange(int(y), m)[1] + 1):
            ho, do, geng = date_state(y, m, d)
            rows.append((ho, do, geng))
    a = np.asarray(rows, dtype=bool)
    ho = a[:,0]
    do = a[:,1]
    geng = a[:,2]

    def frac(mask):
        n = int(mask.sum())
        if n == 0:
            raise RuntimeError(f"{y}: empty conditional calendar subset")
        return float((do & mask).sum() / n), n

    p_h, n_h = frac(ho)
    p_gh, n_gh = frac(ho & geng)
    p_nh, n_nh = frac(ho & ~geng)
    return {
        "p_do_given_ho": p_h,
        "n_ho_dates": n_h,
        "p_do_given_geng_ho": p_gh,
        "n_geng_ho_dates": n_gh,
        "p_do_given_nongeng_ho": p_nh,
        "n_nongeng_ho_dates": n_nh,
    }


def simulate_group(years: pd.Series, p_by_year: dict[int,float], rng: np.random.Generator):
    n = len(years)
    if n == 0:
        return None
    sims = np.zeros(B, dtype=np.int32)
    for y, ny in years.value_counts().sort_index().items():
        sims += rng.binomial(int(ny), float(p_by_year[int(y)]), size=B)
    return sims.astype(float) / n


def tail_stats(obs: float, sims: np.ndarray) -> dict:
    mu = float(sims.mean())
    sd = float(sims.std(ddof=1))
    p_low = float((1 + np.sum(sims <= obs)) / (len(sims) + 1))
    p_high = float((1 + np.sum(sims >= obs)) / (len(sims) + 1))
    return {
        "observed": float(obs),
        "null_mean": mu,
        "ratio": float(obs / mu) if mu > 0 else None,
        "delta": float(obs - mu),
        "z": float((obs - mu) / sd) if sd > 0 else None,
        "p_depletion": p_low,
        "p_enrichment": p_high,
        "p_two_sided": float(min(1.0, 2 * min(p_low, p_high))),
        "null_sd": sd,
        "simulations": len(sims),
    }


def analyze_cohort(repo: Path, label: str, relpath: str, cache: dict, seed_offset: int):
    df = pd.read_csv(repo / relpath)
    dates = pd.to_datetime(df["exact_dob_frozen"])
    obs_rows = []
    for dt in dates:
        ho, do, geng = date_state(dt.year, dt.month, dt.day)
        obs_rows.append((dt.year, ho, do, geng))
    obs = pd.DataFrame(obs_rows, columns=["year","ho","do","geng"])

    h = obs[obs.ho].copy()
    gh = h[h.geng].copy()
    nh = h[~h.geng].copy()

    if len(h) == 0 or len(gh) == 0 or len(nh) == 0:
        raise RuntimeError(f"{label}: empty observed subgroup")

    p_h = {y: cache[y]["p_do_given_ho"] for y in h.year.unique()}
    p_gh = {y: cache[y]["p_do_given_geng_ho"] for y in gh.year.unique()}
    p_nh = {y: cache[y]["p_do_given_nongeng_ho"] for y in nh.year.unique()}

    rng_h = np.random.default_rng(SEED + seed_offset + 1)
    rng_g = np.random.default_rng(SEED + seed_offset + 2)
    rng_n = np.random.default_rng(SEED + seed_offset + 3)

    sim_h = simulate_group(h.year, p_h, rng_h)
    sim_g = simulate_group(gh.year, p_gh, rng_g)
    sim_n = simulate_group(nh.year, p_nh, rng_n)

    obs_h = float(h.do.mean())
    obs_g = float(gh.do.mean())
    obs_n = float(nh.do.mean())

    t5 = tail_stats(obs_h, sim_h)
    geng = tail_stats(obs_g, sim_g)
    nongeng = tail_stats(obs_n, sim_n)

    # Geng exception interaction: positive means Geng is less depleted / more enriched
    # than non-Geng after each subgroup's own exact-year conditional calendar baseline.
    exp_g = geng["null_mean"]
    exp_n = nongeng["null_mean"]
    obs_interaction = (obs_g - exp_g) - (obs_n - exp_n)
    sim_interaction = (sim_g - exp_g) - (sim_n - exp_n)
    interaction = tail_stats(obs_interaction, sim_interaction)

    return {
        "n_total": int(len(obs)),
        "n_ho": int(len(h)),
        "n_geng_total": int(obs.geng.sum()),
        "n_geng_ho": int(len(gh)),
        "n_nongeng_ho": int(len(nh)),
        "t5_do_given_ho": t5,
        "geng_do_given_ho": geng,
        "nongeng_do_given_ho": nongeng,
        "geng_exception_interaction": interaction,
    }


def main():
    repo = Path(__file__).resolve().parents[3]
    years = set()
    for relpath in COHORTS.values():
        d = pd.read_csv(repo / relpath)
        years.update(pd.to_datetime(d["exact_dob_frozen"]).dt.year.astype(int).tolist())

    cache = {}
    for y in sorted(years):
        cache[int(y)] = year_profile(int(y))

    results = {
        "analysis_role": "post_reveal_theory_aligned_exploratory_correction",
        "does_not_replace_frozen_t5": True,
        "representation": "M0 six known Y/M/D positions, branch main qi; Day Stem self-position contributes neither HO nor DO",
        "null": "exact birth year; calendar dates additionally conditioned on the relevant anchor (HO, Geng+HO, or nonGeng+HO)",
        "direction_t5": "depletion: P(DO|HO) < calendar-conditioned expectation",
        "direction_geng_exception": "positive interaction: Geng is less depleted / more enriched than non-Geng after subgroup-specific calendar centering",
        "simulations": B,
        "seed": SEED,
        "cohorts": {},
    }

    for j, (label, relpath) in enumerate(COHORTS.items()):
        results["cohorts"][label] = analyze_cohort(repo, label, relpath, cache, 10000*j)

    # Archived-summary reproduction guardrail for NEW_TARGET.
    n = results["cohorts"]["2023_M_NEW_TARGET"]
    checks = {
        "t5_obs_vs_archived_0.3178": abs(n["t5_do_given_ho"]["observed"] - 0.3178),
        "t5_null_vs_archived_0.3621": abs(n["t5_do_given_ho"]["null_mean"] - 0.3621),
        "geng_obs_vs_archived_0.2000": abs(n["geng_do_given_ho"]["observed"] - 0.2000),
        "geng_null_vs_archived_0.3264": abs(n["geng_do_given_ho"]["null_mean"] - 0.3264),
    }
    results["reproduction_check_abs_diff"] = checks
    results["reproduction_check_pass"] = bool(max(checks.values()) < 0.01)

    outdir = Path(__file__).resolve().parent
    (outdir / "t5_theory_correction_results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    lines = []
    lines += [
        "T5 THEORY-ALIGNED CORRECTION V1",
        "="*88,
        "POST-REVEAL EXPLORATORY CORRECTION; DOES NOT REPLACE FROZEN T5/T5G.",
        f"Monte Carlo B={B:,}; seed={SEED}",
        "",
    ]
    for label, r in results["cohorts"].items():
        t, g, ng, ix = (
            r["t5_do_given_ho"], r["geng_do_given_ho"],
            r["nongeng_do_given_ho"], r["geng_exception_interaction"],
        )
        lines += [
            label,
            "-"*88,
            f"N={r['n_total']} | HO+={r['n_ho']} | Geng={r['n_geng_total']} | Geng+HO={r['n_geng_ho']} | nonGeng+HO={r['n_nongeng_ho']}",
            f"T5 DO|HO: obs={t['observed']:.6f} null={t['null_mean']:.6f} ratio={t['ratio']:.4f} delta={t['delta']:+.6f} z={t['z']:+.3f} p_deplete={t['p_depletion']:.6g} p_enrich={t['p_enrichment']:.6g} p2={t['p_two_sided']:.6g}",
            f"Geng DO|HO: obs={g['observed']:.6f} null={g['null_mean']:.6f} ratio={g['ratio']:.4f} delta={g['delta']:+.6f} z={g['z']:+.3f} p_deplete={g['p_depletion']:.6g} p_enrich={g['p_enrichment']:.6g} p2={g['p_two_sided']:.6g}",
            f"nonGeng DO|HO: obs={ng['observed']:.6f} null={ng['null_mean']:.6f} ratio={ng['ratio']:.4f} delta={ng['delta']:+.6f} z={ng['z']:+.3f} p_deplete={ng['p_depletion']:.6g} p_enrich={ng['p_enrichment']:.6g} p2={ng['p_two_sided']:.6g}",
            f"Geng exception interaction: I={ix['observed']:+.6f} null={ix['null_mean']:+.6f} z={ix['z']:+.3f} p_exception_positive={ix['p_enrichment']:.6g} p_negative={ix['p_depletion']:.6g} p2={ix['p_two_sided']:.6g}",
            "",
        ]

    lines += [
        "REPRODUCTION CHECK — 2023_M_NEW_TARGET",
        "-"*88,
        *[f"{k} = {v:.6g}" for k,v in checks.items()],
        f"PASS (<0.01 each): {results['reproduction_check_pass']}",
        "",
        "INTERPRETATION GUARDRAIL",
        "The corrected depletion direction and Geng interaction were specified after the original results were visible.",
        "Therefore all p-values in this correction are exploratory/descriptive, regardless of nominal significance.",
    ]
    summary = "\n".join(lines)
    (outdir / "t5_theory_correction_summary.txt").write_text(summary, encoding="utf-8")
    print(summary)

    if not results["reproduction_check_pass"]:
        raise SystemExit("Archived T5/T5G reproduction check failed; do not interpret correction.")


if __name__ == "__main__":
    main()
