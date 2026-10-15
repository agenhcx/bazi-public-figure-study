#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

SCRIPT_VERSION = "japan-academy-broad-section-degree-rule-freeze-v1"
SOURCE_SNAPSHOT_DATE = "2026-10-15"

DEFAULT_REVIEW_SUMMARY = Path("data/japan_academy_roster_discovery_review_v1/summary.json")
DEFAULT_IMPERIAL_ACCEPTED = Path("data/japan_academy_imperial_section_adjudication_v1/accepted_section2_evidence_v1.csv")
DEFAULT_IMPERIAL_EXCLUDED = Path("data/japan_academy_imperial_section_adjudication_v1/excluded_section1_evidence_v1.csv")
DEFAULT_POSTWAR_UNRESOLVED = Path("data/japan_academy_postwar_official_source_discovery_v1/unresolved_member_postwar_source_partition_v1.csv")
DEFAULT_OUT = Path("data/japan_academy_broad_section_degree_rule_freeze_v1")

RULE_STATUS = "degree_suggested_section_ii_not_frozen"
EXPECTED_LINKED_BROAD_EVALUABLE = 106
EXPECTED_LINKED_BROAD_MATCHES = 106
EXPECTED_LINKED_SCIENCE_SECTION2 = 65
EXPECTED_LINKED_HUMANITIES_SECTION1 = 41
EXPECTED_IMPERIAL_DEGREE_ACCEPTED = 86
EXPECTED_IMPERIAL_DEGREE_EXCLUDED = 0
EXPECTED_POSTWAR_UNRESOLVED = 239
EXPECTED_RULE_ACCEPTED = 199
EXPECTED_REMAINING = 40

def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0].keys()) if rows else []
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def as_int(v: Any) -> int:
    if v is None or v == "":
        return 0
    return int(v)

def self_test() -> None:
    rows = [
        {"source_queue_status": RULE_STATUS},
        {"source_queue_status": "subsection_unresolved"},
    ]
    accepted = [r for r in rows if r["source_queue_status"] == RULE_STATUS]
    remaining = [r for r in rows if r["source_queue_status"] != RULE_STATUS]
    assert len(accepted) == 1 and len(remaining) == 1
    print("SELF-TEST OK: broad-section rule routing and guardrails are consistent")

