#!/usr/bin/env python3
"""UK-only adapter of locked 327cc country reveal, statistical functions unchanged.

Code preparation does not read cohort data. The command-line entry point requires
a remotely verified execution-lock receipt before reading any study features.
One person is one observation; five positions are never independent people.
"""
import argparse
from collections import Counter, defaultdict
import datetime as dt
import gzip
import hashlib
import json
from pathlib import Path
import re
import subprocess
import zipfile

import numpy as np

BASE = Path(__file__).resolve().parents[2]
COUNTRIES = ["NAS", "UK_Royal_Society", "DE_Leopoldina", "France", "Japan", "CAS"]
STEMS = list("甲乙丙丁戊己庚辛壬癸")
GODS = ["比肩", "劫财", "食神", "伤官", "偏财", "正财", "七杀", "正官", "偏印", "正印"]
METRICS = ["PI_count", "SG_count", "GY_narrow", "SGY_narrow", "water_DM", "DM_index"]
CASE_ORDER = ["strict_primary", "expanded", "strict_broad", "strict_noJie",
              "strict_yearMonth", "expanded_withoutLOC", "strict_withoutFields"]
REPLICATES = 99999
BOOTSTRAPS = 10000
BONFERRONI_FAMILY_SIZE = 36


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"


def read_jsonl(path):
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify_gate(args):
    """UK authorization and content-hash gate; no study rows opened here.

    The root agent verifies remote Git bytes before writing this receipt. This
    adapter uses frozen date-pool rows instead of requiring the archived chart
    container; no calendar values, methods or dates are recalculated.
    """
    receipt = json.loads(Path(args.execution_receipt).read_text())
    scope = json.loads(Path(args.scope).read_text())
    require(receipt.get("country") == scope.get("country") == "UK_Royal_Society", "UK-only country gate")
    require(receipt.get("remote_plan_and_code_verified_before_summary") is True, "Remote code lock not verified")
    require(receipt.get("scope_sha256") == sha(args.scope), "Scope hash differs from receipt")
    require(receipt.get("locked_file_manifest_sha256") == sha(args.locked_files), "Locked manifest hash differs")
    commit = receipt.get("commit", receipt.get("lock_commit_sha", ""))
    require(bool(re.fullmatch(r"[0-9a-f]{40}", commit)), "Invalid execution-lock SHA")
    pins = json.loads(Path(args.locked_files).read_text())
    own = str(Path(__file__).resolve().relative_to(BASE))
    require(own in pins, "Analysis adapter absent from locked files")
    for rel, digest in pins.items():
        path = (BASE / rel).resolve()
        require(path.is_relative_to(BASE), "Pinned path escapes workspace")
        require(sha(path) == digest, "Locked file changed: " + rel)
    require(sha(args.v4_zip) == "53302ef5c4bbb946adcaceb70d7a7fd576c7f06d03c3e7080874654e1a2644f9", "V4 source pin changed")
    require(sha(args.calendar_npz) == "d150883033464ebd3afafaf764738ed3b573d0d0fb4bd252a955e403a75fcc8b", "Frozen calendar pool changed")
    return receipt, {"V4_zip": Path(args.v4_zip), "calendar_pool": Path(args.calendar_npz)}


def load_pool(path):
    with np.load(path, allow_pickle=False) as source:
        data = {k: source[k] for k in source.files}
    require(data["feature_names"].tolist() == METRICS, "Calendar metric order changed")
    require(data["dm_stems"].tolist() == STEMS, "Calendar day-master order changed")
    require(data["ten_god_names"].tolist() == GODS, "Calendar Ten-God order changed")
    dates = data["dates"].tolist()
    expected = []
    cursor = dt.date(1835, 1, 1)
    while cursor <= dt.date(1985, 12, 31):
        expected.append(cursor.isoformat())
        cursor += dt.timedelta(days=1)
    require(dates == expected, "Calendar must contain all and only valid 1835-1985 dates in order")
    n = len(expected)
    require(data["features"].shape == (n, 6), "Calendar feature shape mismatch")
    require(data["ten_god_counts"].shape == (n, 10), "Calendar Ten-God shape mismatch")
    require(np.all(data["ten_god_counts"].sum(axis=1) == 5), "Calendar five-position totals invalid")
    return data


