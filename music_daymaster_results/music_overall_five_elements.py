#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Music overall Five-Element composition analysis (Y/M/D, main-qi version).

Default discovery sample:
    1986 1987 1988 1989

Definition of "overall Five Elements"
-------------------------------------
For each person, use exactly 6 equally weighted components:

    年干
    年支本气
    月干
    月支本气
    日干
    日支本气

Each component contributes 1 count to one of:
    木 火 土 金 水

So every included person contributes exactly 6 element units.

Why this version?
-----------------
- No birth hour is available.
- No arbitrary weighting of hidden stems is introduced.
- Branches are represented by their main hidden stem / 本气.
- Transition-ambiguous dates (where year/month pillar changes during the civil date)
  are excluded because exact birth time is unknown.

Null model
----------
Matched to the ACTUAL Gregorian birth-year composition of the Music sample.

For each birth year:
1) Enumerate all civil dates.
2) Exclude transition-ambiguous dates using the same rule as the observed sample.
3) Calculate the 6-component element vector for every eligible date.

Monte Carlo then samples dates within each birth year, preserving:
- cohort sizes,
- leap-year structure,
- sexagenary/calendar dependence,
- within-chart dependence among the 6 components.

This avoids the incorrect assumption that the 6*N element slots are independent.

Scopes
------
full:
    all Music-classified people

known:
    Music people with known P19/P625 latitude

north:
    Music people with birth latitude > 0

Recommended now:
    python music_overall_five_elements.py --years 1986 1987 1988 1989

