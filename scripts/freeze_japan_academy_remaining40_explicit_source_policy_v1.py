#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

SCRIPT_VERSION = "japan-academy-remaining40-explicit-source-policy-freeze-v1"
SOURCE_SNAPSHOT_DATE = "2026-10-16"
DEFAULT_INPUT = Path("data/japan_academy_remaining40_direct_evidence_queue_v1/remaining40_direct_evidence_queue_v1.csv")
DEFAULT_OUT = Path("data/japan_academy_remaining40_explicit_source_policy_freeze_v1")
EXPECTED_ROWS = 40

SOURCE_POLICY = [
    {
        "tier": "A",
        "acceptance": "accept_if_explicit",
        "definition": "Japan Academy first-party HTML/PDF/publication explicitly states Japan Academy Section I/II or subsection for the exact person.",
    },
    {
        "tier": "B",
        "acceptance": "accept_if_explicit_and_identity_clear",
        "definition": "Government, university, museum/archive, or recognized academic/professional society source explicitly states the exact person's Japan Academy division/subsection; it must clearly refer to Japan Academy, not the Science Council of Japan or another organization.",
    },
    {
        "tier": "C",
        "acceptance": "review_only_not_accept",
        "definition": "Publisher, newspaper, encyclopedia, personal site, blog, search-result snippet, or other non-institutional source. May discover leads but cannot by itself resolve section.",
    },
]

REJECT_RULES = [
    "Do not infer Section I/II from degree marker, specialty, faculty affiliation, prize field, publication topic, or co-occurrence with known members.",
    "Do not treat Science Council of Japan division labels as Japan Academy section evidence.",
    "Do not accept a search-engine snippet without fetching and preserving the underlying source.",
    "Do not accept a source that says only Japan Academy member without an explicit Japan Academy division/subsection.",
    "Do not reinterpret absence from a roster or webpage as Section I, Section II, or non-membership.",
]

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
    assert SOURCE_POLICY[0]["tier"] == "A"
    assert SOURCE_POLICY[1]["acceptance"] == "accept_if_explicit_and_identity_clear"
    assert SOURCE_POLICY[2]["acceptance"] == "review_only_not_accept"
    assert len(REJECT_RULES) == 5
    print("SELF-TEST OK: explicit-source tiers and rejection guardrails are consistent")

def run(inp: Path, out: Path) -> None:
    if not inp.exists():
        raise FileNotFoundError(inp)
    rows = read_csv(inp)
    if len(rows) != EXPECTED_ROWS:
        raise RuntimeError(f"Expected {EXPECTED_ROWS} remaining rows, found {len(rows)}")

    out.mkdir(parents=True, exist_ok=True)
    plan: list[dict[str, Any]] = []

    for r in rows:
        name = r.get("name_jp", "")
        for division in ("第1部", "第2部"):
            plan.append({
                "member_key": r.get("member_key", ""),
                "name_jp": name,
                "name_en": r.get("name_en", ""),
                "degree_jp": r.get("degree_jp", ""),
                "specialty_jp": r.get("specialty_jp", ""),
                "first_election_date": r.get("first_election_date", ""),
                "final_retirement_date": r.get("final_retirement_date", ""),
                "postwar_source_partition": r.get("postwar_source_partition", ""),
                "query_purpose": f"explicit_{division}",
                "search_query": f'"{name}" "日本学士院" "{division}"',
                "discovered_url": "",
                "source_tier": "",
                "source_organization": "",
                "source_title": "",
                "explicit_phrase": "",
                "explicit_section": "",
                "explicit_subsection": "",
                "identity_clear": "",
                "source_fetched_and_archived": 0,
                "decision": "unreviewed",
                "final_roster_row_written": 0,
                "dob_collection_started": 0,
                "bazi_variables_computed": 0,
            })

    write_csv(out / "remaining40_explicit_source_search_plan_v1.csv", plan)
    write_json(out / "source_policy_v1.json", {
        "dataset": SCRIPT_VERSION,
        "source_snapshot_date": SOURCE_SNAPSHOT_DATE,
        "source_tiers": SOURCE_POLICY,
        "reject_rules": REJECT_RULES,
    })

    md = """# Japan Academy remaining-40 explicit-source policy freeze v1

This policy is frozen before systematic external searching for the remaining 40 people.

Accepted evidence:
- Tier A: Japan Academy first-party material explicitly states the person's Japan Academy division/subsection.
- Tier B: a government, university, museum/archive, or recognized academic/professional society source explicitly states the person's Japan Academy division/subsection, with clear identity.

Not accepted by itself:
- publisher/newspaper/encyclopedia/blog/search snippet;
- degree, specialty, faculty, prize field, publication topic, or other discipline inference;
- division labels belonging to the Science Council of Japan or another institution;
- a statement that the person was merely a Japan Academy member.

Every accepted Tier-B row must preserve the fetched source and exact explicit phrase.
No final roster, DOB, or BaZi variable is written at this layer.
"""
    (out / "REMAINING40_EXPLICIT_SOURCE_POLICY_FREEZE_V1.md").write_text(md, encoding="utf-8")

    summary = {
        "dataset": SCRIPT_VERSION,
        "source_snapshot_date": SOURCE_SNAPSHOT_DATE,
        "input_members": len(rows),
        "search_plan_rows": len(plan),
        "tier_a_rule": "Japan Academy first-party explicit division/subsection",
        "tier_b_rule": "institutional explicit Japan Academy division/subsection with clear identity",
        "tier_c_rule": "discovery/review only; cannot resolve section by itself",
        "discipline_inference_allowed": 0,
        "search_snippet_acceptance_allowed": 0,
        "science_council_division_confusion_allowed": 0,
        "direct_section_evidence_accepted": 0,
        "final_roster_rows_written": 0,
        "final_roster_frozen": 0,
        "dob_collection_started": 0,
        "bazi_variables_computed": 0,
        "input_sha256": {"remaining40_queue": sha256_file(inp)},
        "next_action": "Discover Tier-A/Tier-B candidate URLs, fetch/archive underlying sources, and adjudicate only explicit Japan Academy division/subsection statements.",
    }
    write_json(out / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=str(DEFAULT_INPUT))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        self_test()
        return 0
    run(Path(args.input), Path(args.out))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
