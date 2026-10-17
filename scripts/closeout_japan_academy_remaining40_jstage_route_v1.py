#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

SCRIPT_VERSION = "japan-academy-remaining40-jstage-route-closeout-v1"
SOURCE_SNAPSHOT_DATE = "2026-10-17"

DEFAULT_DISCOVERY = Path("data/japan_academy_remaining40_jstage_candidate_discovery_v1/summary.json")
DEFAULT_TRIAGE = Path("data/japan_academy_remaining40_jstage_triage_v1/summary.json")
DEFAULT_P1 = Path("data/japan_academy_remaining40_jstage_p1_adjudication_v1/summary.json")
DEFAULT_SECTION = Path("data/japan_academy_remaining40_jstage_section_intersection_v1/summary.json")
DEFAULT_STRONG = Path("data/japan_academy_remaining40_jstage_strong_section_intersection_v1/summary.json")
DEFAULT_STRONG_ADJ = Path("data/japan_academy_remaining40_jstage_strong_adjudication_v1/summary.json")
DEFAULT_OUT = Path("data/japan_academy_remaining40_jstage_route_closeout_v1")

EXPECTED = {
    "discovery_candidates": 80,
    "discovery_members": 21,
    "triage_unique_articles": 62,
    "triage_p1": 3,
    "triage_p2": 25,
    "triage_p3": 34,
    "p1_articles": 3,
    "p1_members": 4,
    "p1_accepted": 0,
    "section_intersection_articles": 27,
    "section_intersection_members": 18,
    "strong_intersection_articles": 1,
    "strong_intersection_members": 4,
    "strong_adjudication_articles": 1,
    "strong_adjudication_members": 4,
    "strong_adjudication_accepted": 0,
}

def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0].keys()) if rows else []
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

def expect(label: str, actual: Any, expected: Any) -> None:
    if actual != expected:
        raise RuntimeError(f"{label}: expected {expected!r}, found {actual!r}")

def self_test() -> None:
    assert EXPECTED["triage_p1"] + EXPECTED["triage_p2"] + EXPECTED["triage_p3"] == EXPECTED["triage_unique_articles"]
    assert EXPECTED["p1_accepted"] == 0
    assert EXPECTED["strong_adjudication_accepted"] == 0
    print("SELF-TEST OK: J-STAGE route closeout count invariants are consistent")

