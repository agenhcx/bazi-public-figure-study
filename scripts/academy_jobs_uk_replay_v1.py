#!/usr/bin/env python3
"""Rebuild and verify the frozen UK collection without changing frozen inputs.

This runner uses only checked-in files and the Python standard library. It does
not acquire DOBs or perform downstream analysis. The original builder is run in
a temporary output directory; the verified rebuild is copied to job artifacts.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import redirect_stdout
import csv
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import traceback


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = Path("data/royal_society_dob_freeze_v1.json")
BUILDER = Path("scripts/royal_society_dob_freeze_v1.py")
FROZEN_DIR = Path("data/royal_society_dob_freeze_v1")
INPUTS = (
    MANIFEST,
    Path("ROYAL_SOCIETY_DOB_CLOSEOUT_V1.md"),
    BUILDER,
    Path("data/royal_society_roster_freeze_v1/royal_society_fellows_roster_freeze_v1.csv"),
    Path("data/royal_society_past_dob_closeout_v1/accepted_exact_dob_final_v1.csv"),
    Path("data/royal_society_current_dob_candidate_v1/current_exact_dob_candidate_pool_v1.csv"),
    Path("data/royal_society_current_dob_candidate_v1/authority_recovery_whitelist_v1.csv"),
)
EXPECTED_HASH_FIELDS = {
    "royal_society_fellows_dob_crosswalk_v1.csv": "unified_crosswalk_sha256",
    "royal_society_current_exact_dob_final_v1.csv": "generated_current_exact_csv_sha256",
    "royal_society_current_authority_reaudit_v1.csv": "generated_authority_reaudit_sha256",
    "missingness_by_status_v1.csv": "generated_missingness_status_sha256",
    "missingness_by_election_era_v1.csv": "generated_missingness_era_sha256",
}
TRACKED_CSVS = tuple(name for name in EXPECTED_HASH_FIELDS if "crosswalk" not in name)
EXPECTED_COUNTS = {
    "roster_rows": 8669,
    "unique_cohort_keys": 8669,
    "past_rows": 7099,
    "current_rows": 1570,
    "exact_dob_rows": 4983,
    "past_exact_dob_rows": 4884,
    "current_exact_dob_rows": 99,
    "unresolved_rows": 3686,
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def csv_semantics(path: Path) -> tuple[tuple[str, ...], Counter]:
    """Compare named cell values, preserving duplicate multiplicity, not BOM/order."""
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fields = tuple(sorted(reader.fieldnames or []))
        if not fields or len(fields) != len(set(fields)):
            raise ValueError(f"Missing or duplicate CSV headers: {path}")
        rows = []
        for row in reader:
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f"Malformed CSV row: {path}")
            rows.append(tuple(row[field] for field in fields))
        return fields, Counter(rows)


def check(report: dict, name: str, passed: bool, **details) -> None:
    report["checks"].append({"name": name, "passed": bool(passed), **details})


def source_commit() -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=False
    )
    return result.stdout.strip() if result.returncode == 0 else None


def replay(report: dict, output: Path) -> None:
    watched = (*INPUTS, *(FROZEN_DIR / name for name in TRACKED_CSVS))
    before = {str(path): sha256(ROOT / path) for path in watched}
    report["provenance"] = {"source_commit": source_commit(), "source_sha256": before}
    manifest = json.loads((ROOT / MANIFEST).read_text(encoding="utf-8"))
    check(report, "frozen_manifest_policy", manifest.get("freeze_status") == "final"
          and manifest.get("bazi_variables_computed") == 0,
          freeze_status=manifest.get("freeze_status"),
          bazi_variables_computed=manifest.get("bazi_variables_computed"))
    check(report, "frozen_manifest_counts", all(
        manifest.get(key) == expected for key, expected in EXPECTED_COUNTS.items()
        if key not in {"roster_rows", "unique_cohort_keys"}
    ) and manifest.get("cohort_rows") == EXPECTED_COUNTS["roster_rows"])

    spec = importlib.util.spec_from_file_location("academy_uk_frozen_builder", ROOT / BUILDER)
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load frozen Royal Society builder")
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    log = io.StringIO()
    try:
        with tempfile.TemporaryDirectory(prefix="academy_uk_frozen_rebuild_") as temporary:
            rebuilt = Path(temporary)
            builder.OUT = rebuilt
            with redirect_stdout(log):
                builder.main()
            for name, field in EXPECTED_HASH_FIELDS.items():
                expected = manifest["reproducibility_checkpoint"][field]
                actual = sha256(rebuilt / name)
                check(report, f"generated_sha256:{name}", actual == expected,
                      expected_sha256=expected, actual_sha256=actual)
            for name in TRACKED_CSVS:
                expected_semantics = csv_semantics(ROOT / FROZEN_DIR / name)
                actual_semantics = csv_semantics(rebuilt / name)
                check(report, f"tracked_csv_semantics:{name}",
                      expected_semantics == actual_semantics,
                      tracked_rows=expected_semantics[1].total(),
                      rebuilt_rows=actual_semantics[1].total())

            with (rebuilt / "royal_society_fellows_dob_crosswalk_v1.csv").open(
                encoding="utf-8-sig", newline=""
            ) as stream:
                rows = list(csv.DictReader(stream))
            counts = {
                "roster_rows": len(rows),
                "unique_cohort_keys": len({row["cohort_key"] for row in rows}),
                "past_rows": sum(row["status_at_source"] == "past" for row in rows),
                "current_rows": sum(row["status_at_source"] == "current" for row in rows),
                "exact_dob_rows": sum(bool(row["final_exact_dob"]) for row in rows),
                "past_exact_dob_rows": sum(row["status_at_source"] == "past" and bool(
                    row["final_exact_dob"]) for row in rows),
                "current_exact_dob_rows": sum(row["status_at_source"] == "current" and bool(
                    row["final_exact_dob"]) for row in rows),
                "unresolved_rows": sum(not row["final_exact_dob"] for row in rows),
            }
            report["counts"] = counts
            check(report, "independently_counted_rebuild", counts == EXPECTED_COUNTS,
                  expected=EXPECTED_COUNTS, actual=counts)
            shutil.copytree(rebuilt, output / "rebuilt", dirs_exist_ok=True)
    finally:
        (output / "builder_stdout.log").write_text(log.getvalue(), encoding="utf-8")
        after = {str(path): sha256(ROOT / path) for path in watched}
        check(report, "frozen_sources_unchanged", before == after,
              changed_paths=[path for path in before if before[path] != after[path]])

    failed = [item["name"] for item in report["checks"] if not item["passed"]]
    if failed:
        raise RuntimeError("Verification failed: " + "; ".join(failed))


def write_reports(report: dict, output: Path) -> None:
    (output / "summary.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    counts = report.get("counts", {})
    lines = ["# UK frozen DOB deterministic replay", "", f"Status: **{report['status']}**", ""]
    if counts:
        lines.extend(["| Actual measure | Count |", "| --- | ---: |"])
        lines.extend(f"| {name} | {value} |" for name, value in counts.items())
        lines.append("")
    else:
        lines.extend(["Actual counts unavailable: the run failed before the rebuilt crosswalk was read.", ""])
    passed = sum(item["passed"] for item in report["checks"])
    lines.extend([f"Checks passed: {passed}/{len(report['checks'])}.", ""])
    for item in report["checks"]:
        lines.append(f"- {'PASS' if item['passed'] else 'FAIL'}: `{item['name']}`")
    if "error" in report:
        lines.extend(["", "Failure: " + report["error"]])
    lines.extend(["", "Broad DOB acquisition remains stopped. BaZi variables computed: 0.",
                  "The run does not change the final UK freeze.", ""])
    (output / "summary.md").write_text("\n".join(lines), encoding="utf-8")
    failure = output / "failure_summary.json"
    if report["status"] == "failed":
        failure.write_text(json.dumps({
            "job": report["job"], "status": "failed", "error": report.get("error"),
            "failed_checks": [item for item in report["checks"] if not item["passed"]],
            "counts": counts,
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    elif failure.exists():
        failure.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path,
                        default=Path("local_runs/academy_followup_20261028/uk"))
    args = parser.parse_args()
    output = (ROOT / args.output_dir).resolve()
    if output == ROOT or (ROOT in output.parents and not output.is_relative_to(ROOT / "local_runs")):
        parser.error("Output inside the repository must be under local_runs/")
    output.mkdir(parents=True, exist_ok=True)
    os.chdir(ROOT)
    report = {
        "schema_version": 1, "job": "uk", "status": "running", "checks": [],
        "counts": {}, "bazi_variables_computed": 0,
        "scope": "offline deterministic replay of the final Royal Society DOB freeze v1",
    }
    try:
        replay(report, output)
        report["status"] = "passed"
    except Exception as exc:
        report["status"] = "failed"
        report["error"] = f"{type(exc).__name__}: {exc}"
        (output / "traceback.log").write_text(traceback.format_exc(), encoding="utf-8")
    write_reports(report, output)
    print(json.dumps({"status": report["status"], "counts": report["counts"],
                      "output_dir": str(output)}, ensure_ascii=False))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