def observed_arrays(rows, broad=False):
    n = len(rows)
    x = np.zeros((n, 6), dtype=np.int64)
    gods = np.zeros((n, 10), dtype=np.int64)
    for i, row in enumerate(rows):
        gods[i] = [row["ten_god_counts_five_positions"][g] for g in GODS]
        x[i] = [gods[i, 8], gods[i, 3], row["guan_yin_broad" if broad else "guan_yin_narrow"],
                row["shangguan_yin_broad" if broad else "shangguan_yin_narrow"],
                row["day_master_water"], STEMS.index(row["day_master"])]
    require(np.all(gods.sum(axis=1) == 5), "Observed five-position totals invalid")
    return x, gods


class CalendarModel:
    """Exact exhaustive per-year or per-year-month conditional distributions."""
    def __init__(self, pool, month=False, no_jie=False, broad=False):
        self.month = month
        self.no_jie = no_jie
        self.broad = broad
        self.lookup = {}
        keep = ~pool["jie_boundary_plus_minus_one_civil_day"].astype(bool) if no_jie else np.ones(len(pool["dates"]), dtype=bool)
        bucket = defaultdict(list)
        for i in np.flatnonzero(keep):
            key = (int(pool["year"][i]), int(pool["month"][i]) if month else 0)
            bucket[key].append(i)
        for key, indexes in bucket.items():
            idx = np.asarray(indexes, dtype=np.int64)
            x = pool["features"][idx].astype(np.int64).copy()
            if broad:
                x[:, 2] = pool["GY_broad"][idx]
                x[:, 3] = pool["SGY_broad"][idx]
            pmfs = [np.bincount(x[:, j], minlength=(6 if j < 2 else 2)).astype(float) / len(idx) for j in range(5)]
            dm = np.bincount(x[:, 5], minlength=10).astype(float) / len(idx)
            self.lookup[key] = {"n_dates": len(idx), "pmfs": pmfs, "DM": dm,
                                "E": x[:, :5].mean(axis=0), "TG": pool["ten_god_counts"][idx].mean(axis=0)}

    def key(self, row):
        date = dt.date.fromisoformat(row["analysis_DOB"])
        return (date.year, date.month if self.month else 0)

    def expectations(self, rows):
        details = [self.lookup[self.key(row)] for row in rows]
        return (np.asarray([v["E"] for v in details]), np.asarray([v["DM"] for v in details]),
                np.asarray([v["TG"] for v in details]))


def mc_tests(rows, x, expected_dm, model, country_index):
    """Exact marginal null simulation using independent within-stratum counts.

    A multinomial of a feature histogram is distributionally identical to
    drawing each person's calendar date independently, for that endpoint's
    sum. Separate endpoint streams do not preserve their joint dependence;
    Bonferroni does not require that dependence. No multivariate claims follow.
    """
    strata = Counter(model.key(row) for row in rows)
    n = len(rows)
    answer = []
    for metric_index, name in enumerate(METRICS):
        seed = 2026111300 + 100 * country_index + metric_index
        rng = np.random.Generator(np.random.PCG64(seed))
        if metric_index < 5:
            simulated_sum = np.zeros(REPLICATES, dtype=np.int64)
            for key, count in sorted(strata.items()):
                pmf = model.lookup[key]["pmfs"][metric_index]
                if metric_index < 2:
                    simulated_sum += rng.multinomial(count, pmf, size=REPLICATES) @ np.arange(6, dtype=np.int64)
                else:
                    simulated_sum += rng.binomial(count, float(pmf[1]), size=REPLICATES)
            observed_sum = int(x[:, metric_index].sum())
            extreme = int(np.count_nonzero(simulated_sum >= observed_sum))
            statistic = {"observed_integer_sum": observed_sum, "observed_mean": observed_sum / n,
                         "tail": "upper_inclusive_integer_sum"}
        else:
            expected_counts = expected_dm.sum(axis=0)
            observed_counts = np.bincount(x[:, 5], minlength=10)
            require(np.all(expected_counts > 0), "Zero expected day-master cell; no alternative statistic permitted")
            observed_distance = float(np.sum((observed_counts - expected_counts) ** 2 / expected_counts))
            sim_counts = np.zeros((REPLICATES, 10), dtype=np.int64)
            for key, count in sorted(strata.items()):
                sim_counts += rng.multinomial(count, model.lookup[key]["DM"], size=REPLICATES)
            distances = np.sum((sim_counts - expected_counts) ** 2 / expected_counts, axis=1)
            tie_tolerance = 1e-12 * max(1.0, abs(observed_distance))
            extreme = int(np.count_nonzero(distances >= observed_distance - tie_tolerance))
            statistic = {"observed_Pearson_distance": observed_distance, "tail": "upper_inclusive_distance",
                         "floating_point_tie_tolerance": tie_tolerance}
        p = (extreme + 1) / (REPLICATES + 1)
        answer.append({"metric": name, "seed": seed, "generator": "PCG64", "replicates": REPLICATES,
                       "extreme_replicates_including_ties": extreme, "p_nominal_plus_one": p,
                       "p_Bonferroni_36_reference": min(1.0, p * BONFERRONI_FAMILY_SIZE), **statistic})
    return answer


