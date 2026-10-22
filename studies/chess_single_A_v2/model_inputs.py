#!/usr/bin/env python3
"""Prepare and verify the raw-symbol/date inputs; never fit or score a model.

The astronomical conversion deliberately repeats the historical sxtwl calls.
It uses Gregorian dates, default LiChun year boundaries and solar-term months,
without a birth hour or a birthplace/time-zone adjustment. It does not produce
Ten-God, Five-Phase, hidden-stem, strength or combination features.
"""
from __future__ import annotations

import argparse
import calendar
import csv
from datetime import date, datetime, timezone
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import re
import subprocess

import numpy as np
import pandas as pd

STEMS = tuple("甲乙丙丁戊己庚辛壬癸")
BRANCHES = tuple("子丑寅卯辰巳午未申酉戌亥")
RAW_COLUMNS = ("year_stem", "year_branch", "month_stem", "month_branch", "day_stem", "day_branch")
PILLAR_COLUMNS = ("year_pillar", "month_pillar", "day_pillar")
OUTPUT_COLUMNS = ("canonical_id", "snapshot", "exact_dob_frozen", "rating") + RAW_COLUMNS + PILLAR_COLUMNS
COMPLETE = "model_inputs_prepared_no_models_fitted"
SXTWL_VERSION = "2.0.7"
DATA_REL = Path("studies/chess_single_A_v2/data")
CONFIG_REL = Path("studies/chess_single_A_v2/config.json")
ROLE_SOURCES = {
    "development": (DATA_REL / "cohort_2013_M.csv", 1000, "2013-01", "2013_M"),
    "primary_new": (DATA_REL / "cohort_2023_M_NEW_TARGET.csv", 500, "2023-01", "2023_M_NEW_TARGET"),
    "supplementary_full": (DATA_REL / "cohort_2023_M_FULL.csv", 1001, "2023-01", "2023_M_FULL"),
    "legacy_full": (Path("chess_2023_reveal_v1/bazi_2023_M_FULL.csv"), 501, "2023-01", None),
}
REFERENCE_PATHS = (
    "chess_first_reveal_v1/bazi_2013_M.csv",
    "chess_2023_reveal_v1/bazi_2023_M_FULL.csv",
    "chess_2023_reveal_v1/bazi_2023_M_NEW_TARGET.csv",
)
UPSTREAM_REFERENCES = {
    "python_documentation": "https://github.com/yuangu/sxtwl_cpp/blob/master/python/README.md",
    "example": "https://github.com/yuangu/sxtwl_cpp/blob/master/example/main.py",
    "implementation": "https://github.com/yuangu/sxtwl_cpp/blob/master/src/day.cpp",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json_hash(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def _write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    temp.replace(path)


def _safe_path(root: Path, relative: str | Path) -> Path:
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("Input path escapes the repository")
    return path


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or len(reader.fieldnames) != len(set(reader.fieldnames)):
            raise ValueError(f"Invalid CSV header: {path.name}")
        rows = list(reader)
    if any(None in row or any(value is None for value in row.values()) for row in rows):
        raise ValueError(f"Malformed CSV: {path.name}")
    return rows


def canonical_id(row: dict) -> str:
    raw = str(row.get("canonical_id", "")).strip()
    if not raw:
        raw = str(row.get("identity_bridge_modern_fide_id", "")).strip()
    if not raw or raw.lower() in {"nan", "none"}:
        raw = str(row.get("fide_id", "")).strip()
    if not re.fullmatch(r"[0-9]+", raw) or int(raw) < 1:
        raise ValueError(f"Invalid canonical ID: {raw!r}")
    return str(int(raw))


def _snapshot(value: str) -> date:
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}", str(value)):
        raise ValueError(f"Invalid snapshot month: {value!r}")
    parsed = date.fromisoformat(str(value) + "-01")
    if parsed.strftime("%Y-%m") != value:
        raise ValueError("Noncanonical snapshot month")
    return parsed


def _dob(value: str) -> date:
    parsed = date.fromisoformat(str(value))
    if parsed.isoformat() != value:
        raise ValueError("DOB must be canonical YYYY-MM-DD")
    return parsed


def _validate_symbols(row: dict) -> None:
    for i, name in enumerate(RAW_COLUMNS):
        vocab = STEMS if i % 2 == 0 else BRANCHES
        if row.get(name) not in vocab:
            raise ValueError(f"Invalid or missing symbol in {name}")
    for i, name in enumerate(PILLAR_COLUMNS):
        pillar = str(row.get(name, ""))
        pair = row[RAW_COLUMNS[2 * i]] + row[RAW_COLUMNS[2 * i + 1]]
        if pillar != pair:
            raise ValueError(f"Pillar/position disagreement in {name}")
        if STEMS.index(pillar[0]) % 2 != BRANCHES.index(pillar[1]) % 2:
            raise ValueError(f"Impossible stem/branch parity in {name}")


def feature_spec(config: dict) -> dict:
    spec = config.get("representations", {})
    raw = spec.get("raw_A", {})
    if (raw.get("inputs") != list(RAW_COLUMNS)
            or raw.get("stem_vocabulary") != list(STEMS)
            or raw.get("branch_vocabulary") != list(BRANCHES)):
        raise ValueError("Raw feature specification differs from the fixed six-position vocabularies")
    date_spec = spec.get("date_control", {})
    if date_spec.get("inputs") != ["age", "age_squared", "age_cubed", "birth_season_sin1",
                                  "birth_season_cos1", "birth_season_sin2", "birth_season_cos2"]:
        raise ValueError("Date-control column specification differs from the fixed seven features")
    if date_spec.get("harmonics") != [1, 2]:
        raise ValueError("Date-control harmonics must be exactly [1,2]")
    return spec


def make_raw_matrix(frame: pd.DataFrame, config: dict) -> np.ndarray:
    """Stateless position-specific fixed-vocabulary one-hot encoding."""
    feature_spec(config)
    matrix = np.zeros((len(frame), 66), dtype=np.float64)
    offset = 0
    for position, name in enumerate(RAW_COLUMNS):
        vocab = STEMS if position % 2 == 0 else BRANCHES
        lookup = {symbol: index for index, symbol in enumerate(vocab)}
        if name not in frame:
            raise ValueError(f"Missing raw feature column {name}")
        values = frame[name].tolist()
        if any(value not in lookup for value in values):
            raise ValueError(f"Unknown or missing symbol in {name}")
        for row, value in enumerate(values):
            matrix[row, offset + lookup[value]] = 1.0
        offset += len(vocab)
    return matrix


def make_date_matrix(frame: pd.DataFrame, config: dict) -> np.ndarray:
    """Seven unscaled Gregorian age/annual-season variables, without fitting."""
    feature_spec(config)
    rows = []
    for row in frame.to_dict("records"):
        dob, snapshot = _dob(str(row["exact_dob_frozen"])), _snapshot(str(row["snapshot"]))
        if dob > snapshot:
            raise ValueError("DOB after snapshot")
        age = (snapshot - dob).days / 365.2425
        phase = 2 * math.pi * (dob.timetuple().tm_yday - 1) / (366 if calendar.isleap(dob.year) else 365)
        rows.append((age, age * age, age * age * age, math.sin(phase), math.cos(phase),
                     math.sin(2 * phase), math.cos(2 * phase)))
    return np.asarray(rows, dtype=np.float64).reshape(len(frame), 7)


def _load_sxtwl():
    import sxtwl  # Optional until feature generation; encoders/loaders need no astronomy package.
    actual = importlib.metadata.version("sxtwl")
    if actual != SXTWL_VERSION:
        raise ValueError(f"Expected sxtwl {SXTWL_VERSION}, found {actual}")
    return sxtwl


def generate_pillars(dob: str, backend=None) -> dict:
    backend = _load_sxtwl() if backend is None else backend
    parsed = _dob(dob)
    day = backend.fromSolar(parsed.year, parsed.month, parsed.day)
    pairs = (day.getYearGZ(), day.getMonthGZ(), day.getDayGZ())
    row = {}
    for position, gz in enumerate(pairs):
        stem, branch = STEMS[int(gz.tg)], BRANCHES[int(gz.dz)]
        row[RAW_COLUMNS[2 * position]] = stem
        row[RAW_COLUMNS[2 * position + 1]] = branch
        row[PILLAR_COLUMNS[position]] = stem + branch
    _validate_symbols(row)
    return row


def _source_record(row: dict, expected_snapshot: str) -> dict:
    fid = canonical_id(row)
    snapshot = str(row.get("snapshot", ""))
    if snapshot != expected_snapshot:
        raise ValueError(f"Unexpected snapshot for ID {fid}")
    dob = str(row.get("exact_dob_frozen", ""))
    if _dob(dob) > _snapshot(snapshot):
        raise ValueError(f"DOB after snapshot for ID {fid}")
    rating = str(row.get("rating", ""))
    if not re.fullmatch(r"[0-9]+", rating) or not 0 < int(rating) <= 3500:
        raise ValueError(f"Invalid standard Elo for ID {fid}")
    return {"canonical_id": fid, "snapshot": snapshot, "exact_dob_frozen": dob, "rating": int(rating)}


def compare_legacy(generated: dict[str, list[dict]], reference_rows: list[dict], reference_name: str) -> dict:
    """Stop on any reused person's DOB/pillars disagreeing with frozen inputs."""
    references = {}
    for row in reference_rows:
        fid = canonical_id(row)
        if fid in references:
            raise ValueError(f"Duplicate canonical ID in legacy reference {reference_name}")
        references[fid] = row
    comparisons = {}
    for role, rows in generated.items():
        count = 0
        for row in rows:
            ref = references.get(row["canonical_id"])
            if ref is None:
                continue
            count += 1
            if row["exact_dob_frozen"] != ref.get("exact_dob_frozen"):
                raise ValueError(f"Legacy DOB mismatch: {reference_name}/{row['canonical_id']}/{role}")
            for pillar in PILLAR_COLUMNS:
                if row[pillar] != ref.get(pillar):
                    raise ValueError(f"Legacy pillar mismatch: {reference_name}/{row['canonical_id']}/{pillar}/{role}")
            for column in RAW_COLUMNS:
                if column in ref and ref[column] != row[column]:
                    raise ValueError(f"Legacy explicit-position mismatch: {reference_name}/{column}")
            if row["snapshot"] == ref.get("snapshot") and row["rating"] != int(ref["rating"]):
                raise ValueError(f"Legacy snapshot rating mismatch: {reference_name}/{row['canonical_id']}")
        comparisons[role] = count
    return {"reference": reference_name, "reference_n": len(references), "matching_person_comparisons": comparisons}


def _executing_commit(root: Path) -> str:
    if os.environ.get("GITHUB_SHA", "").strip():
        return os.environ["GITHUB_SHA"].strip()
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else "local_uncommitted"


def prepare_inputs(repo_root: Path, *, backend=None) -> dict:
    root = Path(repo_root).resolve()
    data = root / DATA_REL
    data.mkdir(parents=True, exist_ok=True)
    audit_path, manifest_path = data / "feature_audit.json", data / "data_manifest.json"
    _write_json(audit_path, {"status": "feature_preparation_incomplete_no_models_fitted"})
    _write_json(manifest_path, {"status": "feature_preparation_incomplete_no_models_fitted"})
    for role in ROLE_SOURCES:
        (data / f"model_inputs_{role}.csv").unlink(missing_ok=True)
    config = _read_json(root / CONFIG_REL)
    spec = feature_spec(config)
    acquisition = _read_json(data / "manifest.json")
    summary = _read_json(data / "summary.json")
    independent = _read_json(data / "independent_audit.json")
    subsets = _read_json(data / "subset_manifest.json")
    if (acquisition.get("status") != "acquisition_complete_no_models_fitted"
            or summary.get("status") != "acquisition_complete_no_models_fitted"
            or independent.get("status") != "passed"
            or subsets.get("status") != "subsets_fixed_no_models_fitted"):
        raise ValueError("Acquisition, independent audit and training subsets must be complete")
    if (independent.get("manifest_sha256") != sha256(data / "manifest.json")
            or independent.get("summary_sha256") != sha256(data / "summary.json")):
        raise ValueError("Independent audit fingerprints no longer match acquisition")
    if (subsets.get("source_acquisition_manifest_sha256") != sha256(data / "manifest.json")
            or subsets.get("source_acquisition_summary_sha256") != sha256(data / "summary.json")):
        raise ValueError("Subset source fingerprints no longer match acquisition")
    if sha256(root / subsets["output"]["path"]) != subsets["output"]["sha256"]:
        raise ValueError("Training subset CSV fingerprint mismatch")
    output_hashes = {item["file"]: item["sha256"] for item in acquisition["outputs"]}
    backend = _load_sxtwl() if backend is None else backend
    generated, role_info = {}, {}
    cache = {}
    for role, (source_rel, count, snapshot, acquisition_role) in ROLE_SOURCES.items():
        path = _safe_path(root, source_rel)
        digest = sha256(path)
        if acquisition_role is not None:
            cohort = summary["cohorts"][acquisition_role]
            if cohort.get("sha256") != digest or output_hashes.get(path.name) != digest:
                raise ValueError(f"Acquired cohort fingerprint mismatch: {role}")
            if cohort.get("n") != count:
                raise ValueError(f"Unexpected frozen count for {role}")
        rows, seen = [], set()
        for source in _read_csv(path):
            row = _source_record(source, snapshot)
            fid = row["canonical_id"]
            if fid in seen:
                raise ValueError(f"Duplicate canonical person in {role}")
            seen.add(fid)
            dob = row["exact_dob_frozen"]
            if dob not in cache:
                cache[dob] = generate_pillars(dob, backend)
            row.update(cache[dob])
            rows.append(row)
        if len(rows) != count:
            raise ValueError(f"Frozen cohort count mismatch for {role}: {len(rows)} != {count}")
        rows.sort(key=lambda row: row["canonical_id"])
        generated[role] = rows
        role_info[role] = {"n": count, "snapshot": snapshot,
                           "source": {"path": source_rel.as_posix(), "sha256": digest}}
    if ({row["canonical_id"] for row in generated["development"]}
            & {row["canonical_id"] for row in generated["primary_new"]}):
        raise ValueError("Development/NEW identity overlap")
    person_dobs = {}
    for role, rows in generated.items():
        for row in rows:
            previous = person_dobs.setdefault(row["canonical_id"], row["exact_dob_frozen"])
            if previous != row["exact_dob_frozen"]:
                raise ValueError(f"Cross-role DOB disagreement for {row['canonical_id']}")
    comparisons, reference_info = [], []
    for rel in REFERENCE_PATHS:
        path = _safe_path(root, rel)
        reference = _read_csv(path)
        comparisons.append(compare_legacy(generated, reference, rel))
        reference_info.append({"path": rel, "sha256": sha256(path), "n": len(reference)})
    old_2013 = comparisons[0]
    if (old_2013["reference_n"] != 501
            or old_2013["matching_person_comparisons"]["development"] != 501):
        raise ValueError("The original501 development people must all retain identical DOB/pillars")
    if comparisons[1]["matching_person_comparisons"]["supplementary_full"] != 501:
        raise ValueError("The original2023 FULL501 must all retain identical DOB/pillars")
    for role, rows in generated.items():
        path = data / f"model_inputs_{role}.csv"
        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=OUTPUT_COLUMNS, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
        role_info[role].update({"path": path.relative_to(root).as_posix(), "sha256": sha256(path)})
    inputs = ["manifest.json", "summary.json", "independent_audit.json", "subset_manifest.json", "training_subsets.csv"]
    provenance = {name: sha256(data / name) for name in inputs}
    convention = {
        "sxtwl_version": SXTWL_VERSION,
        "calls": ["sxtwl.fromSolar(year,month,day)", "getYearGZ()", "getMonthGZ()", "getDayGZ()"],
        "year_boundary": "default getYearGZ(): LiChun, not Chinese New Year",
        "month_boundary": "sxtwl solar-term date calculation",
        "day_boundary": "civil-date-only getDayGZ; no hour or late-Zi rollover assumption",
        "timezone_place_adjustment": "none; preserves prior date-only convention",
        "boundary_limitation": "birth times are unavailable; within-date solar-term timing uncertainty is not reconstructed",
        "upstream_references": UPSTREAM_REFERENCES,
    }
    audit = {"status": "passed", "executing_commit": _executing_commit(root),
             "prepared_utc": datetime.now(timezone.utc).isoformat(),
             "legacy_comparisons": comparisons, "errors": [],
             "development_new_overlap": 0,
             "input_provenance_sha256": provenance, "convention": convention,
             "model_fits_or_scores_calculated": False}
    _write_json(audit_path, audit)
    manifest = {"status": COMPLETE, "protocol_id": "chess-single-A-v2",
                "executing_preparation_commit": audit["executing_commit"],
                "source_acquisition_executing_commit": acquisition["executing_commit"],
                "prepared_utc": audit["prepared_utc"], "preparation_script_sha256": sha256(Path(__file__)),
                "config_at_preparation_sha256": sha256(root / CONFIG_REL),
                "feature_spec_sha256": _json_hash(spec), "roles": role_info,
                "reference_inputs": reference_info, "input_provenance_sha256": provenance,
                "feature_audit_sha256": sha256(audit_path), "convention": convention,
                "traditional_features_supplied": False, "pretrained_embeddings": False,
                "prior_historical_outcome_access_disclosed": True}
    _write_json(manifest_path, manifest)
    return manifest


def load_model_frame(repo_root: Path, role: str) -> pd.DataFrame:
    root = Path(repo_root).resolve()
    manifest = _read_json(root / DATA_REL / "data_manifest.json")
    if manifest.get("status") != COMPLETE:
        raise ValueError("Model inputs are not complete")
    if role not in ROLE_SOURCES or role not in manifest.get("roles", {}):
        raise ValueError(f"Unknown model input role: {role}")
    spec = feature_spec(_read_json(root / CONFIG_REL))
    if manifest.get("feature_spec_sha256") != _json_hash(spec):
        raise ValueError("Feature specification changed after preparation")
    info = manifest["roles"][role]
    path = _safe_path(root, info["path"])
    if sha256(path) != info["sha256"]:
        raise ValueError(f"Model input fingerprint mismatch for {role}")
    rows = _read_csv(path)
    if len(rows) != info["n"]:
        raise ValueError(f"Model input row count mismatch for {role}")
    for row in rows:
        if set(row) != set(OUTPUT_COLUMNS):
            raise ValueError("Unexpected derived model input columns")
        row["canonical_id"] = canonical_id(row)
        _source_record(row, info["snapshot"])
        _validate_symbols(row)
        row["rating"] = int(row["rating"])
    ids = [row["canonical_id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate model input canonical IDs")
    return pd.DataFrame(rows, columns=OUTPUT_COLUMNS).sort_values("canonical_id").reset_index(drop=True)


def get_training_ids(repo_root: Path, label: str) -> list[str]:
    root = Path(repo_root).resolve()
    manifest = _read_json(root / DATA_REL / "subset_manifest.json")
    if manifest.get("status") != "subsets_fixed_no_models_fitted":
        raise ValueError("Training subsets are not fixed")
    if label not in manifest.get("subsets", {}):
        raise ValueError(f"Unknown training subset: {label}")
    path = _safe_path(root, manifest["output"]["path"])
    if sha256(path) != manifest["output"]["sha256"]:
        raise ValueError("Training subset fingerprint mismatch")
    selected = [row for row in _read_csv(path) if row["label"] == label]
    selected.sort(key=lambda row: int(row["order"]))
    if [int(row["order"]) for row in selected] != list(range(1, len(selected) + 1)):
        raise ValueError("Training subset order is not contiguous")
    ids = [canonical_id(row) for row in selected]
    info = manifest["subsets"][label]
    if len(ids) != info["actual_n"] or len(ids) != len(set(ids)):
        raise ValueError("Training subset count or identity mismatch")
    digest = hashlib.sha256(("\n".join(ids) + "\n").encode("utf-8")).hexdigest()
    if digest != info["ordered_ids_sha256"]:
        raise ValueError("Training subset ordered-ID fingerprint mismatch")
    return ids


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    manifest = prepare_inputs(args.repo_root)
    print(json.dumps({"status": manifest["status"],
                      "cohort_counts": {role: info["n"] for role, info in manifest["roles"].items()},
                      "feature_audit_sha256": manifest["feature_audit_sha256"]}, indent=2))


if __name__ == "__main__":
    main()
