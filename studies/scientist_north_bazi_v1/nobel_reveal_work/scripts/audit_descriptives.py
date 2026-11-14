#!/usr/bin/env python3
"""Independent, gated QA of the Nobel descriptive tables; no new tests.

The cohort audit uses integer calendar-column sums and exact Fraction year
weights. It does not import the descriptive builder or its expectations.
--self-test uses symbolic pillars and tiny arrays, never study populations.
"""

import argparse
from collections import Counter
import datetime as dt
from fractions import Fraction
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import zipfile

import numpy as np

V4_SHA = "53302ef5c4bbb946adcaceb70d7a7fd576c7f06d03c3e7080874654e1a2644f9"
CALENDAR_SHA = "d150883033464ebd3afafaf764738ed3b573d0d0fb4bd252a955e403a75fcc8b"
HIDDEN_SHA = "19e8bc8648fe8b69122161da260e1dae487816241c655bd96a1273783f1ef723"
ENCODER_SHA = "abc1d0de4a7bd94003258323a62d71c6cf4dd4c43ca45d627f85f0d99c427746"
STEMS = list("甲乙丙丁戊己庚辛壬癸")
BRANCHES = list("子丑寅卯辰巳午未申酉戌亥")
GODS = ["比肩", "劫财", "食神", "伤官", "偏财", "正财", "七杀", "正官", "偏印", "正印"]
MODELS = ["M0_5", "M1_priority_5", "M1_share_5", "M1_any_5",
          "M2_main_7", "M3_priority_7", "M3_share_7", "M3_any_7"]
TRAITS = ["PI", "SG"]
DENOMS = [5, 5, 5, 5, 7, 7, 7, 7]
DECADES = list(range(1830, 1990, 10))
INSTITUTIONS = ["NAS", "UK_Royal_Society", "DE_Leopoldina", "France", "Japan", "CAS"]
HIDDEN_STEMS = {"子": "癸", "丑": "己癸辛", "寅": "甲丙戊", "卯": "乙",
                "辰": "戊乙癸", "巳": "丙戊庚", "午": "丁己", "未": "己丁乙",
                "申": "庚壬戊", "酉": "辛", "戌": "戊辛丁", "亥": "壬甲"}


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"


def compare(actual, expected, path="root"):
    """Expected dictionaries specify all audited values, allowing annotations."""
    if isinstance(expected, dict):
        check(isinstance(actual, dict), path + " is not a dictionary")
        for key, value in expected.items():
            check(key in actual, path + " missing " + key)
            compare(actual[key], value, path + "." + key)
    elif isinstance(expected, list):
        check(isinstance(actual, list) and len(actual) == len(expected), path + " list length")
        for i, value in enumerate(expected):
            compare(actual[i], value, path + "[" + str(i) + "]")
    elif expected is None or isinstance(expected, (str, bool)):
        check(actual == expected, path + " identity mismatch")
    elif isinstance(expected, int):
        check(not isinstance(actual, bool) and actual == expected, path + " integer mismatch")
    else:
        check(np.isfinite(actual) and abs(float(actual) - float(expected)) <=
              1e-10 + 1e-11 * abs(float(expected)), path + " numeric mismatch")


def exact_expected(column_sums_by_year, year_sizes, person_years):
    """Finite-sum calendar expectation in unscaled column units."""
    counts = Counter(int(y) for y in person_years)
    width = len(next(iter(column_sums_by_year.values())))
    answer = [Fraction(0) for _ in range(width)]
    for year, count in counts.items():
        sums = column_sums_by_year[year]
        for j, value in enumerate(sums):
            answer[j] += Fraction(count * int(value), year_sizes[year])
    return answer


