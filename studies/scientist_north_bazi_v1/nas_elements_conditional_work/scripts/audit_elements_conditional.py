#!/usr/bin/env python3
"""Independent literal-stem NAS element/conditional audit.

This script never imports the analysis implementation. Study execution requires
an externally verified pre-execution receipt. Pure synthetic QA loads no study
rows. Conditional denominators are the observed anchor-positive subgroup.
"""
import argparse
from collections import Counter
import datetime as dt
from fractions import Fraction
import gzip
import hashlib
import importlib.util
import itertools
import json
import math
from pathlib import Path
import zipfile

import numpy as np
from scipy.signal import convolve

STEMS = "甲乙丙丁戊己庚辛壬癸"
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
ELEMENTS = "木火土金水"
DISPLAY_ELEMENTS = "金木水火土"
GODS = ["比肩", "劫财", "食神", "伤官", "偏财", "正财", "七杀", "正官", "偏印", "正印"]
SELECTED_GODS = ["偏财", "食神", "七杀", "偏印"]
HIDDEN = {"子": "癸", "丑": "己癸辛", "寅": "甲丙戊", "卯": "乙", "辰": "戊乙癸", "巳": "丙戊庚",
          "午": "丁己", "未": "己丁乙", "申": "庚壬戊", "酉": "辛", "戌": "戊辛丁", "亥": "壬甲"}
ELEMENT_BY_STEM = dict(zip(STEMS, "木木火火土土金金水水"))
POLARITY = dict(zip(STEMS, [0, 1] * 5))
ROOT = Path(__file__).resolve().parents[2]
ENCODER = ROOT / "nas_full_tables_work/scripts/build_full_nas_tables.py"
PINNED = {
    "v4_zip": "53302ef5c4bbb946adcaceb70d7a7fd576c7f06d03c3e7080874654e1a2644f9",
    "calendar_npz": "d150883033464ebd3afafaf764738ed3b573d0d0fb4bd252a955e403a75fcc8b",
    "encoder": "4b3ea67141c2363b4fb760ce365063545a4717542860caddf82c501d312ddc1d",
}


def require(condition, message):
    if not bool(condition):
        raise AssertionError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def close(a, b, message, atol=1e-9):
    require(math.isclose(float(a), float(b), rel_tol=1e-10, abs_tol=atol),
            f"{message}: independent={a!r}, analysis={b!r}")


def literal_god(day_stem, target_stem):
    # The five directed element relations are explicit and independent of the
    # analysis encoder's stem-index arithmetic.
    relation = {
        "木": ["木", "火", "土", "金", "水"],
        "火": ["火", "土", "金", "水", "木"],
        "土": ["土", "金", "水", "木", "火"],
        "金": ["金", "水", "木", "火", "土"],
        "水": ["水", "木", "火", "土", "金"],
    }
    element_relation = relation[ELEMENT_BY_STEM[day_stem]].index(ELEMENT_BY_STEM[target_stem])
    return 2 * element_relation + int(POLARITY[day_stem] != POLARITY[target_stem])


def literal_encode(year_pillars, month_pillars, day_pillars):
    n = len(day_pillars)
    elements = {m: np.zeros((n, 5), dtype=np.int16) for m in ["M0", "M1"]}
    gods = {m: np.zeros((n, 10), dtype=np.int16) for m in ["M0", "M1"]}
    for i, (yp, mp, dp) in enumerate(zip(year_pillars, month_pillars, day_pillars)):
        ys, ms, ds = str(yp)[0], str(mp)[0], str(dp)[0]
        branches = [str(yp)[1], str(mp)[1], str(dp)[1]]
        for model in ["M0", "M1"]:
            targets = [ys, ms]
            for branch in branches:
                hidden = HIDDEN[branch]
                matching = [s for s in hidden if s == ys or s == ms]
                targets.append(matching[0] if model == "M1" and matching else hidden[0])
            for target in targets:
                elements[model][i, ELEMENTS.index(ELEMENT_BY_STEM[target])] += 1
                gods[model][i, literal_god(ds, target)] += 1
    require(all(np.all(a.sum(axis=1) == 5) for a in [*elements.values(), *gods.values()]),
            "Literal targets do not all sum to5")
    return elements, gods


