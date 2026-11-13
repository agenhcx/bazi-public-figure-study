#!/usr/bin/env python3
"""Build the uniform Gregorian calendar cache without loading study records.

Execution requires this code to be committed at HEAD and an existing execution
note. The frozen date-only builder supplies every calendar/encoding function.
This program neither reads country selections nor computes group statistics.
"""

import argparse
import calendar
import datetime as dt
import hashlib
import importlib.metadata
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile


STUDY_ROOT = Path(__file__).resolve().parents[2]
REVEAL_ROOT = STUDY_ROOT / "reveal_v1"
START_YEAR, END_YEAR = 1835, 1985
EXPECTED_DATE_ROWS = 55152
FEATURE_NAMES = (
    "PI_count", "SG_count", "GY_narrow", "SGY_narrow", "water_DM", "DM_index"
)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def code_lock():
    """Refuse to compute a cache from an uncommitted builder."""
    source = Path(__file__).resolve()
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], cwd=STUDY_ROOT,
        check=True, capture_output=True, text=True,
    )
    repository = Path(result.stdout.strip()).resolve()
    relative = source.relative_to(repository).as_posix()
    committed = subprocess.run(
        ["git", "show", "HEAD:" + relative], cwd=repository,
        check=True, capture_output=True,
    ).stdout
    current = source.read_bytes()
    if committed != current:
        raise RuntimeError("Calendar builder must match its committed HEAD version before execution")
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repository,
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    return {"git_commit": commit, "code_path": relative,
            "code_sha256": sha(current), "code_matches_committed_HEAD": True}


