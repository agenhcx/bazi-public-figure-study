#!/usr/bin/env python3
"""Fields v1: six locked enrichment tests; no study observations in --qa-only.

Requires frozen calendar/hidden feature universes. Unknown-hour results use the
previously frozen twelve equally weighted hour candidates; they are descriptive.
"""
import argparse
import datetime as dt
import gzip
import hashlib
import json
from pathlib import Path
import zipfile

import numpy as np

STEMS = "甲乙丙丁戊己庚辛壬癸"
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
GODS = ["比肩", "劫财", "食神", "伤官", "偏财", "正财", "七杀", "正官", "偏印", "正印"]
HIDDEN = {"子": "癸", "丑": "己癸辛", "寅": "甲丙戊", "卯": "乙", "辰": "戊乙癸", "巳": "丙戊庚",
          "午": "丁己", "未": "己丁乙", "申": "庚壬戊", "酉": "辛", "戌": "戊辛丁", "亥": "壬甲"}
ENDPOINTS = ["overall_PI", "overall_SG", "year_PI", "year_SG", "month_PI", "month_SG"]
TRAITS = [("PI", 8), ("SG", 3)]
V4_SHA = "53302ef5c4bbb946adcaceb70d7a7fd576c7f06d03c3e7080874654e1a2644f9"
CALENDAR_SHA = "d150883033464ebd3afafaf764738ed3b573d0d0fb4bd252a955e403a75fcc8b"
HIDDEN_SHA = "19e8bc8648fe8b69122161da260e1dae487816241c655bd96a1273783f1ef723"
R = 99999
SEED = 2026111501


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check(ok, message):
    if not bool(ok):
        raise AssertionError(message)