def bootstrap_intervals(x, expected, case_index, country_index):
    # Separate supplementary-country stream; global18 retains its old seed.
    seed = 202611150000 + 100 * country_index + case_index
    rng = np.random.Generator(np.random.PCG64(seed))
    n = len(x)
    means, excess = np.empty((BOOTSTRAPS, 5)), np.empty((BOOTSTRAPS, 5))
    paired = x[:, :5] - expected
    for start in range(0, BOOTSTRAPS, 256):
        stop = min(start + 256, BOOTSTRAPS)
        # The same complete person resample is used for all five endpoints.
        draws = rng.integers(0, n, size=(stop - start, n))
        means[start:stop] = x[draws, :5].mean(axis=1)
        excess[start:stop] = paired[draws].mean(axis=1)
    return {"seed": seed, "generator": "PCG64", "replicates": BOOTSTRAPS,
            "resampling_unit": "person_with_all_five_endpoints_and_paired_calendar_expectations",
            "confidence_level": 0.95, "multiple_comparison_adjusted": False,
            "quantile_method": "linear", "raw_mean_CI": np.quantile(means, [0.025, 0.975], axis=0, method="linear").T,
            "excess_mean_CI": np.quantile(excess, [0.025, 0.975], axis=0, method="linear").T}


def descriptive(rows, model, broad=False):
    n = len(rows)
    if not n:
        return {"status": "not_estimable", "n": 0}
    x, gods = observed_arrays(rows, broad=broad)
    expected, expected_dm, expected_gods = model.expectations(rows)
    metrics = []
    for j, name in enumerate(METRICS[:5]):
        obs, exp = float(x[:, j].mean()), float(expected[:, j].mean())
        metrics.append({"metric": name, "observed_sum": int(x[:, j].sum()), "observed_mean_or_rate": obs,
                        "calendar_expected_mean_or_rate": exp, "observed_minus_expected": obs - exp,
                        "unit": "count_per_person_of_five_positions" if j < 2 else "fraction_of_people",
                        "difference_percentage_points": (obs - exp) * 100 if j >= 2 else None})
    dm_observed = np.bincount(x[:, 5], minlength=10)
    dm_expected = expected_dm.sum(axis=0)
    ten_gods = [{"ten_god": g, "observed_count_sum": int(gods[:, i].sum()),
                 "observed_count_mean_per_person": float(gods[:, i].mean()),
                 "calendar_expected_count_mean_per_person": float(expected_gods[:, i].mean()),
                 "excess_count_mean_per_person": float((gods[:, i] - expected_gods[:, i]).mean()),
                 "observed_share_of_five_positions": float(gods[:, i].mean() / 5),
                 "calendar_expected_share_of_five_positions": float(expected_gods[:, i].mean() / 5)} for i, g in enumerate(GODS)]
    years = np.asarray([dt.date.fromisoformat(row["analysis_DOB"]).year for row in rows])
    design = np.column_stack([np.ones(n), (years - 1900) / 10])
    if np.linalg.matrix_rank(design, tol=1e-12) < 2:
        trend = {"status": "not_estimable", "reason": "birthyear_design_has_no_variation", "hypothesis_test": False}
    else:
        raw = np.linalg.lstsq(design, x[:, 2], rcond=1e-12)[0]
        ex = np.linalg.lstsq(design, x[:, 2] - expected[:, 2], rcond=1e-12)[0]
        trend = {"status": "descriptive_only", "outcome": "GY_broad" if broad else "GY_narrow",
                 "design": ["intercept", "(Gregorian_birthyear-1900)/10"],
                 "raw_rate_slope_per_decade": float(raw[1]), "calendar_excess_rate_slope_per_decade": float(ex[1]),
                 "rcond": 1e-12, "hypothesis_test": False, "global_H2d_test": False,
                 "interpretation": "within_selected_institution_birth_cohort_association_not_causal_institution_change"}
    summary = {"status": "descriptive_only", "n": n, "single_country_person_weight": 1,
               "unique_person_count": len({row["person_id"] for row in rows}), "metric_order": METRICS,
               "scalar_metrics": metrics, "ten_gods_five_position_descriptive_only": ten_gods,
               "day_master_distribution": [{"stem": s, "observed_people": int(dm_observed[i]),
                                            "calendar_expected_people": float(dm_expected[i]),
                                            "observed_fraction": float(dm_observed[i] / n),
                                            "calendar_expected_fraction": float(dm_expected[i] / n)} for i, s in enumerate(STEMS)],
               "birthyear_GY_trend": trend}
    return summary


