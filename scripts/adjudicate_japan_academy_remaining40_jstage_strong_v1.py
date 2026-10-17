#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

SCRIPT_VERSION = "japan-academy-remaining40-jstage-strong-adjudication-v1"
SOURCE_SNAPSHOT_DATE = "2026-10-17"

DEFAULT_QUEUE = Path("data/japan_academy_remaining40_jstage_strong_section_intersection_v1/jstage_strong_section_next_review_queue_v1.csv")
DEFAULT_P1_SUMMARY = Path("data/japan_academy_remaining40_jstage_p1_adjudication_v1/summary.json")
DEFAULT_OUT = Path("data/japan_academy_remaining40_jstage_strong_adjudication_v1")

EXPECTED_DOI = "10.2183/tja.65.1_31"
EXPECTED_TARGETS = {"中川 善之助", "宮沢 俊義", "福田 歓一", "都留 重人"}

MANUAL_REVIEW = {
    "doi": EXPECTED_DOI,
    "source_url": "https://www.jstage.jst.go.jp/article/tja/65/1/65_KJ00006545419/_pdf/-char/ja/",
    "article_title_ja": "国際法の実務家に徹した60年 : 日本の法学者として特異な体験を振り返る",
    "author": "小田 滋",
    "reviewed_context": (
        "The strong section phrases in this article describe author 小田滋's own First-Division context "
        "and his report/joint-meeting relationship with the Second Division. "
        "The target persons are mentioned elsewhere as teachers, colleagues, or scholars who later entered the Academy; "
        "the article does not directly state that 中川善之助, 宮沢俊義, 福田歓一, or 都留重人 belongs to Japan Academy "
        "Section I/II or a subsection."
    ),
    "decision": "no_direct_person_section_binding",
    "decision_reason": (
        "Article-level co-occurrence of a target name and a strong section phrase is insufficient. "
        "The section phrase refers to the author/context, not directly to any target member."
    ),
    "review_locator": "J-STAGE PDF pp.31-33 and full-document text review",
}

def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))

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

def split_pipe(s: str) -> list[str]:
    return [x.strip() for x in str(s or "").split("|") if x.strip()]

def self_test() -> None:
    assert MANUAL_REVIEW["doi"] == EXPECTED_DOI
    assert MANUAL_REVIEW["decision"] == "no_direct_person_section_binding"
    assert "co-occurrence" in MANUAL_REVIEW["decision_reason"]
    print("SELF-TEST OK: strong-intersection manual adjudication constants are consistent")

def run(queue_path: Path, p1_summary_path: Path, out: Path) -> None:
    for p in (queue_path, p1_summary_path):
        if not p.exists():
            raise FileNotFoundError(p)

    queue = read_csv(queue_path)
    if len(queue) != 1:
        raise RuntimeError(f"Expected exactly one strong-intersection review row, found {len(queue)}")

    row = queue[0]
    if row.get("doi", "") != EXPECTED_DOI:
        raise RuntimeError(f"Unexpected DOI: {row.get('doi')}")

    targets = set(split_pipe(row.get("target_members", "")))
    if targets != EXPECTED_TARGETS:
        raise RuntimeError(f"Unexpected target set: {sorted(targets)}")

    p1 = read_json(p1_summary_path)
    if int(p1.get("direct_section_evidence_accepted", -1)) != 0:
        raise RuntimeError("P1 summary unexpectedly contains accepted direct section evidence")

    adjudication_rows: list[dict[str, Any]] = []
    for name, key in zip(
        split_pipe(row.get("target_members", "")),
        split_pipe(row.get("target_member_keys", "")),
    ):
        adjudication_rows.append({
            "member_key": key,
            "name_jp": name,
            "doi": EXPECTED_DOI,
            "article_title_ja": MANUAL_REVIEW["article_title_ja"],
            "source_url": MANUAL_REVIEW["source_url"],
            "matched_strong_terms": row.get("matched_strong_terms", ""),
            "review_locator": MANUAL_REVIEW["review_locator"],
            "manual_review_context": MANUAL_REVIEW["reviewed_context"],
            "adjudication": "remain_unresolved",
            "decision_reason": MANUAL_REVIEW["decision_reason"],
            "direct_section_evidence_accepted": 0,
            "final_roster_row_written": 0,
            "dob_collection_started": 0,
            "bazi_variables_computed": 0,
        })

    out.mkdir(parents=True, exist_ok=True)
    write_csv(out / "strong_intersection_member_adjudication_v1.csv", adjudication_rows)

    summary = {
        "dataset": SCRIPT_VERSION,
        "source_snapshot_date": SOURCE_SNAPSHOT_DATE,
        "strong_intersection_articles_reviewed": 1,
        "strong_intersection_target_members_reviewed": len(adjudication_rows),
        "direct_section_evidence_accepted": 0,
        "members_resolved_by_strong_intersection": 0,
        "members_remaining_unresolved_after_strong_intersection": len(adjudication_rows),
        "p1_direct_section_evidence_accepted": int(p1.get("direct_section_evidence_accepted", 0)),
        "jstage_route_status": "deprioritized_not_exhaustively_negative",
        "route_interpretation": (
            "The P1 review and the stronger section-relation intersection produced no direct person-section binding. "
            "This does not prove that no J-STAGE article could contain such evidence; it shows diminishing retrieval yield, "
            "so the frozen Tier-B institutional-source route is now preferred."
        ),
        "final_roster_rows_written": 0,
        "final_roster_frozen": 0,
        "dob_collection_started": 0,
        "bazi_variables_computed": 0,
        "input_sha256": {
            "strong_section_next_review_queue_v1": sha256_file(queue_path),
            "p1_adjudication_summary": sha256_file(p1_summary_path),
        },
        "next_action": (
            "Move to the frozen Tier-B institutional-source search for the remaining 40. "
            "Preserve J-STAGE as a secondary fallback; do not infer section from discipline."
        ),
    }
    write_json(out / "summary.json", summary)

    md = """# Japan Academy remaining-40 J-STAGE strong-intersection adjudication v1

The strong-section intersection produced one article: DOI 10.2183/tja.65.1_31.

Manual review found that the strong section phrases refer to the article author/context, not directly to any of the four target members:
中川善之助, 宮沢俊義, 福田歓一, 都留重人.

Result: **0 direct person-section evidence accepted**.

The J-STAGE route is therefore deprioritized, not declared exhaustively negative. Tier-B institutional sources become the preferred next route.
No final roster, DOB, or BaZi variable is written.
"""
    (out / "JSTAGE_STRONG_ADJUDICATION_V1.md").write_text(md, encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--queue", default=str(DEFAULT_QUEUE))
    ap.add_argument("--p1-summary", default=str(DEFAULT_P1_SUMMARY))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        self_test()
        return 0

    run(Path(args.queue), Path(args.p1_summary), Path(args.out))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
