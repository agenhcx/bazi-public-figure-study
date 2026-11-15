#!/usr/bin/env python3
"""Execution-gated, post-reveal Nobel birth-decade exploration.

For each integer-valued endpoint, independent year-calendar person variables
are conditioned on their observed cohort total K.  This removes a common
exponential tilt exp(theta * score) of the original calendar probabilities.
Only two global tests per endpoint are inferred; individual bins are descriptive.
"""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
import datetime as dt
from fractions import Fraction
import gzip
import hashlib
import itertools
import json
import math
import multiprocessing as mp
from pathlib import Path
import re
import time
import zipfile

import numpy as np

V4_SHA = "53302ef5c4bbb946adcaceb70d7a7fd576c7f06d03c3e7080874654e1a2644f9"
CALENDAR_SHA = "d150883033464ebd3afafaf764738ed3b573d0d0fb4bd252a955e403a75fcc8b"
HIDDEN_SHA = "19e8bc8648fe8b69122161da260e1dae487816241c655bd96a1273783f1ef723"
GODS = ["比肩", "劫财", "食神", "伤官", "偏财", "正财", "七杀", "正官", "偏印", "正印"]
STEMS = list("甲乙丙丁戊己庚辛壬癸")
SOURCES = ["strict", "expanded"]
DECADES = list(range(1830, 1990, 10))
REPLICATES = 99999
SEED_BASE = 202611160000
CTX = None


def require(condition, message):
    if not bool(condition):
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"


def id_hash(rows):
    return hashlib.sha256(canonical(sorted(r["person_id"] for r in rows)).encode()).hexdigest()


