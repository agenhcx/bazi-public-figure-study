#!/usr/bin/env python3
"""Derive a uniform hidden-stem calendar pool from already frozen pillars.

No astronomy, scientist records, country selections or outcome statistics are
loaded. The encoder, this builder and the supplied versioned execution note
must match committed HEAD bytes before the calendar cache can be read.
"""

import argparse
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile

import numpy as np


SCRIPT_DIR = Path(__file__).resolve().parent
STUDY_ROOT = SCRIPT_DIR.parents[1]
SUPPLEMENT_ROOT = SCRIPT_DIR.parent
EXPECTED_ROWS = 55152


def sha(data):
    return hashlib.sha256(data).hexdigest()


def code_lock(execution_note):
    repository = Path(subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], cwd=STUDY_ROOT,
        check=True, capture_output=True, text=True,
    ).stdout.strip()).resolve()
    pins = {}
    for source in (Path(__file__).resolve(), SCRIPT_DIR / "hidden_features.py", execution_note):
        relative = source.relative_to(repository).as_posix()
        committed = subprocess.run(
            ["git", "show", "HEAD:" + relative], cwd=repository,
            check=True, capture_output=True,
        ).stdout
        current = source.read_bytes()
        if current != committed:
            raise RuntimeError("Hidden-supplement code/note must match committed HEAD: " + relative)
        pins[relative] = sha(current)
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repository,
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    return {"git_commit": commit, "committed_code_and_note_sha256": pins,
            "all_code_and_versioned_note_match_HEAD": True}