def run_case(name, rows, model, case_index, country_index):
    rows = sorted(rows, key=lambda r: r["person_id"])
    summary = descriptive(rows, model, broad=model.broad)
    summary.update({"case": name, "case_index": case_index,
                    "person_ids_sha256": hashlib.sha256(canonical([r["person_id"] for r in rows]).encode()).hexdigest(),
                    "calendar_condition": "year_and_month" if model.month else "year",
                    "observed_and_calendar_Jie_pm1_excluded": model.no_jie,
                    "cooccurrence_encoding": "broad" if model.broad else "narrow"})
    if not rows:
        return summary
    x, _ = observed_arrays(rows, broad=model.broad)
    expected, expected_dm, _ = model.expectations(rows)
    tests = mc_tests(rows, x, expected_dm, model, country_index)
    intervals = bootstrap_intervals(x, expected, case_index, country_index)
    for j, entry in enumerate(summary["scalar_metrics"]):
        entry["raw_mean_or_rate_unadjusted_95CI"] = intervals["raw_mean_CI"][j].tolist()
        entry["paired_excess_unadjusted_95CI"] = intervals["excess_mean_CI"][j].tolist()
    intervals.pop("raw_mean_CI")
    intervals.pop("excess_mean_CI")
    primary = name == "strict_primary"
    for test in tests:
        test["secondary_country_family_primary_member"] = primary
        test["FWER_family_size"] = BONFERRONI_FAMILY_SIZE
        test["primary_Bonferroni_36_reject_0_05"] = test["p_Bonferroni_36_reference"] <= 0.05 if primary else None
        test["sensitivity_does_not_rescue_primary"] = not primary
    summary.update({"status": "analyzed", "calendar_MC_tests": tests, "bootstrap": intervals,
                    "global_confirmatory_18_Holm_family_tested": False})
    return summary