def target_god(day_stem, other_stem):
    d, t = STEMS.index(day_stem), STEMS.index(other_stem)
    relation = ((t // 2) - (d // 2)) % 5
    return GODS[relation * 2 + int(d % 2 != t % 2)]


def independent_symbolic_encoder(yp, mp, dp):
    """Independent scalar encoder, all fractions explicit and no lookup cache."""
    dm = dp[0]
    result = np.zeros((8, 2, 2), dtype=np.int64)
    for rule_number in range(4):
        for trait_number, trait in enumerate(["偏印", "伤官"]):
            def direct(stem):
                return Fraction(target_god(dm, stem) == trait)

            def branch(branch_name, visible):
                hidden = HIDDEN_STEMS[branch_name]
                eligible = [s for s in hidden if s in visible]
                if rule_number == 0 or not eligible:
                    return direct(hidden[0])
                if rule_number == 1:
                    return direct(eligible[0])
                if rule_number == 2:
                    return sum((direct(s) for s in eligible), Fraction(0)) / len(eligible)
                return Fraction(any(direct(s) for s in eligible))

            known = direct(yp[0]) + direct(mp[0])
            known += sum((branch(b, {yp[0], mp[0]}) for b in [yp[1], mp[1], dp[1]]), Fraction(0))
            check((known * 72).denominator == 1, "known exact scale")
            result[rule_number, trait_number] = [int(known * 72), 12 * int(known > 0)]
            hourly = []
            for hour_number, hour_branch in enumerate(BRANCHES):
                hour_stem = STEMS[(2 * (STEMS.index(dm) % 5) + hour_number) % 10]
                visible = {yp[0], mp[0], hour_stem}
                score = direct(yp[0]) + direct(mp[0]) + direct(hour_stem)
                score += sum((branch(b, visible) for b in [yp[1], mp[1], dp[1], hour_branch]), Fraction(0))
                hourly.append(score)
            scaled_count = sum(hourly, Fraction(0)) * 6
            check(scaled_count.denominator == 1, "hourly exact scale")
            result[rule_number + 4, trait_number] = [int(scaled_count), sum(x > 0 for x in hourly)]
    return result


def self_test(encoder_path):
    check(sha(encoder_path) == ENCODER_SHA, "Original symbolic reference pin")
    spec = importlib.util.spec_from_file_location("locked_original_symbolic_reference", encoder_path)
    original = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(original)
    fixtures = [("甲子", "甲子", "甲子"), ("己未", "丁酉", "甲子"),
                ("甲子", "丁亥", "甲子"), ("乙丑", "丁亥", "甲子"),
                ("庚申", "壬午", "丙辰"), ("辛巳", "丁丑", "癸酉")]
    fixtures += [(STEMS[i] + BRANCHES[i % 12], STEMS[(i + 3) % 10] + BRANCHES[(i + 4) % 12],
                  STEMS[(i + 5) % 10] + BRANCHES[(i + 8) % 12]) for i in range(10)]
    for p in fixtures:
        own = independent_symbolic_encoder(*p)
        check(np.array_equal(own, original._fraction_reference(*p)), "Independent symbolic reference mismatch: " + str(p))
        check(np.all(own[..., 0] <= np.asarray(DENOMS)[:, None] * 72), "Symbolic count denominator")
        check(np.all((own[..., 1] >= 0) & (own[..., 1] <= 12)), "Symbolic presence scale")
    example = independent_symbolic_encoder("甲子", "甲子", "甲子")
    check(example[4, 0, 0] == example[5, 0, 0] == 12, "Toy equal hourly means")
    check(example[4, 0, 1] == 2 and example[5, 0, 1] == 1, "Presence must average indicators")
    sums = {1900: [3, 2, 0], 1901: [0, 1, 6]}
    sizes = {1900: 3, 1901: 4}
    e = exact_expected(sums, sizes, [1900, 1900, 1901])
    check(e == [Fraction(2), Fraction(19, 12), Fraction(3, 2)], "Exact birthyear weighting toy")
    compare({"a": 3, "b": [0.5, None]}, {"a": 3, "b": [Fraction(1, 2), None]})
    return {"schema": "Nobel_descriptive_independent_auditor_synthetic_QA_v1", "status": "PASS",
            "study_cohort_or_feature_cache_read": False, "symbolic_fixtures": len(fixtures),
            "models_per_fixture": 8, "traits_per_model": 2,
            "checked": ["all_hidden_rules_and_fallback", "day_reference_excluded_from_exposure",
                        "uniform12hour_count_and_indicator_means", "count_scale72_presence_scale12",
                        "five_and_seven_position_denominators", "exact_person_birthyear_calendar_weighting"],
            "original_symbolic_reference_sha256": ENCODER_SHA}


def gate(args):
    scope = json.loads(Path(args.scope).read_text())
    receipt = json.loads(Path(args.execution_receipt).read_text())
    manifest = json.loads(Path(args.locked_files).read_text())
    check(receipt.get("remote_plan_and_code_verified_before_summary") is True or
          receipt.get("remote_Git_lock_verified_before_inference") is True, "Remote lock flag")
    check(re.fullmatch(r"[0-9a-f]{40}", receipt.get("commit", receipt.get("lock_commit_sha", ""))) is not None,
          "Remote lock commit")
    check(receipt.get("scope_sha256") == sha(args.scope), "Scope hash")
    check(receipt.get("locked_file_manifest_sha256") == sha(args.locked_files), "Manifest hash")
    check(any(Path(p).resolve() == Path(__file__).resolve() for p in manifest), "Auditor absent from manifest")
    for p, digest in manifest.items():
        check(sha(p) == digest, "Locked file changed: " + p)
    for p, digest in [(args.v4_zip, V4_SHA), (args.calendar_npz, CALENDAR_SHA),
                      (args.hidden_npz, HIDDEN_SHA), (args.encoder, ENCODER_SHA)]:
        check(sha(p) == digest, "Input/code pin: " + p)
    check(not Path(args.output).exists(), "Refusing to overwrite QA output")
    return scope, receipt


def read_npz(path):
    with np.load(path, allow_pickle=False) as f:
        return {k: f[k] for k in f.files}


def calendar_columns(cal, hidden):
    check(cal["ten_god_names"].tolist() == GODS and cal["dm_stems"].tolist() == STEMS, "M0 labels")
    check(hidden["models"].tolist() == MODELS and hidden["traits"].tolist() == TRAITS, "Hidden labels")
    check(hidden["scales"].tolist() == [72, 12] and hidden["position_denominators"].tolist() == DENOMS,
          "Hidden scales/denominators")
    check(hidden["metrics"].tolist() == ["count_scaled72", "presence_scaled12"], "Hidden metrics")
    for key in ["dates", "year", "month", "jie_boundary_day", "jie_boundary_plus_minus_one_civil_day",
                "year_pillar", "month_pillar", "day_pillar"]:
        check(np.array_equal(cal[key], hidden[key]), "Cache alignment: " + key)
    dates = [dt.date(1835, 1, 1) + dt.timedelta(days=i) for i in range(len(cal["dates"]))]
    check([x.isoformat() for x in dates] == cal["dates"].tolist() and dates[-1] == dt.date(1985, 12, 31),
          "Complete valid calendar")
    tg = cal["ten_god_counts"].astype(np.int64)
    check(tg.shape == (55152, 10) and np.all(tg >= 0) and np.all(tg.sum(axis=1) == 5), "Every date TG sum5")
    dm = cal["DM_index"].astype(np.int64)
    check(np.all((dm >= 0) & (dm < 10)), "DM index domain")
    check([STEMS.index(str(p)[0]) for p in cal["day_pillar"]] == dm.tolist(), "DayMaster reference")
    hc, hp = hidden["count_scaled72"].astype(np.int64), hidden["presence_scaled12"].astype(np.int64)
    check(hc.shape == hp.shape == (55152, 8, 2), "Hidden shape")
    check(np.array_equal(hidden["features"][..., 0], hc) and np.array_equal(hidden["features"][..., 1], hp),
          "Hidden feature aliases")
    check(np.all((hc >= 0) & (hc <= np.asarray(DENOMS)[None, :, None] * 72)), "Count range")
    check(np.all((hp >= 0) & (hp <= 12)), "Presence range")
    check(np.array_equal(hp[:, :4], (hc[:, :4] > 0).astype(int) * 12), "Known5 exact presence")
    check(np.array_equal(hc[:, 0, 0], tg[:, 8] * 72) and np.array_equal(hc[:, 0, 1], tg[:, 3] * 72),
          "M0 hidden/TG count identity")
    basic = cal["features"][:, :5].astype(np.int64)
    check(np.array_equal(basic[:, 0], tg[:, 8]) and np.array_equal(basic[:, 1], tg[:, 3]), "Basic PI/SG")
    check(np.array_equal(basic[:, 4], dm >= 8), "Basic waterDM")
    onehot = np.eye(10, dtype=np.int64)[dm]
    columns = np.column_stack([tg, tg > 0, onehot, basic, hc.reshape(len(dm), 16), hp.reshape(len(dm), 16)])
    sums, sizes = {}, {}
    for y in range(1835, 1986):
        positions = np.flatnonzero(cal["year"] == y)
        sizes[y] = len(positions)
        check(sizes[y] in [365, 366], "Calendar year cardinality")
        sums[y] = columns[positions].sum(axis=0, dtype=np.int64).tolist()
    return columns, sums, sizes


def read_people(archive, source, path="Nobel_full_roster_matched_people"):
    key = "scientist_north_data_freeze_v4/outputs/" + source + "/" + path + ".jsonl.gz"
    return [json.loads(line) for line in gzip.decompress(archive.read(key)).splitlines()]


def source_class(person, source):
    support = person["DOB_support"][source]
    grades = {s.get("DOB_source_grade") for s in support}
    if "S1" in grades:
        return "S1"
    if "S2" in grades:
        return "S2"
    if any(set(s.get("possible_DOB_source_grades", [])) and
           set(s.get("possible_DOB_source_grades", [])) <= {"S1", "S2"} for s in support):
        return "S1_or_S2_union"
    check(source == "expanded" and "S3" in grades, "Source support classification")
    return "S3_only"


def audit_group(actual, rows, columns, date_index, sums, sizes, source, population_meta):
    n = len(rows)
    check(n == {"strict": 621, "expanded": 627}[source], "Source Nobel N")
    ids = [r["person_id"] for r in rows]
    check(len(set(ids)) == n and all(r["hemisphere"] == "north" for r in rows), "Unique north Nobel")
    check(all(not r.get("person_level_DOB_analysis_hold") for r in rows), "No active date hold")
    years = [int(r["analysis_DOB"][:4]) for r in rows]
    indexes = [date_index[r["analysis_DOB"]] for r in rows]
    # Python integer sums are an independent reduction from the table builder.
    observed = [sum(int(columns[i, j]) for i in indexes) for j in range(columns.shape[1])]
    expected = exact_expected(sums, sizes, years)
    expected_float = list(map(float, expected))
    membership = Counter(j for r in rows for j in r["qualified_academy_memberships"])
    check(sum(observed[:10]) == n * 5 and sum(observed[20:30]) == n, "Person/position count conservation")
    check(sum(expected[:10]) == n * 5 and sum(expected[20:30]) == n, "Exact calendar conservation")
    compare(actual, {"people": n, "five_position_denominator": n * 5,
                     "birth_year_min": min(years), "birth_year_max": max(years),
                     "calendar_year_counts": {str(y): c for y, c in sorted(Counter(years).items())},
                     "person_ids_sha256": hashlib.sha256(("\n".join(sorted(ids)) + "\n").encode()).hexdigest(),
                     "academy_membership_counts_nonexclusive": {j: membership[j] for j in INSTITUTIONS},
                     "inferential_p_values_added": False})
    case = "strict_primary" if source == "strict" else "expanded"
    pm = population_meta["cases"][case]["Nobel"]
    check(pm["n"] == n and pm["person_ids_sha256"] == hashlib.sha256(canonical(sorted(ids)).encode()).hexdigest(),
          "Independent population metadata IDs")
    check(pm["source_class_counts"] == dict(Counter(source_class(r, source) for r in rows)), "Source classes")
    check(pm["membership"]["nonfractional_institution_people"] == {j: membership[j] for j in INSTITUTIONS},
          "Source-consistent membership counts")
    basic_names = ["PI_count", "SG_count", "GY_narrow", "SGY_narrow", "water_DM"]
    for j, name in enumerate(basic_names, start=30):
        compare(actual["basic_metrics"][name], {"observed_mean": observed[j] / n,
                "calendar_expected_mean": expected_float[j] / n, "excess_mean": float(Fraction(observed[j]) - expected[j]) / n,
                "observed_sum": observed[j], "calendar_expected_sum": expected_float[j]})
    check(len(actual["TenGod_M0"]) == len(actual["DayMaster10"]) == 10, "Ten-category table lengths")
    for j, label in enumerate(GODS):
        om, em = observed[j] / n, expected_float[j] / n
        op, ep = observed[10+j] / n, expected_float[10+j] / n
        compare(actual["TenGod_M0"][j], {"label": label, "count_total": observed[j],
                "calendar_expected_count_total": expected_float[j], "mean_count_per_person": om,
                "calendar_expected_mean_count": em, "excess_mean_count": om-em,
                "position_share": om/5, "calendar_expected_position_share": em/5,
                "excess_position_share_pp": (om-em)*20, "people_at_least_one": observed[10+j],
                "person_presence_probability": op, "calendar_expected_person_presence_probability": ep,
                "excess_person_presence_pp": (op-ep)*100, "inferential_p_value_added": False})
    for j, label in enumerate(STEMS, start=20):
        compare(actual["DayMaster10"][j-20], {"label": label, "people": observed[j], "share": observed[j]/n,
                "calendar_expected_people": expected_float[j], "calendar_expected_share": expected_float[j]/n,
                "excess_share_pp": float(Fraction(observed[j])-expected[j])*100/n, "inferential_p_value_added": False})
    check(len(actual["hidden_PI_SG_models"]) == 16, "All8x2 hidden rows")
    for mi, model in enumerate(MODELS):
        for ti, trait in enumerate(TRAITS):
            flat = mi*2+ti
            om, em = observed[35+flat]/(72*n), expected_float[35+flat]/(72*n)
            op, ep = observed[51+flat]/(12*n), expected_float[51+flat]/(12*n)
            compare(actual["hidden_PI_SG_models"][flat], {"model": model, "trait": trait,
                    "label": "偏印" if ti == 0 else "伤官", "position_denominator": DENOMS[mi],
                    "count_sum_scaled72": observed[35+flat], "presence_sum_scaled12": observed[51+flat],
                    "mean_count_per_person": om, "calendar_expected_mean_count": em, "excess_mean_count": om-em,
                    "position_share": om/DENOMS[mi], "calendar_expected_position_share": em/DENOMS[mi],
                    "excess_position_share_pp": (om-em)*100/DENOMS[mi],
                    "person_presence_probability": op, "calendar_expected_person_presence_probability": ep,
                    "excess_person_presence_pp": (op-ep)*100,
                    "presence_interpretation": "known_five_position_indicator_mean" if mi < 4 else
                        "mean_of_12_uniform_hour_specific_presence_indicators",
                    "inferential_p_value_added": False})
    check(len(actual["decade_tables"]) == 16, "All16 decade bins")
    for bin_index, decade in enumerate(DECADES):
        b = [j for j, y in enumerate(years) if (y//10)*10 == decade]
        size = len(b)
        oi = [indexes[j] for j in b]
        obs = [sum(int(columns[i, j]) for i in oi) for j in range(30)]
        exp = list(map(float, exact_expected(sums, sizes, [years[j] for j in b])))
        compare(actual["decade_tables"][bin_index], {"decade": decade, "people": size,
                "birth_window_partial": decade in [1830, 1980], "small_bin_n_lt_20": size < 20,
                "TG_count_totals": obs[:10], "TG_calendar_expected_count_totals": exp[:10],
                "TG_position_shares": [v/(size*5) for v in obs[:10]] if size else [None]*10,
                "TG_presence_people": obs[10:20], "TG_calendar_expected_presence_people": exp[10:20],
                "DM_people": obs[20:30], "DM_calendar_expected_people": exp[20:30],
                "DM_shares": [v/size for v in obs[20:30]] if size else [None]*10,
                "inferential_p_value_added": False})
    return {"status": "PASS", "people": n, "TenGod_rows_checked": 10, "DayMaster_rows_checked": 10,
            "hidden_model_trait_rows_checked": 16, "decade_bins_checked": 16,
            "integer_observed_sums_and_exact_fraction_calendar_expectations": True,
            "source_classes_and_memberships_match_population_metadata": True}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--self-test", action="store_true")
    p.add_argument("--self-test-output")
    p.add_argument("--encoder", default="nobel_reveal_work/original/hidden_stem_v1/scripts/hidden_features.py")
    for name in ["scope", "locked-files", "execution-receipt", "v4-zip", "calendar-npz", "hidden-npz",
                 "population-metadata", "descriptives", "output"]:
        p.add_argument("--" + name)
    args = p.parse_args()
    if args.self_test:
        result = self_test(args.encoder)
        if args.self_test_output:
            Path(args.self_test_output).write_text(canonical(result))
        print(canonical(result), end="")
        return
    for name in ["scope", "locked_files", "execution_receipt", "v4_zip", "calendar_npz", "hidden_npz",
                 "population_metadata", "descriptives", "output"]:
        check(bool(getattr(args, name)), "Required argument: " + name)
    _, receipt = gate(args)
    result = json.loads(Path(args.descriptives).read_text())
    check(result["schema"] == "Nobel_descriptive_tables_v1" and result["population"] == "Nobel_full_roster_matched_people",
          "Descriptor output schema/population")
    compare(result, {"source_order": ["strict", "expanded"], "TenGod_order": GODS, "DayMaster_order": STEMS,
                     "hidden_model_order": MODELS, "hidden_trait_order": TRAITS, "decade_bins": DECADES,
                     "new_p_values_or_trend_tests_computed": False, "independent_replication_claim": False})
    check(result["execution_receipt"] == receipt, "Descriptor/QA same execution receipt")
    check(result["source_and_code_sha256"]["V4"] == V4_SHA and
          result["source_and_code_sha256"]["calendar"] == CALENDAR_SHA and
          result["source_and_code_sha256"]["hidden"] == HIDDEN_SHA, "Descriptor source pins")
    cal, hidden = read_npz(args.calendar_npz), read_npz(args.hidden_npz)
    columns, sums, sizes = calendar_columns(cal, hidden)
    date_index = {str(d): i for i, d in enumerate(cal["dates"])}
    population_meta = json.loads(Path(args.population_metadata).read_text())
    cases = {}
    with zipfile.ZipFile(args.v4_zip) as z:
        people = {s: read_people(z, s) for s in ["strict", "expanded"]}
    e = {r["person_id"]: r["analysis_DOB"] for r in people["expanded"]}
    check(all(e.get(r["person_id"]) == r["analysis_DOB"] for r in people["strict"]), "Source nesting/same DOB")
    for source in ["strict", "expanded"]:
        cases[source] = audit_group(result["groups"][source], people[source], columns, date_index, sums,
                                    sizes, source, population_meta)
    output = {"schema": "Nobel_descriptive_independent_QA_v1", "status": "PASS", "cases": cases,
              "method": "independent integer column reductions; exact Fraction year-calendar weighted sums",
              "p_values_or_additional_hypothesis_tests_computed": False,
              "hashes": {"descriptives": sha(args.descriptives), "auditor": sha(__file__),
                         "V4": V4_SHA, "calendar": CALENDAR_SHA, "hidden": HIDDEN_SHA,
                         "original_hidden_encoder": ENCODER_SHA, "population_metadata": sha(args.population_metadata),
                         "scope": sha(args.scope), "locked_files": sha(args.locked_files),
                         "execution_receipt": sha(args.execution_receipt)},
              "completed_utc": dt.datetime.now(dt.timezone.utc).isoformat()}
    Path(args.output).write_text(canonical(output))
    print(canonical({"status": "PASS", "output": args.output, "descriptives_sha256": sha(args.descriptives)}), end="")


if __name__ == "__main__":
    main()
