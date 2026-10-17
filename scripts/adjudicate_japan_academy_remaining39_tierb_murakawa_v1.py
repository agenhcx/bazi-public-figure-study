#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

SCRIPT_VERSION = "japan-academy-remaining39-tierb-murakawa-adjudication-v1"
SOURCE_SNAPSHOT_DATE = "2026-10-17"

DEFAULT_QUEUE = Path(
    "data/japan_academy_remaining39_tierb_jstage_strong_institutional_intersection_v1/"
    "tierb_strong_institutional_intersection_candidates_v1.csv"
)
DEFAULT_INVENTORY = Path(
    "data/japan_academy_remaining39_tierb_murakawa_source_fetch_v1/"
    "tierb_murakawa_source_inventory_v1.csv"
)
DEFAULT_OUT = Path("data/japan_academy_remaining39_tierb_murakawa_adjudication_v1")

TARGET_KEY = "jpa-unlinked-5eb8bdd403e08b8c"
TARGET_NAME = "村川 堅太郎"
EXPECTED_DOI = "10.5955/jalha.2005.121"
EXPECTED_SOURCE_SHA256 = "79e02b74c6e15ae8a16877b34385fc2d079ead01ff83ddc073f65231226b2539"
EXPECTED_STRONG_TERM = "日本学士院第一部"

