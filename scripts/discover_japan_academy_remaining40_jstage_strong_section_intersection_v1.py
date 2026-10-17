#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from typing import Any

SCRIPT_VERSION = "japan-academy-remaining40-jstage-strong-section-intersection-v1"
SOURCE_SNAPSHOT_DATE = "2026-10-16"

DEFAULT_CANDIDATES = Path("data/japan_academy_remaining40_jstage_triage_v1/jstage_unique_article_triage_v1.csv")
DEFAULT_OUT = Path("data/japan_academy_remaining40_jstage_strong_section_intersection_v1")

API_BASE = "https://api.jstage.jst.go.jp/searchapi/do"
JOURNAL_CODES = ("tja", "tja1948")

# Stronger relational phrases than bare 第一部/第二部/分科.
# These are retrieval filters only; an article hit is never automatic person-section evidence.
STRONG_TERMS = (
    "第一部会員",
    "第二部会員",
    "第1部会員",
    "第2部会員",
    "第一部會員",
    "第二部會員",
    "第一部の会員",
    "第二部の会員",
    "第一部所属",
    "第二部所属",
    "第一部所屬",
    "第二部所屬",
    "第一部に所属",
    "第二部に所属",
    "第一部第一分科",
    "第一部第二分科",
    "第一部第三分科",
    "第二部第四分科",
    "第二部第五分科",
    "第二部第六分科",
    "第二部第七分科",
)

COUNT = 100
MAX_PAGES_PER_QUERY = 20
SLEEP_SECONDS = 0.30
UA = "bazi-public-figure-study/1.0 (noncommercial research; Powered by J-STAGE)"

NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "prism": "http://prismstandard.org/namespaces/basic/2.0/",
    "opensearch": "http://a9.com/-/spec/opensearch/1.1/",
}

P1_CLOSED_DOIS = {
    "10.2183/tja1948.15.271",
    "10.2183/tja1948.36.suppl_1",
    "10.2183/tja1948.50.129",
}

