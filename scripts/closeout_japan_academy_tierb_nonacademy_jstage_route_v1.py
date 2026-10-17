#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

SCRIPT_VERSION = "japan-academy-tierb-nonacademy-jstage-route-closeout-v1"
SOURCE_SNAPSHOT_DATE = "2026-10-17"

DEFAULT_HIRATSUKA = Path("data/japan_academy_remaining40_tierb_hiratsuka_adjudication_v1/summary.json")
DEFAULT_DISCOVERY = Path("data/japan_academy_remaining39_tierb_jstage_institutional_discovery_v1/summary.json")
DEFAULT_STRONG = Path("data/japan_academy_remaining39_tierb_jstage_strong_institutional_intersection_v1/summary.json")
DEFAULT_MURAKAWA = Path("data/japan_academy_remaining39_tierb_murakawa_adjudication_v1/summary.json")
DEFAULT_OUT = Path("data/japan_academy_tierb_nonacademy_jstage_route_closeout_v1")

EXPECTED = {
    "starting_unresolved": 40,
    "hiratsuka_accepted": 1,
    "remaining_search_targets": 39,
    "member_article_candidates": 50,
    "members_with_candidates": 23,
    "unique_articles": 34,
    "strong_articles": 1,
    "strong_members": 1,
    "murakawa_accepted": 0,
    "final_unresolved": 39,
}

def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))

def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0].keys()) if rows else []
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def expect(label: str, actual: Any, expected: Any) -> None:
    if actual != expected:
        raise RuntimeError(f"{label}: expected {expected!r}, found {actual!r}")

def self_test() -> None:
    assert EXPECTED["starting_unresolved"] - EXPECTED["hiratsuka_accepted"] == EXPECTED["final_unresolved"]
    assert EXPECTED["murakawa_accepted"] == 0
    print("SELF-TEST OK: non-Academy J-STAGE Tier-B closeout invariants are consistent")

