#!/usr/bin/env python3
"""Post-NAS-reveal hidden-stem supplement; never runs before its own Git lock.

All eight historical encodings are disclosed descriptively. Only the two
preselected priority-5 count endpoints receive new nominal Monte Carlo p values;
M0 count p values reproduce the preceding NAS diagnostic, rather than add tests.
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

import numpy as np

BASE = Path(__file__).resolve().parents[2]
MODELS = ["M0_5", "M1_priority_5", "M1_share_5", "M1_any_5",
          "M2_main_7", "M3_priority_7", "M3_share_7", "M3_any_7"]
TRAITS = ["PI", "SG"]
DENOMINATORS = [5, 5, 5, 5, 7, 7, 7, 7]
CASE_ORDER = ["strict_primary", "expanded", "strict_noJie", "strict_yearMonth"]
COUNT_SCALE, PRESENCE_SCALE, REPLICATES = 72, 12, 99999


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"


def require(ok, message):
    if not ok:
        raise ValueError(message)


def load_npz(path):
    with np.load(path, allow_pickle=False) as source:
        return {name: source[name] for name in source.files}


def verify_gate(args):
    receipt = json.loads(Path(args.execution_receipt).read_text())
    require(receipt.get("country") == "NAS", "NAS-only authorization missing")
    require(receipt.get("inference_authorized") is True, "Hidden supplement authorization missing")
    require(receipt.get("remote_Git_lock_verified_before_inference") is True, "Supplement remote-lock verification missing")
    commit = receipt.get("lock_commit_sha", "")
    require(bool(re.fullmatch(r"[0-9a-f]{40}", commit)), "Invalid hidden supplement lock SHA")
    require(bool(re.fullmatch(r"[0-9a-f]{40}", receipt.get("original_assumptions_lock_commit", ""))), "Original chart lock missing")
    repo = Path(subprocess.check_output(["git", "-C", str(BASE), "rev-parse", "--show-toplevel"], text=True).strip())
    require(subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip() == commit,
            "Runtime HEAD differs from hidden supplement lock")
    pins = receipt.get("file_sha256", {})
    own = str(Path(__file__).resolve().relative_to(BASE))
    require(own in pins and "hidden_stem_v1/scripts/hidden_features.py" in pins and any(p.endswith(".md") for p in pins),
            "Receipt must pin analyzer, encoder and supplement note")
    for rel, digest in pins.items():
        path = (BASE / rel).resolve()
        require(path.is_relative_to(BASE), "Pinned path escapes study root")
        require(sha(path) == digest, "Locked supplement file changed: " + rel)
        content = subprocess.check_output(["git", "-C", str(repo), "show", commit + ":" + str(path.relative_to(repo))])
        require(hashlib.sha256(content).hexdigest() == digest, "Supplement differs from locked Git object: " + rel)
    paths = {"charts": Path(args.charts_dir) / "charts_unique_expanded.jsonl.gz",
             "groups": Path(args.charts_dir) / "group_memberships.jsonl.gz",
             "calendar_pool": Path(args.calendar_dir) / "calendar_pool.npz",
             "hidden_pool": Path(args.hidden_dir) / "hidden_pool.npz"}
    keys = {"charts": "input_chart_sha256", "groups": "input_groups_sha256",
            "calendar_pool": "pool_npz_sha256", "hidden_pool": "hidden_pool_npz_sha256"}
    for name, path in paths.items():
        require(sha(path) == receipt.get(keys[name]), "Hidden supplement input SHA mismatch: " + name)
    return receipt, paths


def validate_pools(calendar, hidden):
    require(hidden["models"].tolist() == MODELS and hidden["traits"].tolist() == TRAITS, "Hidden model/trait order changed")
    require(hidden["position_denominators"].tolist() == DENOMINATORS, "Hidden model denominators changed")
    require(hidden["scales"].tolist() == [COUNT_SCALE, PRESENCE_SCALE], "Hidden feature integer scales changed")
    require(hidden["metrics"].tolist() == ["count_scaled72", "presence_scaled12"], "Hidden metric axes changed")
    require(np.array_equal(calendar["dates"], hidden["dates"]), "Hidden calendar date identities changed")
    n = len(calendar["dates"])
    for key in ["year", "month", "jie_boundary_day", "jie_boundary_plus_minus_one_civil_day"]:
        require(np.array_equal(calendar[key], hidden[key]), "Hidden calendar metadata changed: " + key)
    count, presence = hidden["count_scaled72"], hidden["presence_scaled12"]
    require(count.shape == presence.shape == (n, 8, 2), "Hidden feature dimensions invalid")
    require(np.issubdtype(count.dtype, np.integer) and np.issubdtype(presence.dtype, np.integer), "Hidden scaled features must be integers")
    require(np.all(count >= 0) and np.all(presence >= 0) and np.all(presence <= PRESENCE_SCALE), "Hidden features out of bounds")
    require(np.all(count <= np.asarray(DENOMINATORS)[None, :, None] * COUNT_SCALE), "Hidden count exceeds model denominator")
    require(np.all(count[:, :2] % COUNT_SCALE == 0), "Main/priority5 counts must be integers")
    require(np.array_equal(count[:, 0, 0] // COUNT_SCALE, calendar["features"][:, 0]), "PI M0 calendar reproduction failed")
    require(np.array_equal(count[:, 0, 1] // COUNT_SCALE, calendar["features"][:, 1]), "SG M0 calendar reproduction failed")
    require(np.array_equal(presence[:, :4], (count[:, :4] > 0) * PRESENCE_SCALE), "Five-position presence must be indicator(count>0)")
    return {str(date): index for index, date in enumerate(calendar["dates"])}


class NullModel:
    def __init__(self, hidden, month=False, no_jie=False):
        self.month, self.no_jie = month, no_jie
        count, presence = hidden["count_scaled72"], hidden["presence_scaled12"]
        keep = ~hidden["jie_boundary_plus_minus_one_civil_day"].astype(bool) if no_jie else np.ones(len(count), dtype=bool)
        buckets = defaultdict(list)
        for i in np.flatnonzero(keep):
            key = (int(hidden["year"][i]), int(hidden["month"][i]) if month else 0)
            buckets[key].append(i)
        self.groups = {}
        for key, indexes in buckets.items():
            idx = np.asarray(indexes)
            pmfs = {}
            for model in (0, 1):
                for trait in (0, 1):
                    values = count[idx, model, trait] // COUNT_SCALE
                    require(np.all(values <= 5), "Tested5-position count out of bounds")
                    pmfs[(model, trait)] = np.bincount(values, minlength=6).astype(float) / len(idx)
            self.groups[key] = {"count_mean_scaled72": count[idx].mean(axis=0),
                                "presence_mean_scaled12": presence[idx].mean(axis=0), "pmfs": pmfs,
                                "calendar_dates": len(idx)}

    def key(self, row):
        date = dt.date.fromisoformat(row["analysis_DOB"])
        return (date.year, date.month if self.month else 0)


def nominal_count_test(rows, observed_scaled, model_index, trait_index, null, case_index):
    # M0 exactly reuses preceding NAS endpoint streams. Priority5 uses a new
    # predeclared supplementary stream; no direction is changed after results.
    seed = 2026111300 + trait_index if model_index == 0 else 202611160000 + 1000 * case_index + trait_index
    rng = np.random.Generator(np.random.PCG64(seed))
    totals = np.zeros(REPLICATES, dtype=np.int64)
    for key, n in sorted(Counter(null.key(row) for row in rows).items()):
        totals += rng.multinomial(n, null.groups[key]["pmfs"][(model_index, trait_index)], size=REPLICATES) @ np.arange(6, dtype=np.int64)
    observed = int(observed_scaled[:, model_index, trait_index].sum() // COUNT_SCALE)
    extreme = int(np.count_nonzero(totals >= observed))
    return {"model": MODELS[model_index], "trait": TRAITS[trait_index], "endpoint": "five_position_count_mean",
            "role": "previous_M0_p_reproduction" if model_index == 0 else "post_reveal_supplement_priority5_nominal_test",
            "observed_integer_count_sum": observed, "seed": seed, "generator": "PCG64", "replicates": REPLICATES,
            "tail": "greater_inclusive_integer_sum", "extreme_replicates_including_ties": extreme,
            "p_nominal_plus_one": (extreme + 1) / (REPLICATES + 1),
            "multiple_comparison_adjusted": False, "original_18_or_country36_family_member": False,
            "confirmatory_global_claim": False}


def summarize_case(name, rows, calendar_index, hidden, null, case_index):
    n = len(rows)
    require(n > 0, "Empty frozen NAS case: " + name)
    indexes = np.asarray([calendar_index[row["analysis_DOB"]] for row in rows])
    count = hidden["count_scaled72"][indexes]
    presence = hidden["presence_scaled12"][indexes]
    expected_count = np.asarray([null.groups[null.key(row)]["count_mean_scaled72"] for row in rows])
    expected_presence = np.asarray([null.groups[null.key(row)]["presence_mean_scaled12"] for row in rows])
    summaries = []
    for m, model_name in enumerate(MODELS):
        for t, trait in enumerate(TRAITS):
            obs_count = float(count[:, m, t].mean() / COUNT_SCALE)
            exp_count = float(expected_count[:, m, t].mean() / COUNT_SCALE)
            obs_presence = float(presence[:, m, t].mean() / PRESENCE_SCALE)
            exp_presence = float(expected_presence[:, m, t].mean() / PRESENCE_SCALE)
            denominator = DENOMINATORS[m]
            summaries.append({"model": model_name, "trait": trait,
                "position_denominator": denominator, "count_mean": obs_count, "calendar_expected_count_mean": exp_count,
                "count_mean_excess": obs_count - exp_count,
                "position_mean_share": obs_count / denominator,
                "calendar_expected_position_mean_share": exp_count / denominator,
                "position_mean_share_excess": (obs_count - exp_count) / denominator,
                "position_mean_share_excess_percentage_points": (obs_count - exp_count) / denominator * 100,
                "person_presence_probability": obs_presence,
                "calendar_expected_person_presence_probability": exp_presence,
                "person_presence_probability_excess": obs_presence - exp_presence,
                "person_presence_excess_percentage_points": (obs_presence - exp_presence) * 100,
                "presence_definition": "P(score>0)_averaged_over12_equal_hour_branches" if m >= 4 else "P(score>0)_across_people",
                "hypothetical_hour_sensitivity": m >= 4, "descriptive_only": True})
    tests = [nominal_count_test(rows, count, m, t, null, case_index) for m in (0, 1) for t in (0, 1)]
    return {"case": name, "case_index": case_index, "n": n,
            "person_ids_sha256": hashlib.sha256(canonical([r["person_id"] for r in rows]).encode()).hexdigest(),
            "calendar_condition": "year_and_month" if null.month else "year",
            "Jie_pm1_excluded_from_observed_and_calendar": null.no_jie,
            "model_trait_descriptions": summaries, "nominal_count_tests": tests,
            "presence_hypothesis_tests_performed": False, "eight_model_multiple_test_search_performed": False}


def main(args):
    receipt, paths = verify_gate(args)
    outdir = Path(args.output_dir)
    require(not outdir.exists(), "Output directory exists; no overwrite")
    groups = defaultdict(set)
    with gzip.open(paths["groups"], "rt", encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            groups[row["population_path"]].add(row["person_id"])
    strict = groups["strict/by_institution/NAS.jsonl.gz"] & groups["strict/academy_excluding_official_Nobel.jsonl.gz"]
    expanded = groups["expanded/by_institution/NAS.jsonl.gz"] & groups["expanded/academy_excluding_official_Nobel.jsonl.gz"]
    require(len(strict) == 908 and len(expanded) == 1462 and strict <= expanded, "Frozen NAS908/1462 selections differ")
    charts = {}
    with gzip.open(paths["charts"], "rt", encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            if row["person_id"] in expanded:
                require(row["person_id"] not in charts, "Duplicate selected NAS person")
                charts[row["person_id"]] = row
    require(set(charts) == expanded, "Selected NAS chart missing")
    require(all(r["assumptions_lock_commit"] == receipt["original_assumptions_lock_commit"] for r in charts.values()), "Chart lock changed")
    calendar, hidden = load_npz(paths["calendar_pool"]), load_npz(paths["hidden_pool"])
    index = validate_pools(calendar, hidden)
    for row in charts.values():
        i = index[row["analysis_DOB"]]
        require(all(row[key] == str(calendar[key][i]) for key in ("year_pillar", "month_pillar", "day_pillar")),
                "Cached calendar pillars differ from frozen NAS chart: " + row["person_id"])
        require(int(hidden["count_scaled72"][i, 0, 0]) == row["ten_god_counts_five_positions"]["偏印"] * COUNT_SCALE and
                int(hidden["count_scaled72"][i, 0, 1]) == row["ten_god_counts_five_positions"]["伤官"] * COUNT_SCALE,
                "M0 observed NAS reproduction failed: " + row["person_id"])
        require(bool(calendar["jie_boundary_plus_minus_one_civil_day"][i]) == row["jie_boundary_plus_minus_one_civil_day"],
                "Observed/null Jie exclusion flags differ")
    strict_rows = [charts[pid] for pid in sorted(strict)]
    expanded_rows = [charts[pid] for pid in sorted(expanded)]
    no_jie = [r for r in strict_rows if not r["jie_boundary_plus_minus_one_civil_day"]]
    require(len(no_jie) == 825, "Frozen NAS noJie825 selection differs")
    year = NullModel(hidden)
    definitions = [("strict_primary", strict_rows, year), ("expanded", expanded_rows, year),
                   ("strict_noJie", no_jie, NullModel(hidden, no_jie=True)),
                   ("strict_yearMonth", strict_rows, NullModel(hidden, month=True))]
    require([name for name, _, _ in definitions] == CASE_ORDER, "Case order changed")
    cases = [summarize_case(name, rows, index, hidden, null, i) for i, (name, rows, null) in enumerate(definitions)]
    result = {"schema": "NAS_hidden_stem_post_reveal_supplement_v1", "country": "NAS",
              "models": MODELS, "traits": TRAITS, "case_order": CASE_ORDER,
              "source_unit": "one_qualified_North_born_unique_NAS_person_without_official_Nobel_full_roster_match",
              "source_identity_DOB_membership_support_unchanged": True,
              "position_mean_share_definition": "mean_person_score/5_or7; not_a_person_prevalence",
              "person_presence_definition": "mean_person_indicator(score>0); hourmodels_average12_indicators_per_person_before_person_mean",
              "hypothetical_hours": "12_equal_hour_branches_exact_average_not_observed_birth_times; no_hour_imputation_into_source_records",
              "historical_encodings": "main_hidden_stem_priority; visibleYG_MG_plusHG_in_hourmodel; noDMexposure; fallbackmain; share1_over_number_qualifying_hidden; anyfullcredit",
              "post_M0_reveal_supplement_not_original_confirmatory_preregistration": True,
              "new_priority5_primary_count_endpoints": ["PI", "SG"],
              "cases": cases,
              "limits": ["All8model means, shares and presence probabilities are reported; no model selection by p value.",
                         "Only M0 reproduction and preselected M1priority5 count means receive nominal Monte Carlo p values.",
                         "Presence probabilities and inferred-hour models are descriptive; no added prevalence or hour tests.",
                         "Nominal p values are not members of original18Holm or country36Bonferroni families and make no global confirmatory claim.",
                         "No allNAS-inclusive trait totals, Nobel subgroup summaries or other-country features are exposed.",
                         "Uniform calendar dates conditional on birthyear are theoretical controls, not measured ordinary-person probabilities."],
              "hashes": {"engine_sha256": sha(__file__), "receipt_sha256": sha(args.execution_receipt),
                         **{name + "_sha256": sha(path) for name, path in paths.items()}},
              "execution_lock_receipt": receipt,
              "completed_at_utc": dt.datetime.now(dt.timezone.utc).isoformat()}
    outdir.mkdir(parents=True, exist_ok=False)
    dest = outdir / "NAS_hidden_stem_results.json"
    dest.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    (outdir / "OUTPUT_SHA256.json").write_text(json.dumps({dest.name: sha(dest)}, indent=2) + "\n")
    print(json.dumps({"status": "PASS", "country": "NAS", "strict_n": 908, "expanded_n": 1462,
                      "cases": len(cases), "models": len(MODELS), "result": str(dest)}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ("charts-dir", "calendar-dir", "hidden-dir", "execution-receipt", "output-dir"):
        parser.add_argument("--" + option, required=True)
    main(parser.parse_args())