def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0].keys()) if rows else [
        "doi","article_title_ja","article_url_ja","article_pdf_url",
        "retrieval_priority","fetch_wave","target_members","target_member_keys",
        "matched_strong_terms","matched_journal_codes","api_match_rows",
        "p1_already_closed","next_review_eligible","automatic_section_acceptance",
        "final_roster_row_written","dob_collection_started","bazi_variables_computed",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def text_of(el: ET.Element | None) -> str:
    if el is None:
        return ""
    return " ".join("".join(el.itertext()).split())

def parse_api(data: bytes) -> tuple[int, int, str, str, list[dict[str, str]]]:
    root = ET.fromstring(data)
    result = root.find("atom:result", NS)
    status = text_of(result.find("atom:status", NS)) if result is not None else ""
    message = text_of(result.find("atom:message", NS)) if result is not None else ""
    total_text = text_of(root.find("opensearch:totalResults", NS))
    start_text = text_of(root.find("opensearch:startIndex", NS))
    total = int(total_text) if total_text.isdecimal() else 0
    start = int(start_text) if start_text.isdecimal() else 1

    rows: list[dict[str, str]] = []
    for e in root.findall("atom:entry", NS):
        doi = text_of(e.find("prism:doi", NS))
        title_root = e.find("atom:article_title", NS)
        title_ja = text_of(title_root.find("atom:ja", NS)) if title_root is not None else ""
        title_en = text_of(title_root.find("atom:en", NS)) if title_root is not None else ""
        if doi or title_ja or title_en:
            rows.append({
                "doi": doi,
                "article_title_ja": title_ja,
                "article_title_en": title_en,
            })
    return total, start, status, message, rows

def build_url(term: str, cdjournal: str, start: int) -> str:
    return API_BASE + "?" + urllib.parse.urlencode({
        "service": 3,
        "cdjournal": cdjournal,
        "text": term,
        "count": COUNT,
        "start": start,
    })

class Fetcher:
    def __init__(self, out: Path, refresh: bool = False):
        self.cache = out / "cache" / "api"
        self.cache.mkdir(parents=True, exist_ok=True)
        self.refresh = refresh
        self.records: list[dict[str, Any]] = []

    def get(self, url: str) -> tuple[bytes, str]:
        key = sha256_bytes(url.encode("utf-8"))
        bp = self.cache / f"{key}.xml"
        mp = self.cache / f"{key}.json"

        if not self.refresh and bp.exists() and mp.exists():
            body = bp.read_bytes()
            meta = json.loads(mp.read_text(encoding="utf-8"))
            if meta.get("url") == url and meta.get("sha256") == sha256_bytes(body):
                self.records.append({
                    "url": url,
                    "state": "cached_hash_verified",
                    "http_status": meta.get("http_status", ""),
                    "bytes": len(body),
                    "sha256": meta.get("sha256", ""),
                    "error": "",
                })
                return body, "cached_hash_verified"

        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                body = resp.read(8 * 1024 * 1024)
                status = getattr(resp, "status", 200)
            meta = {"url": url, "http_status": status, "sha256": sha256_bytes(body)}
            bp.write_bytes(body)
            mp.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            self.records.append({
                "url": url,
                "state": "fetched",
                "http_status": status,
                "bytes": len(body),
                "sha256": meta["sha256"],
                "error": "",
            })
            time.sleep(SLEEP_SECONDS)
            return body, "fetched"
        except urllib.error.HTTPError as e:
            self.records.append({
                "url": url,
                "state": "http_error",
                "http_status": e.code,
                "bytes": 0,
                "sha256": "",
                "error": f"{e.code} {e.reason}",
            })
            return b"", "http_error"
        except Exception as e:
            self.records.append({
                "url": url,
                "state": "network_error",
                "http_status": "",
                "bytes": 0,
                "sha256": "",
                "error": f"{type(e).__name__}: {e}",
            })
            return b"", "network_error"

def self_test() -> None:
    sample = '''<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
 xmlns:prism="http://prismstandard.org/namespaces/basic/2.0/"
 xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/">
 <result><status>0</status><message/></result>
 <opensearch:totalResults>1</opensearch:totalResults>
 <opensearch:startIndex>1</opensearch:startIndex>
 <entry>
  <article_title><ja>sample</ja><en/></article_title>
  <prism:doi>10.2183/tja1948.50.129</prism:doi>
 </entry>
</feed>'''.encode("utf-8")
    total, start, status, _, rows = parse_api(sample)
    assert total == 1 and start == 1 and status == "0"
    assert rows[0]["doi"] == "10.2183/tja1948.50.129"
    assert "第一部会員" in STRONG_TERMS and "第二部第七分科" in STRONG_TERMS
    assert "text=%E7%AC%AC%E4%B8%80%E9%83%A8%E4%BC%9A%E5%93%A1" in build_url("第一部会員", "tja1948", 1)
    print("SELF-TEST OK: strong section-relation terms and J-STAGE parser are consistent")

def run(candidate_path: Path, out: Path, refresh: bool = False) -> None:
    if not candidate_path.exists():
        raise FileNotFoundError(candidate_path)

    candidates = read_csv(candidate_path)
    if len(candidates) != 62:
        raise RuntimeError(f"Expected 62 unique candidate articles, found {len(candidates)}")

    by_doi = {r.get("doi", ""): r for r in candidates if r.get("doi")}
    out.mkdir(parents=True, exist_ok=True)
    fetcher = Fetcher(out, refresh=refresh)

    query_inventory: list[dict[str, Any]] = []
    intersections: dict[str, dict[str, Any]] = {}

    total_families = len(JOURNAL_CODES) * len(STRONG_TERMS)
    family_idx = 0
    started = time.monotonic()

    print(
        f"[start] candidate_articles={len(candidates)} strong_terms={len(STRONG_TERMS)} "
        f"journal_codes={len(JOURNAL_CODES)} query_families={total_families}",
        flush=True,
    )

    for cdjournal in JOURNAL_CODES:
        for term in STRONG_TERMS:
            family_idx += 1
            start = 1
            pages = 0
            family_total = None
            family_intersections = 0

            while pages < MAX_PAGES_PER_QUERY:
                pages += 1
                url = build_url(term, cdjournal, start)
                body, state = fetcher.get(url)

                total = 0
                status = ""
                message = ""
                rows: list[dict[str, str]] = []
                parse_error = ""

                if body:
                    try:
                        total, _, status, message, rows = parse_api(body)
                    except Exception as e:
                        parse_error = f"{type(e).__name__}: {e}"

                if family_total is None:
                    family_total = total

                page_intersections = 0
                for art in rows:
                    doi = art.get("doi", "")
                    if doi not in by_doi:
                        continue
                    page_intersections += 1
                    family_intersections += 1
                    c = by_doi[doi]
                    rec = intersections.setdefault(doi, {
                        "doi": doi,
                        "article_title_ja": c.get("article_title_ja", ""),
                        "article_url_ja": c.get("article_url_ja", ""),
                        "article_pdf_url": c.get("article_pdf_url", ""),
                        "retrieval_priority": c.get("retrieval_priority", ""),
                        "fetch_wave": c.get("fetch_wave", ""),
                        "target_members": c.get("target_members", ""),
                        "target_member_keys": c.get("target_member_keys", ""),
                        "matched_strong_terms": set(),
                        "matched_journal_codes": set(),
                        "api_match_rows": 0,
                    })
                    rec["matched_strong_terms"].add(term)
                    rec["matched_journal_codes"].add(cdjournal)
                    rec["api_match_rows"] += 1

                query_inventory.append({
                    "cdjournal": cdjournal,
                    "strong_term": term,
                    "page_number": pages,
                    "start": start,
                    "api_total": total,
                    "api_status": status,
                    "api_message": message,
                    "records_parsed": len(rows),
                    "candidate_intersections_on_page": page_intersections,
                    "retrieval_state": state,
                    "parse_error": parse_error,
                    "api_url": url,
                })

                if not body or parse_error or not rows or start + COUNT > total:
                    break
                start += COUNT

            print(
                "[progress] "
                f"family={family_idx}/{total_families} journal={cdjournal} term={term} "
                f"api_total={family_total if family_total is not None else 0} pages={pages} "
                f"candidate_intersections={family_intersections} "
                f"unique_articles_so_far={len(intersections)} "
                f"elapsed={time.monotonic()-started:.1f}s",
                flush=True,
            )

    rows_out: list[dict[str, Any]] = []
    for doi, rec in intersections.items():
        p1_closed = int(doi in P1_CLOSED_DOIS)
        rows_out.append({
            **{k: v for k, v in rec.items() if k not in {"matched_strong_terms", "matched_journal_codes"}},
            "matched_strong_terms": " | ".join(sorted(rec["matched_strong_terms"])),
            "matched_journal_codes": " | ".join(sorted(rec["matched_journal_codes"])),
            "p1_already_closed": p1_closed,
            "next_review_eligible": int(not p1_closed),
            "review_status": (
                "already_closed_in_p1"
                if p1_closed
                else "strong_section_relation_article_intersection_manual_review_required"
            ),
            "automatic_section_acceptance": 0,
            "final_roster_row_written": 0,
            "dob_collection_started": 0,
            "bazi_variables_computed": 0,
        })

    rows_out.sort(key=lambda r: (
        int(r["p1_already_closed"]),
        int(r.get("fetch_wave") or 9),
        str(r.get("doi") or ""),
    ))

    next_queue = [r for r in rows_out if r["next_review_eligible"] == 1]

    write_csv(out / "jstage_strong_section_intersection_candidates_v1.csv", rows_out)
    write_csv(out / "jstage_strong_section_next_review_queue_v1.csv", next_queue)
    write_csv(out / "strong_term_query_inventory_v1.csv", query_inventory)
    write_csv(out / "api_fetch_inventory_v1.csv", fetcher.records)

    summary = {
        "dataset": SCRIPT_VERSION,
        "source_snapshot_date": SOURCE_SNAPSHOT_DATE,
        "input_unique_candidate_articles": len(candidates),
        "journal_codes": list(JOURNAL_CODES),
        "strong_terms": list(STRONG_TERMS),
        "query_families_completed": total_families,
        "api_pages_fetched_or_cached": len(query_inventory),
        "fetch_state_counts": dict(sorted(Counter(r["state"] for r in fetcher.records).items())),
        "unique_candidate_articles_with_strong_relation_intersection": len(rows_out),
        "p1_already_closed_articles_in_strong_intersection": sum(r["p1_already_closed"] for r in rows_out),
        "next_review_queue_articles": len(next_queue),
        "next_review_queue_by_original_priority": dict(sorted(Counter(r["retrieval_priority"] for r in next_queue).items())),
        "unique_target_members_in_next_review_queue": len({
            key
            for r in next_queue
            for key in str(r.get("target_member_keys", "")).split(" | ")
            if key
        }),
        "decision_rule": (
            "Retrieval-only intersection using stronger section-relation phrases such as 第一部会員, 第二部所属, "
            "and explicit division/subsection phrases. A hit still does not prove that the phrase refers to the target person. "
            "No section assignment is made without manual review of the underlying source."
        ),
        "automatic_section_acceptance": 0,
        "direct_section_evidence_accepted": 0,
        "final_roster_rows_written": 0,
        "final_roster_frozen": 0,
        "dob_collection_started": 0,
        "bazi_variables_computed": 0,
        "input_sha256": {"jstage_unique_article_triage_v1": sha256_file(candidate_path)},
        "next_action": (
            "If the next-review queue is small, fetch only those PDFs and inspect exact name/section context. "
            "If it is empty or still non-informative, close the J-STAGE route and move to frozen Tier-B institutional web sources."
        ),
    }
    write_json(out / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidates", default=str(DEFAULT_CANDIDATES))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        self_test()
        return 0

    run(Path(args.candidates), Path(args.out), refresh=args.refresh)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
