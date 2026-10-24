#!/usr/bin/env python3
"""Audit frozen chess input identities and schemas without fitting a model.

Rating values are checked only for a nonempty positive integer representation.
They are never retained in the audit records or summarised in the report.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
from datetime import date
from pathlib import Path
from typing import Any


STEMS = "甲乙丙丁戊己庚辛壬癸"
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
ROLES = ("development", "primary_evaluation", "secondary_evaluation")
REQUIRED_COLUMNS = {
    "fide_id", "exact_dob_frozen", "rating", "snapshot", "sex",
    "year_pillar", "month_pillar", "day_pillar",
}
PILLAR_COLUMNS = ("year_pillar", "month_pillar", "day_pillar")
POSITION_COLUMNS = (
    ("year_stem", "year_branch"),
    ("month_stem", "month_branch"),
    ("day_stem", "day_branch"),
)
OVERLAP_PAIRS = {
    "development_primary_evaluation": ("development", "primary_evaluation"),
    "development_secondary_evaluation": ("development", "secondary_evaluation"),
    "primary_evaluation_secondary_evaluation": (
        "primary_evaluation", "secondary_evaluation"
    ),
}


def fingerprints(data: bytes) -> dict[str, Any]:
    """Return byte-level hashes, including the exact Git blob object hash."""
    git_header = b"blob " + str(len(data)).encode("ascii") + b"\0"
    return {
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "git_blob_sha": hashlib.sha1(git_header + data).hexdigest(),
    }


def is_valid_pillar(pillar: str) -> bool:
    return (
        len(pillar) == 2
        and pillar[0] in STEMS
        and pillar[1] in BRANCHES
        and STEMS.index(pillar[0]) % 2 == BRANCHES.index(pillar[1]) % 2
    )


def audit_inputs(repo_root: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    """Validate all input rows; report counts and errors, never outcome metrics."""
    repo_root = repo_root.resolve()
    errors: list[dict[str, Any]] = []
    file_reports: list[dict[str, Any]] = []
    records: dict[str, dict[str, tuple[str, tuple[str, ...]]]] = {}

    def error(code: str, **context: Any) -> None:
        errors.append({"code": code, **context})

    entries = manifest.get("files")
    if not isinstance(entries, list):
        error("manifest_files_not_list")
        entries = []

    for entry_index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            error("manifest_file_not_object", entry_index=entry_index)
            continue
        missing_manifest = sorted({
            "role", "path", "sha256", "git_blob_sha", "bytes",
            "expected_rows", "expected_snapshot",
        } - entry.keys())
        if missing_manifest:
            error("manifest_missing_fields", entry_index=entry_index,
                  fields=missing_manifest)
            continue
        role = entry["role"]
        if role not in ROLES:
            error("manifest_invalid_role", entry_index=entry_index)
            continue
        if role in records:
            error("manifest_duplicate_role", role=role)
            continue
        records[role] = {}
        relative_path = entry["path"]
        if not isinstance(relative_path, str):
            error("manifest_invalid_path", role=role)
            continue
        path = (repo_root / relative_path).resolve()
        if Path(relative_path).is_absolute() or not path.is_relative_to(repo_root):
            error("path_outside_repository", role=role)
            continue
        try:
            raw = path.read_bytes()
        except OSError:
            error("file_unreadable", role=role, path=relative_path)
            continue
        actual_fingerprints = fingerprints(raw)
        file_report: dict[str, Any] = {
            "role": role, "path": relative_path,
            "fingerprints": actual_fingerprints,
            "rows": 0, "unique_ids": 0,
        }
        file_reports.append(file_report)
        for key, actual in actual_fingerprints.items():
            if entry[key] != actual:
                error("fingerprint_mismatch", role=role, field=key)
        try:
            decoded = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            error("invalid_utf8", role=role)
            continue
        reader = csv.DictReader(io.StringIO(decoded, newline=""), strict=True)
        try:
            header = reader.fieldnames or []
            if len(header) != len(set(header)):
                error("duplicate_header", role=role)
            missing_columns = sorted(REQUIRED_COLUMNS - set(header))
            if missing_columns:
                error("missing_required_columns", role=role, fields=missing_columns)
                continue
            rows = list(reader)
        except csv.Error:
            error("invalid_csv", role=role)
            continue
        file_report["rows"] = len(rows)
        if len(rows) != entry["expected_rows"]:
            error("row_count_mismatch", role=role,
                  expected=entry["expected_rows"], observed=len(rows))
        expected_snapshot = entry["expected_snapshot"]
        if not isinstance(expected_snapshot, str) or not re.fullmatch(
            r"\d{4}-\d{2}", expected_snapshot
        ):
            error("manifest_invalid_snapshot", role=role)
            continue
        try:
            snapshot_day = date.fromisoformat(expected_snapshot + "-01")
        except ValueError:
            error("manifest_invalid_snapshot", role=role)
            continue

        for row_number, row in enumerate(rows, start=2):
            context = {"role": role, "row": row_number}
            if None in row or any(value is None for value in row.values()):
                error("malformed_csv_row", **context)
                continue
            values = {key: value.strip() for key, value in row.items()}
            canonical_id = (
                values.get("identity_bridge_modern_fide_id", "")
                or values["fide_id"]
            )
            valid_id = bool(re.fullmatch(r"[0-9]+", canonical_id))
            if not valid_id or int(canonical_id or "0") <= 0:
                error("invalid_canonical_id", **context)
                valid_id = False
            if not re.fullmatch(r"[0-9]+", values["fide_id"]):
                error("invalid_fide_id", **context)
            if values["snapshot"] != expected_snapshot:
                error("snapshot_mismatch", **context)
            if values["sex"] != "M":
                error("sex_mismatch", **context)
            if "analysis_sex" in values and values["analysis_sex"] != "M":
                error("analysis_sex_mismatch", **context)
            # Outcome validation only: do not save or summarise the value.
            rating_text = values["rating"]
            if not re.fullmatch(r"[0-9]+", rating_text) or int(rating_text or "0") <= 0:
                error("invalid_rating_integer", **context)
            dob_text = values["exact_dob_frozen"]
            try:
                if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", dob_text):
                    raise ValueError
                dob = date.fromisoformat(dob_text)
                if dob >= snapshot_day:
                    error("dob_not_before_snapshot", **context)
            except ValueError:
                error("invalid_exact_dob", **context)
            pillars = tuple(values[column] for column in PILLAR_COLUMNS)
            for column, pillar, position_columns in zip(
                PILLAR_COLUMNS, pillars, POSITION_COLUMNS, strict=True
            ):
                if not is_valid_pillar(pillar):
                    error("invalid_pillar", column=column, **context)
                    continue
                for position, character in zip(position_columns, pillar, strict=True):
                    if position in values and values[position] != character:
                        error("position_pillar_mismatch", column=position, **context)
            if valid_id:
                # Normalise decimal identity representation before matching.
                canonical_id = str(int(canonical_id))
                if canonical_id in records[role]:
                    error("duplicate_canonical_id", **context)
                else:
                    records[role][canonical_id] = (dob_text, pillars)
        file_report["unique_ids"] = len(records[role])

    for role in ROLES:
        if role not in records:
            error("manifest_missing_role", role=role)
    expected_overlaps = manifest.get("expected_identity_overlaps", {})
    if not isinstance(expected_overlaps, dict):
        error("manifest_overlaps_not_object")
        expected_overlaps = {}
    overlaps: dict[str, int] = {}
    for key, (left, right) in OVERLAP_PAIRS.items():
        left_records, right_records = records.get(left, {}), records.get(right, {})
        shared_ids = left_records.keys() & right_records.keys()
        overlaps[key] = len(shared_ids)
        if key not in expected_overlaps:
            error("manifest_missing_overlap", pair=key)
        elif len(shared_ids) != expected_overlaps[key]:
            error("identity_overlap_mismatch", pair=key,
                  expected=expected_overlaps[key], observed=len(shared_ids))
        inconsistent = sum(
            left_records[identity] != right_records[identity]
            for identity in shared_ids
        )
        if inconsistent:
            error("cross_file_identity_inconsistent", pair=key, count=inconsistent)
    return {
        "ok": not errors,
        "protocol_id": manifest.get("protocol_id"),
        "source_commit": manifest.get("source_commit"),
        "files": file_reports,
        "identity_overlaps": overlaps,
        "errors": errors,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path,
                        default=Path(__file__).resolve().parents[2])
    parser.add_argument("--manifest", type=Path,
                        default=Path(__file__).with_name("data_manifest.json"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        if not isinstance(manifest, dict):
            raise ValueError("manifest must be an object")
        report = audit_inputs(args.repo_root, manifest)
    except (OSError, ValueError, TypeError) as exc:
        report = {"ok": False, "errors": [{"code": "manifest_unreadable",
                   "error_type": type(exc).__name__}]}
    output = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding="utf-8")
    print(output, end="")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