def normalized_convolve(a, b):
    values = convolve(a, b, mode="full", method="direct")
    require(np.all(values >= 0) and np.isfinite(values).all(), "Invalid independent polynomial")
    total = math.fsum(float(v) for v in values)
    require(total > 0, "Independent polynomial has zero mass")
    return values / total


def polynomial_power(pmf, exponent):
    """Independent grouped-year binary exponentiation, not per-person DP."""
    require(exponent >= 0, "Negative multiplicity")
    result, factor = np.asarray([1.0]), np.asarray(pmf, dtype=float)
    k = int(exponent)
    while k:
        if k & 1:
            result = normalized_convolve(result, factor)
        k //= 2
        if k:
            factor = normalized_convolve(factor, factor)
    return result


def grouped_exact_test(year_terms, observed):
    """Terms are (people, integer outcome histogram); exact E fixes ties."""
    expectation = Fraction(0)
    distribution = np.asarray([1.0])
    for people, histogram in year_terms:
        histogram = np.asarray(histogram, dtype=np.int64)
        days = int(histogram.sum())
        require(days > 0 and people >= 0, "Invalid independent conditional calendar pool")
        expectation += people * Fraction(sum(i * int(n) for i, n in enumerate(histogram)), days)
        distribution = normalized_convolve(distribution, polynomial_power(histogram / days, people))
    distance = abs(Fraction(int(observed)) - expectation)
    # Fraction comparisons are integer exact even when conditional pool sizes
    # create a large common denominator. Inclusive ties must not depend on eps.
    extreme = [i for i in range(len(distribution)) if abs(Fraction(i) - expectation) >= distance]
    p = math.fsum(float(distribution[i]) for i in extreme)
    return {"expectation": expectation, "p": min(1.0, p), "pmf": distribution,
            "extreme_integer_totals": extreme}


def independent_holm(pvalues):
    # Deliberately plain Python rather than the analysis array implementation.
    ordered = sorted(enumerate(float(p) for p in pvalues), key=lambda pair: (pair[1], pair[0]))
    adjusted, last = [0.0] * len(ordered), 0.0
    for rank, (original, p) in enumerate(ordered):
        last = max(last, min(1.0, (len(ordered) - rank) * p))
        adjusted[original] = last
    return adjusted