def load_frozen_builder(dependency_dir):
    """Verify frozen files and the primary calendar package before importing it."""
    manifest_path = STUDY_ROOT / "LOCKED_FILES.sha256.json"
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    for relative, expected in manifest.items():
        actual = sha((STUDY_ROOT / relative).read_bytes())
        if actual != expected:
            raise RuntimeError("Frozen study file changed: " + relative)

    dependency_dir = dependency_dir.resolve()
    if not dependency_dir.is_dir():
        raise FileNotFoundError("Pinned dependency directory is missing: " + str(dependency_dir))
    sys.path.insert(0, str(dependency_dir))
    sys.dont_write_bytecode = True
    import lunar_python

    config = json.loads((STUDY_ROOT / "ASSUMPTIONS_LOCK_V1.json").read_text())
    if importlib.metadata.version("lunar_python") != "1.4.8":
        raise RuntimeError("The primary calendar package must be lunar-python 1.4.8")
    if config["calendar"]["package_version"] != "1.4.8":
        raise RuntimeError("Frozen package-version assumption differs from 1.4.8")
    package_dir = Path(lunar_python.__file__).resolve().parent
    if not package_dir.is_relative_to(dependency_dir):
        raise RuntimeError("Imported lunar_python is outside the pinned dependency directory")
    dependency_qa = json.loads((STUDY_ROOT / "qa/CALENDAR_PRELOCK_QA.json").read_text())
    module_manifest = dependency_qa["dependencies"]["lunar_python"]["module_manifest"]
    package_parent = package_dir.parent
    expected_python_paths = set()
    for entry in module_manifest["files"]:
        relative = entry["path"]
        data = (package_parent / relative).read_bytes()
        if len(data) != entry["bytes"] or sha(data) != entry["sha256"]:
            raise RuntimeError("Pinned calendar source changed: " + relative)
        if relative.endswith(".py"):
            expected_python_paths.add(relative)
    actual_python_paths = {
        path.relative_to(package_parent).as_posix() for path in package_dir.rglob("*.py")
    }
    if actual_python_paths != expected_python_paths:
        raise RuntimeError("Primary calendar package source-file set differs from its pinned manifest")

    builder_path = STUDY_ROOT / "scripts/build_charts.py"
    spec = importlib.util.spec_from_file_location("frozen_scientist_calendar_builder", builder_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load the frozen calendar builder")
    frozen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(frozen)
    provenance = {
        "frozen_files_manifest_sha256": sha(manifest_bytes),
        "frozen_files_verified": len(manifest),
        "frozen_builder_sha256": sha(builder_path.read_bytes()),
        "calendar_package": "lunar_python",
        "calendar_package_version": "1.4.8",
        "calendar_package_directory": str(package_dir),
        "pinned_module_tree_sha256": module_manifest["module_tree_sha256"],
        "calendar_module_files_verified": len(module_manifest["files"]),
        "calendar_module_source_file_set_matches": True,
    }
    return frozen, provenance


def calendar_boundary_masks(frozen, first_date, last_date):
    """Retain the frozen flags while avoiding two extra Solar calls every day."""
    events = []
    near_dates = set()
    event_dates = set()
    for year in range(START_YEAR - 1, END_YEAR + 2):
        yearly = frozen.jie_events(year)
        if len(yearly) != 12:
            raise AssertionError(("Jie event count", year, len(yearly)))
        for event in yearly:
            events.append(dict(event))
            date = dt.date.fromisoformat(event["date"])
            if first_date <= date <= last_date:
                event_dates.add(date)
            for delta in (-1, 0, 1):
                candidate = date + dt.timedelta(days=delta)
                if first_date <= candidate <= last_date:
                    near_dates.add(candidate)

    # Year/month pillars change at the 12 Jie only. On these candidate civil
    # dates, use the exact frozen 00:00 versus 23:59:59 comparison, preserving
    # even a hypothetical transition exactly at midnight rather than simply
    # relabelling every term's civil date as a positive boundary flag.
    exact_boundary_dates = set()
    for date in sorted(event_dates):
        early = frozen.pillars_at(date, 0)
        late = frozen.pillars_at(date, 23, 59, 59)
        if early[:2] != late[:2]:
            exact_boundary_dates.add(date)
    events.sort(key=lambda event: (event["reference_utc_plus_08"], event["name"]))
    return events, near_dates, exact_boundary_dates, len(event_dates)


def deterministic_npz_bytes(np, arrays):
    """Write standard NPZ arrays with fixed ZIP metadata and no object pickles."""
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, array in arrays.items():
            encoded = io.BytesIO()
            np.lib.format.write_array(encoded, np.asarray(array), allow_pickle=False)
            info = zipfile.ZipInfo(name + ".npy", date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o600 << 16
            archive.writestr(info, encoded.getvalue(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return output.getvalue()


def build(args):
    started = time.perf_counter()
    output_dir = args.output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError("Output directory must be new: " + str(output_dir))
    if output_dir.is_relative_to(STUDY_ROOT) and not output_dir.is_relative_to(REVEAL_ROOT):
        raise ValueError("Outputs inside the study must stay under reveal_v1, outside frozen folders")
    execution_note = args.execution_note.resolve()
    if not execution_note.is_file():
        raise FileNotFoundError("An existing execution note is required before calendar generation")
    lock_provenance = code_lock()
    frozen, calendar_provenance = load_frozen_builder(args.dependency_dir)
    import numpy as np

    first_date, last_date = dt.date(START_YEAR, 1, 1), dt.date(END_YEAR, 12, 31)
    expected_rows = (last_date - first_date).days + 1
    if expected_rows != EXPECTED_DATE_ROWS:
        raise AssertionError(("Gregorian date range", expected_rows))
    events, near_dates, boundary_dates, boundary_candidate_days = calendar_boundary_masks(
        frozen, first_date, last_date
    )
    n = expected_rows
    dates = np.empty(n, dtype="U10")
    years, months, days = np.empty(n, dtype="int16"), np.empty(n, dtype="uint8"), np.empty(n, dtype="uint8")
    features = np.empty((n, len(FEATURE_NAMES)), dtype="int8")
    counts = np.empty((n, len(frozen.TEN_GODS)), dtype="int8")
    gy_broad, sgy_broad = np.empty(n, dtype=bool), np.empty(n, dtype=bool)
    near_flags, boundary_flags = np.empty(n, dtype=bool), np.empty(n, dtype=bool)
    year_pillars, month_pillars, day_pillars = (np.empty(n, dtype="U2") for _ in range(3))
    index = 0
    yearly_date_counts = {}

    for year in range(START_YEAR, END_YEAR + 1):
        year_start = dt.date(year, 1, 1)
        year_size = 366 if calendar.isleap(year) else 365
        yearly_date_counts[str(year)] = year_size
        for offset in range(year_size):
            date = year_start + dt.timedelta(days=offset)
            # This is the frozen Solar/EightChar path, fixed noon and sect2.
            # Never call build_charts.build(), chart(), or a study-group loader.
            yp, mp, dp = frozen.pillars_at(date, 12, 0, 0)
            if dp != frozen.day_jdn(date):
                raise AssertionError(("Gregorian JDN day mismatch", date.isoformat()))
            stems = [yp[0], frozen.MAIN_QI[yp[1]], mp[0], frozen.MAIN_QI[mp[1]], frozen.MAIN_QI[dp[1]]]
            gods = [frozen.ten_god(dp[0], stem) for stem in stems]
            counter = {god: gods.count(god) for god in frozen.TEN_GODS}
            pi, sg = counter["偏印"], counter["伤官"]
            gy = counter["正官"] > 0 and counter["正印"] > 0
            sgy = counter["伤官"] > 0 and counter["正印"] > 0
            water = dp[0] in "壬癸"
            dm_index = frozen.STEMS.index(dp[0])
            dates[index] = date.isoformat()
            years[index], months[index], days[index] = date.year, date.month, date.day
            features[index] = (pi, sg, gy, sgy, water, dm_index)
            counts[index] = [counter[god] for god in frozen.TEN_GODS]
            gy_broad[index] = counter["正官"] + counter["七杀"] > 0 and counter["正印"] + counter["偏印"] > 0
            sgy_broad[index] = counter["伤官"] > 0 and counter["正印"] + counter["偏印"] > 0
            near_flags[index], boundary_flags[index] = date in near_dates, date in boundary_dates
            year_pillars[index], month_pillars[index], day_pillars[index] = yp, mp, dp
            index += 1
        completed_years = year - START_YEAR + 1
        if args.progress_every_years and (completed_years % args.progress_every_years == 0 or year == END_YEAR):
            print(json.dumps({"calendar_year_completed": year, "valid_dates_generated": index}), file=sys.stderr, flush=True)

    if index != n or not np.all(counts.sum(axis=1) == 5):
        raise AssertionError("Calendar coverage or five-position count invariant failed")
    if not np.all((features[:, :2] >= 0) & (features[:, :2] <= 5)):
        raise AssertionError("PI/SG count outside five-position range")
    if not np.all((features[:, 5] >= 0) & (features[:, 5] < 10)):
        raise AssertionError("Day-master index outside frozen ten-stem order")
    if not np.array_equal(features[:, 4].astype(bool), features[:, 5] >= 8):
        raise AssertionError("Water/day-master mapping mismatch")
    arrays = {
        "dates": dates, "year": years, "month": months, "day": days,
        "features": features, "feature_names": np.asarray(FEATURE_NAMES, dtype="U12"),
        **{name: features[:, column] for column, name in enumerate(FEATURE_NAMES)},
        "GY_broad": gy_broad, "SGY_broad": sgy_broad,
        "ten_god_counts": counts, "ten_god_names": np.asarray(frozen.TEN_GODS, dtype="U2"),
        "dm_stems": np.asarray(list(frozen.STEMS), dtype="U1"),
        "jie_boundary_day": boundary_flags,
        "jie_boundary_plus_minus_one_civil_day": near_flags,
        "year_pillar": year_pillars, "month_pillar": month_pillars, "day_pillar": day_pillars,
        "jie_event_name": np.asarray([event["name"] for event in events], dtype="U2"),
        "jie_event_date": np.asarray([event["date"] for event in events], dtype="U10"),
        "jie_event_time_fixed_utc08": np.asarray([event["reference_utc_plus_08"] for event in events], dtype="U19"),
    }
    pool_bytes = deterministic_npz_bytes(np, arrays)
    qa = {
        "schema": "uniform_gregorian_calendar_pool_v1", "status": "PASS",
        "study_input_loaded": False, "country_groups_loaded": [],
        "study_group_feature_aggregates_computed": False, "hypothesis_tests_run": False,
        "calendar_feature_frequency_or_mean_summaries_computed": False,
        "date_range": [first_date.isoformat(), last_date.isoformat()],
        "valid_gregorian_date_rows": n, "year_count": END_YEAR - START_YEAR + 1,
        "yearly_valid_date_counts": yearly_date_counts,
        "date_sequence_sha256": sha(("\n".join(dates.tolist()) + "\n").encode("ascii")),
        "date_order": "complete Gregorian civil dates, ascending, one row per valid date",
        "within_year_date_probability": "uniform_valid_days_within_year",
        "reference_time": "12:00:00_fixed_UTC+08:00_not_inferred_birth_time",
        "year_rollover": "exact_LiChun", "month_rollover": "12_exact_Jie",
        "EightChar_sect": 2, "day_rollover": "00:00_civil",
        "day_JDN_checks_passed": n, "all_ten_god_row_counts_sum_to_five": True,
        "feature_names": list(FEATURE_NAMES), "ten_god_names": list(frozen.TEN_GODS),
        "feature_kinds": {"PI_count": "five_position_count", "SG_count": "five_position_count",
                          "GY_narrow": "binary", "SGY_narrow": "binary", "water_DM": "binary",
                          "DM_index": "categorical_index_in_dm_stems_not_a_scalar_endpoint"},
        "day_master_index_stems": list(frozen.STEMS),
        "boundary_flag_method": "Frozen00:00/23:59:59 year/month comparison on every candidate12Jie civil date; false on other dates",
        "near_Jie_flag_method": "Any frozen12Jie in adjacent/current calendar years within inclusive±1civil day",
        "boundary_candidate_civil_dates_checked": boundary_candidate_days,
        "boundary_time_pillar_calls": 2 * boundary_candidate_days,
        "fixed_noon_pillar_calls": n,
        "adjacent_year_Jie_tables": [START_YEAR - 1, END_YEAR + 1],
        "execution_note": str(execution_note), "execution_note_sha256": sha(execution_note.read_bytes()),
        "numpy_version": np.__version__, "elapsed_seconds": time.perf_counter() - started,
        "npz_sha256": sha(pool_bytes),
        "array_schema": {name: {"shape": list(array.shape), "dtype": str(array.dtype)} for name, array in arrays.items()},
        **lock_provenance, **calendar_provenance,
    }
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".calendar-pool-", dir=output_dir.parent))
    try:
        (staging / "calendar_pool.npz").write_bytes(pool_bytes)
        (staging / "calendar_QA.json").write_bytes(json_bytes(qa))
        staging.rename(output_dir)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    print(json.dumps({"status": "PASS", "valid_dates": n, "output_dir": str(output_dir), "npz_sha256": qa["npz_sha256"]}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--execution-note", required=True, type=Path,
                        help="Existing execution note; its exact bytes are hash-recorded without reading any study data")
    parser.add_argument("--dependency-dir", type=Path, default=Path("/tmp/scientist_calendar_audit_deps"))
    parser.add_argument("--progress-every-years", type=int, default=10)
    args = parser.parse_args()
    if args.progress_every_years < 0:
        parser.error("--progress-every-years must be nonnegative")
    build(args)


if __name__ == "__main__":
    main()
