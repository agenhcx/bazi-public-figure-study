#!/usr/bin/env python3
"""NAS-only post-reveal five-element and conditional-presence exploration.

The execution receipt must identify a remotely verified pre-run code/scope lock.
Inference is person-level, retaining the frozen birth-year calendar null.
"""
import argparse
from collections import Counter
from fractions import Fraction
import hashlib
import importlib.util
import json
from pathlib import Path
import zipfile

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
ENCODER = ROOT / "nas_full_tables_work/scripts/build_full_nas_tables.py"
ENCODER_SHA = "4b3ea67141c2363b4fb760ce365063545a4717542860caddf82c501d312ddc1d"
V4_SHA = "53302ef5c4bbb946adcaceb70d7a7fd576c7f06d03c3e7080874654e1a2644f9"
CALENDAR_SHA = "d150883033464ebd3afafaf764738ed3b573d0d0fb4bd252a955e403a75fcc8b"
PRIOR_SHA = "2a92dd9b4f15c719c7448e0bb1bcc1a3a718324c823bc3dee7ddc18da637afcc"
ELEMENTS = ["金", "木", "水", "火", "土"]
ELEMENT_INDEX = {"木": 0, "火": 1, "土": 2, "金": 3, "水": 4}
GODS = ["比肩", "劫财", "食神", "伤官", "偏财", "正财", "七杀", "正官", "偏印", "正印"]
FOCUS = ["偏财", "食神", "七杀", "偏印"]
MODELS = {"M0": "M0_5_mainqi", "M1": "M1_5_priority"}