def synthetic_qa():
    for ds in STEMS:
        require(sorted(literal_god(ds, target) for target in STEMS) == list(range(10)),
                "Literal ten-god bijection failed")
    # All relationships, exposure priorities and fallback cases without any
    # real person's birthdate or calendar data.
    y, m, d = [], [], []
    for ds, ys, ms, b in itertools.product(STEMS, STEMS, STEMS, BRANCHES):
        index = BRANCHES.index(b)
        y.append(ys + b)
        m.append(ms + BRANCHES[(index + 4) % 12])
        d.append(ds + BRANCHES[(index + 7) % 12])
    elements, gods = literal_encode(y, m, d)
    for model in ["M0", "M1"]:
        rebuilt = np.zeros_like(elements[model])
        for i, dp in enumerate(d):
            day = ELEMENTS.index(ELEMENT_BY_STEM[dp[0]])
            for gi in range(10):
                rebuilt[i, (day + gi // 2) % 5] += gods[model][i, gi]
        require(np.array_equal(rebuilt, elements[model]), "Synthetic God-to-element identity failed")
    # 2 Bernoulli(1/2) plus1 Bernoulli(1/3): exact enumerate all8 outcomes.
    terms = [(2, [1, 1]), (1, [2, 1])]
    expected = Fraction(4, 3)
    for observed in range(4):
        exact = Fraction(0)
        for a, b, c in itertools.product([0, 1], repeat=3):
            probability = Fraction(1, 4) * (Fraction(1, 3) if c else Fraction(2, 3))
            if abs(Fraction(a + b + c) - expected) >= abs(Fraction(observed) - expected):
                exact += probability
        tested = grouped_exact_test(terms, observed)
        require(tested["expectation"] == expected, "Independent exact mean differs")
        close(tested["p"], exact, "Independent exact synthetic tail", atol=1e-14)
    centered = grouped_exact_test([(2, [1, 1])], 1)
    require(centered["p"] == 1.0, "Centered inclusive ties must yieldp1")
    require(independent_holm([0.01, 0.04, 0.02]) == [0.03, 0.04, 0.04], "Independent Holm example failed")
    return {"status": "PASS", "study_inputs_loaded": False, "literal_synthetic_pillar_cases": len(y),
            "literal_god_and_absolute_element_identity": True,
            "grouped_year_binary_polynomial_exact_enumeration": True,
            "Fraction_centered_inclusive_ties": True, "Holm_example": True}


def read_rows(z, relative):
    raw = gzip.decompress(z.read("scientist_north_data_freeze_v4/" + relative))
    return [json.loads(line) for line in raw.splitlines()]


def load_selected_nas(v4_zip):
    # Read only roster/identity needed to select NAS non-Nobel people. Never
    # encode, aggregate or expose another institution or Nobel-only subgroup.
    with zipfile.ZipFile(v4_zip) as z:
        sets = {}
        for source in ["strict", "expanded"]:
            nas = {p["person_id"] for p in read_rows(z, f"outputs/{source}/by_institution/NAS.jsonl.gz")}
            nonnobel = {p["person_id"] for p in read_rows(z, f"outputs/{source}/academy_excluding_official_Nobel.jsonl.gz")}
            sets[source] = nas & nonnobel
        people = {p["person_id"]: p for p in read_rows(z, "outputs/expanded/people.jsonl.gz")
                  if p["person_id"] in sets["expanded"]}
    require(len(sets["strict"]) == 908 and len(sets["expanded"]) == 1462 and sets["strict"] <= sets["expanded"],
            "NAS membership differs from frozen cohort")
    require(set(people) == sets["expanded"], "Selected NAS people missing")
    for p in people.values():
        require(p["hemisphere"] == "north" and not p["person_level_DOB_analysis_hold"], "NAS source hold differs")
        require(dt.date(1835, 1, 1) <= dt.date.fromisoformat(p["analysis_DOB"]) <= dt.date(1985, 12, 31),
                "NAS DOB outside frozen window")
    return {name: [people[pid] for pid in sorted(ids)] for name, ids in sets.items()}


def person_hash(rows):
    canonical = json.dumps(sorted(p["person_id"] for p in rows), ensure_ascii=False,
                           sort_keys=True, separators=(",", ":")) + "\n"
    return hashlib.sha256(canonical.encode()).hexdigest()


def canonical_endpoints():
    endpoints = []
    for model in ["M0", "M1"]:
        endpoints.extend({"model": model, "kind": "element", "target": target} for target in DISPLAY_ELEMENTS)
    for model in ["M0", "M1"]:
        endpoints.extend({"model": model, "kind": "marginal", "target": target} for target in SELECTED_GODS)
    for model in ["M0", "M1"]:
        endpoints.extend({"model": model, "kind": "conditional", "anchor": anchor, "target": target}
                         for anchor in SELECTED_GODS for target in SELECTED_GODS if target != anchor)
    require(len(endpoints) == 42, "Independent endpoint count differs")
    return endpoints


def feature_for(endpoint, elements, gods):
    model, target = endpoint["model"], endpoint["target"]
    if endpoint["kind"] == "element":
        return elements[model][:, ELEMENTS.index(target)], None
    target_counts = gods[model][:, GODS.index(target)]
    if endpoint["kind"] == "marginal":
        return target_counts, None
    return (target_counts > 0).astype(np.int8), gods[model][:, GODS.index(endpoint["anchor"])] > 0


def independent_description(endpoint, rows, indexes, calendar_years, elements, gods):
    feature, anchor = feature_for(endpoint, elements, gods)
    birthyears = np.asarray([int(p["analysis_DOB"][:4]) for p in rows], dtype=int)
    if anchor is None:
        keep = np.ones(len(rows), dtype=bool)
        normalizer = 5 * len(rows)
    else:
        keep = anchor[indexes]
        normalizer = int(keep.sum())
    observed = int(feature[indexes[keep]].sum())
    year_counts = Counter(int(y) for y in birthyears[keep])
    expectation = Fraction(0)
    terms = []
    for year, n in sorted(year_counts.items()):
        eligible = calendar_years == year
        if anchor is not None:
            eligible &= anchor
        values = feature[eligible]
        require(len(values) > 0, "Observed anchor has no same-year eligible calendar date")
        histogram = np.bincount(values, minlength=(2 if anchor is not None else 6))
        expectation += n * Fraction(int(values.sum()), len(values))
        terms.append((n, histogram))
    return {"descriptor": endpoint, "observed": observed, "expectation": expectation,
            "denominator": normalizer, "observed_share": observed / normalizer if normalizer else None,
            "expected_share": float(expectation / normalizer) if normalizer else None,
            "conditioning_people": int(keep.sum()), "terms": terms}


def audit_result(args):
    synthetic = synthetic_qa()
    result = json.loads(Path(args.results).read_text())
    require(result["country"] == "NAS" and result["no_other_country_or_Nobel_subgroup_outcomes_opened"] is True,
            "Analysis result scope differs")
    selected = load_selected_nas(args.v4_zip)
    with np.load(args.calendar_npz, allow_pickle=False) as z:
        dates, calendar_years = z["dates"], z["year"]
        yp, mp, dp = z["year_pillar"], z["month_pillar"], z["day_pillar"]
    require(len(dates) == 55152 and len(set(dates.tolist())) == 55152, "Independent calendar identities differ")
    elements, gods = literal_encode(yp, mp, dp)
    spec = importlib.util.spec_from_file_location("frozen_encoder_for_independent_comparison", ENCODER)
    encoder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(encoder)
    encoded, positions = encoder.encode_pool(yp, mp, dp)
    for model, oldkey in [("M0", "M0_5_mainqi"), ("M1", "M1_5_priority")]:
        require(np.array_equal(gods[model], encoded[oldkey]), "Literal all-date ten-god matrix differs: " + model)
        reconstructed = np.zeros_like(elements[model])
        for god in range(10):
            ei = (positions["day_stem"] // 2 + god // 2) % 5
            reconstructed[np.arange(len(dates)), ei] += encoded[oldkey][:, god]
        require(np.array_equal(reconstructed, elements[model]), "Literal all-date element matrix differs: " + model)
    lookup = {str(date): i for i, date in enumerate(dates)}
    canonical = canonical_endpoints()
    expected_definitions = []
    for endpoint in canonical:
        model, kind, target = endpoint["model"], endpoint["kind"], endpoint["target"]
        if kind == "conditional":
            expected_definitions.append({"id": f"{model}_conditional_{target}_given_{endpoint['anchor']}",
                                         "model": model, "kind": "conditional_presence",
                                         "anchor": endpoint["anchor"], "target": target})
        else:
            suffix = "element" if kind == "element" else "god"
            expected_definitions.append({"id": f"{model}_{suffix}_{target}", "model": model,
                                         "kind": "element_count" if kind == "element" else "god_count", "category": target})
    require(result["endpoint_definitions"] == expected_definitions, "Independent fixed42 endpoint definitions differ")
    audit = {"schema": "NAS_elements_conditional_independent_QA_v1", "status": "PASS",
             "synthetic_QA": synthetic, "literal_calendar_rows_independently_encoded": len(dates),
             "frozen_encoder_full_date_comparison": True, "groups": [],
             "other_country_or_Nobel_subgroup_outcomes_opened": False,
             "independent_p_method": "grouped_year_binary_polynomial_exponentiation_scipy_direct_convolve",
             "preselected_p_crosschecks": ["M0_element_水", "M0_conditional_食神_given_七杀", "M1_conditional_偏财_given_七杀"]}
    crosschecks = set(audit["preselected_p_crosschecks"])
    for source in ["strict", "expanded"]:
        rows, group = selected[source], result["groups"][source]
        n = len(rows)
        require(group["people"] == n and group["five_position_denominator"] == 5 * n,
                "Independent cohort size differs: " + source)
        require(group["person_ids_sha256"] == person_hash(rows), "Independent cohort ID hash differs: " + source)
        indexes = np.asarray([lookup[p["analysis_DOB"]] for p in rows], dtype=int)
        require(len(group["endpoints"]) == 42, "Independent42 endpoint rows missing")
        group_checks = {"group": source, "people": n, "endpoint_rows_checked": 42,
                        "all_observed_counts_shares_expectations_and_year_pools_checked": True,
                        "exact_rational_tail_boundaries_checked": True, "independent_p_crosschecks": []}
        for descriptor, definition, item in zip(canonical, expected_definitions, group["endpoints"]):
            require(all(item.get(k) == v for k, v in definition.items()), "Independent endpoint row identity differs")
            expected = independent_description(descriptor, rows, indexes, calendar_years, elements, gods)
            obs, mean, denominator = expected["observed"], expected["expectation"], expected["denominator"]
            conditional = descriptor["kind"] == "conditional"
            if conditional:
                require(item["observed_joint_people"] == obs and item["observed_anchor_people"] == denominator,
                        "Independent conditional numerator/denominator differs: " + item["id"])
                close(expected["observed_share"], item["observed_conditional_probability"], "Observed conditional probability")
                close(expected["expected_share"], item["calendar_expected_conditional_probability"], "Expected conditional probability")
                target, anchor = feature_for(descriptor, elements, gods)
                require(item["observed_target_people"] == int(target[indexes].sum()), "Independent target marginal differs")
                close(obs / n, item["observed_joint_prevalence"], "Independent joint prevalence")
                chosen_years = calendar_years[indexes[anchor[indexes]]]
                year_counts = Counter(int(y) for y in chosen_years)
                expected_pools = {}
                for year, count in year_counts.items():
                    eligible = (calendar_years == year) & anchor
                    expected_pools[str(year)] = {"observed_anchor_people": count,
                                                 "eligible_calendar_dates": int(eligible.sum()),
                                                 "joint_positive_dates": int(target[eligible].sum())}
                require(item["calendar_conditioned_year_pools"] == expected_pools, "Independent conditional year pools differ")
            else:
                require(item["observed_count"] == obs and item["position_denominator"] == denominator,
                        "Independent element/God numerator/denominator differs")
                close(expected["observed_share"], item["observed_position_share"], "Independent observed position share")
                close(expected["expected_share"], item["calendar_expected_position_share"], "Independent expected position share")
                close(obs / n, item["observed_mean_count_per_person"], "Independent observed mean count")
                close(mean / n, item["calendar_expected_mean_count_per_person"], "Independent expected mean count")
                feature, _ = feature_for(descriptor, elements, gods)
                require(item["observed_people_with_at_least_one"] == int((feature[indexes] > 0).sum()),
                        "Independent observed marginal presence differs")
            close(float(mean), item["calendar_expected_total"], "Independent expected total")
            require(str(mean.numerator) == item["exact_expected_numerator"] and
                    str(mean.denominator) == item["exact_expected_denominator"], "Independent exact Fraction differs")
            close((obs - float(mean)) / denominator * 100, item["difference_percentage_points"], "Independent effect pp")
            if mean:
                close(obs / float(mean), item["enrichment_ratio"], "Independent enrichment ratio")
            else:
                require(item["enrichment_ratio"] is None, "Zero expectation must have undefined ratio")
            # Independent analytic variance and exact rational cutoff masks.
            variance = 0.0
            for count, histogram in expected["terms"]:
                days = int(histogram.sum())
                mu = sum(i * int(c) for i, c in enumerate(histogram)) / days
                second = sum(i * i * int(c) for i, c in enumerate(histogram)) / days
                variance += count * max(0.0, second - mu * mu)
            close(math.sqrt(variance), item["null_SD_total"], "Independent null standard deviation")
            max_outcome = denominator if conditional else 5 * n
            lo, hi = item["two_sided_lower_inclusive"], item["two_sided_upper_inclusive"]
            observed_distance = abs(obs * mean.denominator - mean.numerator)
            require(all((k <= lo or k >= hi) ==
                        (abs(k * mean.denominator - mean.numerator) >= observed_distance)
                        for k in range(max_outcome + 1)), "Independent exact tail membership differs")
            require(0 <= item["p_two_sided"] <= 1, "Analysis pvalue outside unit interval")
            if item["id"] in crosschecks:
                tested = grouped_exact_test(expected["terms"], obs)
                require(tested["expectation"] == mean, "Grouped polynomial exact mean differs")
                close(tested["p"], item["p_two_sided"], "Independent preselected exact p", atol=2e-10)
                group_checks["independent_p_crosschecks"].append({"endpoint": item["id"],
                    "analysis_p": item["p_two_sided"], "independent_p": tested["p"]})
        adjusted = independent_holm([item["p_two_sided"] for item in group["endpoints"]])
        for item, corrected in zip(group["endpoints"], adjusted):
            close(corrected, item["p_Holm42"], "Independent Holm42")
            require(item["reject_Holm42_0_05"] == (corrected < 0.05), "Independent Holm decision differs")
        for model in ["M0", "M1"]:
            element_rows = [item for item in group["endpoints"] if item["model"] == model and item["kind"] == "element_count"]
            require(sum(item["observed_count"] for item in element_rows) == 5 * n, "Independent element total differs")
            close(sum(item["calendar_expected_total"] for item in element_rows), 5 * n, "Independent expected element total")
        require(len(group_checks["independent_p_crosschecks"]) == 3, "Independent preselected tests missing")
        group_checks["Holm42_checked"] = True
        audit["groups"].append(group_checks)
    audit["hashes"] = {"results": sha(args.results), "auditor": sha(__file__), "frozen_encoder": sha(ENCODER),
                       "V4": sha(args.v4_zip), "calendar": sha(args.calendar_npz), "execution_receipt": sha(args.execution_receipt)}
    Path(args.output).write_text(json.dumps(audit, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"status": "PASS", "output": args.output, "literal_calendar_dates_checked": len(dates),
                      "groups": {g["group"]: g["people"] for g in audit["groups"]}}, ensure_ascii=False))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--synthetic-qa-only", action="store_true")
    for key in ["v4-zip", "calendar-npz", "results", "output", "execution-receipt"]:
        p.add_argument("--" + key)
    args = p.parse_args()
    if args.synthetic_qa_only:
        result = synthetic_qa()
        if args.output:
            require(not Path(args.output).exists(), "Synthetic output already exists")
            Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    require(all(getattr(args, k) for k in ["v4_zip", "calendar_npz", "results", "output", "execution_receipt"]),
            "Study audit requires all input paths and execution receipt")
    require(not Path(args.output).exists(), "Independent audit output already exists")
    receipt = json.loads(Path(args.execution_receipt).read_text())
    require(receipt.get("remote_plan_and_code_verified_before_summary") is True,
            "Verified pre-execution remote lock receipt is missing")
    for name in ["v4_zip", "calendar_npz"]:
        require(sha(getattr(args, name)) == PINNED[name], "Independent input pin differs: " + name)
    require(sha(ENCODER) == PINNED["encoder"], "Frozen encoder pin differs")
    audit_result(args)


if __name__ == "__main__":
    main()
