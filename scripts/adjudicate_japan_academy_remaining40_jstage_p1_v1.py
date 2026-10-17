#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

SCRIPT_VERSION = "japan-academy-remaining40-jstage-p1-adjudication-v1"
SOURCE_SNAPSHOT_DATE = "2026-10-16"

DEFAULT_QUEUE = Path("data/japan_academy_remaining40_jstage_triage_v1/jstage_priority1_pdf_fetch_queue_v1.csv")
DEFAULT_INVENTORY = Path("data/japan_academy_remaining40_jstage_p1_pdf_fetch_v1/p1_pdf_fetch_inventory_v1.csv")
DEFAULT_OUT = Path("data/japan_academy_remaining40_jstage_p1_adjudication_v1")

EXPECTED_DOIS = {
    "10.2183/tja1948.15.271",
    "10.2183/tja1948.36.suppl_1",
    "10.2183/tja1948.50.129",
}

MANUAL_ARTICLE_REVIEWS = {
    "10.2183/tja1948.15.271": {
        "review_locator": "PDF p1; full 50-page text search",
        "target_members": "宮沢 俊義",
        "observed_evidence": (
            "PDF p1 subtitle says 宮澤俊義会員紹介. In the complete extracted 50-page text, "
            "宮澤 occurs once (the subtitle) and no 第一部/第二部/第1部/第2部/分科 token was found."
        ),
        "decision": "no_direct_person_section_binding",
        "decision_reason": (
            "会員紹介 establishes member-introducer context only; it does not state a Japan Academy division/subsection."
        ),
    },
    "10.2183/tja1948.36.suppl_1": {
        "review_locator": "PDF pp5,7",
        "target_members": "南原 繁",
        "observed_evidence": (
            "The article explicitly describes the Academy's First/Second Division structure by broad fields "
            "(PDF pp5,7) and separately mentions former president 南原繁 on p7."
        ),
        "decision": "no_direct_person_section_binding",
        "decision_reason": (
            "The division description and the person mention are separate statements. "
            "Assigning 南原繁 to a division would require discipline/role inference, which the frozen policy forbids."
        ),
    },
    "10.2183/tja1948.50.129": {
        "review_locator": "PDF pp3,8,10,13",
        "target_members": "南原 繁 | 宮沢 俊義 | 村川 堅太郎 | 高木 貞二",
        "observed_evidence": (
            "PDF p3 states that UAI functioned as an international organization corresponding to the Academy's First Division. "
            "The article separately records 宮沢俊義 as a UAI delegate (p8), 南原繁 and 高木貞二 in related international activities (p10), "
            "and 村川堅太郎 in UAI committee work (p13)."
        ),
        "decision": "no_direct_person_section_binding",
        "decision_reason": (
            "This is organization-to-division mapping plus person-to-organization participation. "
            "It does not directly state that any target person belongs to Japan Academy First Division."
        ),
    },
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
    assert set(MANUAL_ARTICLE_REVIEWS) == EXPECTED_DOIS
    assert all(v["decision"] == "no_direct_person_section_binding" for v in MANUAL_ARTICLE_REVIEWS.values())
    assert "organization-to-division" in MANUAL_ARTICLE_REVIEWS["10.2183/tja1948.50.129"]["decision_reason"]
    print("SELF-TEST OK: P1 manual adjudication constants and policy guardrails are consistent")

def run(queue_path: Path, inventory_path: Path, out: Path) -> None:
    for p in (queue_path, inventory_path):
        if not p.exists():
            raise FileNotFoundError(p)

    queue = read_csv(queue_path)
    inventory = read_csv(inventory_path)

    q_by_doi = {r.get("doi", ""): r for r in queue}
    i_by_doi = {r.get("doi", ""): r for r in inventory}

    if set(q_by_doi) != EXPECTED_DOIS:
        raise RuntimeError(f"Unexpected P1 queue DOI set: {sorted(q_by_doi)}")
    if set(i_by_doi) != EXPECTED_DOIS:
        raise RuntimeError(f"Unexpected PDF inventory DOI set: {sorted(i_by_doi)}")

    article_rows: list[dict[str, Any]] = []
    member_rows: list[dict[str, Any]] = []

    for doi in sorted(EXPECTED_DOIS):
        q = q_by_doi[doi]
        inv = i_by_doi[doi]
        manual = MANUAL_ARTICLE_REVIEWS[doi]

        if str(inv.get("pdf_magic_ok", "")) not in {"1", "1.0"}:
            raise RuntimeError(f"{doi}: pdf_magic_ok is not 1")
        if str(inv.get("pdf_eof_ok", "")) not in {"1", "1.0"}:
            raise RuntimeError(f"{doi}: pdf_eof_ok is not 1")
        if not inv.get("sha256"):
            raise RuntimeError(f"{doi}: missing PDF SHA256")

        article_rows.append({
            "doi": doi,
            "article_title_ja": q.get("article_title_ja", ""),
            "pdf_sha256": inv.get("sha256", ""),
            "pdf_bytes": inv.get("bytes", ""),
            "fetch_state": inv.get("fetch_state", ""),
            "review_locator": manual["review_locator"],
            "target_members": manual["target_members"],
            "observed_evidence": manual["observed_evidence"],
            "decision": manual["decision"],
            "decision_reason": manual["decision_reason"],
            "direct_section_evidence_accepted": 0,
            "automatic_section_acceptance": 0,
            "final_roster_row_written": 0,
            "dob_collection_started": 0,
            "bazi_variables_computed": 0,
        })

        member_keys = [x.strip() for x in str(q.get("target_member_keys", "")).split("|") if x.strip()]
        member_names = [x.strip() for x in str(q.get("target_members", "")).split("|") if x.strip()]
        if len(member_keys) != len(member_names):
            raise RuntimeError(f"{doi}: target member key/name count mismatch")

        for key, name in zip(member_keys, member_names):
            member_rows.append({
                "member_key": key,
                "name_jp": name,
                "doi": doi,
                "article_title_ja": q.get("article_title_ja", ""),
                "review_locator": manual["review_locator"],
                "adjudication": "remain_unresolved",
                "reason": manual["decision_reason"],
                "direct_section_evidence_accepted": 0,
                "final_roster_row_written": 0,
                "dob_collection_started": 0,
                "bazi_variables_computed": 0,
            })

    unique_members = sorted({r["member_key"] for r in member_rows})

    out.mkdir(parents=True, exist_ok=True)
    write_csv(out / "p1_article_adjudication_v1.csv", article_rows)
    write_csv(out / "p1_member_adjudication_v1.csv", member_rows)

    summary = {
        "dataset": SCRIPT_VERSION,
        "source_snapshot_date": SOURCE_SNAPSHOT_DATE,
        "p1_articles_reviewed": len(article_rows),
        "p1_pdfs_validated_complete": len(article_rows),
        "target_member_article_rows": len(member_rows),
        "unique_target_members_reviewed": len(unique_members),
        "direct_section_evidence_accepted": 0,
        "members_resolved_by_p1": 0,
        "members_remaining_unresolved_after_p1": len(unique_members),
        "decision": (
            "All three P1 Tier-A publications were reviewed and none directly binds a target person "
            "to Japan Academy Section I/II or a subsection. All four target members remain unresolved."
        ),
        "policy_note": (
            "Organization-to-division plus person-to-organization participation is not accepted as direct person-section evidence. "
            "Division structure plus a separate person mention is also not accepted."
        ),
        "final_roster_rows_written": 0,
        "final_roster_frozen": 0,
        "dob_collection_started": 0,
        "bazi_variables_computed": 0,
        "input_sha256": {
            "jstage_priority1_pdf_fetch_queue_v1": sha256_file(queue_path),
            "p1_pdf_fetch_inventory_v1": sha256_file(inventory_path),
        },
        "next_action": (
            "Do not expand inference rules. Use a section-term intersection against the existing J-STAGE target-name candidates "
            "to identify the smallest next PDF review queue before fetching P2/P3 material."
        ),
    }
    write_json(out / "summary.json", summary)

    md = """# Japan Academy remaining-40 J-STAGE P1 adjudication v1

Three Tier-A P1 publications were reviewed after all three PDFs were validated complete.

Result: **0 direct person-section evidence accepted**.

- 10.2183/tja1948.15.271: 宮澤俊義会員紹介 is member-introducer context only; no division/subsection statement.
- 10.2183/tja1948.36.suppl_1: division structure and 南原繁 are mentioned separately; no direct binding.
- 10.2183/tja1948.50.129: UAI is described as corresponding to First Division, and target members are described as participating in related organizations; this is an inference chain, not a direct person-section statement.

All target members remain unresolved. No roster, DOB, or BaZi variable is written.
"""
    (out / "JSTAGE_P1_ADJUDICATION_V1.md").write_text(md, encoding="utf-8")

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