def run(
    discovery_path: Path,
    triage_path: Path,
    p1_path: Path,
    section_path: Path,
    strong_path: Path,
    strong_adj_path: Path,
    out: Path,
) -> None:
    discovery = read_json(discovery_path)
    triage = read_json(triage_path)
    p1 = read_json(p1_path)
    section = read_json(section_path)
    strong = read_json(strong_path)
    strong_adj = read_json(strong_adj_path)

    expect("discovery candidate rows", int(discovery["candidate_rows_after_dedup"]), EXPECTED["discovery_candidates"])
    expect("discovery members", int(discovery["members_with_any_jstage_candidate"]), EXPECTED["discovery_members"])

    expect("triage unique articles", int(triage["unique_articles"]), EXPECTED["triage_unique_articles"])
    rc = triage["retrieval_priority_counts"]
    expect("triage P1", int(rc["P1_institutional_or_member_context"]), EXPECTED["triage_p1"])
    expect("triage P2", int(rc["P2_target_authored_or_multi_target"]), EXPECTED["triage_p2"])
    expect("triage P3", int(rc["P3_incidental_name_hit"]), EXPECTED["triage_p3"])

    expect("P1 articles", int(p1["p1_articles_reviewed"]), EXPECTED["p1_articles"])
    expect("P1 unique members", int(p1["unique_target_members_reviewed"]), EXPECTED["p1_members"])
    expect("P1 accepted", int(p1["direct_section_evidence_accepted"]), EXPECTED["p1_accepted"])

    expect("section intersection articles", int(section["unique_candidate_articles_with_section_term_intersection"]), EXPECTED["section_intersection_articles"])
    expect("section intersection members", int(section["unique_target_members_covered"]), EXPECTED["section_intersection_members"])

    expect("strong intersection articles", int(strong["unique_candidate_articles_with_strong_relation_intersection"]), EXPECTED["strong_intersection_articles"])
    expect("strong intersection members", int(strong["unique_target_members_in_next_review_queue"]), EXPECTED["strong_intersection_members"])

    expect("strong adjudication articles", int(strong_adj["strong_intersection_articles_reviewed"]), EXPECTED["strong_adjudication_articles"])
    expect("strong adjudication members", int(strong_adj["strong_intersection_target_members_reviewed"]), EXPECTED["strong_adjudication_members"])
    expect("strong adjudication accepted", int(strong_adj["direct_section_evidence_accepted"]), EXPECTED["strong_adjudication_accepted"])

    for label, obj in [
        ("discovery", discovery),
        ("triage", triage),
        ("p1", p1),
        ("section", section),
        ("strong", strong),
        ("strong_adj", strong_adj),
    ]:
        expect(f"{label} final roster rows", int(obj.get("final_roster_rows_written", 0)), 0)
        expect(f"{label} DOB started", int(obj.get("dob_collection_started", 0)), 0)
        expect(f"{label} BaZi computed", int(obj.get("bazi_variables_computed", 0)), 0)

    layer_rows = [
        {
            "layer": "candidate_discovery",
            "articles_or_rows": int(discovery["candidate_rows_after_dedup"]),
            "members_covered": int(discovery["members_with_any_jstage_candidate"]),
            "direct_section_evidence_accepted": int(discovery["direct_section_evidence_accepted"]),
            "interpretation": "Target-name full-text leads only.",
        },
        {
            "layer": "unique_article_triage",
            "articles_or_rows": int(triage["unique_articles"]),
            "members_covered": "",
            "direct_section_evidence_accepted": int(triage["automatic_section_acceptance"]),
            "interpretation": "62 unique articles; P1/P2/P3 retrieval priority only.",
        },
        {
            "layer": "p1_manual_adjudication",
            "articles_or_rows": int(p1["p1_articles_reviewed"]),
            "members_covered": int(p1["unique_target_members_reviewed"]),
            "direct_section_evidence_accepted": int(p1["direct_section_evidence_accepted"]),
            "interpretation": "Three complete Tier-A PDFs reviewed; no direct person-section binding.",
        },
        {
            "layer": "bare_section_term_intersection",
            "articles_or_rows": int(section["unique_candidate_articles_with_section_term_intersection"]),
            "members_covered": int(section["unique_target_members_covered"]),
            "direct_section_evidence_accepted": int(section["direct_section_evidence_accepted"]),
            "interpretation": "Article-level retrieval intersection only.",
        },
        {
            "layer": "strong_section_relation_intersection",
            "articles_or_rows": int(strong["unique_candidate_articles_with_strong_relation_intersection"]),
            "members_covered": int(strong["unique_target_members_in_next_review_queue"]),
            "direct_section_evidence_accepted": int(strong["direct_section_evidence_accepted"]),
            "interpretation": "One strong-relation article remained for manual review.",
        },
        {
            "layer": "strong_intersection_manual_adjudication",
            "articles_or_rows": int(strong_adj["strong_intersection_articles_reviewed"]),
            "members_covered": int(strong_adj["strong_intersection_target_members_reviewed"]),
            "direct_section_evidence_accepted": int(strong_adj["direct_section_evidence_accepted"]),
            "interpretation": "Strong phrase referred to article author/context, not target members.",
        },
    ]

    out.mkdir(parents=True, exist_ok=True)
    write_csv(out / "jstage_route_layers_v1.csv", layer_rows)

    input_paths = {
        "candidate_discovery_summary": discovery_path,
        "triage_summary": triage_path,
        "p1_adjudication_summary": p1_path,
        "bare_section_intersection_summary": section_path,
        "strong_section_intersection_summary": strong_path,
        "strong_adjudication_summary": strong_adj_path,
    }

    summary = {
        "dataset": SCRIPT_VERSION,
        "source_snapshot_date": SOURCE_SNAPSHOT_DATE,
        "input_remaining_members": 40,
        "candidate_rows": EXPECTED["discovery_candidates"],
        "members_with_any_jstage_candidate": EXPECTED["discovery_members"],
        "unique_candidate_articles": EXPECTED["triage_unique_articles"],
        "p1_articles_manually_reviewed": EXPECTED["p1_articles"],
        "strong_intersection_articles_manually_reviewed": EXPECTED["strong_adjudication_articles"],
        "direct_section_evidence_accepted_across_reviewed_jstage_route": 0,
        "members_resolved_by_reviewed_jstage_route": 0,
        "jstage_route_status": "deprioritized_not_exhaustively_negative",
        "route_closeout_statement": (
            "The reviewed J-STAGE path yielded no direct person-to-Japan-Academy-section binding under the frozen explicit-source policy. "
            "The route is deprioritized because retrieval yield diminished from 62 unique name-hit articles to one strong-relation article, "
            "which was a context false positive. This closeout is not a proof that the entire J-STAGE corpus contains no usable evidence."
        ),
        "next_preferred_route": "frozen_tier_b_institutional_sources",
        "final_roster_rows_written": 0,
        "final_roster_frozen": 0,
        "dob_collection_started": 0,
        "bazi_variables_computed": 0,
        "input_sha256": {k: sha256_file(v) for k, v in input_paths.items()},
    }
    write_json(out / "summary.json", summary)

    md = """# Japan Academy remaining-40 J-STAGE route closeout v1

This closeout freezes the reviewed J-STAGE retrieval route before moving to Tier-B institutional sources.

## Reviewed path

1. 80 target-name candidate rows across 21/40 unresolved members.
2. 62 unique articles after DOI-level deduplication.
3. Three P1 Tier-A PDFs manually reviewed: 0 direct person-section bindings.
4. Bare section-term intersection: 27 articles / 18 target members.
5. Strong section-relation intersection: 1 article / 4 target members.
6. Manual review of that final strong article: 0 direct person-section bindings.

## Interpretation

**J-STAGE is deprioritized, not declared exhaustively negative.**

The reviewed search path showed sharply diminishing yield and ended in a context false positive. This does not prove that no other J-STAGE article contains usable evidence.

The next preferred route is the already frozen Tier-B institutional-source policy.

No final roster row, DOB collection, or BaZi variable is written by this closeout.
"""
    (out / "JSTAGE_ROUTE_CLOSEOUT_V1.md").write_text(md, encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--discovery", default=str(DEFAULT_DISCOVERY))
    ap.add_argument("--triage", default=str(DEFAULT_TRIAGE))
    ap.add_argument("--p1", default=str(DEFAULT_P1))
    ap.add_argument("--section", default=str(DEFAULT_SECTION))
    ap.add_argument("--strong", default=str(DEFAULT_STRONG))
    ap.add_argument("--strong-adj", default=str(DEFAULT_STRONG_ADJ))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        self_test()
        return 0

    run(
        Path(args.discovery),
        Path(args.triage),
        Path(args.p1),
        Path(args.section),
        Path(args.strong),
        Path(args.strong_adj),
        Path(args.out),
    )
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
