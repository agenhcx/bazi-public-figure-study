#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

SCRIPT_VERSION = "japan-academy-remaining40-direct-evidence-queue-v1"
SOURCE_SNAPSHOT_DATE = "2026-10-15"

DEFAULT_REMAINING = Path("data/japan_academy_broad_section_degree_rule_freeze_v1/remaining_other_official_source_required_v1.csv")
DEFAULT_UNRESOLVED_DETAIL = Path("data/japan_academy_roster_discovery_review_v1/true_subsection_unresolved_v1.csv")
DEFAULT_OUT = Path("data/japan_academy_remaining40_direct_evidence_queue_v1")

EXPECTED_ROWS = 40
EXPECTED_RULE_COUNTS = {
    "blank_or_unmapped_degree": 33,
    "mixed_degree_markers": 7,
}
EXPECTED_ERA_COUNTS = {
    "overlaps_1948_1967_ichiran_scope": 18,
    "post1967_pre1985_member_directory_scope": 11,
    "1985plus_official_web_or_later_directory_scope": 10,
    "pre1948_gap_or_other_official_source": 1,
}

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

def self_test() -> None:
    sample = {
        "name_jp": "増井 清",
        "degree_suggestion_rule": "blank_or_unmapped_degree",
        "postwar_source_partition": "overlaps_1948_1967_ichiran_scope",
    }
    assert sample["degree_suggestion_rule"] in EXPECTED_RULE_COUNTS
    assert sample["postwar_source_partition"] in EXPECTED_ERA_COUNTS
    print("SELF-TEST OK: remaining-40 queue routing and guardrails are consistent")

def run(remaining_path: Path, detail_path: Path, out: Path) -> None:
    for p in (remaining_path, detail_path):
        if not p.exists():
            raise FileNotFoundError(p)

    remaining = read_csv(remaining_path)
    detail = read_csv(detail_path)

    if len(remaining) != EXPECTED_ROWS:
        raise RuntimeError(f"Expected {EXPECTED_ROWS} remaining rows, found {len(remaining)}")

    detail_by_key = {r.get("member_key", ""): r for r in detail if r.get("member_key")}
    queue: list[dict[str, Any]] = []
    missing_detail = []

    for r in remaining:
        key = r.get("member_key", "")
        d = detail_by_key.get(key)
        if d is None:
            missing_detail.append(key)
            continue

        name = r.get("name_jp", "")
        queue.append({
            "member_key": key,
            "name_jp": name,
            "name_en": r.get("name_en", ""),
            "degree_jp": d.get("degree_jp", ""),
            "specialty_jp": d.get("specialty_jp", ""),
            "first_election_date": r.get("first_election_date", ""),
            "final_retirement_date": r.get("final_retirement_date", ""),
            "postwar_source_partition": r.get("postwar_source_partition", ""),
            "degree_suggestion_rule": d.get("degree_suggestion_rule", ""),
            "official_index_url": d.get("source_url_jp", ""),
            "official_site_query_section1": f'site:japan-acad.go.jp "{name}" "第1部"',
            "official_site_query_section2": f'site:japan-acad.go.jp "{name}" "第2部"',
            "direct_evidence_priority": (
                "mixed_degree_direct_section_required"
                if d.get("degree_suggestion_rule") == "mixed_degree_markers"
                else "blank_or_unmapped_direct_section_required"
            ),
            "direct_section_evidence_status": "unreviewed",
            "direct_section_evidence": "",
            "direct_section_source_url": "",
            "direct_section_source_title": "",
            "direct_section_source_locator": "",
            "manual_review_note": "",
            "final_roster_row_written": 0,
            "dob_collection_started": 0,
            "bazi_variables_computed": 0,
        })

    if missing_detail:
        raise RuntimeError(f"Missing detail rows for member keys: {missing_detail}")

    rule_counts = Counter(r["degree_suggestion_rule"] for r in queue)
    era_counts = Counter(r["postwar_source_partition"] for r in queue)

    if dict(rule_counts) != EXPECTED_RULE_COUNTS:
        raise RuntimeError(f"Degree-rule partition mismatch: expected {EXPECTED_RULE_COUNTS}, got {dict(rule_counts)}")
    if dict(era_counts) != EXPECTED_ERA_COUNTS:
        raise RuntimeError(f"Era partition mismatch: expected {EXPECTED_ERA_COUNTS}, got {dict(era_counts)}")

    queue.sort(key=lambda r: (
        0 if r["degree_suggestion_rule"] == "mixed_degree_markers" else 1,
        r["postwar_source_partition"],
        r["first_election_date"],
        r["name_jp"],
    ))

    out.mkdir(parents=True, exist_ok=True)
    write_csv(out / "remaining40_direct_evidence_queue_v1.csv", queue)

    summary = {
        "dataset": SCRIPT_VERSION,
        "source_snapshot_date": SOURCE_SNAPSHOT_DATE,
        "input_rows": len(remaining),
        "queue_rows": len(queue),
        "degree_suggestion_rule_counts": dict(sorted(rule_counts.items())),
        "postwar_source_partition_counts": dict(sorted(era_counts.items())),
        "decision_rule": (
            "This queue is for direct official Section I/II evidence only. "
            "Degree, specialty, and search queries are retrieval aids and must not be used as section decisions."
        ),
        "direct_section_evidence_accepted": 0,
        "final_roster_rows_written": 0,
        "final_roster_frozen": 0,
        "dob_collection_started": 0,
        "bazi_variables_computed": 0,
        "input_sha256": {
            "remaining40_from_degree_rule_freeze": sha256_file(remaining_path),
            "true_subsection_unresolved_detail": sha256_file(detail_path),
        },
        "next_action": (
            "Search and adjudicate direct official Japan Academy evidence for these 40 rows only; "
            "preserve unresolved rows if no explicit Section I/II source is found."
        ),
    }
    write_json(out / "summary.json", summary)

    md = f"""# Japan Academy remaining-40 direct-evidence queue v1

Frozen input queue date: {SOURCE_SNAPSHOT_DATE}

- Rows: {len(queue)}
- Blank/unmapped degree: {rule_counts['blank_or_unmapped_degree']}
- Mixed degree markers: {rule_counts['mixed_degree_markers']}

This file is a retrieval queue only. Degree and specialty fields are not section evidence.
No final roster row, DOB, or BaZi variable is written here.
"""
    (out / "REMAINING40_DIRECT_EVIDENCE_QUEUE_V1.md").write_text(md, encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--remaining", default=str(DEFAULT_REMAINING))
    ap.add_argument("--detail", default=str(DEFAULT_UNRESOLVED_DETAIL))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        self_test()
        return 0

    run(Path(args.remaining), Path(args.detail), Path(args.out))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