def require(ok, message):
    if not bool(ok):
        raise AssertionError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_encoder():
    require(sha(ENCODER) == ENCODER_SHA, "Frozen encoder changed")
    spec = importlib.util.spec_from_file_location("frozen_nas_encoder", ENCODER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def endpoint_definitions():
    rows = []
    for model in MODELS:
        rows += [{"id": model + "_element_" + e, "model": model, "kind": "element_count", "category": e}
                 for e in ELEMENTS]
    for model in MODELS:
        rows += [{"id": model + "_god_" + g, "model": model, "kind": "god_count", "category": g}
                 for g in FOCUS]
    for model in MODELS:
        rows += [{"id": model + "_conditional_" + target + "_given_" + anchor,
                  "model": model, "kind": "conditional_presence", "anchor": anchor, "target": target}
                 for anchor in FOCUS for target in FOCUS if anchor != target]
    require(len(rows) == 42 and len({r["id"] for r in rows}) == 42, "Endpoint family differs")
    return rows


def holm(pvalues):
    p = np.asarray(pvalues)
    order = np.argsort(p, kind="stable")
    out = np.empty(len(p))
    running = 0.
    for rank, i in enumerate(order):
        running = max(running, min(1., (len(p) - rank) * float(p[i])))
        out[i] = running
    return out.tolist()


def sum_distribution(year_pmfs, year_counts):
    """Deterministic convolution of independent whole-person count marginals."""
    dist = np.array([1.])
    for year, count in sorted(year_counts.items()):
        p = np.asarray(year_pmfs[int(year)], dtype=float)
        require(abs(float(p.sum()) - 1.) < 1e-12 and np.all(p >= 0), "Invalid PMF")
        for _ in range(int(count)):
            dist = np.convolve(dist, p)
    require(abs(float(dist.sum()) - 1.) < 1e-10 and np.all(dist >= 0), "Convolution mass lost")
    return dist / dist.sum()


def centered_exact_test(observed, expected_fraction, distribution):
    """Inclusive |S-E| tail, with rational cutoffs and floating PMF weights."""
    require(0 <= observed < len(distribution), "Observed total outside null support")
    e = expected_fraction
    if Fraction(observed) == e:
        lower, upper, p = observed, observed, 1.
    elif Fraction(observed) > e:
        reflected = 2 * e - observed
        lower, upper = reflected.numerator // reflected.denominator, observed
        p = (float(distribution[:lower + 1].sum()) if lower >= 0 else 0.) + float(distribution[upper:].sum())
    else:
        reflected = 2 * e - observed
        lower, upper = observed, -((-reflected.numerator) // reflected.denominator)
        p = float(distribution[:lower + 1].sum()) + (float(distribution[upper:].sum()) if upper < len(distribution) else 0.)
    return {"p_two_sided": min(1., p), "two_sided_lower_inclusive": int(lower),
            "two_sided_upper_inclusive": int(upper), "exact_expected_numerator": str(e.numerator),
            "exact_expected_denominator": str(e.denominator),
            "test": "independent_person_convolution_absolute_calendar_centered_inclusive",
            "probability_arithmetic": "float64_PMF_convolution_rational_exact_tail_cutoffs"}


def element_counts(god_counts, day_stems):
    out = np.zeros((len(day_stems), 5), dtype=np.int16)
    for god in range(10):
        element = (day_stems // 2 + god // 2) % 5
        out[np.arange(len(day_stems)), element] += god_counts[:, god]
    require(np.all(out.sum(axis=1) == 5), "Five-element units differ from five")
    return out


def synthetic_qa():
    # All Bernoulli combinations: E=3/4, S=2 has p=1/8; S=0 p=1/2.
    d = np.convolve([.75, .25], [.5, .5])
    require(centered_exact_test(2, Fraction(3, 4), d)["p_two_sided"] == .125, "Exact upper test")
    require(centered_exact_test(0, Fraction(3, 4), d)["p_two_sided"] == .5, "Exact lower test")
    require(centered_exact_test(1, Fraction(1), np.array([.25, .5, .25]))["p_two_sided"] == 1., "Exact E tie")
    # Negative reflected cutoff must not use a Python negative slice.
    require(centered_exact_test(2, Fraction(1, 10), np.array([.925, .05, .025]))["p_two_sided"] == .025, "Negative cutoff")
    require(np.allclose(holm([.01, .04, .03]), [.03, .06, .06]), "Holm regression")
    encoder = load_encoder()
    for dm in range(10):
        v = np.arange(10, dtype=np.int16)[None, :]
        result = element_counts_for_synthetic(v, dm)
        require(result.sum() == v.sum(), "Synthetic count reconstruction")
    return {"status": "PASS", "study_data_loaded": False, "exact_fraction_tail_boundaries": True,
            "zero_or_negative_cutoff": True, "Holm": True, "encoder_synthetic": encoder.synthetic_qa()}


def element_counts_for_synthetic(v, dm):
    out = np.zeros(5, dtype=int)
    for g in range(10):
        out[(dm // 2 + g // 2) % 5] += int(v[0, g])
    return out


def main(args):
    if args.synthetic_qa_only:
        print(json.dumps(synthetic_qa(), ensure_ascii=False, indent=2))
        return
    scope = json.loads(Path(args.scope).read_text())
    receipt = json.loads(Path(args.execution_receipt).read_text())
    require(scope["country"] == "NAS" and scope["endpoint_definitions"] == endpoint_definitions(), "Scope differs")
    require(receipt["remote_plan_and_code_verified_before_summary"] is True, "Remote lock not verified")
    require(receipt["scope_sha256"] == sha(args.scope), "Scope receipt hash differs")
    locked = json.loads(Path(args.locked_files).read_text())
    require(receipt["locked_file_manifest_sha256"] == sha(args.locked_files), "Lock receipt differs")
    for rel, digest in locked.items():
        require(sha(ROOT / rel) == digest, "Locked file changed: " + rel)
    paths = {"v4_zip": args.v4_zip, "calendar_npz": args.calendar_npz, "prior_tables": args.prior_tables}
    for k, p in paths.items():
        require(sha(p) == scope["input_sha256"][k], "Input differs: " + k)
    require(sha(args.v4_zip) == V4_SHA and sha(args.calendar_npz) == CALENDAR_SHA and sha(args.prior_tables) == PRIOR_SHA,
            "Original input pins differ")
    dest = Path(args.output)
    require(not dest.exists(), "No overwrite of outcomes")
    encoder = load_encoder()
    with zipfile.ZipFile(args.v4_zip) as z:
        groups = {}
        for quality in ["strict", "expanded"]:
            nas = {p["person_id"] for p in encoder.read_zip_rows(z, "outputs/" + quality + "/by_institution/NAS.jsonl.gz")}
            academy = {p["person_id"] for p in encoder.read_zip_rows(z, "outputs/" + quality + "/academy_excluding_official_Nobel.jsonl.gz")}
            groups[quality] = nas & academy
        people = {p["person_id"]: p for p in encoder.read_zip_rows(z, "outputs/expanded/people.jsonl.gz")
                  if p["person_id"] in groups["expanded"]}
    require(len(groups["strict"]) == 908 and len(groups["expanded"]) == 1462 and groups["strict"] <= groups["expanded"],
            "Selected NAS population differs")
    with np.load(args.calendar_npz, allow_pickle=False) as z:
        dates, years = z["dates"], z["year"]
        gods, positions = encoder.encode_pool(z["year_pillar"], z["month_pillar"], z["day_pillar"])
    require(len(dates) == 55152 and len(set(dates.tolist())) == 55152, "Calendar differs")
    lookup = {str(d): i for i, d in enumerate(dates)}
    elements = {model: element_counts(gods[name], positions["day_stem"]) for model, name in MODELS.items()}
    prior = json.loads(Path(args.prior_tables).read_text())
    output = {"schema": "NAS_elements_and_conditional_presence_v1", "country": "NAS",
              "endpoint_definitions": endpoint_definitions(), "scope": scope,
              "execution_receipt": receipt, "groups": {}, "no_other_country_or_Nobel_subgroup_outcomes_opened": True,
              "source_and_code_sha256": {"code": sha(__file__), "encoder": sha(ENCODER), **{k: sha(p) for k, p in paths.items()}}}
    for quality in ["strict", "expanded"]:
        rows = [people[pid] for pid in sorted(groups[quality])]
        require(all(p["hemisphere"] == "north" and not p["person_level_DOB_analysis_hold"] for p in rows), "Hemisphere or hold changed")
        indexes = np.array([lookup[p["analysis_DOB"]] for p in rows], dtype=np.intp)
        birthyears = years[indexes]
        year_counts = Counter(int(y) for y in birthyears)
        n = len(rows)
        group = {"people": n, "five_position_denominator": 5 * n,
                 "person_ids_sha256": encoder.id_hash(p["person_id"] for p in rows), "endpoints": []}
        old = prior["groups"]["strict_primary" if quality == "strict" else "expanded"]
        require(group["person_ids_sha256"] == old["person_ids_sha256"], "Frozen person IDs differ")
        for endpoint in endpoint_definitions():
            model = endpoint["model"]
            god = gods[MODELS[model]]
            item = dict(endpoint)
            if endpoint["kind"] == "conditional_presence":
                anchor = god[:, GODS.index(endpoint["anchor"])] > 0
                target = god[:, GODS.index(endpoint["target"])] > 0
                chosen = indexes[anchor[indexes]]
                actual_year_counts = Counter(int(y) for y in years[chosen])
                denominator = len(chosen)
                require(denominator > 0, "Empty observed conditional subgroup")
                observed = int(target[chosen].sum())
                pmfs, fractions, pool_counts = {}, {}, {}
                for year in actual_year_counts:
                    candidates = (years == year) & anchor
                    eligible = int(candidates.sum())
                    positive = int(target[candidates].sum())
                    require(eligible > 0, "Empty conditional year pool")
                    q = Fraction(positive, eligible)
                    pmfs[year] = np.array([1 - float(q), float(q)])
                    fractions[year] = q
                    pool_counts[str(year)] = {"observed_anchor_people": actual_year_counts[year],
                                              "eligible_calendar_dates": eligible, "joint_positive_dates": positive}
                expected_fraction = sum((count * fractions[year] for year, count in actual_year_counts.items()), Fraction())
                item.update(observed_joint_people=observed, observed_anchor_people=denominator,
                            observed_target_people=int(target[indexes].sum()),
                            observed_conditional_probability=observed / denominator,
                            calendar_expected_conditional_probability=float(expected_fraction) / denominator,
                            observed_joint_prevalence=observed / n, calendar_conditioned_year_pools=pool_counts)
            else:
                values = elements[model][:, ELEMENT_INDEX[endpoint["category"]]] if endpoint["kind"] == "element_count" else god[:, GODS.index(endpoint["category"])]
                observed = int(values[indexes].sum())
                denominator = 5 * n
                actual_year_counts = year_counts
                pmfs, fractions = {}, {}
                for year in year_counts:
                    pool = values[years == year]
                    pmfs[year] = np.bincount(pool, minlength=6).astype(float) / len(pool)
                    fractions[year] = Fraction(int(pool.sum()), len(pool))
                expected_fraction = sum((count * fractions[year] for year, count in year_counts.items()), Fraction())
                item.update(observed_count=observed, position_denominator=denominator,
                            observed_position_share=observed / denominator,
                            calendar_expected_position_share=float(expected_fraction) / denominator,
                            observed_mean_count_per_person=observed / n,
                            calendar_expected_mean_count_per_person=float(expected_fraction) / n,
                            observed_people_with_at_least_one=int((values[indexes] > 0).sum()))
                if endpoint["kind"] == "god_count":
                    olditem = next(x for x in old["TenGod_models"][MODELS[model]] if x["ten_god"] == endpoint["category"])
                    require(observed == olditem["observed_count"], "Previously revealed God count changed")
                    require(abs(float(expected_fraction) - olditem["calendar_expected_count"]) < 1e-9, "Previously revealed God expectation changed")
            expected = float(expected_fraction)
            dist = sum_distribution(pmfs, actual_year_counts)
            support = np.arange(len(dist))
            analytic_var = sum(count * (float(np.dot(np.arange(len(pmfs[year])) ** 2, pmfs[year])) -
                                       float(np.dot(np.arange(len(pmfs[year])), pmfs[year])) ** 2)
                               for year, count in actual_year_counts.items())
            require(abs(float(np.dot(support, dist)) - expected) < 1e-8, "Distribution mean differs")
            require(abs(float(np.dot((support - expected) ** 2, dist)) - analytic_var) < 1e-7, "Distribution variance differs")
            item.update(calendar_expected_total=expected,
                        enrichment_ratio=observed / expected if expected else None,
                        difference_percentage_points=(observed - expected) / denominator * 100,
                        null_SD_total=analytic_var ** .5,
                        **centered_exact_test(observed, expected_fraction, dist))
            group["endpoints"].append(item)
        adjusted = holm([x["p_two_sided"] for x in group["endpoints"]])
        for item, p in zip(group["endpoints"], adjusted):
            item.update(p_Holm42=p, reject_Holm42_0_05=p < .05,
                        inference_role="post_reveal_exploratory_primary" if quality == "strict" else "expanded_source_sensitivity_reference")
        for model in MODELS:
            elem = [x for x in group["endpoints"] if x["model"] == model and x["kind"] == "element_count"]
            require(sum(x["observed_count"] for x in elem) == 5 * n, "Element sum not5N")
            require(abs(sum(x["calendar_expected_total"] for x in elem) - 5 * n) < 1e-8, "Expected element sum not5N")
        output["groups"][quality] = group
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"status": "PASS", "output": str(dest), "people": {k: g["people"] for k, g in output["groups"].items()},
                      "Holm42_rejections": {k: sum(x["reject_Holm42_0_05"] for x in g["endpoints"]) for k, g in output["groups"].items()}}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--synthetic-qa-only", action="store_true")
    for name in ["v4-zip", "calendar-npz", "prior-tables", "scope", "locked-files", "execution-receipt", "output"]:
        parser.add_argument("--" + name)
    main(parser.parse_args())
