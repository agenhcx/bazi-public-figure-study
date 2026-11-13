#!/usr/bin/env python3
"""NAS exploratory decade tables and calendar-adjusted linear trends.

No new cohort data are read before the supplied prospective execution scope is
verified. The original18/36 families and earlier NAS results remain untouched.
"""
import argparse
from collections import Counter
import datetime as dt
from fractions import Fraction
import hashlib
import importlib.util
import itertools
import json
import math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
ENCODER = ROOT / "nas_full_tables_work/scripts/build_full_nas_tables.py"
ENCODER_SHA = "4b3ea67141c2363b4fb760ce365063545a4717542860caddf82c501d312ddc1d"
STEMS = "甲乙丙丁戊己庚辛壬癸"
GODS = ["比肩", "劫财", "食神", "伤官", "偏财", "正财", "七杀", "正官", "偏印", "正印"]
DECADES = list(range(1830, 1990, 10))
LCM = 365 * 366
REPLICATES = 99999
V4_SHA = "53302ef5c4bbb946adcaceb70d7a7fd576c7f06d03c3e7080874654e1a2644f9"
CALENDAR_SHA = "d150883033464ebd3afafaf764738ed3b573d0d0fb4bd252a955e403a75fcc8b"


def require(ok, message):
    if not bool(ok):
        raise AssertionError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"


def load_encoder():
    require(sha(ENCODER) == ENCODER_SHA, "Pinned full-TenGod encoder changed")
    spec = importlib.util.spec_from_file_location("frozen_full_nas_encoder", ENCODER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def endpoint_definitions():
    result = [{"id": "DM_" + s, "family": "DM10", "label": s,
               "position_denominator": 1, "display_unit": "person_share"} for s in STEMS]
    for family in ["M0", "M1"]:
        result += [{"id": family + "_" + g, "family": family, "label": g,
                    "position_denominator": 5, "display_unit": "five_position_share"} for g in GODS]
    return result


def holm(values):
    p = np.asarray(values, dtype=float)
    order = np.argsort(p, kind="stable")
    result = np.empty(len(p))
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (len(p) - rank) * p[i]))
        result[i] = running
    return result


def calendar_stats(years, values):
    result = {}
    for year in sorted(set(int(y) for y in years)):
        a = values[years == year]
        require(len(a) in (365, 366), "A Gregorian calendar year has wrong cardinality")
        result[year] = {"D": len(a), "sum": a.sum(axis=0, dtype=np.int64),
                        "square_sum": (a.astype(np.int64) ** 2).sum(axis=0),
                        "pmf": [np.bincount(a[:, j], minlength=(2 if j < 10 else 6)).astype(float) / len(a)
                                for j in range(values.shape[1])]}
    return result