def json_safe(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {k: json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_safe(v) for v in value]
    return value


def _read_v4_rows(archive, relative):
    return [json.loads(line) for line in gzip.decompress(archive.read("scientist_north_data_freeze_v4/" + relative)).splitlines()]


def _selected_population(archive):
    selected, all_uk, fields = {}, {}, {}
    populations = {}
    for quality in ["strict", "expanded"]:
        uk_rows = _read_v4_rows(archive, "outputs/" + quality + "/by_institution/UK_Royal_Society.jsonl.gz")
        all_uk[quality] = {r["person_id"] for r in uk_rows}
        non_nobel = {r["person_id"] for r in _read_v4_rows(archive, "outputs/" + quality + "/academy_excluding_official_Nobel.jsonl.gz")}
        selected[quality] = all_uk[quality] & non_nobel
        fields[quality] = {r["person_id"] for r in _read_v4_rows(archive, "outputs/" + quality + "/Fields_parallel_cohort.jsonl.gz")}
        populations[quality] = {r["person_id"]: r for r in uk_rows if r["person_id"] in selected[quality]}
    require(len(selected["strict"]) == len(selected["expanded"]) == 2293, "UK selected population size differs")
    require(selected["strict"] == selected["expanded"], "UK strict/expanded membership no longer identical")
    expected_id_hash = "15d3eadfe82ca2de2b8b0fd0430083edd7cd450c5d7086d33985c0943fbdede4"
    require(sha_ids(selected["strict"]) == expected_id_hash, "UK frozen person IDs differ")
    require(len(all_uk["strict"]) == len(all_uk["expanded"]) == 2371, "UK inclusive count metadata differs")
    require(all(populations["strict"][pid]["analysis_DOB"] == populations["expanded"][pid]["analysis_DOB"] for pid in selected["strict"]), "UK strict/expanded DOB coordinates differ")
    without_loc = {r["person_id"] for r in _read_v4_rows(archive, "outputs/sensitivity/expanded_without_LOC_quoted_metadata_people.jsonl.gz")}
    return selected, all_uk, fields, populations["expanded"], without_loc


def sha_ids(ids):
    return hashlib.sha256(canonical(sorted(ids)).encode()).hexdigest()


def _pool_observation(person, index, pool, fields, without_loc):
    # Exact features at the original Gregorian analysis coordinate, from the
    # frozen original calendar pool. Do not inspect inclusive Nobel features.
    feature = pool["features"][index]
    pid = person["person_id"]
    return {"person_id": pid, "analysis_DOB": person["analysis_DOB"],
            "ten_god_counts_five_positions": {g: int(v) for g, v in zip(GODS, pool["ten_god_counts"][index])},
            "guan_yin_narrow": bool(feature[2]), "shangguan_yin_narrow": bool(feature[3]),
            "guan_yin_broad": bool(pool["GY_broad"][index]),
            "shangguan_yin_broad": bool(pool["SGY_broad"][index]),
            "day_master_water": bool(feature[4]), "day_master": STEMS[int(feature[5])],
            "jie_boundary_plus_minus_one_civil_day": bool(pool["jie_boundary_plus_minus_one_civil_day"][index]),
            "included_expanded_without_LOC": pid in without_loc,
            "Fields_parallel": pid in fields,
            "assumptions_lock_commit": "6d02e0e4f22da59d171888d75a5163bb1ee410d8"}


def main(args):
    receipt, paths = verify_gate(args)
    output = Path(args.output_dir)
    require(not output.exists(), "Output directory must not exist; no overwrite")
    with zipfile.ZipFile(args.v4_zip) as archive:
        selected, all_uk, fields, people, without_loc = _selected_population(archive)
    require(all(r["hemisphere"] == "north" and not r["person_level_DOB_analysis_hold"] for r in people.values()), "UK source hemisphere/hold changed")
    pool = load_pool(paths["calendar_pool"])
    lookup = {str(date): i for i, date in enumerate(pool["dates"])}
    require(all(r["analysis_DOB"] in lookup for r in people.values()), "UK DOB outside frozen calendar")
    charts = {pid: _pool_observation(r, lookup[r["analysis_DOB"]], pool, fields["expanded"], without_loc)
              for pid, r in people.items()}
    require(len(fields["strict"] & selected["strict"]) == 5, "UK Fields overlap differs")
    models = {"year": CalendarModel(pool), "broad": CalendarModel(pool, broad=True),
              "noJie": CalendarModel(pool, no_jie=True), "yearMonth": CalendarModel(pool, month=True)}
    rows_for = lambda ids: [charts[pid] for pid in sorted(ids)]
    strict_rows, expanded_rows = rows_for(selected["strict"]), rows_for(selected["expanded"])
    definitions = [
        ("strict_primary", strict_rows, models["year"]),
        ("expanded", expanded_rows, models["year"]),
        ("strict_broad", strict_rows, models["broad"]),
        ("strict_noJie", [r for r in strict_rows if not r["jie_boundary_plus_minus_one_civil_day"]], models["noJie"]),
        ("strict_yearMonth", strict_rows, models["yearMonth"]),
        ("expanded_withoutLOC", [r for r in expanded_rows if r["included_expanded_without_LOC"]], models["year"]),
        ("strict_withoutFields", [r for r in strict_rows if not r["Fields_parallel"]], models["year"]),
    ]
    require([name for name, _, _ in definitions] == CASE_ORDER, "Case order changed")
    cases = [run_case(name, rows, model, i, COUNTRIES.index("UK_Royal_Society")) for i, (name, rows, model) in enumerate(definitions)]
    result = {"schema": "scientist_UK_Royal_Society_country_reveal_v1", "country": "UK_Royal_Society",
              "source_unit_definition": "unique North-born person with qualified UK Royal Society membership,1835-1985DOB,admission<=2025; institution country is not nationality/birth country",
              "primary_population": "strict_S1_S2_UK_Royal_Society_excluding_full_official_Nobel_roster",
              "primary_n": len(selected["strict"]), "expanded_sensitivity_n": len(selected["expanded"]),
              "strict_expanded_people_identical": True,
              "all_UK_counts_only_no_feature_reveal": {q: len(ids) for q, ids in all_uk.items()},
              "observation_carrier": "V4 UK-selected analysis_DOB exact index into original frozen calendar_pool; no calendar recomputation",
              "original_country_engine_commit": "327cc1382828b2159a55db9c3a20231c1546345a",
              "original_country_engine_sha256": "c24b25271c3ca8a3e3a870d2476f7d2c2596f457a1232ef5b1bd85f71c9e42fe",
              "original_statistical_functions_unchanged": ["CalendarModel", "observed_arrays", "mc_tests", "bootstrap_intervals", "descriptive", "run_case"],
              "secondary_country_inference_family": {"countries": COUNTRIES, "endpoints": METRICS,
                  "family_size": BONFERRONI_FAMILY_SIZE, "adjustment": "Bonferroni", "alpha": 0.05,
                  "scope": "six_strict_primary_endpoints_per_country36total; sensitivities_descriptive_references_only",
                  "distinct_from_global_18_Holm": True},
              "cases": cases,
              "limitations": ["Only UK non-Nobel feature aggregates produced; other-country and Nobel-specific outcomes unopened.",
                  "Inclusive UK outputs contain count metadata only; no subtractable trait table.",
                  "Calendar null is uniform valid dates conditional on each person's year, not measured population births.",
                  "Each selected person has single-country weight1; original global multi-institution fractional weights unchanged.",
                  "Strict and expanded source groups contain exactly the same2293people; neither is an independent replication.",
                  "Sensitivity MC reuses fixed per-endpoint seeds; no favorable version selection.",
                  "Bonferroni36 family and original18 remain unchanged; unadjusted bootstrap intervals are descriptive.",
                  "No true birth hour, historical timezone or causal mechanism is inferred."],
              "hashes": {"engine_sha256": sha(__file__), "receipt_sha256": sha(args.execution_receipt),
                         **{k + "_sha256": sha(v) for k, v in paths.items()}},
              "execution_lock_receipt": receipt,
              "execution_completed_at_utc": dt.datetime.now(dt.timezone.utc).isoformat()}
    output.mkdir(parents=True, exist_ok=False)
    destination = output / "UK_country_results.json"
    destination.write_text(json.dumps(json_safe(result), ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    (output / "OUTPUT_SHA256.json").write_text(json.dumps({destination.name: sha(destination)}, indent=2) + "\n")
    print(json.dumps({"status": "PASS", "country": "UK_Royal_Society", "primary_n": len(selected["strict"]),
                      "expanded_n": len(selected["expanded"]), "cases": len(cases), "results": str(destination)}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ["v4-zip", "calendar-npz", "scope", "locked-files", "execution-receipt", "output-dir"]:
        parser.add_argument("--" + option, required=True)
    main(parser.parse_args())
