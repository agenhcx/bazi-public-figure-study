#!/usr/bin/env python3
"""Independent postlock chart audit. Never imports the chart builder.

Only run after the remote lock is confirmed and chart generation is authorized.
The report contains validation/coverage counts and mismatch details, never
cohort frequencies of Ten Gods, day masters, or cooccurrence indicators.
"""
import argparse
from collections import Counter
import csv
import datetime as dt
import functools
import gzip
import hashlib
import importlib.metadata
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import zipfile

STEMS = "甲乙丙丁戊己庚辛壬癸"
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
QI = {"子": "癸", "丑": "己", "寅": "甲", "卯": "乙", "辰": "戊", "巳": "丙",
      "午": "丁", "未": "己", "申": "庚", "酉": "辛", "戌": "戊", "亥": "壬"}
POSITIONS = ("year_stem", "year_branch_main_qi", "month_stem", "month_branch_main_qi", "day_branch_main_qi")
# Literal 10x10 reference table: rows/day master and columns/other stem in
# 甲乙丙丁戊己庚辛壬癸 order. This does not use the builder's modular formula.
GOD_ROWS = {
    "甲": "比肩 劫财 食神 伤官 偏财 正财 七杀 正官 偏印 正印",
    "乙": "劫财 比肩 伤官 食神 正财 偏财 正官 七杀 正印 偏印",
    "丙": "偏印 正印 比肩 劫财 食神 伤官 偏财 正财 七杀 正官",
    "丁": "正印 偏印 劫财 比肩 伤官 食神 正财 偏财 正官 七杀",
    "戊": "七杀 正官 偏印 正印 比肩 劫财 食神 伤官 偏财 正财",
    "己": "正官 七杀 正印 偏印 劫财 比肩 伤官 食神 正财 偏财",
    "庚": "偏财 正财 七杀 正官 偏印 正印 比肩 劫财 食神 伤官",
    "辛": "正财 偏财 正官 七杀 正印 偏印 劫财 比肩 伤官 食神",
    "壬": "食神 伤官 偏财 正财 七杀 正官 偏印 正印 比肩 劫财",
    "癸": "伤官 食神 正财 偏财 正官 七杀 正印 偏印 劫财 比肩",
}
GODS = GOD_ROWS["甲"].split()
TEN_GOD = {d: dict(zip(STEMS, words.split())) for d, words in GOD_ROWS.items()}
TERMS = ("冬至", "小寒", "大寒", "立春", "雨水", "惊蛰", "春分", "清明", "谷雨", "立夏", "小满", "芒种",
         "夏至", "小暑", "大暑", "立秋", "处暑", "白露", "秋分", "寒露", "霜降", "立冬", "小雪", "大雪")
JIE = set(TERMS[1::2])
BASE = Path(__file__).resolve().parents[1]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_rows(data):
    return [json.loads(line) for line in gzip.decompress(data).splitlines() if line.strip()]