def npz_bytes(arrays):
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
    note = args.execution_note.resolve()
    if not note.is_file():
        raise FileNotFoundError("The versioned hidden-supplement execution note is required")
    lock = code_lock(note)
    source_path, output_dir = args.calendar_pool.resolve(), args.output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError("Output directory must be new: " + str(output_dir))
    if output_dir.is_relative_to(STUDY_ROOT) and not output_dir.is_relative_to(SUPPLEMENT_ROOT):
        raise ValueError("Study outputs must stay inside hidden_stem_v1")
    source_bytes = source_path.read_bytes()
    if sha(source_bytes) != args.expected_calendar_sha256:
        raise RuntimeError("The original calendar NPZ differs from its locked SHA256")
    source_qa_path = args.calendar_qa or source_path.with_name("calendar_QA.json")
    source_qa_bytes = source_qa_path.read_bytes()
    source_qa = json.loads(source_qa_bytes)
    if source_qa["npz_sha256"] != sha(source_bytes):
        raise RuntimeError("Original calendar QA is not bound to this NPZ")

    sys.path.insert(0, str(SCRIPT_DIR))
    sys.dont_write_bytecode = True
    import hidden_features as encoder

    copied_names = ("dates", "year", "month", "jie_boundary_day", "jie_boundary_plus_minus_one_civil_day",
                    "year_pillar", "month_pillar", "day_pillar")
    with np.load(io.BytesIO(source_bytes), allow_pickle=False) as source:
        copied = {name: source[name].copy() for name in copied_names}
        primary = source["features"].copy()
        primary_names = source["feature_names"].tolist()
    dates = copied["dates"].astype("U10")
    if len(dates) != EXPECTED_ROWS or dates[0] != "1835-01-01" or dates[-1] != "1985-12-31":
        raise AssertionError("The source must be the complete uniform1835–1985 Gregorian pool")
    ordinals = dates.astype("datetime64[D]").astype("int64")
    if not np.all(np.diff(ordinals) == 1):
        raise AssertionError("Calendar dates are not unique, complete and ascending")
    if any(array.shape != (EXPECTED_ROWS,) for array in copied.values()):
        raise AssertionError("An inherited date/pillar/flag vector has the wrong shape")
    encoded = encoder.encode_many_pillars(copied["year_pillar"], copied["month_pillar"], copied["day_pillar"])
    primary_columns = [primary_names.index("PI_count"), primary_names.index("SG_count")]
    expected_main = primary[:, primary_columns].astype("int16") * encoder.COUNT_SCALE
    if not np.array_equal(encoded[:, 0, :, 0], expected_main):
        raise AssertionError("M0 hidden-pool counts do not reproduce the frozen main-qi calendar")
    if not np.array_equal(encoded[:, 0, :, 1], (expected_main > 0).astype("int16") * encoder.PRESENCE_SCALE):
        raise AssertionError("M0 person-presence indicator mismatch")

    arrays = {
        "features": encoded,
        "count_scaled72": encoded[..., 0],
        "presence_scaled12": encoded[..., 1],
        "models": np.asarray(encoder.MODEL_NAMES, dtype="U16"),
        "traits": np.asarray(encoder.TRAIT_NAMES, dtype="U2"),
        "metrics": np.asarray(encoder.METRIC_NAMES, dtype="U20"),
        "scales": np.asarray([encoder.COUNT_SCALE, encoder.PRESENCE_SCALE], dtype="int16"),
        "position_denominators": np.asarray(encoder.POSITION_DENOMINATORS, dtype="int8"),
        **copied,
    }
    encoded_bytes = npz_bytes(arrays)
    qa = {
        "schema": "hidden_stem_calendar_pool_v1", "status": "PASS",
        "source_calendar_npz": str(source_path), "source_calendar_npz_sha256": sha(source_bytes),
        "source_calendar_QA_sha256": sha(source_qa_bytes),
        "hidden_pool_npz_sha256": sha(encoded_bytes), "valid_date_rows": EXPECTED_ROWS,
        "features_shape": list(encoded.shape), "models": list(encoder.MODEL_NAMES),
        "traits": list(encoder.TRAIT_NAMES), "metrics": list(encoder.METRIC_NAMES),
        "count_scale": encoder.COUNT_SCALE, "presence_scale": encoder.PRESENCE_SCALE,
        "position_denominators": list(encoder.POSITION_DENOMINATORS),
        "max_count_scaled72": list(encoder.MAX_COUNT_SCALED72),
        "hidden_stem_order": {branch: list(stems) for branch, stems in encoder.HIDDEN_STEMS.items()},
        "M0_all_calendar_rows_match_original_PI_SG": True,
        "M0_all_calendar_presence_indicators_checked": True,
        "calendar_dates_pillars_year_month_and_Jie_flags_copied_unchanged": True,
        "count_share_decode": "count_scaled72/(72*position_denominator)",
        "person_presence_decode": "presence_scaled12/12; hourly values average twelve per-hour indicators",
        "hour_distribution": "uniform_over12branches_using_actual_reference_DayStem_FiveRat_rule",
        "reference_DayStem_exposure_exclusion": "positional_only; same-character Y/M/H stems stay visible",
        "no_exposed_hidden_stem": "fallback_main_qi",
        "astronomy_calls": 0, "scientist_or_country_inputs_loaded": False,
        "study_group_feature_aggregates_computed": False, "hypothesis_tests_run": False,
        "across_date_hidden_feature_frequency_summaries_computed": False,
        "execution_note": str(note), "execution_note_sha256": sha(note.read_bytes()),
        "numpy_version": np.__version__, "elapsed_seconds": time.perf_counter() - started,
        "array_schema": {name: {"shape": list(array.shape), "dtype": str(array.dtype)} for name, array in arrays.items()},
        **lock,
    }
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".hidden-pool-", dir=output_dir.parent))
    try:
        (staging / "hidden_pool.npz").write_bytes(encoded_bytes)
        (staging / "hidden_pool_QA.json").write_text(json.dumps(qa, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
        staging.rename(output_dir)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    print(json.dumps({"status": "PASS", "valid_dates": EXPECTED_ROWS, "output_dir": str(output_dir),
                      "hidden_pool_npz_sha256": qa["hidden_pool_npz_sha256"]}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--calendar-pool", required=True, type=Path)
    parser.add_argument("--expected-calendar-sha256", required=True)
    parser.add_argument("--calendar-qa", type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--execution-note", required=True, type=Path)
    args = parser.parse_args()
    args.expected_calendar_sha256 = args.expected_calendar_sha256.lower()
    if len(args.expected_calendar_sha256) != 64 or any(character not in "0123456789abcdef" for character in args.expected_calendar_sha256):
        parser.error("--expected-calendar-sha256 must be64 hexadecimal characters")
    build(args)


if __name__ == "__main__":
    main()