def coefficients(observed_years):
    x = (observed_years // 10 * 10 - 1900) // 10
    n = len(x)
    total_x = int(x.sum(dtype=np.int64))
    denominator = int(n * np.dot(x.astype(np.int64), x.astype(np.int64)) - total_x ** 2)
    weights = n * x.astype(np.int64) - total_x
    return x, weights, denominator


def one_trend(observed_years, observed_values, cal, endpoint_index, scale, seed, simulate=True, replicates=REPLICATES):
    x, weights, denominator = coefficients(observed_years)
    if denominator == 0:
        return {"status": "not_estimable", "reason": "no_decade_variation", "people": len(x)}
    observed_numerator = int(np.dot(weights, observed_values.astype(np.int64)))
    year_counts = Counter(int(y) for y in observed_years)
    n, total_x = len(x), int(x.sum(dtype=np.int64))
    expected_numerator_scaled = 0
    terms = []
    variance_numerator = 0.0
    for year, count in sorted(year_counts.items()):
        ay = n * ((year // 10 * 10 - 1900) // 10) - total_x
        stats = cal[year]
        days, s = stats["D"], int(stats["sum"][endpoint_index])
        require(LCM % days == 0, "LCM does not represent a calendar mean exactly")
        expected_numerator_scaled += ay * count * s * (LCM // days)
        variance_y = int(stats["square_sum"][endpoint_index]) / days - (s / days) ** 2
        variance_numerator += ay ** 2 * count * max(0.0, variance_y)
        terms.append((ay, count, stats["pmf"][endpoint_index]))
    observed_centered_scaled = observed_numerator * LCM - expected_numerator_scaled
    require(abs(observed_centered_scaled) < np.iinfo(np.int64).max, "Observed centered contrast exceeds int64")
    raw = scale * observed_numerator / denominator
    expected = scale * expected_numerator_scaled / (LCM * denominator)
    result = {"status": "estimable", "people": n,
              "raw_slope_pp_per_decade": raw,
              "calendar_expected_slope_pp_per_decade": expected,
              "calendar_excess_slope_pp_per_decade": raw - expected,
              "coefficient_design": "intercept + integer_decade_index=(floor(birthyear/10)*10-1900)/10",
              "OLS_integer_denominator": denominator,
              "observed_integer_raw_numerator": observed_numerator,
              "exact_expected_numerator_times_LCM": expected_numerator_scaled,
              "observed_centered_numerator_times_LCM": observed_centered_scaled,
              "LCM": LCM,
              "analytic_null_slope_SD_pp_per_decade": scale * math.sqrt(variance_numerator) / denominator,
              "hypothesis_test_performed": bool(simulate)}
    if not simulate:
        return result
    rng = np.random.Generator(np.random.PCG64(seed))
    null_numerator = np.zeros(replicates, dtype=np.int64)
    for ay, count, pmf in terms:
        if ay == 0:
            continue
        if endpoint_index < 10:
            values = rng.binomial(count, float(pmf[1]), size=replicates)
        else:
            values = rng.multinomial(count, pmf, size=replicates) @ np.arange(6, dtype=np.int64)
        null_numerator += ay * values
    # Never square these integer contrasts: two-sided order uses absolute
    # values, with all mathematically equal discrete values counted exactly.
    max_abs = max(abs(int(null_numerator.min())), abs(int(null_numerator.max())))
    require(max_abs * LCM + abs(expected_numerator_scaled) < np.iinfo(np.int64).max,
            "Simulated centered contrast exceeds int64")
    centered = null_numerator * np.int64(LCM) - np.int64(expected_numerator_scaled)
    extreme = int(np.count_nonzero(np.abs(centered) >= abs(observed_centered_scaled)))
    null_slopes = (null_numerator.astype(float) - expected_numerator_scaled / LCM) * scale / denominator
    result.update({"seed": int(seed), "generator": "PCG64", "replicates": int(replicates),
                   "tail": "two_sided_absolute_calendar_centered_integer_contrast_inclusive",
                   "extreme_replicates_including_ties": extreme,
                   "p_nominal_two_sided": (extreme + 1) / (replicates + 1),
                   "MC_excess_slope_mean_pp_per_decade": float(null_slopes.mean()),
                   "MC_excess_slope_SD_pp_per_decade": float(null_slopes.std(ddof=0)),
                   "zero_weight_years_skipped": True,
                   "integer_arithmetic_no_squared_contrasts": True})
    return result


def summarize_bins(observed_years, observed, cal, endpoints):
    decades = observed_years // 10 * 10
    answer = []
    for decade in DECADES:
        mask = decades == decade
        n = int(mask.sum())
        details = {}
        for j, e in enumerate(endpoints):
            if not n:
                details[e["id"]] = {"observed_total": 0, "calendar_expected_total": 0.0,
                                     "observed_share": None, "calendar_expected_share": None,
                                     "excess_percentage_points": None}
                continue
            obs = int(observed[mask, j].sum())
            year_counts = Counter(int(y) for y in observed_years[mask])
            expected = sum(count * int(cal[y]["sum"][j]) / cal[y]["D"] for y, count in year_counts.items())
            normalizer = n * e["position_denominator"]
            details[e["id"]] = {"observed_total": obs, "calendar_expected_total": float(expected),
                                "observed_share": obs / normalizer,
                                "calendar_expected_share": expected / normalizer,
                                "excess_percentage_points": (obs - expected) / normalizer * 100}
        answer.append({"decade": decade, "n": n, "endpoints": details})
    return answer


def group_result(name, rows, date_index, values, cal, endpoints, case_index, common_decades):
    years = np.asarray([int(p["analysis_DOB"][:4]) for p in rows], dtype=np.int64)
    observed = values[np.asarray([date_index[p["analysis_DOB"]] for p in rows])]
    bins = summarize_bins(years, observed, cal, endpoints)
    trends = []
    for j, e in enumerate(endpoints):
        print(json.dumps({"case": name, "endpoint_started": j + 1, "total_endpoints": len(endpoints), "endpoint": e["id"]}), flush=True)
        scale = 100 / e["position_denominator"]
        trend = one_trend(years, observed[:, j], cal, j, scale, 202611170000 + 1000 * case_index + j)
        trend.update({"endpoint_id": e["id"], "family": e["family"], "label": e["label"]})
        trends.append(trend)
    require(all(t["status"] == "estimable" for t in trends), "Frozen full group has no estimable trend")
    corrected = holm([t["p_nominal_two_sided"] for t in trends])
    for trend, p in zip(trends, corrected):
        trend.update({"p_Holm30": float(p), "reject_Holm30_0_05": bool(p <= 0.05),
                      "inference_role": "post_reveal_exploratory_primary_strict" if case_index == 0 else
                                        "expanded_source_sensitivity_Holm30_reference_not_independent_replication"})
    keep = np.isin(years // 10 * 10, common_decades)
    common = []
    for j, e in enumerate(endpoints):
        trend = one_trend(years[keep], observed[keep, j], cal, j, 100 / e["position_denominator"], 0, simulate=False)
        trend.update({"endpoint_id": e["id"], "family": e["family"], "label": e["label"]})
        common.append(trend)
    return {"people": len(rows), "birth_year_min": int(years.min()), "birth_year_max": int(years.max()),
            "person_ids_sha256": hashlib.sha256(canonical([p["person_id"] for p in rows]).encode()).hexdigest(),
            "bins": bins, "trends": trends,
            "common_adequate_bins_desc": {"people": int(keep.sum()), "decades": common_decades,
                                           "minimum_people_per_bin_in_both_sources": 20,
                                           "hypothesis_tests_performed": False, "trends": common}}


def synthetic_qa():
    # Both artificial years are outside the scientist birth window. Two people
    # per year, with x=10 and12 and independent Bernoulli observations.
    years = np.asarray([2000, 2000, 2020, 2020], dtype=np.int64)
    values = np.asarray([0, 0, 1, 1], dtype=np.int64)
    examples = []
    for p1, p2 in [(Fraction(1, 2), Fraction(1, 2)), (Fraction(1, 3), Fraction(2, 3))]:
        cal = {}
        for year, p in [(2000, p1), (2020, p2)]:
            s = int(p * 366)
            cal[year] = {"D": 366, "sum": np.asarray([s]), "square_sum": np.asarray([s]),
                         "pmf": [np.asarray([1 - float(p), float(p)])]}
        result = one_trend(years, values, cal, 0, 100, 202611170999)
        _, weights, denominator = coefficients(years)
        expected = sum(Fraction(int(w)) * p for w, p in zip(weights, [p1, p1, p2, p2]))
        observed = Fraction(int(np.dot(weights, values)))
        exact = Fraction(0)
        for bits in itertools.product([0, 1], repeat=4):
            probability = Fraction(1)
            for bit, p in zip(bits, [p1, p1, p2, p2]):
                probability *= p if bit else 1 - p
            numerator = sum(Fraction(int(w) * bit) for w, bit in zip(weights, bits))
            if abs(numerator - expected) >= abs(observed - expected):
                exact += probability
        require(result["exact_expected_numerator_times_LCM"] == int(expected * LCM), "Exact calendar centering failed")
        require(abs(result["calendar_excess_slope_pp_per_decade"] - float((observed - expected) * 100 / denominator)) < 1e-12,
                "Exact centered slope failed")
        p = float(exact)
        tolerance = 5 * math.sqrt(p * (1 - p) / REPLICATES) + 2 / REPLICATES
        require(abs(result["p_nominal_two_sided"] - p) <= tolerance, "Two-sided calendar MC differs from exact enumeration")
        examples.append({"p1": str(p1), "p2": str(p2), "exact_two_sided_p": p,
                         "MC_two_sided_p": result["p_nominal_two_sided"], "tolerance": tolerance})
    check_center = one_trend(years, np.asarray([0, 1, 0, 1]), {
        y: {"D": 366, "sum": np.asarray([183]), "square_sum": np.asarray([183]),
            "pmf": [np.asarray([0.5, 0.5])]} for y in [2000, 2020]}, 0, 100, 202611170998)
    require(check_center["observed_centered_numerator_times_LCM"] == 0 and check_center["p_nominal_two_sided"] == 1,
            "Exactly centered integer ties must yield p1")
    h = holm([0.01, 0.04, 0.02])
    require(np.allclose(h, [0.03, 0.04, 0.04]), "Holm adjustment failed")
    empty = summarize_bins(np.asarray([], dtype=np.int64), np.empty((0, 30), dtype=np.int64), {}, endpoint_definitions())
    require(all(b["n"] == 0 and all(v["observed_total"] == 0 and v["calendar_expected_total"] == 0.0 and
                                    v["observed_share"] is None and v["calendar_expected_share"] is None and
                                    v["excess_percentage_points"] is None for v in b["endpoints"].values()) for b in empty),
            "Empty bins need zero count totals and undefined shares")
    return {"schema": "NAS_decade_pure_synthetic_QA_v1", "status": "PASS", "study_inputs_loaded": False,
            "outside_window_synthetic_years": [2000, 2020], "exact_integer_calendar_centering": True,
            "exact_absolute_tail_inclusive_ties_p1": True, "int64_absolute_not_square": True,
            "examples": examples, "Holm_monotonicity_example": True,
            "empty_bin_counts_zero_shares_undefined": True}


def main(args):
    if args.synthetic_qa_only:
        print(json.dumps(synthetic_qa(), ensure_ascii=False, indent=2))
        return
    scope = json.loads(Path(args.scope).read_text())
    require(scope.get("country") == "NAS" and scope.get("decade_descriptive_and_trend_authorized") is True and
            scope.get("exploratory_after_NAS_reveal") is True, "NAS exploratory decade authorization missing")
    require(scope.get("code_sha256") == sha(__file__), "Prospective trend code SHA differs")
    paths = {"v4_zip": args.v4_zip, "calendar_npz": args.calendar_npz, "prior_tables": args.prior_tables}
    for name, path in paths.items():
        require(path and sha(path) == scope["input_sha256"][name], "Input SHA differs: " + name)
    require(sha(args.v4_zip) == V4_SHA and sha(args.calendar_npz) == CALENDAR_SHA, "Original source pin changed")
    output = Path(args.output)
    require(not output.exists(), "Output already exists; no overwrite")
    encoder = load_encoder()
    import zipfile
    with zipfile.ZipFile(args.v4_zip) as z:
        sets = {}
        for source in ["strict", "expanded"]:
            nas = {p["person_id"] for p in encoder.read_zip_rows(z, "outputs/" + source + "/by_institution/NAS.jsonl.gz")}
            no_nobel = {p["person_id"] for p in encoder.read_zip_rows(z, "outputs/" + source + "/academy_excluding_official_Nobel.jsonl.gz")}
            sets[source] = nas & no_nobel
        people = {p["person_id"]: p for p in encoder.read_zip_rows(z, "outputs/expanded/people.jsonl.gz")
                  if p["person_id"] in sets["expanded"]}
    require(len(sets["strict"]) == 908 and len(sets["expanded"]) == 1462 and sets["strict"] <= sets["expanded"],
            "Frozen NAS selections changed")
    require(set(people) == sets["expanded"], "Selected NAS people missing")
    for p in people.values():
        require(p["hemisphere"] == "north" and not p["person_level_DOB_analysis_hold"], "Selected source hold changed")
        dt.date.fromisoformat(p["analysis_DOB"])
    endpoints = endpoint_definitions()
    with np.load(args.calendar_npz, allow_pickle=False) as z:
        dates, years = z["dates"], z["year"].astype(np.int64)
        encoded, positions = encoder.encode_pool(z["year_pillar"], z["month_pillar"], z["day_pillar"])
    require(len(dates) == 55152, "Calendar row count changed")
    values = np.concatenate([np.eye(10, dtype=np.int16)[positions["day_stem"]], encoded["M0_5_mainqi"],
                             encoded["M1_5_priority"]], axis=1).astype(np.int64)
    require(values.shape == (55152, 30), "Endpoint matrix shape changed")
    cal = calendar_stats(years, values)
    index = {str(date): i for i, date in enumerate(dates)}
    metadata = {name: Counter((int(people[i]["analysis_DOB"][:4]) // 10) * 10 for i in ids) for name, ids in sets.items()}
    common = [d for d in DECADES if metadata["strict"][d] >= 20 and metadata["expanded"][d] >= 20]
    require(len(common) >= 2, "Common adequate decade design is not estimable")
    result = {"schema": "NAS_post_reveal_decade_trends_v1", "country": "NAS", "endpoint_order": endpoints,
              "decade_bins": DECADES, "common_adequate_decades": common,
              "no_outcome_selected_decade_boundaries": True,
              "trend_type": "linear_only; absence of slope does not exclude nonlinear decade variation",
              "unit": "unique person; decade OLS is equivalent to person-count-weighted decade means",
              "confirmatory_original18_or_country36_modified": False,
              "inference_status": "new_post_NAS_reveal_exploratory_family30; strictprimary expanded_sensitivity",
              "calendar_null": "fixed individual Gregorian birthyear; uniform valid dates; year-specific features recomputed consistently",
              "Monte_Carlo": {"replicates": REPLICATES, "seed": "202611170000+1000*source_case_index+endpoint_index",
                              "case_order": ["strict", "expanded"], "LCM": LCM,
                              "ties": "inclusive exact absolute integer centered contrast", "adaptive_stopping": False},
              "multiple_testing": "Holm30 on strict exploratory family; expanded Holm30 reference only; no common-bin extra tests",
              "groups": {}, "source_and_code_sha256": {"code": sha(__file__), "encoder": sha(ENCODER),
                                                          **{k: sha(v) for k, v in paths.items()}},
              "execution_scope": scope}
    previous = json.loads(Path(args.prior_tables).read_text())
    previous_map = {"strict": previous["groups"]["strict_primary"], "expanded": previous["groups"]["expanded"]}
    for case_index, name in enumerate(["strict", "expanded"]):
        rows = [people[pid] for pid in sorted(sets[name])]
        group = group_result(name, rows, index, values, cal, endpoints, case_index, common)
        require(group["person_ids_sha256"] == previous_map[name]["person_ids_sha256"], "Prior selected IDs differ")
        require(group["people"] == previous_map[name]["people"], "Prior sample count differs")
        # Reconstruct the previously disclosed full-population totals from bins.
        for j, e in enumerate(endpoints):
            total = sum(b["endpoints"][e["id"]]["observed_total"] or 0 for b in group["bins"])
            expected_total = sum(b["endpoints"][e["id"]]["calendar_expected_total"] or 0 for b in group["bins"])
            if j < 10:
                old = previous_map[name]["HeavenlyStem_positions"]["day_stem"][j]
                old_total, old_expected = old["observed_people"], old["calendar_expected_people"]
            else:
                old = previous_map[name]["TenGod_models"]["M0_5_mainqi" if j < 20 else "M1_5_priority"][(j - 10) % 10]
                old_total, old_expected = old["observed_count"], old["calendar_expected_count"]
            require(total == old_total and np.isclose(expected_total, old_expected, rtol=1e-10, atol=1e-10),
                    "Decade totals do not reproduce previously disclosed population: " + e["id"])
        result["groups"][name] = group
    result["completed_at_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"status": "PASS", "groups": {k: v["people"] for k, v in result["groups"].items()},
                      "endpoints": 30, "bins": len(DECADES), "common_adequate_decades": common, "output": str(output)}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--synthetic-qa-only", action="store_true")
    for option in ["v4-zip", "calendar-npz", "prior-tables", "scope", "output"]:
        parser.add_argument("--" + option)
    main(parser.parse_args())