MANUAL_REVIEW = {
    "source_title": "古代ギリシア史研究と奴隷制",
    "source_organization": "法制史学会",
    "source_tier": "B",
    "review_locator": "PDF pp.125, 138-139, 143-144; full-document text review",
    "observed_target_context": (
        "村川堅太郎 is mentioned as a prior scholar/author and in bibliographic references, "
        "including 村川堅太郎古代史論集 and related cited works."
    ),
    "observed_section_context": (
        "The preserved 36-page PDF contains no direct statement binding 村川堅太郎 to 日本学士院第一部, "
        "第1部, 第一部, or a subsection. The strong J-STAGE API hit is therefore not accepted as "
        "person-section evidence."
    ),
    "decision": "remain_unresolved_context_false_positive",
    "decision_reason": (
        "The target-name occurrences are historiographical/bibliographic references. "
        "No direct Japan Academy Section I/II or subsection statement for the target appears in the preserved source."
    ),
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
    assert TARGET_NAME == "村川 堅太郎"
    assert EXPECTED_DOI == "10.5955/jalha.2005.121"
    assert EXPECTED_STRONG_TERM == "日本学士院第一部"
    assert MANUAL_REVIEW["decision"] == "remain_unresolved_context_false_positive"
    print("SELF-TEST OK: Murakawa Tier-B manual adjudication constants are consistent")

def run(queue_path: Path, inventory_path: Path, out: Path) -> None:
    for p in (queue_path, inventory_path):
        if not p.exists():
            raise FileNotFoundError(p)

    queue = read_csv(queue_path)
    inventory = read_csv(inventory_path)

    if len(queue) != 1:
        raise RuntimeError(f"Expected one strong-intersection queue row, found {len(queue)}")
    q = queue[0]

    if q.get("doi") != EXPECTED_DOI:
        raise RuntimeError(f"Unexpected queue DOI: {q.get('doi')}")
    if q.get("target_member_keys") != TARGET_KEY:
        raise RuntimeError(f"Unexpected queue member key: {q.get('target_member_keys')}")
    if q.get("target_members") != TARGET_NAME:
        raise RuntimeError(f"Unexpected queue target name: {q.get('target_members')}")
    if q.get("matched_strong_terms") != EXPECTED_STRONG_TERM:
        raise RuntimeError(f"Unexpected strong term: {q.get('matched_strong_terms')}")

    inv_rows = [r for r in inventory if r.get("member_key") == TARGET_KEY]
    if len(inv_rows) != 1:
        raise RuntimeError(f"Expected one source inventory row, found {len(inv_rows)}")
    inv = inv_rows[0]

    if inv.get("doi") != EXPECTED_DOI:
        raise RuntimeError(f"Inventory DOI mismatch: {inv.get('doi')}")
    if inv.get("sha256") != EXPECTED_SOURCE_SHA256:
        raise RuntimeError(
            f"Source SHA mismatch: expected {EXPECTED_SOURCE_SHA256}, found {inv.get('sha256')}"
        )
    if str(inv.get("pdf_magic_ok", "")) not in {"1", "1.0"}:
        raise RuntimeError("PDF magic check failed")
    if str(inv.get("pdf_eof_ok", "")) not in {"1", "1.0"}:
        raise RuntimeError("PDF EOF check failed")

    adjudication = [{
        "member_key": TARGET_KEY,
        "name_jp": TARGET_NAME,
        "doi": EXPECTED_DOI,
        "source_tier": MANUAL_REVIEW["source_tier"],
        "source_organization": MANUAL_REVIEW["source_organization"],
        "source_title": MANUAL_REVIEW["source_title"],
        "source_url": inv.get("source_url", ""),
        "source_sha256": inv.get("sha256", ""),
        "matched_strong_term": EXPECTED_STRONG_TERM,
        "review_locator": MANUAL_REVIEW["review_locator"],
        "observed_target_context": MANUAL_REVIEW["observed_target_context"],
        "observed_section_context": MANUAL_REVIEW["observed_section_context"],
        "adjudication": MANUAL_REVIEW["decision"],
        "decision_reason": MANUAL_REVIEW["decision_reason"],
        "accepted_broad_section": "",
        "accepted_exact_subsection": "",
        "direct_section_evidence_accepted": 0,
        "final_roster_row_written": 0,
        "final_roster_frozen": 0,
        "dob_collection_started": 0,
        "bazi_variables_computed": 0,
    }]

    out.mkdir(parents=True, exist_ok=True)
    write_csv(out / "murakawa_tierb_adjudication_v1.csv", adjudication)

    summary = {
        "dataset": SCRIPT_VERSION,
        "source_snapshot_date": SOURCE_SNAPSHOT_DATE,
        "target_member_key": TARGET_KEY,
        "target_name_jp": TARGET_NAME,
        "doi": EXPECTED_DOI,
        "source_sha256_verified": 1,
        "manual_adjudication_performed": 1,
        "direct_section_evidence_accepted": 0,
        "members_resolved_by_this_layer": 0,
        "target_remains_unresolved": 1,
        "adjudication": MANUAL_REVIEW["decision"],
        "interpretation": (
            "The only complete strong institutional J-STAGE intersection for the remaining-39 route "
            "was a contextual false positive: target mentions are scholarly/bibliographic references, "
            "not a direct Japan Academy section statement."
        ),
        "final_roster_rows_written": 0,
        "final_roster_frozen": 0,
        "dob_collection_started": 0,
        "bazi_variables_computed": 0,
        "input_sha256": {
            "tierb_strong_institutional_intersection_candidates_v1": sha256_file(queue_path),
            "tierb_murakawa_source_inventory_v1": sha256_file(inventory_path),
        },
        "next_action": (
            "Deprioritize this non-Academy J-STAGE Tier-B branch after route closeout. "
            "Continue with the frozen Tier-B policy using university archives, government/institutional records, "
            "museum/archive collections, and academic-society pages outside this J-STAGE retrieval branch."
        ),
    }
    write_json(out / "summary.json", summary)

    md = """# Japan Academy remaining-39 Tier-B Murakawa adjudication v1

Target: 村川 堅太郎  
DOI: 10.5955/jalha.2005.121  
Source: 法制史学会, 『古代ギリシア史研究と奴隷制』

Manual review result: **remain unresolved / contextual false positive**.

The target is cited as a prior scholar/author in the article and bibliography. The preserved PDF does not directly bind 村川堅太郎 to 日本学士院第一部, 第1部, or any subsection.

Therefore the J-STAGE strong-term co-occurrence is not accepted under the frozen explicit-source policy.

No final roster row, DOB collection, or BaZi variable is written.
"""
    (out / "TIERB_MURAKAWA_ADJUDICATION_V1.md").write_text(md, encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--queue", default=str(DEFAULT_QUEUE))
    ap.add_argument("--inventory", default=str(DEFAULT_INVENTORY))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        self_test()
        return 0

    run(Path(args.queue), Path(args.inventory), Path(args.out))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
