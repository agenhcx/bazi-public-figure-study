#!/usr/bin/env python3
"""Audit the bounded 239-person Japan section layer without freezing a roster.

The four later decisions are documentary facts in the pinned Git closeout. This
job deliberately does not claim to replay their raw sources; the companion
academy_jobs_japan_replay_v1.py performs that separately.
"""
from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

VERSION = "academy-jobs-japan-integration-v1"
BASE_COMMIT = "2dccafed2a1d938ef740e4bcb776fb5d97d5514a"
DEGREE_DIR = "data/japan_academy_broad_section_degree_rule_freeze_v1"
ACCEPTED = f"{DEGREE_DIR}/accepted_section2_by_degree_rule_v1.csv"
REMAINING = f"{DEGREE_DIR}/remaining_other_official_source_required_v1.csv"
CLOSEOUT = "JAPAN_ACADEMY_SECTION_EVIDENCE_CLOSEOUT_V1.md"
PINNED_INPUTS = {
    ACCEPTED: "6480371b063a9755c3eb7115ba5ff88710f95708c9672ade84199857015a8e92",
    REMAINING: "f608b9c868aeb3d26c5e4fbc95fb5ee7e69740dbca0891fefa082f8fa44ec29b",
    f"{DEGREE_DIR}/summary.json": "a7c2f40abaf1817f8e8ae28742630d3168b16fd8b0006a6b17e5bd1aed9db02f",
    CLOSEOUT: "d588dd3138663d9216da46a99a05bfe4cca88e7065c572842c8cb802f22e20b1",
    "data/japan_academy_remaining40_explicit_source_policy_freeze_v1/source_policy_v1.json": "2ec1c1fb1c8b7b52e585da83f68d8b4181ba58bea1484d03fcef1077e3830c4d",
    "ACADEMY_COHORT_SCOPE_FREEZE_V1.md": "1eda96c666d604533ce7acf03e5966ab876d646b8dac3b1bdeb142ade5d49d6b",
    "DOB_CALENDAR_AUDIT_CLOSEOUT_V1.md": "3e25e12a4acffc186b7a98c09081589c92cc4eb70ea9396a4202e60ee212cb07",
}

# Keys and exact Japanese names are independently checked against the original
# adjudicator constants and the residual CSV, rather than fuzzy name matching.
CASES = (
    {"case": "hiratsuka", "member_key": "jpa-unlinked-67412ee03b08c5d2", "name_jp": "平塚 直秀", "section": "II", "subsection": "6", "script": "adjudicate_japan_academy_remaining40_tierb_hiratsuka_v1.py"},
    {"case": "yoshikawa", "member_key": "jpa-unlinked-ff84801ab056cf46", "name_jp": "吉川 逸治", "section": "I", "subsection": "", "script": "adjudicate_japan_academy_remaining39_tierb_yoshikawa_v1.py"},
    {"case": "nanbara", "member_key": "jpa-unlinked-6b0513d4d49815ad", "name_jp": "南原 繁", "section": "I", "subsection": "", "script": "adjudicate_japan_academy_remaining38_tierb_nanbara_v1.py"},
    {"case": "doi", "member_key": "jpa-unlinked-f21fcc61cad96158", "name_jp": "土居 光知", "section": "I", "subsection": "", "script": "adjudicate_japan_academy_remaining37_tierb_doi_v1.py"},
)
ZERO_FLAGS = ("roster_acceptance_written", "dob_collection_started", "bazi_variables_computed", "final_roster_row_written")


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def prepare_output(repo: Path, requested: Path) -> Path:
    output = (repo / requested).resolve() if not requested.is_absolute() else requested.resolve()
    allowed = (repo / "local_runs").resolve()
    if output == allowed or not output.is_relative_to(allowed):
        raise ValueError("Output must be a fresh subdirectory of this repository's local_runs/")
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise FileExistsError(f"Refusing to overwrite nonempty output: {output}")
    output.mkdir(parents=True, exist_ok=True)
    return output


def unchanged(before: dict[str, str], repo: Path) -> None:
    changed = [name for name, digest in before.items() if not (repo / name).is_file() or sha256(repo / name) != digest]
    if changed:
        raise RuntimeError(f"Input changed during the job: {changed}")