def audit(args):
    import lunar_python
    from lunar_python import Solar
    import sxtwl

    mismatches = []
    checked = Counter()

    def require(ok, kind, **details):
        checked[kind] += 1
        if not ok:
            mismatches.append({"check": kind, **details})

    def equal(actual, expected, kind, **details):
        require(actual == expected, kind, expected=expected, actual=actual, **details)

    require(bool(re.fullmatch(r"[0-9a-f]{40}", args.lock_commit)), "lock_commit_format")
    equal(importlib.metadata.version("lunar_python"), "1.4.8", "lunar_version")
    equal(importlib.metadata.version("sxtwl"), "2.0.7", "sxtwl_version")
    config = json.loads((BASE / "ASSUMPTIONS_LOCK_V1.json").read_text())
    archive = Path(args.input_zip).read_bytes()
    equal(sha(archive), config["inputs"]["V4_zip_sha256"], "V4_archive_sha256")
    # Verify frozen files against Git objects, independently of the builder.
    repo = subprocess.check_output(["git", "-C", str(BASE), "rev-parse", "--show-toplevel"], text=True).strip()
    equal(subprocess.check_output(["git", "-C", repo, "rev-parse", "HEAD"], text=True).strip(), args.lock_commit, "runtime_HEAD_is_lock")
    lock_manifest_path = BASE / "LOCKED_FILES.sha256.json"
    lock_manifest = json.loads(lock_manifest_path.read_text())
    for rel, expected in lock_manifest.items():
        path = BASE / rel
        equal(sha(path.read_bytes()), expected, "locked_file_sha256", file=rel)
        git_rel = str(path.relative_to(repo))
        committed = subprocess.check_output(["git", "-C", repo, "show", args.lock_commit + ":" + git_rel])
        equal(sha(committed), expected, "file_matches_lock_Git_object", file=rel)
    dependency = json.loads((BASE / "qa/CALENDAR_PRELOCK_QA.json").read_text())
    package_parent = Path(lunar_python.__file__).resolve().parent.parent
    for package in ("lunar_python", "sxtwl"):
        for item in dependency["dependencies"][package]["module_manifest"]["files"]:
            equal(sha((package_parent / item["path"]).read_bytes()), item["sha256"], "dependency_file_sha256", package=package, file=item["path"])

    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        prefix = "scientist_north_data_freeze_v4/outputs/"
        population_paths = [n[len(prefix):] for n in z.namelist() if n.startswith(prefix)
                            and n.endswith(".jsonl.gz")
                            and n[len(prefix):].split("/")[0] in {"expanded", "strict", "sensitivity"}
                            and "/source_bridges/" not in n]
        populations = {key: read_rows(z.read(prefix + key)) for key in population_paths}
        holds = {name: read_rows(z.read(prefix + "holds/" + name + ".jsonl.gz"))
                 for name in ("person_DOB_or_calendar_holds", "membership_scope_holds", "expanded_source_support_unresolved_people")}
    group_sets = {key: {p["person_id"] for p in rows} for key, rows in populations.items()}
    source_rows = populations["expanded/people.jsonl.gz"]
    source = {p["person_id"]: p for p in source_rows}
    strict_ids = group_sets["strict/people.jsonl.gz"]
    equal(len(source_rows), len(source), "V4_expanded_unique_IDs")
    equal(len(source), 6537, "expanded_person_count")
    equal(len(strict_ids), 5894, "strict_person_count")
    require(strict_ids <= set(source), "strict_subset_expanded")
    charts_dir = Path(args.charts)
    chart_rows = read_rows((charts_dir / "charts_unique_expanded.jsonl.gz").read_bytes())
    charts = {p["person_id"]: p for p in chart_rows}
    equal(len(chart_rows), len(charts), "chart_unique_IDs")
    equal(set(charts), set(source), "chart_exact_V4_ID_set")
    receipt = json.loads((charts_dir / "LOCK_RECEIPT.json").read_text())
    equal(receipt.get("lock_commit_sha"), args.lock_commit, "receipt_lock_commit")
    require(receipt.get("remote_Git_lock_verified_before_study_transform") is True, "remote_lock_receipt_true")
    equal(receipt.get("locked_files_manifest_sha256"), sha(lock_manifest_path.read_bytes()), "receipt_manifest_sha256")
    for filename, expected in json.loads((charts_dir / "OUTPUT_SHA256.json").read_text()).items():
        equal(sha((charts_dir / filename).read_bytes()), expected, "output_file_sha256", file=filename)

    @functools.lru_cache(maxsize=None)
    def primary_jie(year):
        # Separate direct LunarYear ephemeris access; no builder helper imported.
        from lunar_python import Lunar, LunarYear
        events = []
        for name, jd in zip(Lunar.JIE_QI_IN_USE, LunarYear.fromYear(year).getJieQiJulianDays()):
            name = {"DA_XUE": "大雪", "XIAO_HAN": "小寒", "LI_CHUN": "立春", "JING_ZHE": "惊蛰"}.get(name, name)
            solar = Solar.fromJulianDay(jd)
            if name in JIE and solar.getYear() == year:
                stamp = solar.toYmdHms()
                events.append((name, stamp))
        events = sorted(set(events), key=lambda p: p[1])
        if len(events) != 12:
            raise ValueError(("primary_Jie_count", year, len(events)))
        return events

    @functools.lru_cache(maxsize=None)
    def secondary_jie_dates(year):
        found = set()
        for reference_year in (year - 1, year, year + 1):
            for event in sxtwl.getJieQiByYear(reference_year):
                if event.jqIndex % 2 != 1:
                    continue
                t = sxtwl.JD2DD(event.jd)
                when = dt.datetime(int(t.Y), int(t.M), int(t.D)) + dt.timedelta(hours=t.h, minutes=t.m, seconds=t.s)
                if when.year == year:
                    found.add((TERMS[event.jqIndex], when.date()))
        if len(found) != 12:
            raise ValueError(("secondary_Jie_count", year, len(found)))
        return found

    @functools.lru_cache(maxsize=None)
    def date_reference(date_text):
        date = dt.date.fromisoformat(date_text)
        # Independent standard-library Gregorian ordinal route, not the
        # builder's Fliegel/Van Flandern integer formula.
        jdn = date.toordinal() + 1721425
        day = STEMS[(jdn + 49) % 10] + BRANCHES[(jdn + 49) % 12]
        sx = sxtwl.fromSolar(date.year, date.month, date.day)
        to_gz = lambda v: STEMS[v.tg] + BRANCHES[v.dz]
        expected_near = []
        for year in (date.year - 1, date.year, date.year + 1):
            for name, stamp in primary_jie(year):
                term_date = dt.date.fromisoformat(stamp[:10])
                delta = (date - term_date).days
                if abs(delta) <= 1:
                    expected_near.append({"name": name, "reference_utc_plus_08": stamp,
                                          "date": stamp[:10], "DOB_minus_Jie_civil_days": delta})
        sx_near = any(abs((date - term_date).days) <= 1
                      for year in (date.year - 1, date.year, date.year + 1)
                      for _, term_date in secondary_jie_dates(year))
        return {"JDN_day": day, "sxtwl_day": to_gz(sx.getDayGZ()),
                "sxtwl_year": to_gz(sx.getYearGZ(False)), "sxtwl_month": to_gz(sx.getMonthGZ()),
                "near": expected_near, "secondary_near": sx_near,
                "boundary_day": any(e["date"] == date_text and e["reference_utc_plus_08"][11:] != "00:00:00"
                                    for e in expected_near)}

    year_month_compared = 0
    year_month_boundary_skipped = 0
    for pid in sorted(set(charts) & set(source)):
        row, original = charts[pid], source[pid]
        for field, value in original.items():
            equal(row.get(field), value, "V4_field_preserved", person_id=pid, field=field)
        date = dt.date.fromisoformat(original["analysis_DOB"])
        require(dt.date(1835, 1, 1) <= date <= dt.date(1985, 12, 31), "Gregorian_DOB_window", person_id=pid)
        require(original["hemisphere"] == "north" and not original["person_level_DOB_analysis_hold"], "hemisphere_and_hold_eligibility", person_id=pid)
        equal(row.get("assumptions_lock_commit"), args.lock_commit, "row_lock_commit", person_id=pid)
        equal(row.get("hour_pillar"), None, "hour_remains_unknown", person_id=pid)
        equal(row.get("birth_time_known"), False, "birth_time_remains_unknown", person_id=pid)
        equal(row.get("day_rollover"), "00:00_civil_sect2", "day_rollover_convention", person_id=pid)
        equal(row.get("computation_reference"), "civil_date_12:00:00_fixed_UTC+08:00_not_inferred_birth_time", "computation_reference", person_id=pid)
        equal(row.get("feature_transform_authorized"), True, "transform_authorized", person_id=pid)
        equal(row.get("hypothesis_inference_authorized_by_current_task"), False, "inference_not_authorized", person_id=pid)
        equal(row.get("hypothesis_inference_executed"), False, "inference_not_executed", person_id=pid)
        equal(row.get("V4_analysis_unblinding_ready_original"), original["analysis_unblinding_ready"], "original_unblinding_flag", person_id=pid)
        equal(row.get("included_strict"), pid in strict_ids, "strict_membership_flag", person_id=pid)
        for label, key in [("Nobel_full_roster", "expanded/Nobel_full_roster_matched_people.jsonl.gz"),
                           ("Nobel_legacy_cohort", "expanded/Nobel_frozen_candidate_cohort.jsonl.gz"),
                           ("Fields_parallel", "expanded/Fields_parallel_cohort.jsonl.gz"),
                           ("included_expanded_without_LOC", "sensitivity/expanded_without_LOC_quoted_metadata_people.jsonl.gz")]:
            equal(row.get(label), pid in group_sets[key], "derived_membership_flag", person_id=pid, field=label)
        reference = date_reference(date.isoformat())
        equal(row.get("day_pillar"), reference["JDN_day"], "all_person_JDN_day", person_id=pid)
        equal(row.get("day_pillar"), reference["sxtwl_day"], "all_person_sxtwl_day", person_id=pid)
        equal(row.get("near_jie_events"), reference["near"], "exact_primary_Jie_events", person_id=pid)
        equal(row.get("jie_boundary_plus_minus_one_civil_day"), bool(reference["near"]), "Jie_plus_minus_one_flag", person_id=pid)
        equal(row.get("jie_boundary_day"), reference["boundary_day"], "Jie_exact_day_flag", person_id=pid)
        # sxtwl's day-level year/month API differs at intraday boundaries.
        # Derive exclusions independently; do not trust the supplied flag alone.
        if not reference["near"] and not reference["secondary_near"]:
            equal(row.get("year_pillar"), reference["sxtwl_year"], "off_boundary_sxtwl_year", person_id=pid)
            equal(row.get("month_pillar"), reference["sxtwl_month"], "off_boundary_sxtwl_month", person_id=pid)
            year_month_compared += 1
        else:
            year_month_boundary_skipped += 1
        yp, mp, dp = (row.get(k, "") for k in ("year_pillar", "month_pillar", "day_pillar"))
        if any(len(p) != 2 or p[0] not in STEMS or p[1] not in BRANCHES for p in (yp, mp, dp)):
            require(False, "pillar_encoding", person_id=pid)
            continue
        equal(row.get("date_known_six_characters"), yp + mp + dp, "six_characters", person_id=pid)
        expected_stems = dict(zip(POSITIONS, (yp[0], QI[yp[1]], mp[0], QI[mp[1]], QI[dp[1]])))
        expected_gods = {position: TEN_GOD[dp[0]][stem] for position, stem in expected_stems.items()}
        expected_counts = {god: list(expected_gods.values()).count(god) for god in GODS}
        equal(row.get("five_position_stems"), expected_stems, "five_position_stems", person_id=pid)
        equal(row.get("five_position_ten_gods"), expected_gods, "literal_TenGod_table", person_id=pid)
        equal(row.get("ten_god_counts_five_positions"), expected_counts, "five_position_counts", person_id=pid)
        equal(sum(expected_counts.values()), 5, "five_position_count_sum", person_id=pid)
        expected_flags = {
            "guan_yin_narrow": "正官" in expected_gods.values() and "正印" in expected_gods.values(),
            "guan_yin_broad": bool({"正官", "七杀"} & set(expected_gods.values())) and bool({"正印", "偏印"} & set(expected_gods.values())),
            "shangguan_yin_narrow": "伤官" in expected_gods.values() and "正印" in expected_gods.values(),
            "shangguan_yin_broad": "伤官" in expected_gods.values() and bool({"正印", "偏印"} & set(expected_gods.values())),
            "day_master_water": dp[0] in {"壬", "癸"}, "day_master": dp[0],
            "day_master_element": {"甲": "木", "乙": "木", "丙": "火", "丁": "火", "戊": "土", "己": "土", "庚": "金", "辛": "金", "壬": "水", "癸": "水"}[dp[0]],
        }
        for field, expected in expected_flags.items():
            equal(row.get(field), expected, "fixed_indicator_definition", person_id=pid, field=field)

    for hold_name in ("person_DOB_or_calendar_holds", "expanded_source_support_unresolved_people"):
        forbidden = {p["person_id"] for p in holds[hold_name]}
        require(not (forbidden & set(charts)), "held_people_absent", hold=hold_name, unexpected_ids=sorted(forbidden & set(charts)))
    # Membership holds are source/path-level; do not exclude an otherwise eligible
    # person merely because another path is held. Exact V4 group checks enforce it.
    positive = read_rows((charts_dir / "group_memberships.jsonl.gz").read_bytes())
    exclusions = read_rows((charts_dir / "exclusion_group_references.jsonl.gz").read_bytes())
    expected_positive = {(key, pid) for key, ids in group_sets.items() if Path(key).name != "excluded_people.jsonl.gz" for pid in ids}
    actual_positive = [(r["population_path"], r["person_id"]) for r in positive]
    equal(set(actual_positive), expected_positive, "exact_positive_V4_group_memberships")
    equal(len(actual_positive), len(set(actual_positive)), "no_duplicate_positive_group_links")
    require(all(pid in charts for _, pid in actual_positive), "positive_links_have_generated_chart")
    expected_exclusions = {(key, pid) for key, ids in group_sets.items() if Path(key).name == "excluded_people.jsonl.gz" for pid in ids}
    actual_exclusions = [(r["population_path"], r["person_id"]) for r in exclusions]
    equal(set(actual_exclusions), expected_exclusions, "exact_V4_exclusion_references")
    equal(len(actual_exclusions), len(set(actual_exclusions)), "no_duplicate_exclusion_references")
    for row in exclusions:
        equal(row.get("role"), "exclusion_reference_only", "exclusion_reference_role", person_id=row["person_id"])
        equal(row.get("has_generated_chart"), row["person_id"] in charts, "exclusion_chart_presence_flag", person_id=row["person_id"])

    # CSV is a second delivery representation, not a source of truth.
    for filename, expected_ids in [("charts_unique_expanded.csv", set(source)), ("charts_unique_strict.csv", strict_ids)]:
        with (charts_dir / filename).open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            csv_rows = list(reader)
            headers = reader.fieldnames or []
        expected_headers = {"person_id", "display_name", "analysis_DOB", "included_strict", "included_expanded",
                            "academy_memberships", "Nobel_full_roster", "Nobel_legacy_cohort", "Fields_parallel",
                            "year_pillar", "month_pillar", "day_pillar", "hour_pillar", "date_known_six_characters",
                            "day_master", "day_master_element", "jie_boundary_day", "jie_boundary_plus_minus_one_civil_day",
                            "guan_yin_narrow", "guan_yin_broad", "shangguan_yin_narrow", "shangguan_yin_broad", "day_master_water"}
        expected_headers |= {prefix + position for prefix in ("stem_", "ten_god_") for position in POSITIONS}
        expected_headers |= {"count_" + god for god in GODS}
        equal(set(headers), expected_headers, "CSV_complete_schema", file=filename)
        equal(len(headers), len(set(headers)), "CSV_unique_column_names", file=filename)
        csv_map = {r["person_id"]: r for r in csv_rows}
        equal(len(csv_rows), len(csv_map), "CSV_unique_IDs", file=filename)
        equal(set(csv_map), expected_ids, "CSV_exact_ID_set", file=filename)
        for pid in sorted(set(csv_map) & set(charts)):
            row = charts[pid]
            flattened = {key: row.get(key) for key in headers}
            flattened.update({"academy_memberships": ";".join(row["qualified_academy_memberships"]), "hour_pillar": "未知"})
            flattened.update({"stem_" + k: v for k, v in row["five_position_stems"].items()})
            flattened.update({"ten_god_" + k: v for k, v in row["five_position_ten_gods"].items()})
            flattened.update({"count_" + k: v for k, v in row["ten_god_counts_five_positions"].items()})
            for field in headers:
                expected = "" if flattened.get(field) is None else str(flattened[field])
                equal(csv_map[pid].get(field), expected, "CSV_matches_audited_JSON", file=filename, person_id=pid, field=field)

    def json_safe(value):
        if isinstance(value, set):
            return sorted(value)
        raise TypeError(type(value).__name__)

    report = {
        "status": "PASS" if not mismatches else "FAIL", "auditor_imports_builder": False,
        "lock_commit": args.lock_commit, "V4_zip_sha256": sha(archive),
        "unique_expanded_charts": len(charts), "unique_strict_IDs": len(strict_ids),
        "all_person_JDN_day_checks": checked["all_person_JDN_day"],
        "all_person_sxtwl_day_checks": checked["all_person_sxtwl_day"],
        "sxtwl_year_month_off_boundary_person_checks": year_month_compared,
        "sxtwl_year_month_boundary_person_checks_skipped": year_month_boundary_skipped,
        "V4_population_counts": {key: len(ids) for key, ids in sorted(group_sets.items())},
        "V4_hold_reference_counts": {key: len(rows) for key, rows in holds.items()},
        "membership_holds_handled_as_paths_not_blanket_person_exclusion": True,
        "check_counts": dict(sorted(checked.items())), "mismatch_count": len(mismatches),
        "inference_executed": False, "cohort_feature_frequencies_computed": False,
        "limits": ["sxtwl and lunar_python share ShouXing ancestry; this is a separate implementation check, not independent astronomical theory.",
                   "sxtwl day-level year/month comparisons omit the union of primary and secondary Jie +/-1civilday dates.",
                   "No claim that noon is observed birth time; no hour pillar is inferred."]}
    if mismatches:
        report["mismatches"] = mismatches
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=json_safe) + "\n")
    print(json.dumps({key: report[key] for key in ("status", "unique_expanded_charts", "unique_strict_IDs", "mismatch_count", "inference_executed")}))
    return 0 if not mismatches else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-zip", required=True)
    parser.add_argument("--charts", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--lock-commit", required=True)
    args = parser.parse_args()
    try:
        return audit(args)
    except Exception as exc:
        # Fail closed, including missing pins/dependencies or a malformed chart.
        result = {"status": "ERROR", "error_type": type(exc).__name__, "error": str(exc),
                  "lock_commit": args.lock_commit, "inference_executed": False,
                  "cohort_feature_frequencies_computed": False}
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps(result), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