def dump(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def id_hash(ids):
    value = json.dumps(sorted(ids), ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    return hashlib.sha256(value.encode()).hexdigest()


def tg_index(day, other):
    return 2 * ((other // 2 - day // 2) % 5) + (day % 2 != other % 2)


def priority_stem(branch, year_stem, month_stem):
    hs = HIDDEN[branch]
    exposed = [s for s in hs if s in (year_stem, month_stem)]
    return exposed[0] if exposed else hs[0]


def encode(year_pillars, month_pillars, day_pillars):
    """Positions are YG,YB,MG,MB,DB; reference DayStem never counted/exposed."""
    si = {s: i for i, s in enumerate(STEMS)}
    n = len(day_pillars)
    ys = np.array([si[str(p)[0]] for p in year_pillars])
    ms = np.array([si[str(p)[0]] for p in month_pillars])
    ds = np.array([si[str(p)[0]] for p in day_pillars])
    branches = [[str(p)[1] for p in pp] for pp in (year_pillars, month_pillars, day_pillars)]
    out = {}
    for model in ("M0", "M1"):
        rep = []
        for bb in branches:
            if model == "M0":
                rep.append(np.array([si[HIDDEN[b][0]] for b in bb]))
            else:
                rep.append(np.array([si[priority_stem(b, STEMS[y], STEMS[m])]
                                     for b, y, m in zip(bb, ys, ms)]))
        stems = np.column_stack((ys, rep[0], ms, rep[1], rep[2]))
        cats = tg_index(ds[:, None], stems).astype(np.int8)
        counts = np.zeros((n, 10), dtype=np.int16)
        for j in range(5):
            counts[np.arange(n), cats[:, j]] += 1
        endpoints = np.column_stack((
            counts[:, 8], counts[:, 3],
            (cats[:, :2] == 8).any(axis=1), (cats[:, :2] == 3).any(axis=1),
            (cats[:, 2:4] == 8).any(axis=1), (cats[:, 2:4] == 3).any(axis=1),
        )).astype(np.int16)
        out[model] = {"categories": cats, "counts": counts, "endpoints": endpoints}
    return out, ds


def holm(p):
    p = np.asarray(p, dtype=float)
    order = np.argsort(p, kind="stable")
    adjusted = np.minimum(1, np.maximum.accumulate(p[order] * np.arange(len(p), 0, -1)))
    out = np.empty_like(p)
    out[order] = adjusted
    return out


def candidate_pools(years, months, indexes, conditional_month=False, eligible=None):
    eligible = np.ones(len(years), dtype=bool) if eligible is None else eligible
    pools = []
    for idx in indexes:
        mask = (years == years[idx]) & eligible
        if conditional_month:
            mask &= months == months[idx]
        pool = np.flatnonzero(mask)
        check(len(pool) > 0, "Empty null calendar pool")
        pools.append(pool)
    return pools


def summarize_endpoints(values, indexes, pools, inference=False):
    n = len(indexes)
    check(n > 0, "Empty cohort")
    observed = values[indexes].sum(axis=0).astype(int)
    expected = np.sum([values[p].mean(axis=0) for p in pools], axis=0)
    p = adjusted = None
    if inference:
        rng = np.random.Generator(np.random.PCG64(SEED))
        simulated = np.zeros((R, len(ENDPOINTS)), dtype=np.int16)
        # Each sampled date contributes the joint six-dimensional person vector.
        for pool in pools:
            sampled = pool[rng.integers(0, len(pool), size=R)]
            simulated += values[sampled]
        p = (1 + np.sum(simulated >= observed[None, :], axis=0)) / (R + 1)
        adjusted = holm(p)
    result = []
    for j, endpoint in enumerate(ENDPOINTS):
        denom = 5 * n if j < 2 else n
        item = {"endpoint": endpoint, "N": n, "observed_sum": int(observed[j]),
                "expected_sum": float(expected[j]), "observed_per_person": float(observed[j] / n),
                "expected_per_person": float(expected[j] / n), "reporting_denominator": denom,
                "observed_fraction": float(observed[j] / denom),
                "expected_fraction": float(expected[j] / denom),
                "difference_percentage_points": float(100 * (observed[j] - expected[j]) / denom)}
        if inference:
            item.update(raw_p_one_sided=float(p[j]), holm6_p=float(adjusted[j]),
                        MC_standard_error=float(np.sqrt(p[j] * (1 - p[j]) / (R + 1))))
        result.append(item)
    return result


def descriptive_counts(values, indexes, pools, labels, denominator):
    obs = values[indexes].sum(axis=0)
    exp = np.sum([values[p].mean(axis=0) for p in pools], axis=0)
    return [{"label": str(label), "observed_sum": float(obs[j]), "expected_sum": float(exp[j]),
             "observed_fraction": float(obs[j] / denominator),
             "expected_fraction": float(exp[j] / denominator)} for j, label in enumerate(labels)]


def load_universe(calendar, hidden):
    check(sha(calendar) == CALENDAR_SHA, "Calendar universe SHA mismatch")
    check(sha(hidden) == HIDDEN_SHA, "Hidden-stem universe SHA mismatch")
    with np.load(calendar, allow_pickle=False) as z:
        cal = {k: z[k].copy() for k in z.files}
    with np.load(hidden, allow_pickle=False) as z:
        hid = {k: z[k].copy() for k in z.files}
    check(np.array_equal(cal["dates"], hid["dates"]), "Universe dates differ")
    model, ds = encode(cal["year_pillar"], cal["month_pillar"], cal["day_pillar"])
    check(len(cal["dates"]) == 55152 and len(set(cal["dates"].tolist())) == 55152,
          "Calendar length or uniqueness differs")
    check(np.array_equal(model["M0"]["counts"], cal["ten_god_counts"]), "M0 ten-god encoder differs")
    for t, j in TRAITS:
        check(np.array_equal(model["M0"]["counts"][:, j], cal[t + "_count"]), "M0 count mismatch " + t)
    check(np.all(model["M0"]["counts"].sum(axis=1) == 5), "M0 positions differ")
    check(np.all(model["M1"]["counts"].sum(axis=1) == 5), "M1 positions differ")
    for k, model_name in enumerate(("M0", "M1")):
        for t, (_, j) in enumerate(TRAITS):
            check(np.array_equal(model[model_name]["counts"][:, j] * 72,
                                 hid["count_scaled72"][:, k, t]), "Hidden cache count projection differs")
            check(np.array_equal((model[model_name]["counts"][:, j] > 0) * 12,
                                 hid["presence_scaled12"][:, k, t]), "Hidden cache presence projection differs")
    check(np.array_equal(ds, cal["DM_index"]), "Day-master encoder differs")
    return cal, hid, model, ds


def qa(calendar, hidden):
    for d in range(10):
        check(sorted(int(tg_index(d, t)) for t in range(10)) == list(range(10)), "TG bijection")
    check(tg_index(0, 1) == 1 and tg_index(0, 3) == 3 and tg_index(0, 8) == 8,
          "Ten-god identity failed")
    check(priority_stem("未", "丁", "乙") == "丁", "M1 middle before residual priority failed")
    check(priority_stem("亥", "丁", "己") == "壬", "M1 main fallback failed")
    m, _ = encode(["甲子", "乙丑"], ["丁亥", "丁亥"], ["甲子", "甲子"])
    check(m["M1"]["counts"][0, 8] == 0 and m["M1"]["counts"][1, 8] == 1,
          "DayStem reference exposure exclusion failed")
    check(np.allclose(holm([.01, .04, .03, .2, .9, .5]), [.06, .16, .15, .6, 1., 1.]),
          "Holm6 ordering failed")
    tail = np.array([0, 1, 1, 2], dtype=int)
    check(int(np.sum(tail >= 1)) == 3 and (1 + int(np.sum(tail >= 1))) / 5 == .8,
          "Inclusive integer tail or plus-one p failed")
    cal, _, models, _ = load_universe(calendar, hidden)
    fake = np.array([0, 1, 365])
    pools = candidate_pools(cal["year"], cal["month"], fake)
    check(all(len(p) in (365, 366) for p in pools), "Gregorian year calendar pool sizes")
    for v in models.values():
        check(np.max(v["endpoints"][:, 2:]) <= 1, "Pillar presence not binary")
        check(np.all(v["endpoints"][:, 2] <= v["endpoints"][:, 0]), "Year PI subset")
        check(np.all(v["endpoints"][:, 4] <= v["endpoints"][:, 0]), "Month PI subset")
    return {"status": "PASS", "study_cohort_loaded": False, "universe_dates": len(cal["dates"]),
            "M0_all10_exact_reproduction": True, "M0_M1_hidden_cache_PI_SG_exact_reproduction": True,
            "synthetic_TG_priority_reference_and_Holm_checks": True,
            "year_and_month_presence_binary": True, "endpoint_order": ENDPOINTS,
            "input_SHA256": {"calendar": sha(calendar), "hidden": sha(hidden)}, "code_sha256": sha(__file__)}


def zip_rows(z, relative):
    name = "scientist_north_data_freeze_v4/" + relative
    return [json.loads(line) for line in gzip.decompress(z.read(name)).splitlines()]


def execute(args):
    receipt = json.loads(Path(args.receipt).read_text())
    check(receipt.get("remote_lock_verified") is True, "Remote lock receipt is required")
    check(receipt.get("code_sha256") == sha(__file__), "Code changed after lock")
    check(sha(args.v4) == V4_SHA, "Frozen cohort archive SHA mismatch")
    cal, hid, models, ds = load_universe(args.calendar, args.hidden)
    with zipfile.ZipFile(args.v4) as z:
        rows = zip_rows(z, "outputs/strict/Fields_parallel_cohort.jsonl.gz")
        expanded = zip_rows(z, "outputs/expanded/Fields_parallel_cohort.jsonl.gz")
        academy_ids = {r["person_id"] for r in zip_rows(z, "outputs/strict/academy_excluding_official_Nobel.jsonl.gz")}
    rows = sorted(rows, key=lambda r: r["person_id"])
    check(len(rows) == 57 and len({r["person_id"] for r in rows}) == 57, "Fields cohort N/identity differs")
    check(rows == sorted(expanded, key=lambda r: r["person_id"]), "Strict and expanded Fields differ")
    lookup = {str(d): i for i, d in enumerate(cal["dates"])}
    for r in rows:
        check(r["hemisphere"] == "north" and not r["person_level_DOB_analysis_hold"], "Cohort hold or geography")
        check("1835-01-01" <= r["analysis_DOB"] <= "1985-12-31", "Fixed birth window")
    indexes = np.array([lookup[r["analysis_DOB"]] for r in rows], dtype=int)
    pools = candidate_pools(cal["year"], cal["month"], indexes)
    overlap = np.array([r["person_id"] in academy_ids for r in rows])
    check(int(overlap.sum()) == 18, "Prior-academy overlap differs")
    primary = summarize_endpoints(models["M0"]["endpoints"], indexes, pools, inference=True)
    result = {"schema": "Fields_reveal_v1", "created_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
              "N": len(rows), "person_ids_sha256": id_hash(r["person_id"] for r in rows),
              "strict_equals_expanded": True, "all_hemisphere_north": True,
              "prior_academy_overlap_N": int(overlap.sum()), "R": R, "seed": SEED,
              "generator": "NumPy_PCG64", "primary_family_size": 6,
              "primary_null": "Each person's Gregorian birth year uniformly sampled over valid dates",
              "primary_tail": "one-sided inclusive >=; plus-one Monte Carlo p",
              "primary_multiplicity": "Holm6 FWER .05", "primary": primary,
              "source_sha256": {"V4": sha(args.v4), "calendar": sha(args.calendar), "hidden": sha(args.hidden),
                                "code": sha(__file__)}, "execution_receipt": receipt,
              "sensitivity_extra_p_values": 0, "sensitivities": {}, "descriptives": {}}
    result["sensitivities"]["M1_priority_5"] = summarize_endpoints(models["M1"]["endpoints"], indexes, pools)
    ym_pools = candidate_pools(cal["year"], cal["month"], indexes, conditional_month=True)
    result["sensitivities"]["M0_birth_year_and_month_null"] = summarize_endpoints(models["M0"]["endpoints"], indexes, ym_pools)
    eligible = ~cal["jie_boundary_plus_minus_one_civil_day"].astype(bool)
    keep = eligible[indexes]
    # Boundary sensitivity removes observed people only; the original year null
    # remains the full Gregorian year, as frozen in the execution plan.
    nojie_pools = candidate_pools(cal["year"], cal["month"], indexes[keep])
    result["sensitivities"]["M0_noJie_plus_minus_one_day"] = summarize_endpoints(models["M0"]["endpoints"], indexes[keep], nojie_pools)
    independent = indexes[~overlap]
    independent_pools = candidate_pools(cal["year"], cal["month"], independent)
    result["sensitivities"]["M0_without_prior_academy_overlap"] = summarize_endpoints(models["M0"]["endpoints"], independent, independent_pools)
    for model_name, value in models.items():
        result["descriptives"][model_name + "_all10_TG"] = descriptive_counts(value["counts"], indexes, pools, GODS, 5 * len(rows))
    dm = np.eye(10)[ds]
    result["descriptives"]["day_master"] = descriptive_counts(dm, indexes, pools, STEMS, len(rows))
    hidden_results = []
    for m, model_name in enumerate(hid["models"]):
        for t, trait in enumerate(hid["traits"]):
            counts = hid["count_scaled72"][:, m, t].astype(float) / 72
            presence = hid["presence_scaled12"][:, m, t].astype(float) / 12
            expected_count = sum(counts[p].mean() for p in pools)
            expected_presence = sum(presence[p].mean() for p in pools)
            den = int(hid["position_denominators"][m])
            hidden_results.append({"model": str(model_name), "trait": str(trait), "position_denominator": den,
                                   "observed_count_mean": float(counts[indexes].mean()),
                                   "expected_count_mean": float(expected_count / len(rows)),
                                   "observed_position_share": float(counts[indexes].mean() / den),
                                   "expected_position_share": float(expected_count / len(rows) / den),
                                   "observed_person_presence": float(presence[indexes].mean()),
                                   "expected_person_presence": float(expected_presence / len(rows))})
    result["descriptives"]["hidden_models"] = hidden_results
    audit = []
    for r, idx in zip(rows, indexes):
        audit.append({"person_id": r["person_id"], "display_name": r.get("display_name"), "DOB": r["analysis_DOB"],
                      "year_pillar": str(cal["year_pillar"][idx]), "month_pillar": str(cal["month_pillar"][idx]),
                      "day_pillar": str(cal["day_pillar"][idx]),
                      "M0_categories": [GODS[int(x)] for x in models["M0"]["categories"][idx]],
                      "M1_categories": [GODS[int(x)] for x in models["M1"]["categories"][idx]],
                      "M0_endpoints": models["M0"]["endpoints"][idx].tolist(),
                      "prior_academy_overlap": r["person_id"] in academy_ids})
    dump(args.output, result)
    dump(str(Path(args.output).with_name("INDIVIDUAL_AUDIT.json")), audit)
    print(json.dumps({"status": "PASS", "N": len(rows), "results_path": args.output,
                      "primary": primary}, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--calendar", default="fields_restore_v1/methods/scientist_US_NAS_reveal_v1/calendar_pool.npz")
    parser.add_argument("--hidden", default="fields_restore_v1/methods/scientist_US_NAS_reveal_v2_hidden_stems/hidden_pool.npz")
    parser.add_argument("--v4", default="hypothesis_inputs_v1/scientist_north_data_freeze_v4.zip")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--qa-only", action="store_true")
    action.add_argument("--execute", action="store_true")
    parser.add_argument("--receipt")
    parser.add_argument("--output", default="fields_reveal_v1/RESULTS.json")
    args = parser.parse_args()
    if args.qa_only:
        result = qa(args.calendar, args.hidden)
        dump(args.output, result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        check(args.receipt is not None, "--receipt required for execution")
        check(not Path(args.output).exists(), "Output already exists; no overwrite")
        execute(args)


if __name__ == "__main__":
    main()
