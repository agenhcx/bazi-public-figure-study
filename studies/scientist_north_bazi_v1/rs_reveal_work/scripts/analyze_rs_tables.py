#!/usr/bin/env python3
"""Gated UK Royal Society count tables and birth-decade supplement.

Shared NAS encoding and numerical kernels are reused without mutation.  This
module never executes cohort summaries merely by being imported.
"""
import argparse
from collections import Counter
import copy
import datetime as dt
from fractions import Fraction
import hashlib
import importlib.util
import json
from pathlib import Path
import zipfile

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
COUNTRY = "UK_Royal_Society"
STEMS = "甲乙丙丁戊己庚辛壬癸"
GODS = ["比肩", "劫财", "食神", "伤官", "偏财", "正财", "七杀", "正官", "偏印", "正印"]
ELEMENTS = ["金", "木", "水", "火", "土"]
ELEMENT_INDEX = {"木": 0, "火": 1, "土": 2, "金": 3, "水": 4}
N_PEOPLE = 2293
ID_SHA = "15d3eadfe82ca2de2b8b0fd0430083edd7cd450c5d7086d33985c0943fbdede4"
V4_SHA = "53302ef5c4bbb946adcaceb70d7a7fd576c7f06d03c3e7080874654e1a2644f9"
CALENDAR_SHA = "d150883033464ebd3afafaf764738ed3b573d0d0fb4bd252a955e403a75fcc8b"
TREND_SEED_BASE = 202611180000
DEPENDENCIES = {
    "encoder": ("nas_full_tables_work/scripts/build_full_nas_tables.py", "4b3ea67141c2363b4fb760ce365063545a4717542860caddf82c501d312ddc1d"),
    "decades": ("nas_decade_work/scripts/analyze_decades.py", "60805842463d7578704b42e1ad95a3943e77086902c08fd8d5d28709bf39817f"),
    "counts": ("nas_elements_conditional_work/scripts/analyze_elements_conditional.py", "d0a9c1a73853c976e8183598b2a46775261301a90bf11e70c3ba0b9ca0948b73"),
}