def failure(output: Path | None, version: str, error: Exception) -> None:
    result = {
        "dataset": version, "status": "failed", "error_type": type(error).__name__,
        "error": str(error), "final_roster_frozen": 0, "dob_collection_started": 0,
        "bazi_variables_computed": 0, "accepted_results_claimed": 0,
    }
    if hasattr(error, "blocked_source"):
        result["status"] = "blocked_source"
        result["blocked_source"] = error.blocked_source
        result["source_request_attempts"] = getattr(error, "attempts", [])
    if output is not None:
        write_json(output / "failure_summary.json", result)
        write_json(output / "summary.json", result)
        (output / "summary.md").write_text(
            f"Japan job status: **{result['status']}**.\n\n{type(error).__name__}: {error}\n\n"
            "No completed integration or evidence replay is claimed. No final roster/DOB freeze or BaZi computation.\n",
            encoding="utf-8",
        )
    print(json.dumps(result, ensure_ascii=False), file=sys.stderr)


def literal_constants(path: Path) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    try:
                        values[target.id] = ast.literal_eval(node.value)
                    except (ValueError, TypeError):
                        pass
    return values


def validate_partition(accepted: list[dict[str, str]], remaining: list[dict[str, str]]) -> None:
    if len(accepted) != 199 or len(remaining) != 40:
        raise ValueError(f"Expected 199/40 rows, found {len(accepted)}/{len(remaining)}")
    keys = [row.get("member_key", "") for row in accepted + remaining]
    if any(not key for key in keys) or len(set(keys)) != 239:
        raise ValueError("The 239-person partition has missing, duplicate, or overlapping member keys")
    for row in accepted + remaining:
        if not row.get("name_jp"):
            raise ValueError(f"Missing identity fields: {row.get('member_key')}")
        election = date.fromisoformat(row["first_election_date"])
        if election > date(2025, 12, 31):
            raise ValueError(f"Election after the frozen cutoff: {row['member_key']}")
        for flag in ZERO_FLAGS:
            if row.get(flag) != "0":
                raise ValueError(f"Upstream nonzero/missing guardrail {flag}: {row['member_key']}")
        if row.get("broad_section_only") != "1" or row.get("exact_subsection_assigned") != "0":
            raise ValueError(f"Unexpected exact-subsection assignment: {row['member_key']}")
    for row in accepted:
        if row.get("source_queue_status") != "degree_suggested_section_ii_not_frozen" or row.get("broad_section_rule_status") != "accepted_section2_by_frozen_degree_rule" or row.get("final_section_evidence") != "2":
            raise ValueError(f"Invalid broad-only degree-rule row: {row['member_key']}")
    residual = {row["member_key"]: row for row in remaining}
    for case in CASES:
        if residual.get(case["member_key"], {}).get("name_jp") != case["name_jp"]:
            raise ValueError(f"Exact residual key/name mismatch: {case['case']}")


