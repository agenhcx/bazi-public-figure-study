#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

SCRIPT_VERSION = "japan-academy-remaining40-jstage-triage-v1"
SOURCE_SNAPSHOT_DATE = "2026-10-16"

DEFAULT_INPUT = Path("data/japan_academy_remaining40_jstage_candidate_discovery_v1/jstage_article_candidates_v1.csv")
DEFAULT_OUT = Path("data/japan_academy_remaining40_jstage_triage_v1")

EXPECTED_CANDIDATE_ROWS = 80
EXPECTED_UNIQUE_ARTICLES = 62

INSTITUTIONAL_TITLE_RE = re.compile(
    r"日本学士院|日本學士院|学士院|學士院|会員紹介|會員紹介|会員選定|會員選定|"
    r"追悼|物故|名簿|百年|沿革|歩み"
)

def norm(s: str) -> str:
    return re.sub(r"[\s　・･]+", "", str(s or ""))

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

def target_is_author(row: dict[str, str]) -> bool:
    return bool(norm(row.get("name_jp", ""))) and norm(row.get("name_jp", "")) in norm(row.get("authors_ja", ""))

def article_key(row: dict[str, str]) -> tuple[str, str]:
    doi = str(row.get("doi", "") or "").strip()
    url = str(row.get("article_url_ja", "") or row.get("article_url_en", "") or "").strip()
    return doi, url

def self_test() -> None:
    assert INSTITUTIONAL_TITLE_RE.search("日本学士院百年の歩み")
    assert INSTITUTIONAL_TITLE_RE.search("明治憲法起草過程の資料的研究 (宮澤俊義会員紹介)")
    assert not INSTITUTIONAL_TITLE_RE.search("利子思想史の一節")
    assert norm("宮沢 俊義") == "宮沢俊義"
    print("SELF-TEST OK: J-STAGE title triage and name normalization are consistent")

def run(inp: Path, out: Path) -> None:
    if not inp.exists():
        raise FileNotFoundError(inp)

    rows = read_csv(inp)
    if len(rows) != EXPECTED_CANDIDATE_ROWS:
        raise RuntimeError(f"Expected {EXPECTED_CANDIDATE_ROWS} candidate rows, found {len(rows)}")

    groups: dict[tuple[str, str], list[dict[str, str]]] = {}
    for r in rows:
        groups.setdefault(article_key(r), []).append(r)

    if len(groups) != EXPECTED_UNIQUE_ARTICLES:
        raise RuntimeError(f"Expected {EXPECTED_UNIQUE_ARTICLES} unique articles, found {len(groups)}")

    triage: list[dict[str, Any]] = []

    for (doi, url), g in groups.items():
        first = g[0]
        title = str(first.get("article_title_ja", "") or "")
        target_members = sorted({r.get("name_jp", "") for r in g if r.get("name_jp")})
        target_keys = sorted({r.get("member_key", "") for r in g if r.get("member_key")})
        n_targets = len(target_keys)
        target_author_any = any(target_is_author(r) for r in g)
        institutional = bool(INSTITUTIONAL_TITLE_RE.search(title))

        if institutional:
            priority = "P1_institutional_or_member_context"
            fetch_wave = 1
            rationale = "title_has_institutional_or_member_context_signal"
        elif target_author_any or n_targets >= 2:
            priority = "P2_target_authored_or_multi_target"
            fetch_wave = 2
            rationale = "target_is_author_or_article_hits_multiple_targets"
        else:
            priority = "P3_incidental_name_hit"
            fetch_wave = 3
            rationale = "single_target_non_author_name_hit_without_institutional_title_signal"

        triage.append({
            "doi": doi,
            "article_url_ja": first.get("article_url_ja", ""),
            "article_url_en": first.get("article_url_en", ""),
            "article_pdf_url": first.get("article_pdf_url_guess", ""),
            "article_title_ja": title,
            "article_title_en": first.get("article_title_en", ""),
            "authors_ja": first.get("authors_ja", ""),
            "pubyear": first.get("pubyear", ""),
            "journal_code": first.get("cdjournal", ""),
            "volume": first.get("volume", ""),
            "issue": first.get("issue", ""),
            "starting_page": first.get("starting_page", ""),
            "ending_page": first.get("ending_page", ""),
            "n_target_members_hit": n_targets,
            "target_members": " | ".join(target_members),
            "target_member_keys": " | ".join(target_keys),
            "target_is_author_any": int(target_author_any),
            "institutional_title_signal": int(institutional),
            "retrieval_priority": priority,
            "fetch_wave": fetch_wave,
            "triage_rationale": rationale,
            "automatic_section_acceptance": 0,
            "final_roster_row_written": 0,
            "dob_collection_started": 0,
            "bazi_variables_computed": 0,
        })

    triage.sort(key=lambda r: (
        int(r["fetch_wave"]),
        -int(r["n_target_members_hit"]),
        str(r["pubyear"]),
        str(r["doi"]),
    ))

    p1 = [r for r in triage if r["fetch_wave"] == 1]
    p2 = [r for r in triage if r["fetch_wave"] == 2]
    p3 = [r for r in triage if r["fetch_wave"] == 3]

    expected_p1_dois = {
        "10.2183/tja1948.15.271",
        "10.2183/tja1948.36.suppl_1",
        "10.2183/tja1948.50.129",
    }
    actual_p1_dois = {r["doi"] for r in p1}
    if actual_p1_dois != expected_p1_dois:
        raise RuntimeError(
            f"P1 DOI set mismatch. expected={sorted(expected_p1_dois)} actual={sorted(actual_p1_dois)}"
        )

    out.mkdir(parents=True, exist_ok=True)
    write_csv(out / "jstage_unique_article_triage_v1.csv", triage)
    write_csv(out / "jstage_priority1_pdf_fetch_queue_v1.csv", p1)
    write_csv(out / "jstage_priority2_deferred_queue_v1.csv", p2)
    write_csv(out / "jstage_priority3_deferred_queue_v1.csv", p3)

    summary = {
        "dataset": SCRIPT_VERSION,
        "source_snapshot_date": SOURCE_SNAPSHOT_DATE,
        "input_candidate_rows": len(rows),
        "unique_articles": len(triage),
        "retrieval_priority_counts": dict(sorted(Counter(r["retrieval_priority"] for r in triage).items())),
        "priority1_unique_articles": len(p1),
        "priority1_target_members_covered": len({
            key
            for r in p1
            for key in str(r["target_member_keys"]).split(" | ")
            if key
        }),
        "priority1_dois": [r["doi"] for r in p1],
        "triage_basis": (
            "Retrieval priority only. P1 is based solely on institutional/member-context words in article titles; "
            "P2 is target-authored or multi-target; P3 is other incidental name hits. "
            "No specialty/degree inference and no Section I/II acceptance occurs here."
        ),
        "automatic_section_acceptance": 0,
        "final_roster_rows_written": 0,
        "final_roster_frozen": 0,
        "dob_collection_started": 0,
        "bazi_variables_computed": 0,
        "input_sha256": {"jstage_article_candidates_v1": sha256_file(inp)},
        "next_action": (
            "Fetch only the three P1 PDFs first, preserve hashes, and review the underlying PDF text/images "
            "for explicit Japan Academy Section I/II or subsection statements tied to the target person."
        ),
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