def require(ok, message):
    if not bool(ok):
        raise AssertionError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_dependencies():
    out = {}
    for key, (rel, digest) in DEPENDENCIES.items():
        path = ROOT / rel
        require(sha(path) == digest, "Frozen shared numerical module differs: " + key)
        spec = importlib.util.spec_from_file_location("RS_shared_" + key, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        out[key] = module
    return out


def endpoint_definitions():
    endpoints = [{"id": "DM_" + s, "family": "DM10", "label": s,
                  "position_denominator": 1, "display_unit": "person_share"} for s in STEMS]
    for model in ["M0", "M1"]:
        endpoints += [{"id": model + "_" + god, "family": model, "label": god,
                       "position_denominator": 5, "display_unit": "five_position_share"} for god in GODS]
    for model in ["M0", "M1"]:
        endpoints += [{"id": model + "_element_" + e, "family": model + "_elements", "label": e,
                       "position_denominator": 5, "display_unit": "five_position_share"} for e in ELEMENTS]
    require(len(endpoints) == 40, "Count endpoint family differs")
    return endpoints


def level_result(years, observed, cal, endpoint, j, counts_module):
    year_counts = Counter(int(y) for y in years)
    observed_total = int(observed[:, j].sum())
    expectation = sum((count * Fraction(int(cal[year]["sum"][j]), cal[year]["D"])
                       for year, count in year_counts.items()), Fraction())
    pmfs = {year: cal[year]["pmf"][j] for year in year_counts}
    dist = counts_module.sum_distribution(pmfs, year_counts)
    support = np.arange(len(dist))
    expected_total = float(expectation)
    analytic_var = sum(count * (int(cal[year]["square_sum"][j]) / cal[year]["D"] -
                               (int(cal[year]["sum"][j]) / cal[year]["D"]) ** 2)
                       for year, count in year_counts.items())
    require(abs(float(np.dot(support, dist)) - expected_total) < 1e-8, "Count PMF mean mismatch")
    require(abs(float(np.dot((support - expected_total) ** 2, dist)) - analytic_var) < 1e-7,
            "Count PMF variance mismatch")
    denominator = len(years) * endpoint["position_denominator"]
    return {"endpoint_id": endpoint["id"], "family": endpoint["family"], "label": endpoint["label"],
            "people": len(years), "position_denominator": denominator,
            "observed_total": observed_total, "calendar_expected_total": expected_total,
            "observed_share": observed_total / denominator, "calendar_expected_share": expected_total / denominator,
            "observed_mean_per_person": observed_total / len(years),
            "calendar_expected_mean_per_person": expected_total / len(years),
            "excess_percentage_points": (observed_total - expected_total) / denominator * 100,
            "enrichment_ratio": observed_total / expected_total if expected_total else None,
            "observed_people_with_at_least_one": int((observed[:, j] > 0).sum()),
            "null_SD_total": max(0., analytic_var) ** .5,
            **counts_module.centered_exact_test(observed_total, expectation, dist)}


def synthetic_qa():
    deps = load_dependencies()
    require(len(endpoint_definitions()) == 40 and len(endpoint_definitions()[:30]) == 30, "Fixed family size")
    # No observed cohort or calendar files are loaded here.
    count = deps["counts"].synthetic_qa()
    decade = deps["decades"].synthetic_qa()
    return {"schema": "RS_tables_synthetic_QA_v1", "status": "PASS", "study_inputs_loaded": False,
            "count_kernels": count, "decade_kernels": decade, "fixed_level_count": 40, "fixed_trend_count": 30}


def main(args):
    if args.synthetic_qa_only:
        print(json.dumps(synthetic_qa(), ensure_ascii=False, indent=2))
        return
    scope = json.loads(Path(args.scope).read_text())
    receipt = json.loads(Path(args.execution_receipt).read_text())
    require(scope["country"] == COUNTRY and scope["endpoint_definitions"] == endpoint_definitions(), "UK scope differs")
    require(scope["code_sha256"] == sha(__file__), "UK code differs from prospective scope")
    require(receipt["remote_plan_and_code_verified_before_summary"] is True, "UK remote execution lock absent")
    require(receipt["scope_sha256"] == sha(args.scope), "Execution scope hash mismatch")
    locked = json.loads(Path(args.locked_files).read_text())
    require(receipt["locked_file_manifest_sha256"] == sha(args.locked_files), "Execution lock manifest hash mismatch")
    for rel, digest in locked.items():
        require(sha(ROOT / rel) == digest, "Locked file changed: " + rel)
    require(sha(args.v4_zip) == V4_SHA == scope["input_sha256"]["v4_zip"], "Frozen V4 input changed")
    require(sha(args.calendar_npz) == CALENDAR_SHA == scope["input_sha256"]["calendar_npz"], "Frozen calendar changed")
    output = Path(args.output)
    require(not output.exists(), "No overwrite of UK results")
    deps = load_dependencies()
    encoder, decades, counts = deps["encoder"], deps["decades"], deps["counts"]
    with zipfile.ZipFile(args.v4_zip) as z:
        selected = {}
        for source in ["strict", "expanded"]:
            institution = {p["person_id"] for p in encoder.read_zip_rows(z, "outputs/" + source + "/by_institution/" + COUNTRY + ".jsonl.gz")}
            no_nobel = {p["person_id"] for p in encoder.read_zip_rows(z, "outputs/" + source + "/academy_excluding_official_Nobel.jsonl.gz")}
            selected[source] = institution & no_nobel
        require(selected["strict"] == selected["expanded"] and len(selected["strict"]) == N_PEOPLE,
                "Frozen UK source memberships differ from identical2293")
        people = {p["person_id"]: p for p in encoder.read_zip_rows(z, "outputs/expanded/people.jsonl.gz")
                  if p["person_id"] in selected["strict"]}
    require(set(people) == selected["strict"], "Selected UK people missing")
    rows = [people[pid] for pid in sorted(people)]
    require(encoder.id_hash(people) == ID_SHA, "Frozen UK person ID hash differs")
    require(all(p["hemisphere"] == "north" and not p["person_level_DOB_analysis_hold"] for p in rows), "UK hemisphere/hold differs")
    observed_years = np.asarray([int(p["analysis_DOB"][:4]) for p in rows], dtype=np.int64)
    require(np.all((observed_years >= 1835) & (observed_years <= 1985)), "UK date outside frozen window")
    with np.load(args.calendar_npz, allow_pickle=False) as z:
        dates, years = z["dates"], z["year"].astype(np.int64)
        gods, positions = encoder.encode_pool(z["year_pillar"], z["month_pillar"], z["day_pillar"])
    require(len(dates) == 55152 and len(set(dates.tolist())) == 55152, "Calendar cardinality changed")
    elements = [counts.element_counts(gods[name], positions["day_stem"])
                for name in ["M0_5_mainqi", "M1_5_priority"]]
    display_indexes = [ELEMENT_INDEX[e] for e in ELEMENTS]
    values = np.concatenate([np.eye(10, dtype=np.int16)[positions["day_stem"]],
                             gods["M0_5_mainqi"], gods["M1_5_priority"],
                             elements[0][:, display_indexes], elements[1][:, display_indexes]], axis=1).astype(np.int64)
    require(values.shape == (55152, 40), "Fixed endpoint matrix shape differs")
    date_index = {str(d): i for i, d in enumerate(dates)}
    indexes = np.asarray([date_index[p["analysis_DOB"]] for p in rows], dtype=np.intp)
    observed = values[indexes]
    endpoints = endpoint_definitions()
    cal = decades.calendar_stats(years, values)
    population_decades = Counter(int(y // 10 * 10) for y in observed_years)
    common = [d for d in decades.DECADES if population_decades[d] >= 20]
    require(len(common) >= 2, "UK adequate-bin trend not estimable")
    if "common_adequate_decades" in scope:
        require(scope["common_adequate_decades"] == common, "Preselected common bins differ")
    levels = []
    for j, endpoint in enumerate(endpoints):
        print(json.dumps({"phase": "level", "endpoint": endpoint["id"], "index": j + 1, "total": 40}), flush=True)
        levels.append(level_result(observed_years, observed, cal, endpoint, j, counts))
    for entry, p in zip(levels, decades.holm([e["p_two_sided"] for e in levels])):
        entry.update(p_Holm40=float(p), reject_Holm40_0_05=bool(p <= .05),
                     inference_role="UK_supplementary_level_family40_strict")
    bins = decades.summarize_bins(observed_years, observed, cal, endpoints)
    trends = []
    for j, endpoint in enumerate(endpoints[:30]):
        print(json.dumps({"phase": "trend", "endpoint": endpoint["id"], "index": j + 1, "total": 30}), flush=True)
        t = decades.one_trend(observed_years, observed[:, j], cal, j,
                              100 / endpoint["position_denominator"], TREND_SEED_BASE + j)
        t.update(endpoint_id=endpoint["id"], family=endpoint["family"], label=endpoint["label"])
        trends.append(t)
    for entry, p in zip(trends, decades.holm([t["p_nominal_two_sided"] for t in trends])):
        entry.update(p_Holm30=float(p), reject_Holm30_0_05=bool(p <= .05),
                     inference_role="UK_supplementary_birth_decade_trends_family30_strict")
    keep = np.isin(observed_years // 10 * 10, common)
    common_trends = []
    for j, endpoint in enumerate(endpoints[:30]):
        t = decades.one_trend(observed_years[keep], observed[keep, j], cal, j,
                              100 / endpoint["position_denominator"], 0, simulate=False)
        t.update(endpoint_id=endpoint["id"], family=endpoint["family"], label=endpoint["label"])
        common_trends.append(t)
    # Supplemental year/month stem tables are descriptive; DayStem reproduces
    # the10 already tested DM endpoints. No further tests are introduced.
    stem_tables = {}
    for position in ["year_stem", "month_stem", "day_stem"]:
        a = positions[position]
        obs = np.bincount(a[indexes], minlength=10)
        exp = sum(count * np.bincount(a[years == year], minlength=10) / int(np.count_nonzero(years == year))
                  for year, count in Counter(int(y) for y in observed_years).items())
        stem_tables[position] = [{"stem": s, "observed_people": int(obs[j]), "calendar_expected_people": float(exp[j]),
                                  "observed_share": float(obs[j] / len(rows)), "calendar_expected_share": float(exp[j] / len(rows)),
                                  "hypothesis_test_performed_in_this_table": False,
                                  "same_as_level_DM_endpoint" : position == "day_stem"} for j, s in enumerate(STEMS)]
    group = {"people": len(rows), "five_position_denominator": 5 * len(rows), "person_ids_sha256": ID_SHA,
             "birth_year_min": int(observed_years.min()), "birth_year_max": int(observed_years.max()),
             "levels": levels, "bins": bins, "trends": trends, "HeavenlyStem_positions": stem_tables,
             "common_adequate_bins_desc": {"people": int(keep.sum()), "decades": common,
                                           "minimum_people_per_bin_in_both_sources": 20,
                                           "hypothesis_tests_performed": False, "trends": common_trends}}
    for family in ["DM10", "M0", "M1", "M0_elements", "M1_elements"]:
        normalizer = len(rows) * (1 if family == "DM10" else 5)
        require(sum(e["observed_total"] for e in levels if e["family"] == family) == normalizer, "Family totals differ")
        require(abs(sum(e["calendar_expected_total"] for e in levels if e["family"] == family) - normalizer) < 1e-8,
                "Calendar family totals differ")
    expanded = copy.deepcopy(group)
    expanded.update(reused_from="strict", inference_role="identical_source_membership_duplicate_display_not_replication")
    result = {"schema": "UK_Royal_Society_full_tables_and_decade_trends_v1", "country": COUNTRY,
              "endpoint_order": endpoints, "trend_endpoint_order": endpoints[:30],
              "decade_bins": decades.DECADES, "common_adequate_decades": common,
              "source_groups_identical": True, "expanded_equals_strict": True,
              "computed_source_cases": ["strict"], "expanded_results_reused_from": "strict",
              "groups": {"strict": group, "expanded": expanded},
              "multiple_testing": "Holm40_UK_levels;separate_Holm30_UK_decade_linear_trends;original18_and_country36_unchanged",
              "trend_type": "linear_only;no_linear_signal_does_not_exclude_nonlinear_decade_variation",
              "yearly_null": "uniform_valid_dates_given_each_Gregorian_birthyear;whole_person_count_marginals",
              "trends_MC": {"replicates": decades.REPLICATES, "seed_base": TREND_SEED_BASE,
                            "seed_formula": "seed_base+endpoint_index0to29;one_source_case_only",
                            "integer_LCM": decades.LCM, "adaptive_stopping": False},
              "original18_or_country36_modified": False, "other_unopened_country_or_Nobel_subgroups_aggregated": False,
              "execution_scope": scope, "execution_receipt": receipt,
              "source_and_code_sha256": {"code": sha(__file__), "v4_zip": sha(args.v4_zip),
                                         "calendar_npz": sha(args.calendar_npz),
                                         **{key: digest for key, (_, digest) in DEPENDENCIES.items()}},
              "completed_at_utc": dt.datetime.now(dt.timezone.utc).isoformat()}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"status": "PASS", "output": str(output), "people": len(rows),
                      "expanded_identical_reused": True, "Holm40_rejections": sum(e["reject_Holm40_0_05"] for e in levels),
                      "Holm30_rejections": sum(t["reject_Holm30_0_05"] for t in trends)}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--synthetic-qa-only", action="store_true")
    for option in ["scope", "locked-files", "execution-receipt", "v4-zip", "calendar-npz", "output"]:
        parser.add_argument("--" + option)
    main(parser.parse_args())
