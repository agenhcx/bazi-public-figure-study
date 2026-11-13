#!/usr/bin/env python3
"""NAS-only descriptive tables, preserving the disclosed cohorts and rules.

No hypothesis tests or new inferential claims. The full Ten-God M1 encoding is
the same priority replacement rule already used for PI/SG, extended symmetrically
to all ten categories. Year/month/day stem distributions are separate displays.
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
V4_SHA = "53302ef5c4bbb946adcaceb70d7a7fd576c7f06d03c3e7080874654e1a2644f9"
CALENDAR_SHA = "d150883033464ebd3afafaf764738ed3b573d0d0fb4bd252a955e403a75fcc8b"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check(ok, message):
    if not bool(ok):
        raise AssertionError(message)


def close(a, b, message):
    check(np.allclose(a, b, rtol=1e-10, atol=1e-10), message)


def tg_index(day, other):
    return 2 * ((other // 2 - day // 2) % 5) + (day % 2 != other % 2)


def priority_stem(branch, year_stem, month_stem):
    hs = HIDDEN[branch]
    exposed = [s for s in hs if s == year_stem or s == month_stem]
    return exposed[0] if exposed else hs[0]


def encode_pool(year_pillars, month_pillars, day_pillars):
    n = len(day_pillars)
    si, bi = {s: i for i, s in enumerate(STEMS)}, {b: i for i, b in enumerate(BRANCHES)}
    y = np.asarray([[si[str(v)[0]], bi[str(v)[1]]] for v in year_pillars], dtype=np.int16)
    m = np.asarray([[si[str(v)[0]], bi[str(v)[1]]] for v in month_pillars], dtype=np.int16)
    d = np.asarray([[si[str(v)[0]], bi[str(v)[1]]] for v in day_pillars], dtype=np.int16)
    selected = np.empty((10, 10, 12), dtype=np.int16)
    for ys in range(10):
        for ms in range(10):
            for branch in range(12):
                selected[ys, ms, branch] = si[priority_stem(BRANCHES[branch], STEMS[ys], STEMS[ms])]
    main = np.asarray([si[HIDDEN[b][0]] for b in BRANCHES])
    result = {}
    for name, exposure in [("M0_5_mainqi", False), ("M1_5_priority", True)]:
        count = np.zeros((n, 10), dtype=np.int16)
        positions = [y[:, 0], m[:, 0]]
        for branches in [y[:, 1], m[:, 1], d[:, 1]]:
            positions.append(selected[y[:, 0], m[:, 0], branches] if exposure else main[branches])
        for other in positions:
            categories = tg_index(d[:, 0], other).astype(np.intp)
            count[np.arange(n), categories] += 1
        check(np.all(count.sum(axis=1) == 5), name + " must have five informative positions")
        result[name] = count
    stem_positions = {"year_stem": y[:, 0], "month_stem": m[:, 0], "day_stem": d[:, 0]}
    return result, stem_positions


def read_zip_rows(z, name):
    return [json.loads(line) for line in gzip.decompress(z.read("scientist_north_data_freeze_v4/" + name)).splitlines()]


def id_hash(ids):
    data = json.dumps(sorted(ids), ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    return hashlib.sha256(data.encode()).hexdigest()


def expected_by_year(years, values):
    return {int(y): values[years == y].mean(axis=0) for y in np.unique(years)}


def describe_group(rows, indexes, years, counts, stem_positions):
    n = len(rows)
    observed_years = np.asarray([int(p["analysis_DOB"][:4]) for p in rows])
    out = {"people": n, "person_ids_sha256": id_hash(p["person_id"] for p in rows), "TenGod_models": {},
           "HeavenlyStem_positions": {}}
    for model, values in counts.items():
        expectation = expected_by_year(years, values)
        prevalence = expected_by_year(years, (values > 0).astype(float))
        observed = values[indexes]
        obs_sum = observed.sum(axis=0)
        expected_sum = np.sum([expectation[int(y)] for y in observed_years], axis=0)
        obs_people = (observed > 0).sum(axis=0)
        expected_people = np.sum([prevalence[int(y)] for y in observed_years], axis=0)
        check(int(obs_sum.sum()) == 5 * n, "Observed Ten-God total differs from5*N")
        close(expected_sum.sum(), 5 * n, "Expected Ten-God total differs from5*N")
        out["TenGod_models"][model] = [
            {"ten_god": g, "observed_count": int(obs_sum[j]), "calendar_expected_count": float(expected_sum[j]),
             "observed_count_mean_per_person": float(obs_sum[j] / n),
             "calendar_expected_count_mean_per_person": float(expected_sum[j] / n),
             "observed_position_share": float(obs_sum[j] / (5 * n)),
             "calendar_expected_position_share": float(expected_sum[j] / (5 * n)),
             "position_share_difference_percentage_points": float((obs_sum[j] - expected_sum[j]) / (5 * n) * 100),
             "observed_people_with_at_least_one": int(obs_people[j]),
             "calendar_expected_people_with_at_least_one": float(expected_people[j]),
             "observed_person_presence": float(obs_people[j] / n),
             "calendar_expected_person_presence": float(expected_people[j] / n)} for j, g in enumerate(GODS)]
    for position, values in stem_positions.items():
        indicators = np.eye(10, dtype=np.int8)[values]
        expectations = expected_by_year(years, indicators)
        obs = np.bincount(values[indexes], minlength=10)
        exp = np.sum([expectations[int(y)] for y in observed_years], axis=0)
        check(int(obs.sum()) == n, "Stem-position count total differs fromN")
        close(exp.sum(), n, "Stem-position expectation total differs fromN")
        out["HeavenlyStem_positions"][position] = [
            {"stem": s, "observed_people": int(obs[j]), "calendar_expected_people": float(exp[j]),
             "observed_share": float(obs[j] / n), "calendar_expected_share": float(exp[j] / n),
             "difference_percentage_points": float((obs[j] - exp[j]) / n * 100)} for j, s in enumerate(STEMS)]
    return out


def verify_prior(result, main, hidden):
    checks = []
    prior_main = {c["case"]: c for c in main["cases"]}
    prior_hidden = {c["case"]: c for c in hidden["cases"]}
    for name in ["strict_primary", "expanded"]:
        group, a, b = result["groups"][name], prior_main[name], prior_hidden[name]
        check(group["people"] == a["n"] == b["n"], "Prior sample counts differ")
        check(group["person_ids_sha256"] == a["person_ids_sha256"] == b["person_ids_sha256"], "Prior selected person IDs differ")
        for item in group["TenGod_models"]["M0_5_mainqi"]:
            old = next(v for v in a["ten_gods_five_position_descriptive_only"] if v["ten_god"] == item["ten_god"])
            check(item["observed_count"] == old["observed_count_sum"], "Prior M0 observed count differs")
            close(item["calendar_expected_count_mean_per_person"], old["calendar_expected_count_mean_per_person"], "Prior M0 expectation differs")
        for item, old in zip(group["HeavenlyStem_positions"]["day_stem"], a["day_master_distribution"]):
            check(item["stem"] == old["stem"] and item["observed_people"] == old["observed_people"], "Prior DayMaster count differs")
            close(item["calendar_expected_people"], old["calendar_expected_people"], "Prior DayMaster expectation differs")
        for trait, god in [("PI", "偏印"), ("SG", "伤官")]:
            new = next(x for x in group["TenGod_models"]["M1_5_priority"] if x["ten_god"] == god)
            old = next(x for x in b["model_trait_descriptions"] if x["model"] == "M1_priority_5" and x["trait"] == trait)
            for nk, ok in [("observed_count_mean_per_person", "count_mean"),
                           ("calendar_expected_count_mean_per_person", "calendar_expected_count_mean"),
                           ("observed_person_presence", "person_presence_probability"),
                           ("calendar_expected_person_presence", "calendar_expected_person_presence_probability")]:
                close(new[nk], old[ok], "Prior M1 PI/SG projection differs: " + nk)
        checks.append({"case": name, "M0_all10_reproduced": True, "DayMaster_all10_reproduced": True,
                       "M1_PI_SG_reproduced": True, "person_ID_hashes_reproduced": True})
    return checks


def synthetic_qa():
    for d in range(10):
        check(sorted(int(tg_index(d, t)) for t in range(10)) == list(range(10)), "Ten-God bijection failed")
    check(priority_stem("未", "己", "丁") == "己", "Priority failed")
    check(priority_stem("未", "丁", "乙") == "丁", "Middle-stem priority failed")
    check(priority_stem("亥", "丁", "己") == "壬", "Main-qi fallback failed")
    check(priority_stem("亥", "甲", "丁") == "甲", "Same-character visible DayStem must stay visible")
    model, _ = encode_pool(["甲子", "乙丑"], ["丁亥", "丁亥"], ["甲子", "甲子"])
    check(model["M1_5_priority"][0, 8] == 0 and model["M1_5_priority"][1, 8] == 1,
          "Reference DayStem exposure exclusion failed")
    return {"status": "PASS", "study_inputs_loaded": False, "full_TenGod_bijection": True,
            "priority_fallback_and_visible_reference_character": True, "five_position_totals": True}


def main(args):
    if args.synthetic_qa_only:
        print(json.dumps(synthetic_qa(), ensure_ascii=False, indent=2))
        return
    auth = json.loads(Path(args.authorization).read_text())
    check(auth.get("country") == "NAS" and auth.get("full_ten_god_descriptive_authorized") is True and
          auth.get("no_new_hypothesis_tests") is True, "NAS descriptive authorization missing")
    check(auth.get("code_sha256") == sha(__file__), "Execution code SHA differs from authorization")
    paths = {"v4_zip": args.v4_zip, "calendar_npz": args.calendar_npz,
             "prior_main_json": args.prior_main_json, "prior_hidden_json": args.prior_hidden_json}
    for key, path in paths.items():
        check(path and sha(path) == auth["input_sha256"][key], "Input SHA mismatch: " + key)
    check(sha(args.v4_zip) == V4_SHA and sha(args.calendar_npz) == CALENDAR_SHA, "Original source pin differs")
    dest = Path(args.output)
    check(not dest.exists(), "Output exists; no overwrite")
    with zipfile.ZipFile(args.v4_zip) as z:
        sets = {}
        for quality in ["strict", "expanded"]:
            nas = {p["person_id"] for p in read_zip_rows(z, "outputs/" + quality + "/by_institution/NAS.jsonl.gz")}
            non_nobel = {p["person_id"] for p in read_zip_rows(z, "outputs/" + quality + "/academy_excluding_official_Nobel.jsonl.gz")}
            sets[quality] = nas & non_nobel
        people = {p["person_id"]: p for p in read_zip_rows(z, "outputs/expanded/people.jsonl.gz") if p["person_id"] in sets["expanded"]}
    check(len(sets["strict"]) == 908 and len(sets["expanded"]) == 1462 and sets["strict"] <= sets["expanded"], "NAS selections differ")
    check(set(people) == sets["expanded"], "NAS selected people missing")
    for person in people.values():
        check(person["hemisphere"] == "north" and not person["person_level_DOB_analysis_hold"], "Source selection hold or hemisphere changed")
        date = dt.date.fromisoformat(person["analysis_DOB"])
        check(dt.date(1835, 1, 1) <= date <= dt.date(1985, 12, 31), "Source DOB outside fixed window")
    with np.load(args.calendar_npz, allow_pickle=False) as z:
        dates, years = z["dates"], z["year"]
        model, positions = encode_pool(z["year_pillar"], z["month_pillar"], z["day_pillar"])
    check(len(dates) == 55152 and len(set(dates.tolist())) == 55152, "Calendar identities differ")
    lookup = {str(date): i for i, date in enumerate(dates)}
    result = {"schema": "NAS_all10_stems_and_TenGods_descriptive_v1", "country": "NAS", "groups": {},
              "ten_stems_primary_meaning": "DayMaster (DayStem); YearStem/MonthStem given separately",
              "TenGod_M0": "YG,MG,Ybranch main, Mbranch main,Dbranch main; referenceDayStem excluded",
              "TenGod_M1": "samefivepositions; branch representative first hidden stem exposed in YG/MG else main; no hour",
              "no_new_hypothesis_tests": True, "other_countries_or_Nobel_subgroups_aggregated": False,
              "source_and_code_sha256": {"code": sha(__file__), **{k: sha(v) for k, v in paths.items()}},
              "execution_authorization": auth}
    for quality, case in [("strict", "strict_primary"), ("expanded", "expanded")]:
        rows = [people[pid] for pid in sorted(sets[quality])]
        indexes = np.asarray([lookup[p["analysis_DOB"]] for p in rows], dtype=np.intp)
        result["groups"][case] = describe_group(rows, indexes, years, model, positions)
    result["prior_projection_QA"] = verify_prior(result, json.loads(Path(args.prior_main_json).read_text()),
                                                   json.loads(Path(args.prior_hidden_json).read_text()))
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"status": "PASS", "groups": {k: v["people"] for k, v in result["groups"].items()},
                      "full_categories": 10, "M0_M1_DayMaster_prior_projections": "PASS", "output": str(dest)}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--synthetic-qa-only", action="store_true")
    for option in ["v4-zip", "calendar-npz", "prior-main-json", "prior-hidden-json", "authorization", "output"]:
        parser.add_argument("--" + option)
    main(parser.parse_args())