def safe(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {str(k): safe(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [safe(v) for v in value]
    return value


def endpoint_definitions():
    answer = [{"id": "TG_M0_" + g, "kind": "M0_TenGod_count", "label": g,
               "maximum_person_score": 5, "position_denominator": 5}
              for g in GODS]
    answer += [{"id": "DM_" + s, "kind": "DayMaster_indicator", "label": s,
                "maximum_person_score": 1, "position_denominator": 1}
               for s in STEMS]
    answer += [
        {"id": "DM_water", "kind": "DayMaster_indicator", "label": "壬癸水日主",
         "maximum_person_score": 1, "position_denominator": 1},
        {"id": "GY_narrow", "kind": "cooccurrence_indicator", "label": "狭义官印共现",
         "maximum_person_score": 1, "position_denominator": 1},
        {"id": "SGY_narrow", "kind": "cooccurrence_indicator", "label": "狭义伤官配印共现",
         "maximum_person_score": 1, "position_denominator": 1},
        {"id": "M1_priority_PI_count", "kind": "M1_priority_TenGod_count", "label": "优先透干偏印",
         "maximum_person_score": 5, "position_denominator": 5},
        {"id": "M1_priority_SG_count", "kind": "M1_priority_TenGod_count", "label": "优先透干伤官",
         "maximum_person_score": 5, "position_denominator": 5},
    ]
    require(len(answer) == 25, "Fixed endpoint count differs")
    return answer


def test_definitions():
    return [{"test_id": e["id"] + "_" + kind, "endpoint_id": e["id"], "kind": kind}
            for e in endpoint_definitions() for kind in ["heterogeneity", "linear"]]


def holm(values):
    p = np.asarray(values, dtype=float)
    order = np.argsort(p, kind="stable")
    adjusted = np.empty(len(p)); previous = 0.
    for rank, j in enumerate(order):
        previous = max(previous, min(1., (len(p) - rank) * p[j]))
        adjusted[j] = previous
    return adjusted.tolist()


def pmf_for_terms(terms):
    """Full finite-support PMF; term=(person multiplicity, integer day histogram)."""
    p = np.asarray([1.])
    total_people, total_score_cap = 0, 0
    for number, histogram in terms:
        histogram = np.asarray(histogram, dtype=np.int64)
        require(np.all(histogram >= 0) and histogram.sum() > 0, "Invalid calendar histogram")
        last = int(np.flatnonzero(histogram)[-1])
        q = histogram[:last + 1].astype(float) / int(histogram.sum())
        for _ in range(int(number)):
            p = np.convolve(p, q)
        total_people += int(number)
        total_score_cap += int(number) * last
    require(abs(float(p.sum()) - 1.) < 3e-10, "Unconditional bin probability mass differs")
    require(len(p) == total_score_cap + 1, "Bin score support differs")
    return p, total_people


def conditional_structure(bin_pmfs, K):
    K = int(K); m = len(bin_pmfs)
    prefix = [np.asarray([1.])]
    for p in bin_pmfs:
        prefix.append(np.convolve(prefix[-1], p)[:K + 1])
    suffix = [None] * (m + 1); suffix[m] = np.asarray([1.])
    for d in range(m - 1, -1, -1):
        suffix[d] = np.convolve(bin_pmfs[d], suffix[d + 1])[:K + 1]
    require(K < len(prefix[-1]), "Observed total outside calendar support")
    normalizer = float(prefix[-1][K])
    require(normalizer > 0 and math.isfinite(normalizer), "Conditioning event has zero numerical mass")
    marginals, means, variances, fourth = [], [], [], []
    for d, p in enumerate(bin_pmfs):
        others = np.convolve(prefix[d], suffix[d + 1])[:K + 1]
        support = np.arange(min(len(p) - 1, K) + 1)
        weights = np.zeros(len(p), dtype=float)
        keep = K - support < len(others)
        weights[support[keep]] = p[support[keep]] * others[K - support[keep]]
        mass = float(weights.sum())
        require(mass > 0 and abs(mass / normalizer - 1.) < 3e-9, "Conditional marginal mass differs")
        weights /= mass; k = np.arange(len(weights))
        mean = float(k @ weights)
        variance = float(((k - mean) ** 2) @ weights)
        marginals.append(weights); means.append(mean); variances.append(variance)
        fourth.append(float(((k - mean) ** 4) @ weights))
    means = np.asarray(means)
    require(abs(float(means.sum()) - K) < 3e-8, "Conditional expected bin totals do not sum K")
    return {"prefix": prefix, "suffix": suffix, "normalizer": normalizer,
            "marginals": marginals, "means": means,
            "variances": np.asarray(variances), "fourth_central": np.asarray(fourth), "K": K}


def conditional_draws(bin_pmfs, structure, R, seed):
    """Exact conditional bin-count vectors; stable grouping avoids R*K scans."""
    K = structure["K"]; suffix = structure["suffix"]
    rng = np.random.Generator(np.random.PCG64(seed))
    remaining = np.full(R, K, dtype=np.int64)
    output = np.zeros((R, len(bin_pmfs)), dtype=np.int16)
    future_cap = np.cumsum([len(p) - 1 for p in bin_pmfs][::-1])[::-1]
    for d, p in enumerate(bin_pmfs):
        cap = len(p) - 1
        if cap == 0:
            continue
        after_cap = int(future_cap[d + 1]) if d + 1 < len(bin_pmfs) else 0
        order = np.argsort(remaining, kind="stable")
        sorted_remaining = remaining[order].copy()
        starts = np.r_[0, np.flatnonzero(np.diff(sorted_remaining)) + 1, R]
        for first, stop in zip(starts[:-1], starts[1:]):
            r = int(sorted_remaining[first]); rows = order[first:stop]
            lo, hi = max(0, r - after_cap), min(cap, r)
            support = np.arange(lo, hi + 1, dtype=np.int64)
            need = r - support
            weights = np.zeros(len(support))
            valid = need < len(suffix[d + 1])
            weights[valid] = p[support[valid]] * suffix[d + 1][need[valid]]
            mass = float(weights.sum())
            require(mass > 0, "Conditional sampler row has zero probability")
            if len(support) == 1:
                sampled = np.full(len(rows), support[0], dtype=np.int64)
            else:
                cdf = np.cumsum(weights / mass); cdf[-1] = 1.
                sampled = support[np.searchsorted(cdf, rng.random(len(rows)), side="right")]
            output[rows, d] = sampled
            remaining[rows] -= sampled
    require(np.all(remaining == 0) and np.all(output.sum(axis=1) == K), "Conditional sampler violates fixed K")
    return output


def integer_linear_moments(person_terms, K):
    """Integer C/M/S coefficient recurrence for scores c=0..5, no rounding.

    term=(person multiplicity, histogram of eligible date scores, integer x).
    C is an unnormalized probability coefficient; M,S are L and L² moments.
    Products of calendar day denominators cancel after conditioning on total K.
    """
    C, M, S = [0] * (K + 1), [0] * (K + 1), [0] * (K + 1)
    C[0] = 1; processed_cap = 0
    for number, histogram, x in person_terms:
        entries = [(c, int(w), int(x) * c) for c, w in enumerate(histogram) if w]
        cap = entries[-1][0]
        for _ in range(int(number)):
            top = min(K, processed_cap + cap)
            for k in range(top, -1, -1):
                ck = mk = sk = 0
                for c, weight, step in entries:
                    if c > k:
                        break
                    pc, pm, ps = C[k - c], M[k - c], S[k - c]
                    ck += weight * pc
                    mk += weight * (pm + step * pc)
                    sk += weight * (ps + 2 * step * pm + step * step * pc)
                C[k], M[k], S[k] = ck, mk, sk
            processed_cap += cap
    require(C[K] > 0, "Integer conditioning coefficient is zero")
    expected = Fraction(M[K], C[K])
    variance = Fraction(S[K], C[K]) - expected * expected
    require(variance >= 0, "Integer conditional variance is negative")
    return expected, variance, len(str(C[K]))


def reflected_integer_cutoffs(observed, expected):
    observed = int(observed)
    if Fraction(observed) == expected:
        return observed, observed, True
    reflected = 2 * expected - observed
    if observed > expected:
        return reflected.numerator // reflected.denominator, observed, False
    return observed, -((-reflected.numerator) // reflected.denominator), False


def analyze_statistics(bin_pmfs, structure, observed, x, person_terms, seed, R=REPLICATES):
    observed = np.asarray(observed, dtype=np.int64); x = np.asarray(x, dtype=np.int64)
    require(int(observed.sum()) == structure["K"], "Observed fixed K differs")
    means, variances = structure["means"], structure["variances"]
    draws = conditional_draws(bin_pmfs, structure, R, seed)
    mc_mean = draws.mean(axis=0); mc_var = draws.var(axis=0)
    mean_tol = 6 * np.sqrt(variances / R) + 1e-9
    var_tol = 6 * np.sqrt(np.maximum(0., structure["fourth_central"] - variances ** 2) / R) + 1e-8
    require(np.all(np.abs(mc_mean - means) <= mean_tol), "Conditional MC means fail analytic moments")
    require(np.all(np.abs(mc_var - variances) <= var_tol), "Conditional MC variances fail analytic moments")
    positive = variances > 0
    q_obs = float(np.sum((observed[positive] - means[positive]) ** 2 / variances[positive]))
    q_null = np.sum((draws[:, positive] - means[positive]) ** 2 / variances[positive], axis=1)
    q_tol = 1e-12 * max(1., abs(q_obs)); q_extreme = int(np.count_nonzero(q_null >= q_obs - q_tol))
    E, V, digits = integer_linear_moments(person_terms, structure["K"])
    require(abs(float(x @ means) - float(E)) < 3e-8, "Integer and float conditional linear expectation differ")
    l_obs = int(x @ observed); l_null = draws.astype(np.int64) @ x
    require(abs(float(l_null.mean()) - float(E)) <= 6 * math.sqrt(float(V) / R) + 1e-9,
            "MC linear mean fails exact integer moment")
    lower, upper, centered = reflected_integer_cutoffs(l_obs, E)
    l_extreme = R if centered else int(np.count_nonzero((l_null <= lower) | (l_null >= upper)))
    common = {"seed": int(seed), "generator": "PCG64", "replicates": int(R),
              "conditioning": "observed_whole_Nobel_endpoint_total_K_fixed"}
    return {
        "heterogeneity": {**common, "observed_statistic": q_obs,
                          "statistic": "sum_nondegenerate_bins_(O-conditionalE)^2/conditionalVar",
                          "nondegenerate_bins": int(positive.sum()), "floating_inclusive_tolerance": q_tol,
                          "extreme_replicates": q_extreme, "p_nominal": (1 + q_extreme) / (R + 1)},
        "linear": {**common, "observed_integer_L": l_obs, "conditional_expected_L": float(E),
                   "exact_expected_L_numerator": str(E.numerator), "exact_expected_L_denominator": str(E.denominator),
                   "conditional_variance_L": float(V), "integer_coefficient_digits": digits,
                   "lower_inclusive": int(lower), "upper_inclusive": int(upper),
                   "observation_exactly_centered": centered,
                   "tail": "two_sided_absolute_centered_L_exact_rational_reflection_boundaries",
                   "extreme_replicates": l_extreme, "p_nominal": (1 + l_extreme) / (R + 1),
                   "MC_L_mean": float(l_null.mean()), "MC_L_SD": float(l_null.std())},
        "simulation": {**common, "fixed_K_each_draw_verified": True,
                       "bin_MC_means": mc_mean.tolist(), "bin_MC_variances": mc_var.tolist(),
                       "analytic_mean_variance_checks": "PASS"}}


def load_npz(path):
    with np.load(path, allow_pickle=False) as source:
        return {key: source[key] for key in source.files}


def load_inputs(args):
    calendar, hidden = load_npz(args.calendar_npz), load_npz(args.hidden_npz)
    require(calendar["ten_god_names"].tolist() == GODS and calendar["dm_stems"].tolist() == STEMS, "Calendar category order changed")
    require(np.array_equal(calendar["dates"], hidden["dates"]), "Calendar/hidden date alignment changed")
    require(hidden["models"].tolist()[1] == "M1_priority_5", "Priority hidden model index changed")
    require(np.all(hidden["count_scaled72"][:, 1] % 72 == 0), "Priority model no longer an integer count")
    features = np.column_stack([calendar["ten_god_counts"],
                               np.eye(10, dtype=np.int8)[calendar["DM_index"]],
                               calendar["water_DM"], calendar["GY_narrow"], calendar["SGY_narrow"],
                               hidden["count_scaled72"][:, 1, 0] // 72,
                               hidden["count_scaled72"][:, 1, 1] // 72]).astype(np.int8)
    require(features.shape == (55152, 25), "Endpoint calendar feature shape differs")
    require(np.all(features[:, :10].sum(axis=1) == 5), "Five-position totals differ")
    require(np.array_equal(features[:, 20], features[:, 18] + features[:, 19]), "Water/DM calendar mismatch")
    index = {str(d): i for i, d in enumerate(calendar["dates"])}
    with zipfile.ZipFile(args.v4_zip) as archive:
        rows = {}
        for source in SOURCES:
            key = "scientist_north_data_freeze_v4/outputs/" + source + "/Nobel_full_roster_matched_people.jsonl.gz"
            rows[source] = sorted([json.loads(line) for line in gzip.decompress(archive.read(key)).splitlines()],
                                  key=lambda r: r["person_id"])
    require([len(rows[s]) for s in SOURCES] == [621, 627], "Nobel population sizes changed")
    require(all(r["hemisphere"] == "north" for rr in rows.values() for r in rr), "Hemisphere changed")
    for source in SOURCES:
        require(len({r["person_id"] for r in rows[source]}) == len(rows[source]), "Duplicate Nobel person")
        for r in rows[source]:
            r["_calendar_index"] = index[r["analysis_DOB"]]
    n0 = Counter(int(r["analysis_DOB"][:4]) // 10 * 10 for r in rows["strict"])
    n1 = Counter(int(r["analysis_DOB"][:4]) // 10 * 10 for r in rows["expanded"])
    adequate = [d for d in DECADES if n0[d] >= 20 and n1[d] >= 20]
    return calendar, features, rows, adequate


def one_case(endpoint_index, source_index):
    calendar, features, rows_by_source, adequate = CTX
    source = SOURCES[source_index]; rows = rows_by_source[source]
    endpoint = endpoint_definitions()[endpoint_index]; started = time.time()
    endpoint_id = endpoint["id"]; N = len(rows)
    indexes = np.asarray([r["_calendar_index"] for r in rows], dtype=np.int64)
    years = np.asarray([int(r["analysis_DOB"][:4]) for r in rows], dtype=np.int64)
    decades = years // 10 * 10
    observed_person = features[indexes, endpoint_index].astype(np.int64); K = int(observed_person.sum())
    year_counts = Counter(years.tolist()); histograms = {}
    for y in sorted(year_counts):
        values = features[calendar["year"] == y, endpoint_index]
        histograms[y] = np.bincount(values, minlength=endpoint["maximum_person_score"] + 1).astype(np.int64)
    pmfs, bins, person_terms = [], [], []
    for d in DECADES:
        terms = [(year_counts[y], histograms[y]) for y in sorted(year_counts) if y // 10 * 10 == d]
        p, n = pmf_for_terms(terms); pmfs.append(p)
        expected = sum(number * float(np.arange(len(hist)) @ hist) / int(hist.sum()) for number, hist in terms)
        o = int(observed_person[decades == d].sum())
        bins.append({"decade": d, "n": n, "observed_total": o,
                     "observed_mean": o / n if n else None,
                     "calendar_expected_total": expected, "calendar_expected_mean": expected / n if n else None,
                     "adequate_for_descriptive_plot": d in adequate, "local_p_value_computed": False})
        person_terms += [(number, hist.tolist(), (d - 1900) // 10) for number, hist in terms]
    structure = conditional_structure(pmfs, K)
    for b, mean, var in zip(bins, structure["means"], structure["variances"]):
        b.update(conditional_expected_total=float(mean), conditional_expected_mean=float(mean) / b["n"] if b["n"] else None,
                 conditional_variance_total=float(var))
    seed = SEED_BASE + endpoint_index * 1000 + source_index * 100
    stats = analyze_statistics(pmfs, structure, [b["observed_total"] for b in bins],
                               [(d - 1900) // 10 for d in DECADES], person_terms, seed)
    x = (decades - 1900) // 10; sx = int(x.sum()); denominator = int(N * (x @ x) - sx * sx)
    raw_slope = float((N * int(sum(((d - 1900) // 10) * b["observed_total"] for d, b in zip(DECADES, bins))) - sx * K) / denominator)
    E = Fraction(int(stats["linear"]["exact_expected_L_numerator"]), int(stats["linear"]["exact_expected_L_denominator"]))
    conditional_slope = float((N * E - sx * K) / denominator)
    expected_total = float(sum(b["calendar_expected_total"] for b in bins))
    expected_l = sum(((b["decade"] - 1900) // 10) * b["calendar_expected_total"] for b in bins)
    calendar_slope = float((N * expected_l - sx * expected_total) / denominator)
    stats["linear"].update(raw_slope_score_per_decade=raw_slope,
                            calendar_expected_slope_score_per_decade=calendar_slope,
                            conditional_expected_slope_score_per_decade=conditional_slope,
                            conditional_excess_slope_score_per_decade=raw_slope - conditional_slope,
                            slope_x="(floor(birthyear/10)*10-1900)/10", OLS_integer_denominator=denominator)
    result = {"endpoint_id": endpoint_id, "source": source, "people": N, "target_total": K,
              "person_ids_sha256": id_hash(rows), "calendar_year_counts": dict(sorted(year_counts.items())),
              "overall_observed_mean": K / N, "calendar_expected_total": expected_total,
              "calendar_expected_mean": expected_total / N, "local_decades": adequate,
              "bins": bins, "global_tests": {"heterogeneity": stats["heterogeneity"], "linear": stats["linear"]},
              "simulation": stats["simulation"],
              "conditioning_total_probability_under_calendar": structure["normalizer"],
              "inference_role": "post_reveal_exploratory_primary_Holm50" if source == "strict" else "source_sensitivity_reference_not_independent_replication",
              "elapsed_seconds": time.time() - started}
    print(json.dumps({"endpoint": endpoint_id, "source": source, "completed": True,
                      "elapsed_seconds": result["elapsed_seconds"]}), flush=True)
    return result


def verify_gate(args):
    scope = json.loads(Path(args.scope).read_text()); manifest = json.loads(Path(args.locked_files).read_text())
    receipt = json.loads(Path(args.execution_receipt).read_text())
    require(receipt.get("remote_plan_and_code_verified_before_summary") is True or
            receipt.get("remote_Git_lock_verified_before_inference") is True, "Remote execution lock missing")
    require(re.fullmatch(r"[0-9a-f]{40}", receipt.get("commit", receipt.get("lock_commit_sha", ""))) is not None,
            "Execution lock commit missing")
    require(receipt.get("scope_sha256") == sha(args.scope), "Scope digest differs")
    require(receipt.get("locked_file_manifest_sha256") == sha(args.locked_files), "Manifest digest differs")
    own = str(Path(__file__).resolve().relative_to(Path.cwd()))
    require(own in manifest, "This engine is absent from manifest")
    for p, digest in manifest.items():
        require(sha(p) == digest, "Locked file changed: " + p)
    require(sha(args.v4_zip) == V4_SHA, "V4 input pin differs")
    require(sha(args.calendar_npz) == CALENDAR_SHA, "Original calendar pin differs")
    require(sha(args.hidden_npz) == HIDDEN_SHA, "Original hidden pin differs")
    require(scope.get("endpoint_order", [e["id"] for e in endpoint_definitions()]) == [e["id"] for e in endpoint_definitions()], "Endpoint order differs")
    require(scope.get("family_size", 50) == 50, "Family size differs")
    require(not Path(args.output).exists(), "Output exists; refusing overwrite")
    require(1 <= args.workers <= 3, "Worker count must be 1..3")
    return scope, receipt


def synthetic_qa():
    # Independent exact enumeration of six invented three-level people.
    hists = [[2, 1, 1], [1, 2, 1], [1, 1, 2]]
    terms = [[(2, hist)] for hist in hists]; pmfs = [pmf_for_terms(t)[0] for t in terms]
    x = [-1, 0, 2]; K = 5
    structure = conditional_structure(pmfs, K)
    total = Fraction(0); first = Fraction(0); second = Fraction(0)
    margins = [[Fraction(0)] * 5 for _ in range(3)]; vectors = []
    for values in itertools.product(range(3), repeat=6):
        if sum(values) != K:
            continue
        probability = math.prod(Fraction(hists[i // 2][v], sum(hists[i // 2])) for i, v in enumerate(values))
        counts = [sum(values[j:j + 2]) for j in [0, 2, 4]]; L = sum(a * b for a, b in zip(x, counts))
        total += probability; first += probability * L; second += probability * L * L
        for d, k in enumerate(counts):
            margins[d][k] += probability
        vectors.append((counts, probability))
    require(abs(structure["normalizer"] - float(total)) < 1e-14, "Toy conditioning mass")
    for actual, expected in zip(structure["marginals"], margins):
        require(np.allclose(actual, [float(p / total) for p in expected], atol=1e-14), "Toy exact marginal")
    moment_terms = [(2, hist, xx) for hist, xx in zip(hists, x)]
    E, V, _ = integer_linear_moments(moment_terms, K)
    require(E == first / total and V == second / total - E * E, "Toy exact C/M/S moments")
    # Conditioning cancels a common tilt, including a score-two category.
    tilted = []
    for hist in hists:
        q = np.asarray(hist, float) * np.power(2., np.arange(3)); q /= q.sum()
        tilted.append(np.convolve(q, q))
    ts = conditional_structure(tilted, K)
    require(all(np.allclose(a, b, atol=1e-14) for a, b in zip(ts["marginals"], structure["marginals"])), "Exponential tilt cancellation")
    stats = analyze_statistics(pmfs, structure, [0, 1, 4], x, moment_terms, 202611169999, R=19999)
    exact_q = exact_l = Fraction(0); qobs = stats["heterogeneity"]["observed_statistic"]
    lobs = stats["linear"]["observed_integer_L"]
    for counts, p in vectors:
        q = sum((o - mu) ** 2 / var for o, mu, var in zip(counts, structure["means"], structure["variances"]) if var > 0)
        if q >= qobs - 1e-12 * max(1., abs(qobs)):
            exact_q += p / total
        if abs(Fraction(sum(a * b for a, b in zip(x, counts))) - E) >= abs(Fraction(lobs) - E):
            exact_l += p / total
    for kind, expected in [("heterogeneity", float(exact_q)), ("linear", float(exact_l))]:
        tolerance = 6 * math.sqrt(expected * (1 - expected) / 19999) + 2 / 20000
        require(abs(stats[kind]["p_nominal"] - expected) <= tolerance, "Toy sampler tail calibration")
    for k in [0, 12]:
        ss = conditional_structure(pmfs, k)
        dd = conditional_draws(pmfs, ss, 100, 101 + k)
        require(np.all(dd.sum(axis=1) == k), "Toy deterministic total")
    sparse_hist = [2, 0, 1, 0, 0, 1]
    sparse_pmfs = [pmf_for_terms([(2, sparse_hist)])[0], pmf_for_terms([(1, sparse_hist)])[0]]
    sparse_structure = conditional_structure(sparse_pmfs, 7)
    sparse_total = Fraction(0); sparse_first = Fraction(0); sparse_second = Fraction(0)
    for v in itertools.product([0, 2, 5], repeat=3):
        if sum(v) != 7:
            continue
        pp = math.prod(Fraction(sparse_hist[k], 4) for k in v)
        ll = -2 * (v[0] + v[1]) + 3 * v[2]
        sparse_total += pp; sparse_first += pp * ll; sparse_second += pp * ll * ll
    se, sv, _ = integer_linear_moments([(2, sparse_hist, -2), (1, sparse_hist, 3)], 7)
    require(se == sparse_first / sparse_total and sv == sparse_second / sparse_total - se * se,
            "Sparse score-five exact moments")
    sd = conditional_draws(sparse_pmfs, sparse_structure, 1000, 778899)
    require(np.all(sd.sum(axis=1) == 7) and set(np.unique(sd[:, 1])) <= {0, 2, 5},
            "Sparse support inverse-CDF sampler")
    for observed in range(-5, 10):
        lo, hi, centered = reflected_integer_cutoffs(observed, E)
        for L in range(-5, 10):
            require((centered or L <= lo or L >= hi) == (abs(Fraction(L) - E) >= abs(Fraction(observed) - E)), "Exact reflected tails")
    require(np.allclose(holm([.01, .04, .03]), [.03, .06, .06]), "Toy Holm")
    require(len(test_definitions()) == 50, "Fixed family differs")
    return {"schema": "Nobel_discrete_conditional_decade_synthetic_QA_v1", "status": "PASS",
            "study_inputs_loaded": False, "six_ternary_people_exhaustively_enumerated": True,
            "conditional_marginals_and_integer_CMS_moments": True, "exponential_tilt_cancellation": True,
            "score_five_and_sparse_support": True,
            "fixed_total_K0_and_max": True, "inclusive_integer_reflection": True,
            "conditional_MC_tail_checks": {"heterogeneity": {"exact_p": float(exact_q), "MC_p": stats["heterogeneity"]["p_nominal"]},
                                           "linear": {"exact_p": float(exact_l), "MC_p": stats["linear"]["p_nominal"]}},
            "endpoints": 25, "family_size": 50}


def synthetic_benchmark():
    started = time.time(); rng = np.random.Generator(np.random.PCG64(334455))
    ns = rng.multinomial(621, np.full(16, 1 / 16)); hist = [200, 140, 25]; x = list(range(-7, 9)); K = 300
    pmfs = [pmf_for_terms([(int(n), hist)])[0] for n in ns]
    structure = conditional_structure(pmfs, K)
    observed = np.floor(K * ns / 621).astype(int)
    for j in range(K - int(observed.sum())):
        observed[j] += 1
    stats = analyze_statistics(pmfs, structure, observed, x, [(int(n), hist, xx) for n, xx in zip(ns, x)], 202611169998, R=1000)
    return {"schema": "Nobel_decade_synthetic_benchmark_v1", "study_inputs_loaded": False,
            "N": 621, "K": K, "maximum_person_score": 2, "replicates": 1000,
            "seconds": time.time() - started, "status": "PASS", "exact_integer_coefficient_digits": stats["linear"]["integer_coefficient_digits"]}


def main(args):
    global CTX
    if args.synthetic_qa:
        print(json.dumps(synthetic_qa(), ensure_ascii=False, indent=2)); return
    if args.synthetic_benchmark:
        print(json.dumps(synthetic_benchmark(), ensure_ascii=False, indent=2)); return
    scope, receipt = verify_gate(args)
    CTX = load_inputs(args)
    checkpoints = Path(args.output).with_suffix(".checkpoints"); checkpoints.mkdir(exist_ok=False)
    values = {}; tasks = [(i, s) for i in range(25) for s in range(2)]
    with ProcessPoolExecutor(max_workers=args.workers, mp_context=mp.get_context("fork")) as executor:
        futures = {executor.submit(one_case, i, s): (i, s) for i, s in tasks}
        for future in as_completed(futures):
            i, s = futures[future]; value = future.result(); values[(i, s)] = value
            (checkpoints / (str(i).zfill(2) + "_" + SOURCES[s] + ".json")).write_text(json.dumps(safe(value), ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    groups = {e["id"]: {source: values[(i, s)] for s, source in enumerate(SOURCES)} for i, e in enumerate(endpoint_definitions())}
    tests = {}
    for source in SOURCES:
        rows = []
        for e in endpoint_definitions():
            for kind in ["heterogeneity", "linear"]:
                t = groups[e["id"]][source]["global_tests"][kind]
                rows.append({"test_id": e["id"] + "_" + kind, "endpoint_id": e["id"], "kind": kind, "p_nominal": t["p_nominal"]})
        adjusted = holm([r["p_nominal"] for r in rows])
        for r, p in zip(rows, adjusted):
            r.update(p_Holm50_reference=p, primary_exploratory_family=source == "strict",
                     reject_primary_Holm50_0_05=bool(source == "strict" and p <= .05))
            groups[r["endpoint_id"]][source]["global_tests"][r["kind"]].update(p_Holm50_reference=p,
                                                                                 reject_primary_Holm50_0_05=r["reject_primary_Holm50_0_05"])
        tests[source] = rows
    result = {"schema": "Nobel_post_reveal_conditional_birth_decades_v1", "endpoint_order": [e["id"] for e in endpoint_definitions()],
              "endpoint_definitions": endpoint_definitions(), "source_order": SOURCES, "decade_bins": DECADES,
              "adequate_descriptive_decades": CTX[3], "test_definitions": test_definitions(), "family_size": 50,
              "groups": groups, "tests_by_source": tests, "scope": scope, "execution_receipt": receipt,
              "source_pins": {"engine": sha(__file__), "V4": sha(args.v4_zip), "calendar": sha(args.calendar_npz), "hidden": sha(args.hidden_npz)},
              "no_local_decade_p_values": True, "original_global18_unchanged": True,
              "conditional_null": "independent_person_year_calendar_discrete_scores_given_observed_total_K; common_exponential_tilt_cancels",
              "interpretation": "post_reveal_exploration; source_sensitivity_not_independent_validation; no_specific_bin_significance_claim",
              "completed_utc": dt.datetime.now(dt.timezone.utc).isoformat()}
    Path(args.output).write_text(json.dumps(safe(result), ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"status": "PASS", "output": args.output, "endpoints": 25,
                      "primary_Holm50_rejections": sum(t["reject_primary_Holm50_0_05"] for t in tests["strict"])}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["scope", "locked-files", "execution-receipt", "v4-zip", "calendar-npz", "hidden-npz", "output"]:
        parser.add_argument("--" + name)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--synthetic-qa", action="store_true")
    parser.add_argument("--synthetic-benchmark", action="store_true")
    main(parser.parse_args())