def run(review_summary: Path, imperial_accepted: Path, imperial_excluded: Path,
        postwar_unresolved: Path, out: Path) -> None:
    for p in [review_summary, imperial_accepted, imperial_excluded, postwar_unresolved]:
        if not p.exists():
            raise FileNotFoundError(p)

    review = json.loads(review_summary.read_text(encoding="utf-8"))
    broad = review.get("degree_broad_section_diagnostic") or {}

    expected = {
        "evaluable_single_science_or_humanities_markers": EXPECTED_LINKED_BROAD_EVALUABLE,
        "matches": EXPECTED_LINKED_BROAD_MATCHES,
        "mismatches": 0,
        "single_science_markers_official_section2": EXPECTED_LINKED_SCIENCE_SECTION2,
        "humanities_social_markers_official_section1": EXPECTED_LINKED_HUMANITIES_SECTION1,
    }
    for key, value in expected.items():
        if as_int(broad.get(key)) != value:
            raise RuntimeError(f"Linked-detail broad-section diagnostic mismatch for {key}: expected {value}, got {broad.get(key)}")

    if review.get("final_roster_frozen") != 0 or review.get("dob_collection_started") != 0 or review.get("bazi_variables_computed") != 0:
        raise RuntimeError("Upstream discovery review guardrail violated.")

    imp_acc = read_csv(imperial_accepted)
    imp_exc = read_csv(imperial_excluded)

    imp_degree_acc = [r for r in imp_acc if r.get("source_queue_status") == RULE_STATUS]
    imp_degree_exc = [r for r in imp_exc if r.get("source_queue_status") == RULE_STATUS]

    if len(imp_degree_acc) != EXPECTED_IMPERIAL_DEGREE_ACCEPTED:
        raise RuntimeError(f"Expected {EXPECTED_IMPERIAL_DEGREE_ACCEPTED} independently confirmed imperial degree-rule Section II rows, found {len(imp_degree_acc)}")
    if len(imp_degree_exc) != EXPECTED_IMPERIAL_DEGREE_EXCLUDED:
        raise RuntimeError(f"Expected zero imperial Section I exclusions from the single-science rule, found {len(imp_degree_exc)}")

    unresolved = read_csv(postwar_unresolved)
    if len(unresolved) != EXPECTED_POSTWAR_UNRESOLVED:
        raise RuntimeError(f"Expected {EXPECTED_POSTWAR_UNRESOLVED} postwar unresolved rows, found {len(unresolved)}")

    rule_rows = [r for r in unresolved if r.get("source_queue_status") == RULE_STATUS]
    remaining = [r for r in unresolved if r.get("source_queue_status") != RULE_STATUS]

    if len(rule_rows) != EXPECTED_RULE_ACCEPTED or len(remaining) != EXPECTED_REMAINING:
        raise RuntimeError(
            f"Unexpected postwar rule partition: accepted={len(rule_rows)} remaining={len(remaining)} "
            f"(expected {EXPECTED_RULE_ACCEPTED}/{EXPECTED_REMAINING})"
        )

    if any(as_int(r.get("roster_acceptance_written")) or as_int(r.get("dob_collection_started")) or as_int(r.get("bazi_variables_computed")) for r in unresolved):
        raise RuntimeError("Postwar unresolved input already contains downstream writes.")

    out.mkdir(parents=True, exist_ok=True)

    accepted_out = []
    for r in rule_rows:
        accepted_out.append({
            **r,
            "broad_section_rule": "single_science_degree_marker_to_section2",
            "broad_section_rule_status": "accepted_section2_by_frozen_degree_rule",
            "broad_section_only": 1,
            "exact_subsection_assigned": 0,
            "final_section_evidence": 2,
            "final_roster_row_written": 0,
            "dob_collection_started": 0,
            "bazi_variables_computed": 0,
        })

    remaining_out = []
    for r in remaining:
        remaining_out.append({
            **r,
            "broad_section_rule": "not_applicable",
            "broad_section_rule_status": "other_official_source_still_required",
            "broad_section_only": 1,
            "exact_subsection_assigned": 0,
            "final_roster_row_written": 0,
            "dob_collection_started": 0,
            "bazi_variables_computed": 0,
        })

    write_csv(out / "accepted_section2_by_degree_rule_v1.csv", accepted_out)
    write_csv(out / "remaining_other_official_source_required_v1.csv", remaining_out)

    summary = {
        "dataset": SCRIPT_VERSION,
        "source_snapshot_date": SOURCE_SNAPSHOT_DATE,
        "rule_definition": (
            "For formal Japan/Imperial Academy members whose upstream frozen status is "
            "'degree_suggested_section_ii_not_frozen' (single science degree marker only), "
            "classify broad Section II membership only. Do not assign exact subsections 4-7. "
            "Mixed, blank, or unmapped degree markers are not covered."
        ),
        "linked_detail_validation": {
            "evaluable_single_science_or_humanities_markers": EXPECTED_LINKED_BROAD_EVALUABLE,
            "matches": EXPECTED_LINKED_BROAD_MATCHES,
            "mismatches": 0,
            "single_science_markers_official_section2": EXPECTED_LINKED_SCIENCE_SECTION2,
            "humanities_social_markers_official_section1": EXPECTED_LINKED_HUMANITIES_SECTION1,
        },
        "independent_imperial_roster_validation": {
            "degree_rule_rows_confirmed_section2": len(imp_degree_acc),
            "degree_rule_rows_confirmed_section1": len(imp_degree_exc),
        },
        "combined_single_science_marker_section2_confirmations": EXPECTED_LINKED_SCIENCE_SECTION2 + len(imp_degree_acc),
        "combined_observed_broad_section_mismatches": 0,
        "postwar_unresolved_input_rows": len(unresolved),
        "accepted_section2_by_frozen_degree_rule_rows": len(accepted_out),
        "remaining_other_official_source_required_rows": len(remaining_out),
        "accepted_partition_counts": dict(sorted(Counter(r.get("postwar_source_partition", "") for r in accepted_out).items())),
        "remaining_partition_counts": dict(sorted(Counter(r.get("postwar_source_partition", "") for r in remaining_out).items())),
        "guardrails": [
            "This rule assigns broad Section II only; it never assigns exact subsection 4-7.",
            "Mixed degree markers are not accepted by this rule.",
            "Blank or unmapped degree markers remain unresolved.",
            "The 5 exact-subsection validation mismatches do not invalidate the broad-section rule because all remained official Section II.",
            "No final roster is frozen in this layer.",
            "No DOB collection or BaZi computation is started in this layer.",
        ],
        "final_roster_rows_written": 0,
        "final_roster_frozen": 0,
        "dob_collection_started": 0,
        "bazi_variables_computed": 0,
        "input_sha256": {
            "roster_discovery_review_summary": sha256_file(review_summary),
            "imperial_accepted_section2": sha256_file(imperial_accepted),
            "imperial_excluded_section1": sha256_file(imperial_excluded),
            "postwar_unresolved_partition": sha256_file(postwar_unresolved),
        },
        "next_action": (
            "Collect direct official section evidence only for the remaining 40 rows; "
            "retain direct-evidence-only versus expanded-degree-rule cohort routes for later sensitivity analysis."
        ),
    }
    write_json(out / "summary.json", summary)

    freeze_md = f"""# Japan Academy broad Section II degree-rule freeze v1

Frozen on {SOURCE_SNAPSHOT_DATE} before DOB collection and before any BaZi computation.

## Rule

Accept broad Section II only when the upstream frozen roster-discovery status is
'{RULE_STATUS}', which is generated only by the single-science-degree-marker rule.
This freeze does not assign subsections 4-7.

Mixed, blank, and unmapped degree markers are excluded from this rule.

## Validation

- Linked official detail pages: {EXPECTED_LINKED_BROAD_MATCHES}/{EXPECTED_LINKED_BROAD_EVALUABLE} broad-section matches.
- Of those, {EXPECTED_LINKED_SCIENCE_SECTION2}/{EXPECTED_LINKED_SCIENCE_SECTION2} single-science markers were official Section II.
- Independent Imperial Academy roster evidence: {len(imp_degree_acc)}/{len(imp_degree_acc)} degree-rule rows confirmed Section II; {len(imp_degree_exc)} confirmed Section I.
- Combined observed single-science-marker Section II confirmations: {EXPECTED_LINKED_SCIENCE_SECTION2 + len(imp_degree_acc)}, with 0 observed broad-section mismatches.

## Application

- Postwar unresolved input: {len(unresolved)}
- Accepted by frozen broad rule: {len(accepted_out)}
- Remaining for direct official-source work: {len(remaining_out)}

No final roster row, DOB, or BaZi variable is written here.
"""
    (out / "BROAD_SECTION_DEGREE_RULE_FREEZE_V1.md").write_text(freeze_md, encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--review-summary", default=str(DEFAULT_REVIEW_SUMMARY))
    ap.add_argument("--imperial-accepted", default=str(DEFAULT_IMPERIAL_ACCEPTED))
    ap.add_argument("--imperial-excluded", default=str(DEFAULT_IMPERIAL_EXCLUDED))
    ap.add_argument("--postwar-unresolved", default=str(DEFAULT_POSTWAR_UNRESOLVED))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        self_test()
        return 0
    run(
        Path(args.review_summary),
        Path(args.imperial_accepted),
        Path(args.imperial_excluded),
        Path(args.postwar_unresolved),
        Path(args.out),
    )
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
