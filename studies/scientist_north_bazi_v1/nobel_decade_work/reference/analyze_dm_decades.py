#!/usr/bin/env python3
"""Two targeted post-reveal DayMaster decade analyses, conditional on total K.

Only CAS Xin and NAS Water are authorized.  Real-data execution requires a
remotely verified scope/manifest receipt. Import and synthetic QA load no study
rows. Per-person calendar probabilities remain fixed by Gregorian birthyear.
"""
import argparse
from collections import Counter
import datetime as dt
from fractions import Fraction
import gzip
import hashlib
import itertools
import json
import math
from pathlib import Path
import zipfile

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
TARGET_ORDER = ["CAS_xin", "NAS_water"]
SOURCE_ORDER = ["strict", "expanded"]
TARGET_CONFIG = {
    "CAS_xin": {"institution": "CAS", "label": "中国科学院辛日主", "day_stem_indices": [7],
                "local_decades": list(range(1890, 1970, 10))},
    "NAS_water": {"institution": "NAS", "label": "美国科学院壬癸水日主", "day_stem_indices": [8, 9],
                  "local_decades": list(range(1890, 1960, 10))},
}
DECADES = list(range(1830, 1990, 10))
V4_SHA = "53302ef5c4bbb946adcaceb70d7a7fd576c7f06d03c3e7080874654e1a2644f9"
CALENDAR_SHA = "d150883033464ebd3afafaf764738ed3b573d0d0fb4bd252a955e403a75fcc8b"
REPLICATES = 99999
SEED_BASE = 202611240000


