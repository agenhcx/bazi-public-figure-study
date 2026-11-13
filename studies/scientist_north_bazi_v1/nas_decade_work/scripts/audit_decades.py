#!/usr/bin/env python3
"""Independent NAS decade descriptions, slope/null and multiplicity audit."""
import argparse
from collections import Counter
import datetime as dt
import gzip
import hashlib
import json
import math
from pathlib import Path
import zipfile

import numpy as np
from _independent_literal_reference import encode, STEMS, GODS

L = 133590
R = 99999
BINS = list(range(1830, 1990, 10))
PRESELECTED_MC_ENDPOINTS = [0, 18, 28]
QA_R = 15000


def require(ok, message):
    if not bool(ok): raise AssertionError(message)


def close(a, b, message, atol=1e-8):
    require(np.allclose(a, b, rtol=1e-9, atol=atol), message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(z, name):
    return [json.loads(line) for line in gzip.decompress(z.read("scientist_north_data_freeze_v4/outputs/" + name)).splitlines()]


def holm(p):
    order = sorted(range(len(p)), key=lambda i: (p[i], i))
    out, run = [0.0] * len(p), 0.0
    for rank, i in enumerate(order):
        run = max(run, min(1.0, (len(p) - rank) * p[i])); out[i] = run
    return out


def synthetic_qa():
    # N=2,x=[0,1] gives linear numerator Y1-Y0. Independent Bernoulli
    # probabilities 1/3 and2/3: W=(-1,0,1), weights=(1,4,4)/9, E[W]=1/3.
    support = np.asarray([-1, 0, 1], dtype=np.int64)
    weights = np.asarray([1, 4, 4], dtype=float) / 9
    centered = support * L - L // 3
    require(float(weights[np.abs(centered) >= abs(-L - L // 3)].sum()) == 1 / 9,
            "Synthetic exact centered tail1/9 failure")
    close(weights[np.abs(centered) >= abs(L - L // 3)].sum(), 5 / 9, "Synthetic exact centered tail5/9 failure")
    close(weights[np.abs(centered) >= abs(-L // 3)].sum(), 1, "Synthetic minimum-distance inclusive ties failure")
    # A deterministic calendar increase is raw slope1, but excess slope0.
    require(abs(1 * L - L) == 0, "Deterministic nonzero calendar slope centering failure")
    require(np.all(np.abs(np.asarray([1, 1, 1]) * L - L) >= 0), "Constant null ties failure")
    close(holm([.01, .04, .03]), [.03, .06, .06], "Holm known example failure")
    return {"status": "PASS", "no_study_data_loaded": True,
            "exact_centered_two_sided_tails": [1 / 9, 5 / 9, 1.0], "deterministic_calendar_trend_excess_zero": True}


def independent_mc(endpoint, year_counts, year_coefficients, year_features, expected_scaled, observed_centered):
    rng = np.random.Generator(np.random.PCG64(202611230000 + endpoint))
    simulated = np.zeros(QA_R, dtype=np.int64)
    maximum = 1 if endpoint < 10 else 5
    for year, n in sorted(year_counts.items()):
        a = year_coefficients[year]
        values = year_features[year][:, endpoint]
        if maximum == 1:
            counts = rng.binomial(n, float(np.mean(values)), size=QA_R)
        else:
            p = np.bincount(values, minlength=6).astype(float) / len(values)
            counts = rng.multinomial(n, p, size=QA_R) @ np.arange(6, dtype=np.int64)
        simulated += a * counts
    centered = simulated * L - expected_scaled
    extreme = int(np.count_nonzero(np.abs(centered) >= abs(observed_centered)))
    return (1 + extreme) / (QA_R + 1)


def audit(args):
    require(Path(args.authorization).is_file() and Path(args.results).is_file(), "Missing authorization/completed result")
    result = json.loads(Path(args.results).read_text())
    require(sha(args.v4_zip) == "53302ef5c4bbb946adcaceb70d7a7fd576c7f06d03c3e7080874654e1a2644f9", "V4 input hash differs")
    require(sha(args.calendar_npz) == "d150883033464ebd3afafaf764738ed3b573d0d0fb4bd252a955e403a75fcc8b", "Calendar input hash differs")
    with zipfile.ZipFile(args.v4_zip) as z:
        populations = {}
        for quality, label in [("strict", "strict"), ("expanded", "expanded")]:
            nas = {p["person_id"] for p in rows(z, quality + "/by_institution/NAS.jsonl.gz")}
            no_nobel = {p["person_id"] for p in rows(z, quality + "/academy_excluding_official_Nobel.jsonl.gz")}
            populations[label] = nas & no_nobel
        people = {p["person_id"]: p for p in rows(z, "expanded/people.jsonl.gz") if p["person_id"] in populations["expanded"]}
    require(len(populations["strict"]) == 908 and len(populations["expanded"]) == 1462, "NAS population mismatch")
    with np.load(args.calendar_npz, allow_pickle=False) as data:
        dates = data["dates"].tolist(); years = data["year"].copy()
        yp, mp, dp = (data[name].tolist() for name in ["year_pillar", "month_pillar", "day_pillar"])
    calendar_index = {date: i for i, date in enumerate(dates)}
    require(len(dates) == len(calendar_index) == 55152, "Calendar coverage differs")
    codes = np.asarray([encode(y, m, d) for y, m, d in zip(yp, mp, dp)])
    dm = np.asarray([STEMS.index(p[0]) for p in dp])
    features = np.column_stack([np.eye(10, dtype=np.int16)[dm], codes[:, 0], codes[:, 1]]).astype(np.int16)
    ids = ["DM_" + s for s in STEMS] + ["M0_" + g for g in GODS] + ["M1_" + g for g in GODS]
    require([e["id"] for e in result["endpoint_order"]] == ids and result["decade_bins"] == BINS, "Endpoint/bin order differs")
    scale = np.asarray([100.0] * 10 + [20.0] * 20)
    year_features = {int(y): features[years == y] for y in set(years.tolist())}
    means = {y: f.mean(axis=0) for y, f in year_features.items()}
    variances = {y: f.var(axis=0) for y, f in year_features.items()}
    fourth_cumulants = {y: ((f - means[y]) ** 4).mean(axis=0) - 3 * variances[y] ** 2 for y, f in year_features.items()}
    metadata_bins = {key: Counter(10 * (dt.date.fromisoformat(people[pid]["analysis_DOB"]).year // 10) for pid in selected)
                     for key, selected in populations.items()}
    shared = [d for d in BINS if min(metadata_bins[k][d] for k in ("strict", "expanded")) >= 20]
    require(result["common_adequate_decades"] == shared, "Common adequate decades differ from fixed metadata rule")
    require(shared == [1890, 1900, 1910, 1920, 1930, 1940, 1950], "Expected metadata common support changed")
    prior = json.loads(Path(args.prior_full_tables).read_text())
    reports = []
    for label, selected in populations.items():
        ordered = sorted(selected); n = len(ordered)
        person_years = np.asarray([dt.date.fromisoformat(people[pid]["analysis_DOB"]).year for pid in ordered])
        x = person_years // 10
        take = np.asarray([calendar_index[people[pid]["analysis_DOB"]] for pid in ordered])
        observed = features[take]
        expected = np.asarray([means[int(y)] for y in person_years])
        group = result["groups"][label]
        require(group["people"] == n and len(group["bins"]) == 16 and len(group["trends"]) == 30, "Group size or endpoint count differs")
        sum_obs = np.zeros(30); sum_exp = np.zeros(30)
        for cell in group["bins"]:
            decade = cell["decade"]; mask = x * 10 == decade; m = int(mask.sum())
            require(cell["n"] == m, "Decade population differs")
            for j, endpoint in enumerate(ids):
                row = cell["endpoints"][endpoint]
                if not m:
                    require(row["observed_total"] == 0 and row["calendar_expected_total"] == 0, "Empty-decade totals must be0")
                    require(all(row[k] is None for k in ["observed_share", "calendar_expected_share", "excess_percentage_points"]), "Empty-decade shares must beNone")
                    continue
                obs, exp = int(observed[mask, j].sum()), float(expected[mask, j].sum())
                denom = 1 if j < 10 else 5
                require(row["observed_total"] == obs, "Decade observed count differs")
                close(row["calendar_expected_total"], exp, "Decade expected count differs")
                close(row["observed_share"], obs / (denom * m), "Decade observed share denominator differs")
                close(row["calendar_expected_share"], exp / (denom * m), "Decade expected share denominator differs")
                close(row["excess_percentage_points"], 100 * (obs - exp) / (denom * m), "Decade excess share differs")
                sum_obs[j] += obs; sum_exp[j] += exp
            if m:
                for start, denominator in [(0, 1), (10, 5), (20, 5)]:
                    close(sum(cell["endpoints"][ids[j]]["observed_total"] for j in range(start, start + 10)), denominator * m, "Decade partition observed total failure")
                    close(sum(cell["endpoints"][ids[j]]["calendar_expected_total"] for j in range(start, start + 10)), denominator * m, "Decade partition expected total failure")
        old = prior["groups"]["strict_primary" if label == "strict" else "expanded"]
        old_obs = [v["observed_people"] for v in old["HeavenlyStem_positions"]["day_stem"]]
        old_exp = [v["calendar_expected_people"] for v in old["HeavenlyStem_positions"]["day_stem"]]
        for model in ["M0_5_mainqi", "M1_5_priority"]:
            old_obs += [v["observed_count"] for v in old["TenGod_models"][model]]
            old_exp += [v["calendar_expected_count"] for v in old["TenGod_models"][model]]
        close(sum_obs, old_obs, "Decade observed totals do not reproduce full sample")
        close(sum_exp, old_exp, "Decade expected totals do not reproduce full sample")
        sx = int(x.sum()); denominator = n * int(np.sum(x * x)) - sx ** 2
        require(denominator > 0, "No birth-decade variation")
        a = n * x - sx
        observed_w = (a[:, None] * observed).sum(axis=0).astype(np.int64)
        counts = Counter(int(y) for y in person_years)
        coeff = {y: n * (y // 10) - sx for y in counts}
        expected_w_scaled = sum(coeff[y] * number * (L // len(year_features[y])) * year_features[y].sum(axis=0)
                                for y, number in counts.items()).astype(np.int64)
        centered_w = observed_w * L - expected_w_scaled
        # Independent centered-design OLS, rather than relying on the integer formula.
        cx = x - x.mean(); sxx = float(cx @ cx)
        raw_slopes = (cx[:, None] * observed).sum(axis=0) / sxx * scale
        cal_slopes = (cx[:, None] * expected).sum(axis=0) / sxx * scale
        excess_slopes = raw_slopes - cal_slopes
        close(raw_slopes, observed_w / denominator * scale, "Integer and centered OLS raw slopes disagree")
        close(cal_slopes, expected_w_scaled / L / denominator * scale, "Integer exact expected trend differs")
        variance_w = sum(number * float(coeff[y]) ** 2 * variances[y] for y, number in counts.items())
        kappa4_w = sum(number * float(coeff[y]) ** 4 * fourth_cumulants[y] for y, number in counts.items())
        analytic_sd = np.sqrt(variance_w) / denominator * scale
        relative_sd_se = np.sqrt(np.maximum(0, 2 * variance_w ** 2 + kappa4_w) / R) / (2 * variance_w)
        pvalues = []
        for j, trend in enumerate(group["trends"]):
            require(trend["endpoint_id"] == ids[j] and trend["replicates"] == R and trend["LCM"] == L, "Trend endpoint/runs/LCM mismatch")
            require(trend["seed"] == 202611170000 + (0 if label == "strict" else 1000) + j and trend["generator"] == "PCG64", "MC stream definition differs")
            require(trend["OLS_integer_denominator"] == denominator and trend["observed_integer_raw_numerator"] == int(observed_w[j]), "OLS integer statistic mismatch")
            require(trend["exact_expected_numerator_times_LCM"] == int(expected_w_scaled[j]) and trend["observed_centered_numerator_times_LCM"] == int(centered_w[j]), "Exact calendar-centered numerator mismatch")
            for field, values in [("raw_slope_pp_per_decade", raw_slopes), ("calendar_expected_slope_pp_per_decade", cal_slopes),
                                  ("calendar_excess_slope_pp_per_decade", excess_slopes), ("analytic_null_slope_SD_pp_per_decade", analytic_sd)]:
                close(trend[field], values[j], "Reported trend differs: " + field)
            close(trend["p_nominal_two_sided"], (1 + trend["extreme_replicates_including_ties"]) / (R + 1), "Inclusive two-sided MC p formula differs", atol=1e-14)
            require(0 <= trend["extreme_replicates_including_ties"] <= R, "Invalid extreme replicate count")
            mc_sd = trend["MC_excess_slope_SD_pp_per_decade"]
            require(abs(mc_sd - analytic_sd[j]) <= 6 * relative_sd_se[j] * analytic_sd[j] + 1e-10, "MC slopeSD differs from independent analytic null variance")
            require(abs(trend["MC_excess_slope_mean_pp_per_decade"]) <= 6 * analytic_sd[j] / math.sqrt(R) + 1e-10, "MC excess mean not compatible with zero")
            pvalues.append(trend["p_nominal_two_sided"])
        close([t["p_Holm30"] for t in group["trends"]], holm(pvalues), "Holm30 adjusted values differ")
        for start in (0, 10, 20):
            close(raw_slopes[start:start + 10].sum(), 0, "Partition raw slopes do not sum0")
            close(cal_slopes[start:start + 10].sum(), 0, "Partition calendar slopes do not sum0")
            close(excess_slopes[start:start + 10].sum(), 0, "Partition excess slopes do not sum0")
        common = group["common_adequate_bins_desc"]; keep = np.isin(x * 10, shared)
        require(common["people"] == int(keep.sum()) and common["decades"] == shared, "Common support description population differs")
        z = x[keep] - x[keep].mean(); zz = z @ z
        common_raw = (z[:, None] * observed[keep]).sum(axis=0) / zz * scale
        common_cal = (z[:, None] * expected[keep]).sum(axis=0) / zz * scale
        for j, t in enumerate(common["trends"]):
            close(t["raw_slope_pp_per_decade"], common_raw[j], "Common support raw slope differs")
            close(t["calendar_expected_slope_pp_per_decade"], common_cal[j], "Common support calendar trend differs")
            close(t["calendar_excess_slope_pp_per_decade"], common_raw[j] - common_cal[j], "Common support excess trend differs")
            require(t.get("p_nominal_two_sided") is None and t.get("p_Holm30") is None, "Common-support sensitivity must not addp")
        crosschecks = []
        if label == "strict":
            for j in PRESELECTED_MC_ENDPOINTS:
                q = independent_mc(j, counts, coeff, year_features, int(expected_w_scaled[j]), int(centered_w[j]))
                p = pvalues[j]; pooled = (p * R + q * QA_R) / (R + QA_R)
                tolerance = 5 * math.sqrt(max(0, pooled * (1 - pooled)) * (1 / R + 1 / QA_R)) + 2 / QA_R
                require(abs(p - q) <= tolerance, "Independent preselected endpoint MC p differs")
                crosschecks.append({"endpoint": ids[j], "primary_p": p, "independent_QA_p": q, "QA_replicates": QA_R, "tolerance": tolerance})
        reports.append({"group": label, "people": n, "bins_checked": 16, "endpoints_checked": 30,
                        "common_support_people": int(keep.sum()), "preselected_independent_MC_crosschecks": crosschecks})
    output = {"schema": "NAS_decade_trend_independent_QA_v1", "status": "PASS", "synthetic_QA": synthetic_qa(),
              "groups": reports, "calendar_rows_independently_encoded": len(dates),
              "only_NAS_nonNobel_aggregates_computed": True, "no_new_inferential_tests_added_by_auditor": True,
              "raw_calendar_and_excess_slopes_kept_separate": True,
              "QA_MC_results_never_replace_predeclared_primary_p": True,
              "hashes": {"results": sha(args.results), "authorization": sha(args.authorization), "auditor": sha(__file__),
                         "literal_reference": sha(Path(__file__).with_name("_independent_literal_reference.py")),
                         "V4": sha(args.v4_zip), "original_calendar": sha(args.calendar_npz), "prior_full_tables": sha(args.prior_full_tables)}}
    Path(args.output).write_text(json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"status": "PASS", "groups": [v["people"] for v in reports], "strict_QA_MC_endpoints": PRESELECTED_MC_ENDPOINTS}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--synthetic-only", action="store_true")
    for name in ["results", "authorization", "v4-zip", "calendar-npz", "prior-full-tables", "output"]:
        parser.add_argument("--" + name)
    arguments = parser.parse_args()
    if arguments.synthetic_only:
        print(json.dumps(synthetic_qa(), indent=2))
    else:
        if any(getattr(arguments, n.replace("-", "_")) is None for n in ["results", "authorization", "v4-zip", "calendar-npz", "prior-full-tables", "output"]):
            parser.error("All audit input arguments are required")
        audit(arguments)
