#!/usr/bin/env python3
"""Date-only scientist charts; no cohort outcome summaries or hypothesis tests."""
import argparse
import calendar
import csv
import datetime as dt
import functools
import gzip
import hashlib
import importlib.metadata
import io
import json
from pathlib import Path
import zipfile

from lunar_python import Solar
import lunar_python

STEMS = "甲乙丙丁戊己庚辛壬癸"
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
ELEMENTS = "木火土金水"
MAIN_QI = dict(zip(BRANCHES, "癸己甲乙戊丙丁己庚辛戊壬"))
TEN_GODS = ["比肩", "劫财", "食神", "伤官", "偏财", "正财", "七杀", "正官", "偏印", "正印"]
JIE = {"小寒", "立春", "惊蛰", "清明", "立夏", "芒种", "小暑", "立秋", "白露", "寒露", "立冬", "大雪"}
JIE_ALIASES = {"DA_XUE": "大雪", "XIAO_HAN": "小寒", "LI_CHUN": "立春", "JING_ZHE": "惊蛰"}
POSITIONS = ["year_stem", "year_branch_main_qi", "month_stem", "month_branch_main_qi", "day_branch_main_qi"]
ROOT = Path(__file__).resolve().parents[1]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"


def ten_god(day, other):
    di, oi = STEMS.index(day), STEMS.index(other)
    delta = (oi // 2 - di // 2) % 5
    same = di % 2 == oi % 2
    return {0: ("比肩", "劫财"), 1: ("食神", "伤官"), 2: ("偏财", "正财"), 3: ("七杀", "正官"), 4: ("偏印", "正印")}[delta][0 if same else 1]


def day_jdn(date):
    # Integer proleptic Gregorian JDN, astronomical noon. Epoch offset is fixed.
    a = (14 - date.month) // 12
    y, m = date.year + 4800 - a, date.month + 12 * a - 3
    jdn = date.day + (153 * m + 2) // 5 + 365 * y + y // 4 - y // 100 + y // 400 - 32045
    return STEMS[(jdn + 49) % 10] + BRANCHES[(jdn + 49) % 12]


def pillars_at(date, hour=12, minute=0, second=0):
    # Do not delegate Gregorian validity to lunar-python's permissive constructor.
    dt.datetime(date.year, date.month, date.day, hour, minute, second)
    ec = Solar.fromYmdHms(date.year, date.month, date.day, hour, minute, second).getLunar().getEightChar()
    ec.setSect(2)
    return ec.getYear(), ec.getMonth(), ec.getDay()


@functools.lru_cache(maxsize=None)
def jie_events(year):
    # Lunar table spans adjacent calendar years. Filter actual event year and deduplicate aliases.
    table = Solar.fromYmdHms(year, 7, 1, 12, 0, 0).getLunar().getJieQiTable()
    found = {}
    for key, solar in table.items():
        label = JIE_ALIASES.get(key, key)
        if label in JIE and solar.getYear() == year:
            stamp = solar.toYmdHms()
            found[(label, stamp)] = {"name": label, "reference_utc_plus_08": stamp, "date": stamp[:10]}
    events = sorted(found.values(), key=lambda e: e["reference_utc_plus_08"])
    if len(events) != 12:
        raise AssertionError(("Jie event count", year, len(events)))
    return events


@functools.lru_cache(maxsize=None)
def chart(date_string):
    date = dt.date.fromisoformat(date_string)
    yp, mp, dp = pillars_at(date)
    if dp != day_jdn(date):
        raise AssertionError(("Gregorian JDN day mismatch", date_string))
    stems = [yp[0], MAIN_QI[yp[1]], mp[0], MAIN_QI[mp[1]], MAIN_QI[dp[1]]]
    gods = [ten_god(dp[0], s) for s in stems]
    counts = {g: gods.count(g) for g in TEN_GODS}
    near = []
    for year in [date.year - 1, date.year, date.year + 1]:
        for event in jie_events(year):
            delta = (date - dt.date.fromisoformat(event["date"])).days
            if abs(delta) <= 1:
                near.append({**event, "DOB_minus_Jie_civil_days": delta})
    early, late = pillars_at(date, 0), pillars_at(date, 23, 59, 59)
    return {
        "year_pillar": yp, "month_pillar": mp, "day_pillar": dp,
        "date_known_six_characters": yp + mp + dp,
        "hour_pillar": None, "birth_time_known": False,
        "computation_reference": "civil_date_12:00:00_fixed_UTC+08:00_not_inferred_birth_time",
        "day_rollover": "00:00_civil_sect2",
        "day_master": dp[0], "day_master_element": ELEMENTS[STEMS.index(dp[0]) // 2],
        "day_master_water": dp[0] in "壬癸",
        "five_position_stems": dict(zip(POSITIONS, stems)),
        "five_position_ten_gods": dict(zip(POSITIONS, gods)),
        "ten_god_counts_five_positions": counts,
        "guan_yin_narrow": counts["正官"] > 0 and counts["正印"] > 0,
        "guan_yin_broad": counts["正官"] + counts["七杀"] > 0 and counts["正印"] + counts["偏印"] > 0,
        "shangguan_yin_narrow": counts["伤官"] > 0 and counts["正印"] > 0,
        "shangguan_yin_broad": counts["伤官"] > 0 and counts["正印"] + counts["偏印"] > 0,
        "jie_boundary_day": early[:2] != late[:2],
        "jie_boundary_plus_minus_one_civil_day": bool(near),
        "near_jie_events": near,
    }


def synthetic_qa():
    # All fixtures are outside the frozen 1835-1985 cohort window.
    expected = {
        "2000-01-07": ("己卯", "丁丑", "甲子"),
        "2024-02-10": ("甲辰", "丙寅", "甲辰"),
        "2024-02-04": ("癸卯", "乙丑", "戊戌"),
    }
    for date, value in expected.items():
        assert pillars_at(dt.date.fromisoformat(date)) == value, (date, value)
    # Leap-century handling and consecutive sexagenary days independently checked.
    checked = 0
    for year in [1800, 2000, 2024, 2100]:
        start = dt.date(year, 1, 1)
        for offset in range(366 if calendar.isleap(year) else 365):
            date = start + dt.timedelta(days=offset)
            assert pillars_at(date)[2] == day_jdn(date), date
            checked += 1
    for day in STEMS:
        row = [ten_god(day, other) for other in STEMS]
        assert sorted(row) == sorted(TEN_GODS)
        assert ten_god(day, day) == "比肩"
    for year in [1800, 2000, 2024, 2100]:
        assert len(jie_events(year)) == 12
    assert pillars_at(dt.date(2024, 2, 4), 16, 26, 0)[:2] == ("癸卯", "乙丑")
    assert pillars_at(dt.date(2024, 2, 4), 16, 28, 0)[:2] == ("甲辰", "丙寅")
    assert pillars_at(dt.date(2000, 1, 7), 23, 30)[2] == "甲子"
    for invalid in ["1900-02-29", "1985-02-30", "2001-13-01"]:
        try:
            dt.date.fromisoformat(invalid)
        except ValueError:
            pass
        else:
            raise AssertionError(("Invalid Gregorian coordinate accepted", invalid))
    return {"status": "PASS", "study_input_loaded": False, "out_of_window_JDN_day_checks": checked,
            "all_100_ten_god_pairs_checked": True, "explicit_sect2_23h_check": True,
            "LiChun_before_after_check": True, "synthetic_fixed_fixtures": expected}


def read_jsonl(data):
    return [json.loads(line) for line in gzip.decompress(data).splitlines()]


def write_jsonl(path, rows):
    data = "".join(canonical(r) for r in rows).encode()
    path.write_bytes(gzip.compress(data, mtime=0))


def write_csv(path, rows):
    fields = ["person_id", "display_name", "analysis_DOB", "included_strict", "included_expanded", "academy_memberships", "Nobel_full_roster", "Nobel_legacy_cohort", "Fields_parallel", "year_pillar", "month_pillar", "day_pillar", "hour_pillar", "date_known_six_characters", "day_master", "day_master_element", "jie_boundary_day", "jie_boundary_plus_minus_one_civil_day"]
    fields += ["stem_" + p for p in POSITIONS] + ["ten_god_" + p for p in POSITIONS]
    fields += ["count_" + g for g in TEN_GODS] + ["guan_yin_narrow", "guan_yin_broad", "shangguan_yin_narrow", "shangguan_yin_broad", "day_master_water"]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for r in rows:
            flat = {f: r.get(f) for f in fields}
            flat["academy_memberships"] = ";".join(r["qualified_academy_memberships"])
            flat["hour_pillar"] = "未知"
            flat.update({"stem_" + k: v for k, v in r["five_position_stems"].items()})
            flat.update({"ten_god_" + k: v for k, v in r["five_position_ten_gods"].items()})
            flat.update({"count_" + k: v for k, v in r["ten_god_counts_five_positions"].items()})
            writer.writerow(flat)


def build(args):
    config = json.loads((ROOT / "ASSUMPTIONS_LOCK_V1.json").read_text())
    receipt = json.loads(Path(args.lock_receipt).read_text())
    manifest_bytes = (ROOT / "LOCKED_FILES.sha256.json").read_bytes()
    assert receipt["remote_Git_lock_verified_before_study_transform"] is True
    assert len(receipt["lock_commit_sha"]) == 40
    assert receipt["locked_files_manifest_sha256"] == sha(manifest_bytes)
    for rel, expected in json.loads(manifest_bytes).items():
        assert sha((ROOT / rel).read_bytes()) == expected, ("Locked code/protocol changed", rel)
    assert importlib.metadata.version("lunar_python") == config["calendar"]["package_version"]
    dependency_qa = json.loads((ROOT / "qa/CALENDAR_PRELOCK_QA.json").read_text())
    package_parent = Path(lunar_python.__file__).resolve().parent.parent
    dependency_manifest = dependency_qa["dependencies"]["lunar_python"]["module_manifest"]
    for item in dependency_manifest["files"]:
        assert sha((package_parent / item["path"]).read_bytes()) == item["sha256"], ("Calendar module changed", item["path"])
    synthetic = synthetic_qa()
    input_bytes = Path(args.input_zip).read_bytes()
    assert sha(input_bytes) == config["inputs"]["V4_zip_sha256"]
    with zipfile.ZipFile(io.BytesIO(input_bytes)) as z:
        prefix = "scientist_north_data_freeze_v4/"
        paths = [n for n in z.namelist() if n.startswith(prefix + "outputs/") and n.endswith(".jsonl.gz") and ("/strict/" in n or "/expanded/" in n or "/sensitivity/" in n) and "/source_bridges/" not in n]
        selections = {n[len(prefix + "outputs/"):]: [p["person_id"] for p in read_jsonl(z.read(n))] for n in paths}
        people = read_jsonl(z.read(prefix + "outputs/expanded/people.jsonl.gz"))
        strict = read_jsonl(z.read(prefix + "outputs/strict/people.jsonl.gz"))
        sensitivity = read_jsonl(z.read(prefix + "outputs/sensitivity/expanded_without_LOC_quoted_metadata_people.jsonl.gz"))
    selection_pin = json.loads((ROOT / "input_freeze/GROUP_SELECTION_SHA256.json").read_text())
    assert sha(canonical(selections).encode()) == selection_pin["canonical_group_person_ids_json_sha256"]
    people.sort(key=lambda r: r["person_id"])
    ids = [p["person_id"] for p in people]
    id_set = set(ids)
    assert len(people) == len(set(ids)) == 6537
    assert {p["person_id"] for p in strict} == set(selections["strict/people.jsonl.gz"])
    assert set(ids) == set(selections["expanded/people.jsonl.gz"])
    assert len(strict) == 5894
    no_loc = {p["person_id"] for p in sensitivity}
    group_sets = {key: set(value) for key, value in selections.items()}
    rows = []
    for p in people:
        pid, date = p["person_id"], p["analysis_DOB"]
        assert p["hemisphere"] == "north" and not p["person_level_DOB_analysis_hold"]
        assert "1835-01-01" <= date <= "1985-12-31"
        assert date == p["retained_candidate_date_coordinate"]
        c = chart(date)
        out = {**p, **c,
               "Nobel_full_roster": pid in group_sets["expanded/Nobel_full_roster_matched_people.jsonl.gz"],
               "Nobel_legacy_cohort": pid in group_sets["expanded/Nobel_frozen_candidate_cohort.jsonl.gz"],
               "Fields_parallel": pid in group_sets["expanded/Fields_parallel_cohort.jsonl.gz"],
               "included_expanded_without_LOC": pid in no_loc,
               "analysis_unblinding_ready": False,
               "feature_transform_authorized": True,
               "hypothesis_inference_authorized_by_current_task": False,
               "hypothesis_inference_executed": False,
               "unblinding_stage": "date_only_chart_transform_no_inference",
               "V4_analysis_unblinding_ready_original": p["analysis_unblinding_ready"],
               "assumptions_lock_commit": receipt["lock_commit_sha"]}
        assert sum(c["ten_god_counts_five_positions"].values()) == 5
        assert len(c["date_known_six_characters"]) == 6 and c["hour_pillar"] is None
        rows.append(out)
    outdir = Path(args.output)
    outdir.mkdir(parents=True, exist_ok=False)
    write_jsonl(outdir / "charts_unique_expanded.jsonl.gz", rows)
    write_csv(outdir / "charts_unique_expanded.csv", rows)
    strict_rows = [r for r in rows if r["included_strict"]]
    write_csv(outdir / "charts_unique_strict.csv", strict_rows)
    groups, exclusions = [], []
    for key, members in sorted(selections.items()):
        if Path(key).name == "excluded_people.jsonl.gz":
            exclusions.extend({"population_path": key, "person_id": pid, "role": "exclusion_reference_only", "has_generated_chart": pid in id_set} for pid in members)
        else:
            groups.extend({"population_path": key, "person_id": pid} for pid in members)
    write_jsonl(outdir / "group_memberships.jsonl.gz", groups)
    write_jsonl(outdir / "exclusion_group_references.jsonl.gz", exclusions)
    # Coverage summaries contain no Ten-God/DM/cooccurrence frequencies or effects.
    qa = {"status": "PASS", "unique_charts_expanded": len(rows), "unique_charts_strict": len(strict_rows),
          "source_DOB_and_ID_preserved": True, "strict_subset_of_expanded": True,
          "all_24_effective_DOB_holds_absent": True, "source_date_coordinate_changes": 0,
          "hour_pillars_filled": 0, "all_day_pillars_JDN_verified": True,
          "all_ten_god_count_sums_equal_five": True,
          "group_population_counts": {k: len(v) for k, v in sorted(selections.items())},
          "boundary_flagged_expanded": sum(r["jie_boundary_plus_minus_one_civil_day"] for r in rows),
          "boundary_exact_day_expanded": sum(r["jie_boundary_day"] for r in rows),
          "synthetic_QA": synthetic, "inference_executed": False,
          "hypothesis_outcome_frequencies_or_effects_computed": False}
    (outdir / "BUILD_QA.json").write_text(json.dumps(qa, ensure_ascii=False, indent=2) + "\n")
    (outdir / "LOCK_RECEIPT.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
    hashes = {p.name: sha(p.read_bytes()) for p in sorted(outdir.iterdir()) if p.is_file()}
    (outdir / "OUTPUT_SHA256.json").write_text(json.dumps(hashes, indent=2) + "\n")
    print(json.dumps({k: qa[k] for k in ["status", "unique_charts_expanded", "unique_charts_strict", "hour_pillars_filled", "inference_executed"]}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--synthetic-qa-only", action="store_true")
    parser.add_argument("--input-zip")
    parser.add_argument("--lock-receipt")
    parser.add_argument("--output")
    args = parser.parse_args()
    if args.synthetic_qa_only:
        print(json.dumps(synthetic_qa(), ensure_ascii=False, indent=2))
    else:
        if not all([args.input_zip, args.lock_receipt, args.output]):
            parser.error("Study transformation requires --input-zip, --lock-receipt and --output")
        build(args)