def require(ok, message):
    if not bool(ok):
        raise AssertionError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def id_hash(ids):
    raw = json.dumps(sorted(ids), ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    return hashlib.sha256(raw.encode()).hexdigest()


def holm(values):
    order = sorted(range(len(values)), key=lambda j: (values[j], j))
    adjusted, running = [0.] * len(values), 0.
    for rank, j in enumerate(order):
        require(0 <= values[j] <= 1, "p outside [0,1]")
        running = max(running, min(1., (len(values) - rank) * values[j]))
        adjusted[j] = running
    return adjusted


def test_definitions():
    definitions = []
    for target in TARGET_ORDER:
        definitions += [{"test_id": f"{target}_local_{d}", "target": target, "kind": "local", "decade": d}
                        for d in TARGET_CONFIG[target]["local_decades"]]
        definitions += [{"test_id": target + "_heterogeneity", "target": target, "kind": "global_heterogeneity"},
                        {"test_id": target + "_linear", "target": target, "kind": "global_linear"}]
    require(len(definitions) == 19, "Fixed exploratory family must contain19tests")
    return definitions


def pmf_for_year_terms(terms):
    """terms=(people, successful dates, total dates), preserving person unit."""
    probability = np.array([1.])
    expected = Fraction(0)
    count = 0
    for n, success, days in sorted(terms):
        require(n >= 0 and 0 <= success <= days and days > 0, "Invalid year probability")
        q = success / days
        for _ in range(int(n)):
            probability = np.convolve(probability, [1 - q, q])
        expected += n * Fraction(int(success), int(days))
        count += n
    require(len(probability) == count + 1 and np.all(probability >= 0), "Count support differs")
    require(abs(float(probability.sum()) - 1.) < 1e-10, "Unconditional PMF mass differs")
    probability /= probability.sum()
    return probability, expected


def conditional_structure(bin_pmfs, K):
    """Prefix/suffix convolution and all exact-support conditional marginals.

    PMF weights are float64. Truncation at K discards only coefficients that
    cannot contribute to the conditioning event, without a probability cutoff.
    """
    m = len(bin_pmfs)
    n_total = sum(len(p) - 1 for p in bin_pmfs)
    require(0 <= K <= n_total, "Conditioning K outside support")
    prefix = [np.asarray([1.])]
    for p in bin_pmfs:
        prefix.append(np.convolve(prefix[-1], p)[:K + 1])
    suffix = [None] * (m + 1)
    suffix[m] = np.asarray([1.])
    for d in range(m - 1, -1, -1):
        suffix[d] = np.convolve(bin_pmfs[d], suffix[d + 1])[:K + 1]
    normalizer = float(prefix[-1][K])
    require(normalizer > 0 and math.isfinite(normalizer), "Conditioning event has zero numerical mass")
    marginals, means, variances, fourth = [], [], [], []
    for d, p in enumerate(bin_pmfs):
        others = np.convolve(prefix[d], suffix[d + 1])[:K + 1]
        weights = np.zeros(len(p), dtype=float)
        for k in range(min(len(p) - 1, K) + 1):
            if K - k < len(others):
                weights[k] = p[k] * others[K - k]
        mass = float(weights.sum())
        require(mass > 0 and abs(mass / normalizer - 1.) < 2e-10, "Conditional marginal mass mismatch")
        weights /= mass
        support = np.arange(len(weights))
        mean = float(np.dot(support, weights))
        variance = float(np.dot((support - mean) ** 2, weights))
        marginals.append(weights)
        means.append(mean)
        variances.append(variance)
        fourth.append(float(np.dot((support - mean) ** 4, weights)))
    means = np.asarray(means)
    require(abs(float(means.sum()) - K) < 2e-8, "Conditional expected bin counts do not sumK")
    return {"prefix": prefix, "suffix": suffix, "normalizer": normalizer,
            "marginals": marginals, "means": means, "variances": np.asarray(variances),
            "fourth_central": np.asarray(fourth), "N": n_total, "K": K}


def conditional_draws(bin_pmfs, structure, R, seed):
    """Forward-back grouped-bin draws, fixing K in every simulated vector."""
    K, suffix = structure["K"], structure["suffix"]
    rng = np.random.Generator(np.random.PCG64(seed))
    remaining = np.full(R, K, dtype=np.int64)
    result = np.zeros((R, len(bin_pmfs)), dtype=np.int16)
    future_n = np.cumsum([len(p) - 1 for p in bin_pmfs][::-1])[::-1]
    for d, p in enumerate(bin_pmfs):
        n = len(p) - 1
        if n == 0:
            continue
        after_n = int(future_n[d + 1]) if d + 1 < len(bin_pmfs) else 0
        for r in np.unique(remaining):
            rows = np.flatnonzero(remaining == r)
            lo, hi = max(0, int(r) - after_n), min(n, int(r))
            support = np.arange(lo, hi + 1, dtype=np.int64)
            weights = np.asarray([p[k] * suffix[d + 1][int(r) - k]
                                  if int(r) - k < len(suffix[d + 1]) else 0.
                                  for k in support], dtype=float)
            require(float(weights.sum()) > 0, "Conditional sampling row has zero mass")
            if len(support) == 1:
                sampled = np.full(len(rows), support[0], dtype=np.int64)
            else:
                cdf = np.cumsum(weights / weights.sum())
                cdf[-1] = 1.
                sampled = support[np.searchsorted(cdf, rng.random(len(rows)), side="right")]
            result[rows, d] = sampled
            remaining[rows] -= sampled
    require(np.all(remaining == 0) and np.all(result.sum(axis=1) == K), "Simulated fixedK violated")
    return result


def integer_linear_moments(person_terms, K):
    """Exact integer coefficients C,M,S; common product(days) cancels givenK.

    Each term=(number of people, success-day count, total-day count, decade x).
    M_k is the unnormalized first moment of L=sum(x_i*indicator_i), S_k second.
    """
    C, M, S = [0] * (K + 1), [0] * (K + 1), [0] * (K + 1)
    C[0] = 1
    processed = 0
    for n, success, days, x in sorted(person_terms):
        success, fail, x = int(success), int(days - success), int(x)
        for _ in range(int(n)):
            top = min(K, processed + 1)
            for k in range(top, 0, -1):
                prev_c, prev_m, prev_s = C[k - 1], M[k - 1], S[k - 1]
                C[k] = fail * C[k] + success * prev_c
                M[k] = fail * M[k] + success * (prev_m + x * prev_c)
                S[k] = fail * S[k] + success * (prev_s + 2 * x * prev_m + x * x * prev_c)
            C[0] *= fail
            M[0] *= fail
            S[0] *= fail
            processed += 1
    require(C[K] > 0, "Integer conditioning coefficient is zero")
    expected = Fraction(M[K], C[K])
    variance = Fraction(S[K], C[K]) - expected * expected
    require(variance >= 0, "Exact conditional variance negative")
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
    observed = np.asarray(observed, dtype=np.int64)
    require(int(observed.sum()) == structure["K"], "Observed fixedK differs")
    means, variances = structure["means"], structure["variances"]
    draws = conditional_draws(bin_pmfs, structure, R, seed)
    mc_mean = draws.mean(axis=0)
    mc_var = draws.var(axis=0)
    mean_tolerance = 6 * np.sqrt(variances / R) + 1e-9
    variance_tolerance = 6 * np.sqrt(np.maximum(0., structure["fourth_central"] - variances ** 2) / R) + 1e-8
    require(np.all(np.abs(mc_mean - means) <= mean_tolerance), "Conditional MC means fail analytic moments")
    require(np.all(np.abs(mc_var - variances) <= variance_tolerance), "Conditional MC variances fail analytic moments")
    positive = variances > 0
    q_observed = float(np.sum((observed[positive] - means[positive]) ** 2 / variances[positive]))
    q_null = np.sum((draws[:, positive] - means[positive]) ** 2 / variances[positive], axis=1)
    q_tolerance = 1e-12 * max(1., abs(q_observed))
    q_extreme = int(np.count_nonzero(q_null >= q_observed - q_tolerance))
    E, V, coefficient_digits = integer_linear_moments(person_terms, structure["K"])
    x = np.asarray(x, dtype=np.int64)
    l_observed = int(np.dot(x, observed))
    l_null = draws.astype(np.int64) @ x
    require(abs(float(np.dot(x, means)) - float(E)) < 2e-8, "Integer and float conditional linear E differ")
    l_variance = float(V)
    require(abs(float(l_null.mean()) - float(E)) <= 6 * math.sqrt(l_variance / R) + 1e-9,
            "Conditional MC linear mean differs")
    lower, upper, centered = reflected_integer_cutoffs(l_observed, E)
    l_extreme = R if centered else int(np.count_nonzero((l_null <= lower) | (l_null >= upper)))
    common = {"seed": int(seed), "generator": "PCG64", "replicates": int(R),
              "conditioning": "observed_full_cohort_target_total_K_fixed"}
    return {
        "heterogeneity": {**common, "observed_statistic": q_observed,
                          "statistic": "sum_nonzero_variance_bins_(O-conditionalE)^2/conditionalVar",
                          "floating_inclusive_tolerance": q_tolerance,
                          "extreme_replicates": q_extreme, "p_nominal": (q_extreme + 1) / (R + 1),
                          "MC_statistic_mean": float(q_null.mean())},
        "linear": {**common, "observed_integer_L": l_observed, "conditional_expected_L": float(E),
                   "exact_expected_L_numerator": str(E.numerator), "exact_expected_L_denominator": str(E.denominator),
                   "conditional_variance_L": l_variance, "integer_coefficient_digits": coefficient_digits,
                   "lower_inclusive": int(lower), "upper_inclusive": int(upper),
                   "observation_exactly_centered": centered,
                   "tail": "two_sided_absolute_centered_L_exact_rational_reflection_boundaries",
                   "extreme_replicates": l_extreme, "p_nominal": (l_extreme + 1) / (R + 1),
                   "MC_L_mean": float(l_null.mean()), "MC_L_SD": float(l_null.std())},
        "simulation": {**common, "fixedK_each_draw_verified": True,
                       "bin_MC_means": mc_mean.tolist(), "bin_MC_variances": mc_var.tolist(),
                       "analytic_bin_mean_and_variance_checks": "PASS"}}


def synthetic_qa():
    # Six artificial people in3bins, with different rational probabilities.
    terms = [[(2, 1, 3)], [(2, 1, 2)], [(2, 2, 3)]]
    pmfs = [pmf_for_year_terms(t)[0] for t in terms]
    x = [-1, 0, 2]
    K = 3
    structure = conditional_structure(pmfs, K)
    total, marginals = Fraction(0), [[Fraction(0)] * 3 for _ in terms]
    first, second = Fraction(0), Fraction(0)
    probabilities = [Fraction(1, 3)] * 2 + [Fraction(1, 2)] * 2 + [Fraction(2, 3)] * 2
    exact_vectors = []
    for bits in itertools.product([0, 1], repeat=6):
        if sum(bits) != K:
            continue
        p = math.prod(q if bit else 1 - q for q, bit in zip(probabilities, bits))
        counts = [sum(bits[j:j + 2]) for j in [0, 2, 4]]
        L = sum(a * b for a, b in zip(x, counts))
        total += p; first += p * L; second += p * L * L
        for d, k in enumerate(counts):
            marginals[d][k] += p
        exact_vectors.append((counts, p))
    require(abs(structure["normalizer"] - float(total)) < 1e-14, "Toy conditioning mass")
    for d in range(3):
        require(np.allclose(structure["marginals"][d], [float(p / total) for p in marginals[d]], atol=1e-14),
                "Toy exact conditional marginal")
    moment_terms = [(2, 1, 3, -1), (2, 1, 2, 0), (2, 2, 3, 2)]
    E, V, _ = integer_linear_moments(moment_terms, K)
    require(E == first / total and V == second / total - E * E, "Toy integer exact moments")
    for observed in range(-2, 5):
        lo, hi, centered = reflected_integer_cutoffs(observed, E)
        for support in range(-2, 5):
            require((centered or support <= lo or support >= hi) == (abs(Fraction(support) - E) >= abs(Fraction(observed) - E)),
                    "Exact reflected inclusive boundary")
    stats = analyze_statistics(pmfs, structure, np.asarray([0, 1, 2]), x, moment_terms, 202611249999, R=29999)
    qobs = stats["heterogeneity"]["observed_statistic"]
    lobs = stats["linear"]["observed_integer_L"]
    exact_q, exact_l = Fraction(0), Fraction(0)
    for vector, probability in exact_vectors:
        q = sum((o - m) ** 2 / v for o, m, v in zip(vector, structure["means"], structure["variances"]) if v > 0)
        L = sum(a * b for a, b in zip(x, vector))
        if q >= qobs - 1e-12 * max(1., abs(qobs)):
            exact_q += probability / total
        if abs(Fraction(L) - E) >= abs(Fraction(lobs) - E):
            exact_l += probability / total
    for key, p in [("heterogeneity", float(exact_q)), ("linear", float(exact_l))]:
        tolerance = 6 * math.sqrt(p * (1 - p) / 29999) + 2 / 30000
        require(abs(stats[key]["p_nominal"] - p) <= tolerance, "Toy MC tail differs from exact enumeration")
    for k in [0, 6]:
        s = conditional_structure(pmfs, k)
        draw = conditional_draws(pmfs, s, 100, 202611249998 + k)
        require(np.all(draw.sum(axis=1) == k), "DeterministicK toy failure")
    require(holm([.01, .04, .03]) == [.03, .06, .06], "Holm toy")
    require(len(test_definitions()) == 19, "Synthetic fixed family")
    return {"schema": "DM_decade_conditional_synthetic_QA_v1", "status": "PASS", "study_inputs_loaded": False,
            "exact_enumeration_people": 6, "exact_enumeration_conditioning_K": 3,
            "conditional_marginals_and_integer_linear_moments": True, "inclusive_reflected_tails": True,
            "conditional_sampler_exact_tail_MC_checks": {"heterogeneity": {"exact_p": float(exact_q), "MC_p": stats['heterogeneity']['p_nominal']},
                                                        "linear": {"exact_p": float(exact_l), "MC_p": stats['linear']['p_nominal']}},
            "deterministic_K0_KN": True, "fixed_test_family": 19}


def read_v4_rows(archive, path):
    return [json.loads(line) for line in gzip.decompress(archive.read("scientist_north_data_freeze_v4/outputs/" + path)).splitlines()]


def selected_people(archive, institution, source, expected):
    rows = read_v4_rows(archive, source + "/by_institution/" + institution + ".jsonl.gz")
    no_nobel = {r["person_id"] for r in read_v4_rows(archive, source + "/academy_excluding_official_Nobel.jsonl.gz")}
    people = {r["person_id"]: r for r in rows if r["person_id"] in no_nobel}
    require(len(people) == expected["people"] and id_hash(people) == expected["person_ids_sha256"], "Frozen target population differs")
    require(all(p["hemisphere"] == "north" and not p["person_level_DOB_analysis_hold"] for p in people.values()), "Frozen target holds differ")
    for p in people.values():
        date = dt.date.fromisoformat(p["analysis_DOB"])
        require(dt.date(1835, 1, 1) <= date <= dt.date(1985, 12, 31), "Frozen DOB window differs")
    return [people[k] for k in sorted(people)]


def one_group(target, source, rows, dates, years, target_feature, scope, target_index, source_index):
    date_lookup = {str(d): i for i, d in enumerate(dates)}
    indexes = np.asarray([date_lookup[p["analysis_DOB"]] for p in rows], dtype=np.intp)
    birthyears = years[indexes].astype(np.int64)
    decade = birthyears // 10 * 10
    observed_feature = target_feature[indexes]
    N, K = len(rows), int(observed_feature.sum())
    year_counts = Counter(int(y) for y in birthyears)
    year_cal = {}
    for y in year_counts:
        feature = target_feature[years == y]
        require(len(feature) in [365, 366], "Calendar year not complete")
        year_cal[y] = (int(feature.sum()), len(feature))
    bin_pmfs, bins, person_terms = [], [], []
    raw_calendar_E_L = Fraction(0)
    raw_calendar_E_K = Fraction(0)
    for d in DECADES:
        mask = decade == d
        actual = Counter(int(y) for y in birthyears[mask])
        terms = [(n, *year_cal[y]) for y, n in actual.items()]
        probability, expectation = pmf_for_year_terms(terms)
        bin_pmfs.append(probability)
        n, observed = int(mask.sum()), int(observed_feature[mask].sum())
        x = (d - 1900) // 10
        raw_calendar_E_K += expectation
        raw_calendar_E_L += x * expectation
        person_terms += [(count, *year_cal[y], x) for y, count in actual.items()]
        bins.append({"decade": d, "n": n, "observed_target_people": observed,
                     "observed_share": observed / n if n else None,
                     "calendar_expected_target_people": float(expectation),
                     "calendar_expected_share": float(expectation) / n if n else None,
                     "local_test_eligible": d in TARGET_CONFIG[target]["local_decades"]})
    require(sum(b["n"] for b in bins) == N and sum(b["observed_target_people"] for b in bins) == K, "Bin partitions differ")
    structure = conditional_structure(bin_pmfs, K)
    for b, probability, mean, variance in zip(bins, structure["marginals"], structure["means"], structure["variances"]):
        b.update(conditional_expected_target_people=float(mean),
                 conditional_expected_share=float(mean) / b["n"] if b["n"] else None,
                 conditional_variance_target_people=float(variance),
                 conditional_upper_p=float(probability[b["observed_target_people"]:].sum()) if b["local_test_eligible"] else None)
        if b["local_test_eligible"]:
            require(b["n"] >= 20, "Predetermined local bin has fewer20people")
    seed = SEED_BASE + 1000 * target_index + 100 * source_index
    stats = analyze_statistics(bin_pmfs, structure, [b['observed_target_people'] for b in bins],
                               [(d - 1900) // 10 for d in DECADES], person_terms, seed)
    xperson = (decade - 1900) // 10
    sx = int(xperson.sum()); denominator = int(N * np.dot(xperson, xperson) - sx * sx)
    require(denominator > 0, "No birth-decade variation")
    linear = stats["linear"]
    raw_slope = 100 * (N * linear["observed_integer_L"] - sx * K) / denominator
    calendar_slope = float(100 * (N * raw_calendar_E_L - sx * raw_calendar_E_K) / denominator)
    conditional_slope = float(100 * (N * Fraction(int(linear['exact_expected_L_numerator']), int(linear['exact_expected_L_denominator'])) - sx * K) / denominator)
    linear.update(raw_slope_pp_per_decade=raw_slope, calendar_expected_slope_pp_per_decade=calendar_slope,
                  calendar_excess_slope_pp_per_decade=raw_slope - calendar_slope,
                  conditional_expected_slope_pp_per_decade=conditional_slope,
                  conditional_excess_slope_pp_per_decade=raw_slope - conditional_slope,
                  OLS_integer_denominator=denominator, x_predictor="(floor(birthyear/10)*10-1900)/10")
    adequate = [b for b in bins if b["local_test_eligible"]]
    return {"people": N, "person_ids_sha256": id_hash(p["person_id"] for p in rows),
            "target_people": K, "overall_observed_share": K / N,
            "calendar_expected_target_people": float(raw_calendar_E_K), "calendar_expected_share": float(raw_calendar_E_K) / N,
            "calendar_year_counts": {str(y): {"people": n, "success_dates": year_cal[y][0], "total_dates": year_cal[y][1]}
                                     for y, n in sorted(year_counts.items())},
            "local_decades": TARGET_CONFIG[target]["local_decades"],
            "adequate_local_people": sum(b["n"] for b in adequate),
            "adequate_local_target_people": sum(b["observed_target_people"] for b in adequate),
            "bins": bins, "global_tests": {"heterogeneity": stats["heterogeneity"], "linear": linear},
            "simulation": stats["simulation"], "conditioning_target_total_probability_under_calendar": structure["normalizer"],
            "inference_role": "post_reveal_exploratory_primary_strict" if source == "strict" else "expanded_source_sensitivity_reference_not_replication"}


def main(args):
    if args.synthetic_qa_only:
        answer = synthetic_qa()
        if args.synthetic_output:
            p = Path(args.synthetic_output); require(not p.exists(), "Synthetic QA output exists")
            p.write_text(json.dumps(answer, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps(answer, ensure_ascii=False, indent=2))
        return
    scope = json.loads(Path(args.scope).read_text())
    receipt = json.loads(Path(args.execution_receipt).read_text())
    require(scope["target_order"] == TARGET_ORDER and scope.get("source_order", SOURCE_ORDER) == SOURCE_ORDER, "Target/source authorization differs")
    for key, expected in TARGET_CONFIG.items():
        actual = scope["targets"][key]
        require(all(actual[k] == expected[k] for k in ["institution", "day_stem_indices", "local_decades"]), "Target definition differs: " + key)
    own_sha = scope.get("code_sha256", {})
    if isinstance(own_sha, dict):
        own_sha = own_sha["main"]
    require(own_sha == sha(__file__), "Prospective analysis code differs")
    require(receipt["remote_plan_and_code_verified_before_summary"] is True, "Remote pre-execution lock missing")
    require(receipt["scope_sha256"] == sha(args.scope), "Scope receipt hash differs")
    require(receipt["locked_file_manifest_sha256"] == sha(args.locked_files), "Manifest receipt hash differs")
    for rel, digest in json.loads(Path(args.locked_files).read_text()).items():
        require(sha(ROOT / rel) == digest, "Locked file changed: " + rel)
    require(sha(args.v4_zip) == V4_SHA == scope["input_sha256"]["v4_zip"], "Frozen V4 bytes changed")
    require(sha(args.calendar_npz) == CALENDAR_SHA == scope["input_sha256"]["calendar_npz"], "Frozen calendar bytes changed")
    if "test_definitions" in scope:
        require(scope["test_definitions"] == test_definitions(), "Fixed19 endpoints differ")
    output = Path(args.output)
    require(not output.exists(), "No outcome overwrite")
    with np.load(args.calendar_npz, allow_pickle=False) as z:
        dates, years, dm = z["dates"], z["year"].astype(np.int64), z["DM_index"].astype(np.int16)
    require(len(dates) == len(years) == len(dm) == 55152 and len(set(dates.tolist())) == 55152, "Calendar cardinality differs")
    require(np.all((dm >= 0) & (dm < 10)), "Invalid DayMaster index")
    groups = {}
    with zipfile.ZipFile(args.v4_zip) as archive:
        for ti, target in enumerate(TARGET_ORDER):
            groups[target] = {}
            feature = np.isin(dm, TARGET_CONFIG[target]["day_stem_indices"]).astype(np.int8)
            previous_ids = None
            previous_dobs = None
            for si, source in enumerate(SOURCE_ORDER):
                print(json.dumps({"target": target, "source_started": source}), flush=True)
                rows = selected_people(archive, TARGET_CONFIG[target]["institution"], source,
                                       scope["targets"][target]["populations"][source])
                if previous_ids is not None:
                    require(previous_ids <= {p["person_id"] for p in rows}, "Strict cohort not subsetexpanded")
                    current = {p["person_id"]: p["analysis_DOB"] for p in rows}
                    require(all(previous_dobs[p] == current[p] for p in previous_ids), "Shared source DOB changed")
                previous_ids = {p["person_id"] for p in rows}
                previous_dobs = {p["person_id"]: p["analysis_DOB"] for p in rows}
                groups[target][source] = one_group(target, source, rows, dates, years, feature, scope, ti, si)
            adequate = [d for d in DECADES
                        if min(groups[target][s]['bins'][DECADES.index(d)]['n'] for s in SOURCE_ORDER) >= 20]
            require(adequate == TARGET_CONFIG[target]['local_decades'], "Local support rule differs")
    tests = {}
    for source in SOURCE_ORDER:
        rows = []
        for definition in test_definitions():
            group = groups[definition["target"]][source]
            if definition["kind"] == "local":
                item = group["bins"][DECADES.index(definition["decade"])]
                p = item["conditional_upper_p"]
            else:
                item = group["global_tests"]["heterogeneity" if definition["kind"] == "global_heterogeneity" else "linear"]
                p = item["p_nominal"]
            rows.append({**definition, "p_nominal": p})
        for row, adjusted in zip(rows, holm([r["p_nominal"] for r in rows])):
            row.update(p_Holm19=adjusted, reject_Holm19_0_05=adjusted <= .05)
            group = groups[row["target"]][source]
            item = group["bins"][DECADES.index(row["decade"])] if row['kind'] == 'local' else group['global_tests']['heterogeneity' if row['kind'] == 'global_heterogeneity' else 'linear']
            item.update(p_Holm19=adjusted, reject_Holm19_0_05=adjusted <= .05)
        tests[source] = rows
    result = {"schema": "targeted_DM_birth_decades_conditional_v1", "target_order": TARGET_ORDER,
              "source_order": SOURCE_ORDER, "target_definitions": TARGET_CONFIG, "decade_bins": DECADES,
              "groups": groups, "tests_by_source": tests,
              "null_interpretation": "calendar odds with one common cohort enrichment odds multiplier; conditioning on full-cohort K removes multiplier",
              "multiple_testing": "one_Holm19_strict_primary;expanded_same19_reference_only;original_families_unchanged",
              "local_tails": "upper enrichment conditional on full-cohort total K;not unconditional calendar enrichment p",
              "new_tests_are_post_reveal_exploratory": True, "old_CAS_Xin_Holm30_test_replaced": False,
              "Nobel_global18_or_other_institutions_aggregated": False,
              "scope": scope, "execution_receipt": receipt,
              "source_and_code_sha256": {"code": sha(__file__), "v4_zip": sha(args.v4_zip), "calendar_npz": sha(args.calendar_npz)},
              "completed_at_utc": dt.datetime.now(dt.timezone.utc).isoformat()}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"status": "PASS", "output": str(output), "family_size": 19,
                      "Holm19_rejections": {s: sum(r['reject_Holm19_0_05'] for r in t) for s, t in tests.items()}}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--synthetic-qa-only", action="store_true")
    parser.add_argument("--synthetic-output")
    for key in ["scope", "locked-files", "execution-receipt", "v4-zip", "calendar-npz", "output"]:
        parser.add_argument("--" + key)
    main(parser.parse_args())
