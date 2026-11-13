#!/usr/bin/env python3
"""Independently audit NAS-only results after the remote execution lock.

Preparing/importing this module does not open study or calendar data. The CLI
requires the prospective execution receipt, current Git object hashes, and a
completed NAS result. Exact univariate tails below are QA references only; the
reported, locked 99,999-replicate Monte Carlo p values are never replaced.
"""
import argparse
from collections import Counter
import datetime as dt
import gzip
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import zipfile

import numpy as np

BASE = Path(__file__).resolve().parents[2]
STEMS = list("甲乙丙丁戊己庚辛壬癸")
GODS = ["比肩", "劫财", "食神", "伤官", "偏财", "正财", "七杀", "正官", "偏印", "正印"]
METRICS = ["PI_count", "SG_count", "GY_narrow", "SGY_narrow", "water_DM", "DM_index"]
CASES = ["strict_primary", "expanded", "strict_broad", "strict_noJie", "strict_yearMonth", "expanded_withoutLOC", "strict_withoutFields"]
R = 99999
V4_SHA = "53302ef5c4bbb946adcaceb70d7a7fd576c7f06d03c3e7080874654e1a2644f9"
CHECKS = []


def require(ok, message):
    if not bool(ok):
        raise AssertionError(message)


def close(actual, expected, label, atol=1e-10):
    require(np.allclose(actual, expected, rtol=1e-10, atol=atol), label)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical_ids(ids):
    value = json.dumps(sorted(ids), ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    return hashlib.sha256(value.encode()).hexdigest()


def verify_gate(args):
    """No cohort/calendar feature file is opened before this returns."""
    require(not Path(args.output).exists(), "Audit output already exists; no overwrite")
    require(Path(args.results).is_file(), "Completed result is required before audit")
    receipt = json.loads(Path(args.execution_receipt).read_text())
    require(receipt.get("country") == "NAS", "This audit is authorized for NAS only")
    require(receipt.get("inference_authorized") is True, "Missing NAS inference authorization")
    require(receipt.get("remote_Git_lock_verified_before_inference") is True, "Missing prior remote execution lock")
    commit = receipt.get("lock_commit_sha", "")
    require(re.fullmatch(r"[0-9a-f]{40}", commit), "Invalid execution-lock commit")
    original = receipt.get("original_assumptions_lock_commit", "")
    require(re.fullmatch(r"[0-9a-f]{40}", original), "Missing original chart lock")
    repo = Path(subprocess.check_output(["git", "-C", str(BASE), "rev-parse", "--show-toplevel"], text=True).strip())
    require(subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip() == commit,
            "Runtime HEAD differs from execution lock")
    pinned = receipt.get("file_sha256", {})
    require(str(Path(__file__).resolve().relative_to(BASE)) in pinned, "Receipt must pin this audit script")
    require(any(p.endswith(".md") for p in pinned), "Receipt must pin the execution note")
    for rel, digest in pinned.items():
        path = (BASE / rel).resolve()
        require(path.is_relative_to(BASE), "Execution pin escapes study root")
        require(sha(path) == digest, "Changed execution file: " + rel)
        content = subprocess.check_output(["git", "-C", str(repo), "show", commit + ":" + str(path.relative_to(repo))])
        require(hashlib.sha256(content).hexdigest() == digest, "Execution pin differs from committed Git object: " + rel)
    inputs = {"charts": Path(args.charts_dir) / "charts_unique_expanded.jsonl.gz",
              "groups": Path(args.charts_dir) / "group_memberships.jsonl.gz",
              "calendar_pool": Path(args.calendar_dir) / "calendar_pool.npz",
              "V4_zip": Path(args.v4_zip)}
    for key, receipt_key in [("charts", "input_chart_sha256"), ("groups", "input_groups_sha256"), ("calendar_pool", "pool_npz_sha256")]:
        require(sha(inputs[key]) == receipt.get(receipt_key), "Input receipt SHA mismatch: " + key)
    require(sha(inputs["V4_zip"]) == V4_SHA, "V4 immutable source hash differs")
    return receipt, inputs


def select_NAS(inputs, original_lock):
    wanted = {"strict/by_institution/NAS.jsonl.gz", "expanded/by_institution/NAS.jsonl.gz",
              "strict/academy_excluding_official_Nobel.jsonl.gz", "expanded/academy_excluding_official_Nobel.jsonl.gz"}
    groups = {key: set() for key in wanted}
    with gzip.open(inputs["groups"], "rt", encoding="utf-8") as handle:
        for line in handle:
            member = json.loads(line)
            if member["population_path"] in groups:
                groups[member["population_path"]].add(member["person_id"])
    all_strict = groups["strict/by_institution/NAS.jsonl.gz"]
    all_expanded = groups["expanded/by_institution/NAS.jsonl.gz"]
    strict = all_strict & groups["strict/academy_excluding_official_Nobel.jsonl.gz"]
    expanded = all_expanded & groups["expanded/academy_excluding_official_Nobel.jsonl.gz"]
    require(len(all_strict) == 1130 and len(all_expanded) == 1690, "NAS all-member population changed")
    require(len(strict) == 908 and len(expanded) == 1462, "NAS nonNobel primary populations changed")
    require(strict <= expanded <= all_expanded and all_strict <= all_expanded, "NAS groups are not nested")
    charts = {}
    chart_metadata = {}
    metadata_keys = ["person_id", "analysis_DOB", "included_strict", "included_expanded", "qualified_academy_memberships", "DOB_support", "hemisphere", "person_level_DOB_analysis_hold", "assumptions_lock_commit", "full_official_award_status"]
    with gzip.open(inputs["charts"], "rt", encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            if row["person_id"] in all_expanded:
                pid = row["person_id"]
                require(pid not in chart_metadata, "Duplicate NAS chart ID")
                chart_metadata[pid] = {key:row[key] for key in metadata_keys}
                if pid in expanded:
                    charts[pid] = row
    require(set(chart_metadata) == all_expanded and set(charts) == expanded, "NAS chart metadata/feature coverage mismatch")
    with zipfile.ZipFile(inputs["V4_zip"]) as archive:
        source = gzip.decompress(archive.read("scientist_north_data_freeze_v4/outputs/person_data_eligibility_v4.jsonl.gz"))
    seen = set()
    keys = ["analysis_DOB", "included_strict", "included_expanded", "qualified_academy_memberships", "DOB_support", "hemisphere", "person_level_DOB_analysis_hold"]
    for line in source.decode().splitlines():
        original = json.loads(line)
        pid = original["person_id"]
        if pid not in chart_metadata:
            continue
        row = chart_metadata[pid]
        require(all(row[k] == original[k] for k in keys), "NAS chart altered a V4 source field: " + pid)
        require(row["assumptions_lock_commit"] == original_lock, "NAS chart assumptions lock changed")
        require(row["hemisphere"] == "north" and not row["person_level_DOB_analysis_hold"], "Held/nonNorth NAS person selected")
        require("NAS" in row["qualified_academy_memberships"], "No qualified NAS route")
        require("1835-01-01" <= row["analysis_DOB"] <= "1985-12-31", "NAS DOB outside locked window")
        dt.date.fromisoformat(row["analysis_DOB"])
        require(row["included_expanded"] is True, "Noneligible chart selected")
        for support in row["DOB_support"]["expanded"]:
            require(support["analysis_date_coordinate"] == row["analysis_DOB"], "Same-person source support uses another date")
        if pid in strict:
            require(row["included_strict"] is True and row["DOB_support"]["strict"], "Strict source support absent")
        if pid in expanded:
            require(row["full_official_award_status"]["eligible_as_nonNobel_control_for_award_condition_only"] is True,
                    "NonNobel selection not supported by full-roster screen")
        seen.add(pid)
    require(seen == all_expanded, "Missing original V4 NAS records")
    return charts, strict, expanded, all_strict, all_expanded


def read_calendar(path):
    with np.load(path, allow_pickle=False) as source:
        p = {key: source[key] for key in source.files}
    require(p["feature_names"].tolist() == METRICS and p["dm_stems"].tolist() == STEMS,
            "Calendar metric/stem order changed")
    require(p["ten_god_names"].tolist() == GODS, "Calendar TenGod order changed")
    start, stop = dt.date(1835, 1, 1), dt.date(1985, 12, 31)
    dates = [start + dt.timedelta(days=i) for i in range((stop-start).days+1)]
    require(p["dates"].tolist() == [d.isoformat() for d in dates], "Calendar does not enumerate all valid locked dates")
    require(np.array_equal(p["year"], [d.year for d in dates]), "Pool year labels mismatch date strings")
    require(np.array_equal(p["month"], [d.month for d in dates]), "Pool month labels mismatch date strings")
    require(p["features"].shape == (len(dates), 6), "Calendar feature dimensions invalid")
    require(np.all(p["ten_god_counts"].sum(axis=1) == 5), "Calendar five-position total invalid")
    require(np.all((p["features"][:, :2] >= 0) & (p["features"][:, :2] <= 5)), "Count support outside0..5")
    require(np.all((p["features"][:, 2:5] >= 0) & (p["features"][:, 2:5] <= 1)), "Binary support outside0..1")
    require(np.all((p["features"][:, 5] >= 0) & (p["features"][:, 5] <= 9)), "DM index outside0..9")
    return p


def observed(rows, broad):
    vals, gods, dm = [], [], []
    for row in rows:
        g = row["ten_god_counts_five_positions"]
        require(set(g) == set(GODS) and sum(g.values()) == 5, "Observed five-position counts invalid")
        gy = (g["正官"] + (g["七杀"] if broad else 0) > 0) and (g["正印"] + (g["偏印"] if broad else 0) > 0)
        sgy = g["伤官"] > 0 and (g["正印"] + (g["偏印"] if broad else 0) > 0)
        require(bool(row["guan_yin_broad" if broad else "guan_yin_narrow"]) == gy, "Stored GY flag does not match counted cooccurrence")
        require(bool(row["shangguan_yin_broad" if broad else "shangguan_yin_narrow"]) == sgy, "Stored SGY flag mismatch")
        require(row["day_pillar"][0] == row["day_master"], "Stored DM differs from day pillar")
        index = STEMS.index(row["day_master"])
        water = index in (8,9)
        require(bool(row["day_master_water"]) == water, "Stored water indicator differs from DM")
        vals.append([g["偏印"],g["伤官"],int(gy),int(sgy),int(water)])
        gods.append([g[name] for name in GODS])
        dm.append(index)
    return np.asarray(vals,dtype=np.int64), np.asarray(gods,dtype=np.int64), np.asarray(dm,dtype=np.int64)


def distributions(rows, pool, month, no_jie, broad):
    """Independent date-mask lookup, not the result engine's calendar model."""
    keys = []
    cache = {}
    for row in rows:
        date = dt.date.fromisoformat(row["analysis_DOB"])
        key = (date.year, date.month if month else None)
        keys.append(key)
        if key in cache:
            continue
        mask = pool["year"] == date.year
        if month:
            mask = mask & (pool["month"] == date.month)
        if no_jie:
            mask = mask & ~pool["jie_boundary_plus_minus_one_civil_day"].astype(bool)
        require(mask.any(), "Empty prespecified calendar candidate set")
        v = pool["features"][mask].astype(np.int64).copy()
        if broad:
            v[:,2] = pool["GY_broad"][mask]
            v[:,3] = pool["SGY_broad"][mask]
        pmfs = [np.bincount(v[:,j],minlength=6 if j<2 else 2).astype(float)/len(v) for j in range(5)]
        expected = np.asarray([np.dot(np.arange(len(p)),p) for p in pmfs])
        dm = np.bincount(v[:,5],minlength=10).astype(float)/len(v)
        cache[key] = {"pmfs":pmfs,"expected":expected,"DM":dm,"gods":pool["ten_god_counts"][mask].mean(axis=0),"dates":int(mask.sum())}
    return keys,cache


def exact_sum_distribution(keys, cache, metric):
    """Product of independent person-specific probability polynomials."""
    distribution = np.asarray([1.0])
    for key in keys:
        pmf = cache[key]["pmfs"][metric]
        # Keep the absolute integer support, including leading zero coefficients.
        last = np.flatnonzero(pmf)[-1]
        distribution = np.convolve(distribution,pmf[:last+1])
    mass = float(distribution.sum())
    require(abs(mass-1.0)<1e-9 and np.all(distribution>=0), "Exact QA convolution lost probability mass")
    distribution /= mass
    return distribution


def distance_tie_tolerance(observed_distance):
    """Prospectively fixed numeric tie handling for the DM10 distance only."""
    return 1e-12 * max(1.0, abs(float(observed_distance)))


def check_summary(summary, rows, pool, broad=False, month=False, no_jie=False, tested=False, case_index=None):
    n = len(rows)
    require(summary["n"] == n and summary["unique_person_count"] == len({r["person_id"] for r in rows}) == n,
            "NAS summary population size mismatch")
    require(n > 0, "Unexpected empty locked NAS case")
    x,gods,dm = observed(rows,broad)
    keys,cache = distributions(rows,pool,month,no_jie,broad)
    expected = np.asarray([cache[k]["expected"] for k in keys])
    expected_dm = np.asarray([cache[k]["DM"] for k in keys]).sum(axis=0)
    expected_gods = np.asarray([cache[k]["gods"] for k in keys]).mean(axis=0)
    require(len(summary["scalar_metrics"]) == 5, "Wrong scalar endpoint family")
    for j,entry in enumerate(summary["scalar_metrics"]):
        require(entry["metric"] == METRICS[j], "Changed scalar endpoint order")
        require(entry["observed_sum"] == int(x[:,j].sum()), "Observed scalar sum mismatch")
        close(entry["observed_mean_or_rate"],x[:,j].mean(),"Observed scalar mean mismatch")
        close(entry["calendar_expected_mean_or_rate"],expected[:,j].mean(),"Calendar scalar mean mismatch")
        close(entry["observed_minus_expected"],x[:,j].mean()-expected[:,j].mean(),"Scalar excess mismatch")
        if tested:
            for label in ["raw_mean_or_rate_unadjusted_95CI","paired_excess_unadjusted_95CI"]:
                interval = np.asarray(entry[label],dtype=float)
                require(interval.shape==(2,) and np.isfinite(interval).all() and interval[0]<=interval[1],"Malformed descriptive CI")
                # A percentile CI is not forced to contain its observed point.
                bound = 5 if j<2 else 1
                lower = 0 if label.startswith("raw") else -bound
                require(interval[0]>=lower-1e-12 and interval[1]<=bound+1e-12,"CI outside possible endpoint bounds")
    dm_observed = np.bincount(dm,minlength=10)
    require(len(summary["day_master_distribution"])==10,"DM category count changed")
    for j,entry in enumerate(summary["day_master_distribution"]):
        require(entry["stem"]==STEMS[j] and entry["observed_people"]==int(dm_observed[j]),"Observed DM distribution mismatch")
        close(entry["calendar_expected_people"],expected_dm[j],"Calendar DM expected count mismatch")
        close(entry["observed_fraction"],dm_observed[j]/n,"Observed DM fraction mismatch")
        close(entry["calendar_expected_fraction"],expected_dm[j]/n,"Calendar DM expected fraction mismatch")
    close(expected_dm.sum(),n,"Expected DM total mismatch")
    require(len(summary["ten_gods_five_position_descriptive_only"])==10,"TenGod descriptive category count changed")
    for j,entry in enumerate(summary["ten_gods_five_position_descriptive_only"]):
        require(entry["ten_god"]==GODS[j] and entry["observed_count_sum"]==int(gods[:,j].sum()),"TenGod descriptive count mismatch")
        close(entry["observed_count_mean_per_person"],gods[:,j].mean(),"TenGod observed mean mismatch")
        close(entry["calendar_expected_count_mean_per_person"],expected_gods[j],"TenGod expected mean mismatch")
    if not tested:
        return {"n":n,"descriptive_values_recomputed":True,"hypothesis_tests_added":False}
    require(summary["case_index"]==case_index and summary["person_ids_sha256"]==canonical_ids(r["person_id"] for r in rows),"Case IDs or order changed")
    require(summary["calendar_condition"] == ("year_and_month" if month else "year"),"Wrong conditioning label")
    require(summary["observed_and_calendar_Jie_pm1_excluded"] is no_jie,"Asymmetric Jie conditioning label")
    require(summary["cooccurrence_encoding"] == ("broad" if broad else "narrow"),"Encoding changed")
    require(len(summary["calendar_MC_tests"])==6,"Wrong diagnostic endpoint family")
    primary = summary["case"]=="strict_primary"
    qa=[]
    for j,test in enumerate(summary["calendar_MC_tests"]):
        require(test["metric"]==METRICS[j] and test["replicates"]==R and test["seed"]==2026111300+j,"MC endpoint/seed/replicate contract changed")
        extreme=test["extreme_replicates_including_ties"]
        require(isinstance(extreme,int) and 0<=extreme<=R,"Invalid MC extreme count")
        p=(extreme+1)/(R+1)
        close(test["p_nominal_plus_one"],p,"Plus-one MC p formula incorrect",atol=1e-15)
        p36=min(1.0,36*p)
        close(test["p_Bonferroni_36_reference"],p36,"Bonferroni36 formula incorrect",atol=1e-15)
        require(test["FWER_family_size"]==36 and test["secondary_country_family_primary_member"] is primary,"Wrong country family")
        require(test["primary_Bonferroni_36_reject_0_05"]==(p36<=0.05 if primary else None),"Wrong primary rejection rule")
        require(test["sensitivity_does_not_rescue_primary"] is (not primary),"Sensitivity decision semantics changed")
        if j<5:
            observed_sum=int(x[:,j].sum())
            require(test["observed_integer_sum"]==observed_sum and test["tail"]=="upper_inclusive_integer_sum","Wrong scalar tail, ties or sum")
            distribution=exact_sum_distribution(keys,cache,j)
            close(np.dot(np.arange(len(distribution)),distribution),expected[:,j].sum(),"Convolution mean differs from date-mask expectation",atol=1e-7)
            exact_p=float(distribution[observed_sum:].sum()) if observed_sum<len(distribution) else 0.0
            mc_se=math.sqrt(exact_p*(1-exact_p)/R)
            tolerance=5*mc_se+2/R
            require(abs(p-exact_p)<=tolerance,"MC tail differs from exact conditional convolution beyond frozen QA tolerance")
            qa.append({"metric":METRICS[j],"reported_MC_p_unchanged":p,"exact_conditional_upper_inclusive_QA_p":exact_p,"MC_se_reference":mc_se,"allowed_absolute_difference":tolerance,"absolute_difference":abs(p-exact_p),"exact_distribution_total_mass":float(distribution.sum()),"exact_QA_p_does_not_replace_reported_MC_p":True})
        else:
            require(np.all(expected_dm>0),"Empty expected DM cell")
            statistic=float(np.sum((dm_observed-expected_dm)**2/expected_dm))
            close(test["observed_Pearson_distance"],statistic,"DM Pearson distance mismatch")
            require(test["tail"]=="upper_inclusive_distance","Wrong DM distance tail")
            tie_tolerance=distance_tie_tolerance(statistic)
            require(math.isclose(test["floating_point_tie_tolerance"],tie_tolerance,rel_tol=1e-12,abs_tol=1e-24),
                    "DM floating-point inclusive-tie tolerance changed")
            qa.append({"metric":"DM_index","observed_Pearson_distance_independently_recomputed":statistic,"floating_point_tie_tolerance_independently_recomputed":tie_tolerance,"DM_expected_and_observed_counts_recomputed":True,"reported_MC_plus_one_and_BF36_formulas_verified":True,"multivariate_exact_tail_not_claimed":True})
    bootstrap=summary["bootstrap"]
    require(bootstrap["replicates"]==10000 and bootstrap["confidence_level"]==0.95 and bootstrap["multiple_comparison_adjusted"] is False and bootstrap["quantile_method"]=="linear","Bootstrap interval contract changed")
    require(bootstrap["seed"]==202611150000+case_index,"Bootstrap seed changed or overlaps original MC range")
    require(summary["global_confirmatory_18_Holm_family_tested"] is False,"Country audit must not test global18family")
    return {"case":summary["case"],"n":n,"person_ids_sha256":summary["person_ids_sha256"],"conditional_calendar_strata":len(cache),"scalar_exact_tail_QA_and_DM_checks":qa,"descriptive_CI_shape_bounds_verified_not_forced_to_contain_point":True}


def main(args):
    receipt,inputs=verify_gate(args)
    result=json.loads(Path(args.results).read_text())
    require(result["schema"]=="scientist_NAS_country_reveal_v1" and result["country"]=="NAS","Unexpected country result")
    require(result["execution_lock_receipt"]==receipt,"Results did not use supplied execution receipt")
    require(result["primary_n"]==908 and result["expanded_sensitivity_n"]==1462,"Primary population contract changed")
    require(result["hashes"]["receipt_sha256"]==sha(args.execution_receipt),"Result receipt hash mismatch")
    for key in ["charts","groups","calendar_pool"]:
        require(result["hashes"][key+"_sha256"]==sha(inputs[key]),"Result input hash mismatch: "+key)
    require(result["hashes"]["engine_sha256"]==sha(BASE/"reveal_v1/scripts/analyze_country.py"),"Result engine hash differs from locked code")
    charts,strict,expanded,all_strict,all_expanded=select_NAS(inputs,receipt["original_assumptions_lock_commit"])
    pool=read_calendar(inputs["calendar_pool"])
    ids={"strict_primary":strict,"expanded":expanded,"strict_broad":strict,
         "strict_noJie":{pid for pid in strict if not charts[pid]["jie_boundary_plus_minus_one_civil_day"]},
         "strict_yearMonth":strict,
         "expanded_withoutLOC":{pid for pid in expanded if charts[pid]["included_expanded_without_LOC"]},
         "strict_withoutFields":{pid for pid in strict if not charts[pid]["Fields_parallel"]}}
    require(len(ids["strict_withoutFields"])==907,"NAS Fields sensitivity set changed")
    require([c["case"] for c in result["cases"]]==CASES,"Country cases missing or reordered")
    reports=[]
    for i,case in enumerate(result["cases"]):
        name=case["case"]
        rows=[charts[pid] for pid in sorted(ids[name])]
        reports.append(check_summary(case,rows,pool,broad=name=="strict_broad",month=name=="strict_yearMonth",no_jie=name=="strict_noJie",tested=True,case_index=i))
    require("all_NAS_descriptions_include_Nobel_without_separate_Nobel_results" not in result,
            "Inclusive NAS traits would permit a residual Nobel-subgroup reveal")
    require(result["all_NAS_counts_only_no_feature_reveal"]=={"strict":len(all_strict),"expanded":len(all_expanded)},
            "All-NAS count-only metadata mismatch")
    inclusive_checks={"strict":len(all_strict),"expanded":len(all_expanded),"features_aggregated":False}
    output={"schema":"NAS_country_independent_result_audit_v1","status":"PASS","country":"NAS","execution_lock_commit":receipt["lock_commit_sha"],
            "population_source_ID_and_DOB_checks_passed":True,"primary_n":908,"expanded_sensitivity_n":1462,
            "cases":reports,"all_NAS_counts_only_checks":inclusive_checks,
            "exact_QA_p_values_replace_reported_locked_MC_results":False,
            "other_country_features_or_Nobel_specific_subgroup_aggregates_computed":False,
            "CI_check_scope":"finite ordered valid endpoint bounds; no forced containment of the observed point; full bootstrap replay not claimed",
            "DM_MC_check_scope":"independent expectedcounts and Pearsonstatistic plus reportedMC/BF36formula; no exact10dimensionaltailclaimed",
            "input_and_code_SHA256":{**{k:sha(v) for k,v in inputs.items()},"result":sha(args.results),"execution_receipt":sha(args.execution_receipt),"audit_script":sha(__file__),"analysis_engine":sha(BASE/"reveal_v1/scripts/analyze_country.py")},
            "completed_at_utc":dt.datetime.now(dt.timezone.utc).isoformat()}
    destination=Path(args.output)
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps(output,ensure_ascii=False,indent=2,allow_nan=False)+"\n")
    print(json.dumps({"status":"PASS","country":"NAS","cases_checked":len(reports),"primary_n":908,"expanded_n":1462,"output":str(destination)}))


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--charts-dir",required=True)
    parser.add_argument("--calendar-dir",required=True)
    parser.add_argument("--v4-zip",required=True)
    parser.add_argument("--execution-receipt",required=True)
    parser.add_argument("--results",required=True)
    parser.add_argument("--output",required=True)
    main(parser.parse_args())