Do NOT include 1990-1992 until any new hypotheses are frozen/preregistered.
"""

import argparse
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from lunar_python import Solar


ELEMENTS = ["木", "火", "土", "金", "水"]

STEM_ELEMENT = {
    "甲":"木","乙":"木",
    "丙":"火","丁":"火",
    "戊":"土","己":"土",
    "庚":"金","辛":"金",
    "壬":"水","癸":"水",
}

# Main hidden stem / 本气 for every earthly branch.
BRANCH_MAIN_STEM = {
    "子":"癸","丑":"己","寅":"甲","卯":"乙","辰":"戊","巳":"丙",
    "午":"丁","未":"己","申":"庚","酉":"辛","戌":"戊","亥":"壬",
}


def all_dates_in_year(y):
    d = date(int(y), 1, 1)
    end = date(int(y), 12, 31)
    while d <= end:
        yield d
        d += timedelta(days=1)


def eight_char_at(y, m, d, hour=12, minute=0):
    ec = Solar.fromYmdHms(
        int(y), int(m), int(d), int(hour), int(minute), 0
    ).getLunar().getEightChar()
    return {
        "year": ec.getYear(),
        "month": ec.getMonth(),
        "day": ec.getDay(),
    }


def transition_ambiguous(y, m, d):
    a = eight_char_at(y, m, d, 0, 30)
    b = eight_char_at(y, m, d, 22, 30)
    return (
        a["year"] != b["year"]
        or a["month"] != b["month"]
    )


def element_vector_for_date(y, m, d):
    """
    Returns:
      vector [木,火,土,金,水] counts, summing to exactly 6
      plus audit fields
    """
    ec = eight_char_at(y, m, d, 12, 0)

    yp = ec["year"]
    mp = ec["month"]
    dp = ec["day"]

    ys, yb = yp[0], yp[1]
    ms, mb = mp[0], mp[1]
    ds, db = dp[0], dp[1]

    components = [
        ("year_stem", ys, STEM_ELEMENT[ys]),
        ("year_branch_main", BRANCH_MAIN_STEM[yb], STEM_ELEMENT[BRANCH_MAIN_STEM[yb]]),
        ("month_stem", ms, STEM_ELEMENT[ms]),
        ("month_branch_main", BRANCH_MAIN_STEM[mb], STEM_ELEMENT[BRANCH_MAIN_STEM[mb]]),
        ("day_stem", ds, STEM_ELEMENT[ds]),
        ("day_branch_main", BRANCH_MAIN_STEM[db], STEM_ELEMENT[BRANCH_MAIN_STEM[db]]),
    ]

    cnt = Counter(x[2] for x in components)
    vec = np.array([cnt[e] for e in ELEMENTS], dtype=int)

    if int(vec.sum()) != 6:
        raise RuntimeError(f"Element vector does not sum to 6: {(y,m,d)} {vec}")

    return {
        "year_pillar": yp,
        "month_pillar": mp,
        "day_pillar": dp,
        "year_stem_element": STEM_ELEMENT[ys],
        "year_branch_main_stem": BRANCH_MAIN_STEM[yb],
        "year_branch_main_element": STEM_ELEMENT[BRANCH_MAIN_STEM[yb]],
        "month_stem_element": STEM_ELEMENT[ms],
        "month_branch_main_stem": BRANCH_MAIN_STEM[mb],
        "month_branch_main_element": STEM_ELEMENT[BRANCH_MAIN_STEM[mb]],
        "day_stem_element": STEM_ELEMENT[ds],
        "day_branch_main_stem": BRANCH_MAIN_STEM[db],
        "day_branch_main_element": STEM_ELEMENT[BRANCH_MAIN_STEM[db]],
        **{f"n_{e}": int(vec[i]) for i, e in enumerate(ELEMENTS)},
    }


def build_calendar_baseline(years):
    """
    For each Gregorian year, store every eligible date's 5-element vector.
    """
    baseline = {}

    print("Building matched-calendar baseline...")

    for y in sorted(set(map(int, years))):
        rows = []
        excluded = 0

        for dt in all_dates_in_year(y):
            if transition_ambiguous(dt.year, dt.month, dt.day):
                excluded += 1
                continue

            x = element_vector_for_date(dt.year, dt.month, dt.day)
            rows.append([x[f"n_{e}"] for e in ELEMENTS])

        arr = np.asarray(rows, dtype=np.int16)

        baseline[y] = {
            "vectors": arr,
            "n_dates": len(arr),
            "excluded_transition_dates": excluded,
            "mean_vector": arr.mean(axis=0),
        }

        means = ", ".join(
            f"{e}={baseline[y]['mean_vector'][i]:.3f}"
            for i, e in enumerate(ELEMENTS)
        )
        print(
            f"  {y}: eligible dates={len(arr)}, "
            f"transition excluded={excluded}, mean counts/date: {means}"
        )

    return baseline


def load_music_people(root, years):
    frames = []

    for y in years:
        p = root / f"hemisphere_{y}" / f"{y}_people_with_hemisphere.csv"
        if not p.exists():
            raise SystemExit(
                f"Missing {p}\n"
                f"Run the hemisphere crawler for {y} first."
            )

        d = pd.read_csv(p, encoding="utf-8-sig")

        required = ["_music", "_birth_date_norm", "hemisphere"]
        missing = [c for c in required if c not in d.columns]
        if missing:
            raise SystemExit(f"{p} missing columns: {missing}")

        d = d.loc[
            pd.to_numeric(d["_music"], errors="coerce")
            .fillna(0).astype(int) == 1
        ].copy()

        d["dob"] = pd.to_datetime(
            d["_birth_date_norm"], errors="coerce"
        )
        d = d.loc[d["dob"].notna()].copy()
        d["birth_year"] = d["dob"].dt.year.astype(int)
        d["source_year"] = int(y)

        # Exclude transition-ambiguous dates.
        amb = []
        feat = []
        for dt in d["dob"]:
            is_amb = transition_ambiguous(dt.year, dt.month, dt.day)
            amb.append(is_amb)
            feat.append(
                None if is_amb
                else element_vector_for_date(dt.year, dt.month, dt.day)
            )

        d["pillar_transition_ambiguous"] = amb
        d = d.loc[~d["pillar_transition_ambiguous"]].copy()

        kept_feat = [
            x for x in feat if x is not None
        ]
        # feat order matches original d before filtering; rebuild safely:
        feat_map = {}
        for dt in d["dob"]:
            key = dt.strftime("%Y-%m-%d")
            if key not in feat_map:
                feat_map[key] = element_vector_for_date(
                    dt.year, dt.month, dt.day
                )

        for col in [
            "year_pillar","month_pillar","day_pillar",
            "year_stem_element",
            "year_branch_main_stem","year_branch_main_element",
            "month_stem_element",
            "month_branch_main_stem","month_branch_main_element",
            "day_stem_element",
            "day_branch_main_stem","day_branch_main_element",
        ] + [f"n_{e}" for e in ELEMENTS]:
            d[col] = [
                feat_map[dt.strftime("%Y-%m-%d")][col]
                for dt in d["dob"]
            ]

        frames.append(d)

    if not frames:
        raise SystemExit("No Music rows loaded.")

    return pd.concat(frames, ignore_index=True)


def filter_scope(d, scope):
    if scope == "full":
        return d.copy()
    if scope == "known":
        return d.loc[
            d["hemisphere"].isin(["north","south","equator"])
        ].copy()
    if scope == "north":
        return d.loc[d["hemisphere"] == "north"].copy()
    raise ValueError(scope)


def expected_total_vector(rows, baseline):
    yc = Counter(int(y) for y in rows["birth_year"])
    out = np.zeros(5, dtype=float)

    for y, n in yc.items():
        out += n * baseline[y]["mean_vector"]

    return out


def observed_total_vector(rows):
    return np.array(
        [rows[f"n_{e}"].sum() for e in ELEMENTS],
        dtype=float
    )


def simulate_totals(rows, baseline, reps, seed):
    """
    Monte Carlo null preserving observed Music N in each Gregorian birth year.
    Each synthetic person draws one eligible civil date from their birth year,
    and receives the entire 6-component element vector of that date.

    Returns an array shape (reps, 5).
    """
    rng = np.random.default_rng(seed)
    yc = Counter(int(y) for y in rows["birth_year"])

    sims = np.zeros((reps, 5), dtype=np.int32)

    # Chunk over years; each person's full vector stays intact.
    for y, n in sorted(yc.items()):
        arr = baseline[y]["vectors"]
        n_dates = len(arr)

        # Sample counts in chunks to avoid an enormous (reps x n x 5) tensor.
        chunk_people = 256
        remaining = n

        while remaining > 0:
            k = min(chunk_people, remaining)
            idx = rng.integers(
                0, n_dates, size=(reps, k), endpoint=False
            )
            drawn = arr[idx]  # reps x k x 5
            sims += drawn.sum(axis=1, dtype=np.int32)
            remaining -= k

    return sims


def empirical_pvals(obs, sims):
    """
    Conservative +1 empirical tails.
    """
    reps = sims.shape[0]
    out = []

    for j, e in enumerate(ELEMENTS):
        o = obs[j]
        s = sims[:, j]

        p_upper = (np.sum(s >= o) + 1) / (reps + 1)
        p_lower = (np.sum(s <= o) + 1) / (reps + 1)
        p_two = min(1.0, 2.0 * min(p_upper, p_lower))

        out.append({
            "element": e,
            "p_lower": p_lower,
            "p_upper_enrichment": p_upper,
            "p_two_sided": p_two,
        })

    return out


def holm_adjust(vals):
    p = list(map(float, vals))
    m = len(p)
    order = sorted(range(m), key=lambda i: p[i])

    out = [None] * m
    running = 0.0

    for rank, idx in enumerate(order):
        a = min(1.0, (m-rank)*p[idx])
        running = max(running, a)
        out[idx] = running

    return out


def global_stat(vec, exp):
    # Pearson-style discrepancy on element totals.
    return float(np.sum((vec-exp)**2 / exp))


def analyze_scope(rows, baseline, scope, reps, seed):
    x = filter_scope(rows, scope)

    if len(x) == 0:
        return None

    obs = observed_total_vector(x)
    exp = expected_total_vector(x, baseline)
    total_slots = 6 * len(x)

    sims = simulate_totals(
        x, baseline, reps=reps, seed=seed
    )

    pinfo = empirical_pvals(obs, sims)

    result = []
    for j, e in enumerate(ELEMENTS):
        r = pinfo[j]
        result.append({
            "scope": scope,
            "element": e,
            "music_people_n": len(x),
            "total_element_slots": total_slots,
            "observed_count": int(obs[j]),
            "observed_share": obs[j]/total_slots,
            "observed_mean_per_person": obs[j]/len(x),
            "expected_count": exp[j],
            "expected_share": exp[j]/total_slots,
            "expected_mean_per_person": exp[j]/len(x),
            "enrichment": obs[j]/exp[j],
            "difference_count": obs[j]-exp[j],
            "difference_mean_per_person": (obs[j]-exp[j])/len(x),
            "p_lower": r["p_lower"],
            "p_upper_enrichment": r["p_upper_enrichment"],
            "p_two_sided": r["p_two_sided"],
        })

    adjusted = holm_adjust(
        [r["p_two_sided"] for r in result]
    )
    for r, a in zip(result, adjusted):
        r["p_holm_5"] = a

    summary = pd.DataFrame(result)

    obs_stat = global_stat(obs, exp)
    sim_stats = np.sum(
        (sims-exp[None,:])**2 / exp[None,:],
        axis=1
    )
    global_p = (
        np.sum(sim_stats >= obs_stat - 1e-12) + 1
    ) / (reps + 1)

    global_result = {
        "scope": scope,
        "music_people_n": len(x),
        "pearson_like_stat": obs_stat,
        "mc_reps": reps,
        "mc_global_p": global_p,
    }

    # Distribution of per-person counts 0..6 for each element.
    dist_rows = []
    for e in ELEMENTS:
        vc = x[f"n_{e}"].value_counts().to_dict()
        for k in range(7):
            dist_rows.append({
                "scope": scope,
                "element": e,
                "count_within_person": k,
                "people_n": int(vc.get(k, 0)),
                "people_pct": vc.get(k, 0) / len(x),
            })

    dist = pd.DataFrame(dist_rows)

    return summary, pd.DataFrame([global_result]), dist, x


def write_summary(results, years, outdir):
    lines = [
        "Music overall Five-Element composition analysis",
        f"Years: {', '.join(map(str, years))}",
        "",
        "Definition:",
        "  6 equally weighted components per person:",
        "  year stem + year branch main qi + month stem + month branch main qi",
        "  + day stem + day branch main qi.",
        "",
        "Transition-ambiguous dates are excluded.",
        "Null is matched to actual Music birth-year composition.",
        "Monte Carlo samples whole date-level 6-component vectors, preserving",
        "within-chart dependence rather than treating 6*N slots as independent.",
        "",
    ]

    for scope, (tbl, glob, dist, people) in results.items():
        lines += [
            "="*84,
            f"SCOPE: {scope}",
            f"Music N: {len(people):,}",
            f"Element slots: {6*len(people):,}",
            "",
            "FIVE ELEMENTS, sorted by enrichment:",
        ]

        for _, r in tbl.sort_values(
            "enrichment", ascending=False
        ).iterrows():
            lines.append(
                f"  {r['element']}: "
                f"obs={int(r['observed_count'])} "
                f"({100*r['observed_share']:.2f}%, "
                f"mean/person={r['observed_mean_per_person']:.3f}), "
                f"exp={r['expected_count']:.1f} "
                f"({100*r['expected_share']:.2f}%, "
                f"mean/person={r['expected_mean_per_person']:.3f}), "
                f"enrichment={r['enrichment']:.3f}, "
                f"p_upper={r['p_upper_enrichment']:.6g}, "
                f"p2={r['p_two_sided']:.6g}, "
                f"Holm={r['p_holm_5']:.6g}"
            )

        gr = glob.iloc[0]
        lines += [
            "",
            f"GLOBAL: Pearson-like={gr['pearson_like_stat']:.4f}, "
            f"MonteCarlo p={gr['mc_global_p']:.6g} "
            f"({int(gr['mc_reps'])} reps)",
            "",
        ]

    lines += [
        "Guardrail:",
        "  1986-1989 are exploratory/discovery for this Five-Element composition question.",
        "  Do not inspect 1990-1992 until any new hypotheses are frozen/preregistered.",
        "",
        "Scope interpretation:",
        "  full  = all Music people.",
        "  known = only people with known P19/P625 latitude.",
        "  north = known latitude > 0.",
    ]

    (outdir / "music_overall_five_elements_summary.txt").write_text(
        "\n".join(lines), encoding="utf-8"
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--years",
        nargs="+",
        type=int,
        default=[1986, 1987, 1988, 1989],
    )
    ap.add_argument(
        "--outdir",
        default="music_overall_five_elements_results",
    )
    ap.add_argument(
        "--mc-reps",
        type=int,
        default=100000,
    )
    ap.add_argument(
        "--seed",
        type=int,
        default=20260926,
    )
    args = ap.parse_args()

    root = Path(".").resolve()
    outdir = root / args.outdir
    outdir.mkdir(parents=True, exist_ok=True)

    music = load_music_people(root, args.years)

    print(f"Loaded eligible Music people: {len(music):,}")
    print(
        f"Excluded transition-ambiguous Music dates already during loading."
    )

    baseline = build_calendar_baseline(
        music["birth_year"].tolist()
    )

    results = {}
    summaries = []
    globals_ = []
    dists = []

    for i, scope in enumerate(["full", "known", "north"]):
        print(f"\nAnalyzing scope: {scope}")
        r = analyze_scope(
            music,
            baseline,
            scope,
            reps=args.mc_reps,
            seed=args.seed + 100*i,
        )
        if r is None:
            continue

        tbl, glob, dist, people = r
        results[scope] = r

        summaries.append(tbl)
        globals_.append(glob)
        dists.append(dist)

        tbl.to_csv(
            outdir / f"{scope}_five_element_summary.csv",
            index=False,
            encoding="utf-8-sig",
        )
        glob.to_csv(
            outdir / f"{scope}_global_test.csv",
            index=False,
            encoding="utf-8-sig",
        )
        dist.to_csv(
            outdir / f"{scope}_per_person_element_count_distribution.csv",
            index=False,
            encoding="utf-8-sig",
        )

        print(
            tbl[
                [
                    "element",
                    "observed_count",
                    "observed_share",
                    "expected_count",
                    "expected_share",
                    "enrichment",
                    "p_upper_enrichment",
                    "p_two_sided",
                    "p_holm_5",
                ]
            ].sort_values(
                "enrichment", ascending=False
            ).to_string(index=False)
        )

        print(
            f"Global MC p = "
            f"{float(glob.iloc[0]['mc_global_p']):.6g}"
        )

    pd.concat(
        summaries, ignore_index=True
    ).to_csv(
        outdir / "all_scopes_five_element_summary.csv",
        index=False,
        encoding="utf-8-sig",
    )

    pd.concat(
        globals_, ignore_index=True
    ).to_csv(
        outdir / "all_scopes_global_tests.csv",
        index=False,
        encoding="utf-8-sig",
    )

    pd.concat(
        dists, ignore_index=True
    ).to_csv(
        outdir / "all_scopes_per_person_element_count_distribution.csv",
        index=False,
        encoding="utf-8-sig",
    )

    # Audit-level person file.
    music.to_csv(
        outdir / "music_people_with_6component_elements.csv",
        index=False,
        encoding="utf-8-sig",
    )

    write_summary(
        results, args.years, outdir
    )

    print(f"\nSaved under: {outdir}")
    print("Main file: music_overall_five_elements_summary.txt")


if __name__ == "__main__":
    main()