def run(repo: Path, output: Path) -> dict[str, Any]:
    before: dict[str, str] = {}
    for name, expected in PINNED_INPUTS.items():
        actual = sha256(repo / name)
        if actual != expected:
            raise ValueError(f"Pinned input SHA256 mismatch: {name}")
        before[name] = actual
    for case in CASES:
        script = "scripts/" + case["script"]
        constants = literal_constants(repo / script)
        if constants.get("TARGET_KEY") != case["member_key"] or constants.get("TARGET_NAME") != case["name_jp"]:
            raise ValueError(f"Original adjudicator identity differs: {case['case']}")
        before[script] = sha256(repo / script)
    accepted, remaining = read_csv(repo / ACCEPTED), read_csv(repo / REMAINING)
    validate_partition(accepted, remaining)
    source_summary = json.loads((repo / f"{DEGREE_DIR}/summary.json").read_text())
    for key, expected in {"accepted_section2_by_frozen_degree_rule_rows": 199, "remaining_other_official_source_required_rows": 40, "final_roster_frozen": 0, "dob_collection_started": 0, "bazi_variables_computed": 0}.items():
        if source_summary.get(key) != expected:
            raise ValueError(f"Unexpected frozen degree summary: {key}")
    closeout = (repo / CLOSEOUT).read_text(encoding="utf-8")
    if "effective residual is **36**" not in closeout or "**Hiratsuka Naohide** Section II / subsection 6" not in closeout or "**Yoshikawa Itsuji**, **Nanbara Shigeru**, and **Doi Kōchi** Section I" not in closeout:
        raise ValueError("The pinned closeout does not support the expected four decisions")
    decisions = {case["member_key"]: case for case in CASES}
    integrated = []
    remaining_keys = {row["member_key"] for row in remaining}
    for row in accepted + remaining:
        case = decisions.get(row["member_key"])
        degree = row["member_key"] not in remaining_keys
        integrated.append({
            **row,
            "integration_broad_section": "II" if degree else case["section"] if case else "unresolved",
            "integration_exact_subsection": case["subsection"] if case else "",
            "integration_evidence_origin": "frozen_broad_degree_rule" if degree else "documented_git_closeout_only" if case else "unresolved",
            "integration_raw_evidence_verified": 0,
            "integration_primary_eligibility": "not_finalized",
            "integration_birth_window_status": "not_evaluated_no_DOB_in_this_layer",
            "integration_final_roster_row_written": 0,
        })
    residual = [r for r in integrated if r["integration_broad_section"] == "unresolved"]
    if len(residual) != 36 or next(r for r in residual if r["member_key"] == "jpa-unlinked-e0aae7738ae3f733")["name_jp"] != "太田 博太郎":
        raise ValueError("Residual count or Ota unresolved guardrail failed")
    ledger = [{**case, "evidence_origin": "documented_git_closeout_only", "raw_source_replayed": 0, "decision_source": CLOSEOUT} for case in CASES]
    write_csv(output / "integrated_section_evidence_v1.csv", integrated)
    write_csv(output / "documented_closeout_decisions_v1.csv", ledger)
    write_csv(output / "remaining36_unresolved_v1.csv", residual)
    unchanged(before, repo)
    summary = {
        "dataset": VERSION, "status": "passed", "baseline_commit": BASE_COMMIT,
        "scope": "bounded_239_person_postwar_ambiguous_layer_not_full_Japan_roster",
        "input_rows": 239, "frozen_degree_rule_broad_section_ii_rows": 199,
        "upstream_blank_english_names_preserved": sum(not row.get("name_en") for row in accepted + remaining),
        "original_explicit_source_required_rows": 40, "documented_later_decisions": 4,
        "documented_direct_section_ii_rows": 1, "documented_section_i_exclusions": 3,
        "effective_unresolved_rows": 36, "candidate_section_ii_rows_in_this_layer": 200,
        "exact_subsections_inferred_from_degree_or_discipline": 0,
        "raw_source_cases_replayed": 0, "evidence_verification": "documented_closeout_only_for_four_later_decisions",
        "full_roster_completeness_claimed": 0, "primary_eligibility_finalized": 0,
        "hierarchy_birth_year_window": [1835, 1985], "birth_window_applied": 0,
        "birth_window_reason": "This evidence layer has no DOB assertions; preserve the full archive.",
        "section_source_routes_reopened": 0, "external_requests": 0,
        "final_roster_rows_written": 0, "final_roster_frozen": 0,
        "dob_collection_started": 0, "bazi_variables_computed": 0,
        "frozen_inputs_modified": 0, "input_sha256": before,
        "limitations": ["The 199 degree-rule rows prove broad Section II only, with no exact subsection.", "The four later decisions are integrated from the Git closeout, not raw evidence verified by this job.", "This is a partial evidence layer; it does not establish the final primary Japan cohort or DOB missingness."],
    }
    write_json(output / "summary.json", summary)
    (output / "summary.md").write_text(
        "Japan section integration: **passed**.\n\n"
        "239 input records = 199 frozen broad Section II degree-rule records + 40 requiring explicit evidence. "
        "Four decisions documented in the Git closeout yield 1 additional Section II/subsection 6 record, "
        "3 Section I exclusions, and **36 unresolved**.\n\n"
        "The four decisions are documentary integrations; raw source cases replayed by this job: **0**. "
        "The 199 degree-rule records retain no exact subsection. Ōta remains unresolved.\n\n"
        "This bounded layer is not the complete Japan roster. Final primary eligibility, DOB collection, "
        "and DOB missingness are not frozen. The 1835–1985 hierarchy birth window is recorded but cannot "
        "be applied here because this layer contains no DOB assertions.\n\n"
        "Frozen inputs modified: 0. Source-search routes reopened: 0. External requests: 0. BaZi variables computed: 0.\n",
        encoding="utf-8",
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output-dir", "--output", dest="output", type=Path, required=True)
    args = parser.parse_args()
    output = None
    try:
        repo = args.repo_root.resolve()
        output = prepare_output(repo, args.output)
        result = run(repo, output)
        print(json.dumps({key: value for key, value in result.items() if key != "input_sha256"}, ensure_ascii=False, indent=2))
        return 0
    except Exception as error:
        failure(output, VERSION, error)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