def run(hiratsuka_path: Path, discovery_path: Path, strong_path: Path, murakawa_path: Path, out: Path) -> None:
    hiratsuka = read_json(hiratsuka_path)
    discovery = read_json(discovery_path)
    strong = read_json(strong_path)
    murakawa = read_json(murakawa_path)

    expect("Hiratsuka input remaining", int(hiratsuka["input_remaining_rows"]), EXPECTED["starting_unresolved"])
    expect("Hiratsuka accepted", int(hiratsuka["direct_section_evidence_accepted"]), EXPECTED["hiratsuka_accepted"])
    expect("Hiratsuka broad section", hiratsuka["accepted_broad_section"], "II")
    expect("Hiratsuka subsection", str(hiratsuka["accepted_exact_subsection"]), "6")

    expect("discovery already resolved", int(discovery["already_resolved_tier_b_members"]), 1)
    expect("discovery search targets", int(discovery["search_targets"]), EXPECTED["remaining_search_targets"])
    expect("discovery member-article candidates", int(discovery["deduplicated_member_article_candidates"]), EXPECTED["member_article_candidates"])
    expect("discovery members with candidates", int(discovery["members_with_any_tier_b_jstage_candidate"]), EXPECTED["members_with_candidates"])

    expect("strong input unique articles", int(strong["input_unique_articles"]), EXPECTED["unique_articles"])
    expect("strong retrieval complete", int(strong["retrieval_complete"]), 1)
    expect("strong failed pages", int(strong["failed_query_pages"]), 0)
    expect("strong articles", int(strong["unique_candidate_articles_with_strong_institutional_phrase"]), EXPECTED["strong_articles"])
    expect("strong members", int(strong["unique_target_members_covered"]), EXPECTED["strong_members"])

    expect("Murakawa accepted", int(murakawa["direct_section_evidence_accepted"]), EXPECTED["murakawa_accepted"])
    expect("Murakawa remains unresolved", int(murakawa["target_remains_unresolved"]), 1)
    expect("Murakawa adjudication", murakawa["adjudication"], "remain_unresolved_context_false_positive")

    for label, obj in [
        ("hiratsuka", hiratsuka),
        ("discovery", discovery),
        ("strong", strong),
        ("murakawa", murakawa),
    ]:
        expect(f"{label} final roster rows", int(obj.get("final_roster_rows_written", 0)), 0)
        expect(f"{label} DOB started", int(obj.get("dob_collection_started", 0)), 0)
        expect(f"{label} BaZi computed", int(obj.get("bazi_variables_computed", 0)), 0)

    layers = [
        {
            "layer": "tierb_manual_success_hiratsuka",
            "members_or_rows": 1,
            "unique_articles": 1,
            "accepted_members": 1,
            "interpretation": "Academic-society obituary directly binds 平塚直秀 to Japan Academy Section II and subsection 6.",
        },
        {
            "layer": "remaining39_nonacademy_jstage_discovery",
            "members_or_rows": int(discovery["members_with_any_tier_b_jstage_candidate"]),
            "unique_articles": EXPECTED["unique_articles"],
            "accepted_members": 0,
            "interpretation": "23/39 members had non-Academy J-STAGE article leads; discovery only.",
        },
        {
            "layer": "strong_institutional_phrase_intersection",
            "members_or_rows": int(strong["unique_target_members_covered"]),
            "unique_articles": int(strong["unique_candidate_articles_with_strong_institutional_phrase"]),
            "accepted_members": 0,
            "interpretation": "Complete 26-term strong institutional intersection left one article for one target.",
        },
        {
            "layer": "murakawa_manual_adjudication",
            "members_or_rows": 1,
            "unique_articles": 1,
            "accepted_members": 0,
            "interpretation": "Only remaining strong hit was a contextual false positive; 村川堅太郎 remains unresolved.",
        },
    ]

    out.mkdir(parents=True, exist_ok=True)
    write_csv(out / "tierb_nonacademy_jstage_route_layers_v1.csv", layers)

    input_paths = {
        "hiratsuka_adjudication_summary": hiratsuka_path,
        "remaining39_discovery_summary": discovery_path,
        "strong_intersection_summary": strong_path,
        "murakawa_adjudication_summary": murakawa_path,
    }

    summary = {
        "dataset": SCRIPT_VERSION,
        "source_snapshot_date": SOURCE_SNAPSHOT_DATE,
        "starting_unresolved_members": EXPECTED["starting_unresolved"],
        "members_accepted_by_nonacademy_jstage_tier_b_route": 1,
        "accepted_members": [
            {
                "member_key": hiratsuka["target_member_key"],
                "name_jp": hiratsuka["target_name_jp"],
                "accepted_broad_section": hiratsuka["accepted_broad_section"],
                "accepted_exact_subsection": str(hiratsuka["accepted_exact_subsection"]),
                "source_tier": hiratsuka["source_tier"],
            }
        ],
        "remaining_unresolved_after_route_if_integrated": EXPECTED["final_unresolved"],
        "remaining39_systematic_search_targets": EXPECTED["remaining_search_targets"],
        "remaining39_members_with_article_candidates": EXPECTED["members_with_candidates"],
        "remaining39_unique_candidate_articles": EXPECTED["unique_articles"],
        "remaining39_strong_intersection_articles": EXPECTED["strong_articles"],
        "remaining39_strong_intersection_members": EXPECTED["strong_members"],
        "additional_members_accepted_after_systematic_remaining39_sweep": 0,
        "route_status": "deprioritized_not_exhaustively_negative",
        "route_closeout_statement": (
            "The non-Academy J-STAGE Tier-B route produced one valid direct case (平塚直秀, Section II/subsection 6). "
            "A systematic sweep of the other 39 members produced 34 unique candidate articles across 23 members, "
            "then only one complete strong institutional-phrase intersection; manual review showed that final hit "
            "to be contextual rather than direct person-section evidence. The route is therefore deprioritized, "
            "not treated as exhaustive proof of absence."
        ),
        "next_preferred_route": "tier_b_non_jstage_institutional_sources",
        "final_roster_rows_written": 0,
        "final_roster_frozen": 0,
        "dob_collection_started": 0,
        "bazi_variables_computed": 0,
        "input_sha256": {k: sha256_file(v) for k, v in input_paths.items()},
    }
    write_json(out / "summary.json", summary)

    md = """# Japan Academy Tier-B non-Academy J-STAGE route closeout v1

This closeout covers the external academic-society/J-STAGE Tier-B branch.

## Result

- Starting unresolved set: 40.
- Accepted direct Tier-B case: **平塚直秀 — Section II, subsection 6**.
- Remaining systematic search set: 39.
- Non-Academy J-STAGE discovery: 50 member-article rows, 34 unique articles, 23 members.
- Complete strong institutional-phrase intersection: 1 article, 1 member.
- Manual adjudication of that final hit (村川堅太郎): contextual false positive, unresolved.

Net accepted by this route: **1 member**.
Remaining unresolved if integrated: **39 members**.

The route is **deprioritized, not exhaustively negative**. The preferred next route is non-J-STAGE Tier-B institutional material: university archives, government/institutional records, museum/archive collections, and academic-society websites.

No final Japan Academy roster is written or frozen here. DOB collection and BaZi computation remain blocked.
"""
    (out / "TIERB_NONACADEMY_JSTAGE_ROUTE_CLOSEOUT_V1.md").write_text(md, encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hiratsuka", default=str(DEFAULT_HIRATSUKA))
    ap.add_argument("--discovery", default=str(DEFAULT_DISCOVERY))
    ap.add_argument("--strong", default=str(DEFAULT_STRONG))
    ap.add_argument("--murakawa", default=str(DEFAULT_MURAKAWA))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        self_test()
        return 0

    run(Path(args.hiratsuka), Path(args.discovery), Path(args.strong), Path(args.murakawa), Path(args.out))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
