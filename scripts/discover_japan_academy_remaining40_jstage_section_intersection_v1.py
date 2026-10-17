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
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

SCRIPT_VERSION = "japan-academy-remaining40-jstage-section-intersection-v1"
SOURCE_SNAPSHOT_DATE = "2026-10-16"

DEFAULT_CANDIDATES = Path("data/japan_academy_remaining40_jstage_triage_v1/jstage_unique_article_triage_v1.csv")
DEFAULT_OUT = Path("data/japan_academy_remaining40_jstage_section_intersection_v1")

API_BASE = "https://api.jstage.jst.go.jp/searchapi/do"
JOURNAL_CODES = ("tja", "tja1948")
SECTION_TERMS = ("第一部", "第二部", "第1部", "第2部", "分科")
COUNT = 100
MAX_PAGES_PER_QUERY = 20
SLEEP_SECONDS = 0.30
UA = "bazi-public-figure-study/1.0 (noncommercial research; Powered by J-STAGE)"

NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "prism": "http://prismstandard.org/namespaces/basic/2.0/",
    "opensearch": "http://a9.com/-/spec/opensearch/1.1/",
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

def bilingual(entry: ET.Element, tag: str) -> tuple[str, str]:
    root = entry.find(f"atom:{tag}", NS)
    if root is None:
        return "", ""
    return text_of(root.find("atom:ja", NS)), text_of(root.find("atom:en", NS))

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
        title_ja, title_en = bilingual(e, "article_title")
        link_root = e.find("atom:article_link", NS)
        url_ja = text_of(link_root.find("atom:ja", NS)) if link_root is not None else ""
        url_en = text_of(link_root.find("atom:en", NS)) if link_root is not None else ""
        doi = text_of(e.find("prism:doi", NS))
        if not (title_ja or title_en or doi or url_ja or url_en):
            continue
        rows.append({
            "doi": doi,
            "article_title_ja": title_ja,
            "article_title_en": title_en,
            "article_url_ja": url_ja,
            "article_url_en": url_en,
        })
    return total, start, status, message, rows

def build_url(term: str, cdjournal: str, start: int) -> str:
    params = {
        "service": 3,
        "cdjournal": cdjournal,
        "text": term,
        "count": COUNT,
        "start": start,
    }
    return API_BASE + "?" + urllib.parse.urlencode(params)

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
  <article_title><ja>日本学士院百年の歩み</ja><en/></article_title>
  <article_link><ja>https://example.invalid/a</ja><en/></article_link>
  <prism:doi>10.2183/tja1948.36.suppl_1</prism:doi>
 </entry>
</feed>'''.encode("utf-8")
    total, start, status, _, rows = parse_api(sample)
    assert total == 1 and start == 1 and status == "0"
    assert rows[0]["doi"] == "10.2183/tja1948.36.suppl_1"
    assert "text=%E7%AC%AC%E4%B8%80%E9%83%A8" in build_url("第一部", "tja1948", 1)
    print("SELF-TEST OK: section-term J-STAGE pagination and parsing primitives are consistent")

def run(candidate_path: Path, out: Path, refresh: bool = False) -> None:
    if not candidate_path.exists():
        raise FileNotFoundError(candidate_path)

    candidates = read_csv(candidate_path)
    if len(candidates) != 62:
        raise RuntimeError(f"Expected 62 unique candidate articles, found {len(candidates)}")

    by_doi = {r.get("doi", ""): r for r in candidates if r.get("doi")}
    if not by_doi:
        raise RuntimeError("No DOI-bearing candidate articles")

    out.mkdir(parents=True, exist_ok=True)
    fetcher = Fetcher(out, refresh=refresh)

    query_inventory: list[dict[str, Any]] = []
    intersections: dict[str, dict[str, Any]] = {}
    total_query_families = len(JOURNAL_CODES) * len(SECTION_TERMS)
    family_idx = 0
    started = time.monotonic()

    print(
        f"[start] candidate_articles={len(candidates)} section_terms={len(SECTION_TERMS)} "
        f"journal_codes={len(JOURNAL_CODES)} query_families={total_query_families}",
        flush=True,
    )

    for cdjournal in JOURNAL_CODES:
        for term in SECTION_TERMS:
            family_idx += 1
            start = 1
            pages = 0
            family_total = None
            family_hits = 0

            while pages < MAX_PAGES_PER_QUERY:
                pages += 1
                url = build_url(term, cdjournal, start)
                body, state = fetcher.get(url)

                total = 0
                api_start = start
                api_status = ""
                api_message = ""
                rows: list[dict[str, str]] = []
                parse_error = ""

                if body:
                    try:
                        total, api_start, api_status, api_message, rows = parse_api(body)
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
                    family_hits += 1
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
                        "matched_section_terms": set(),
                        "matched_journal_codes": set(),
                        "api_match_rows": 0,
                        "automatic_section_acceptance": 0,
                        "final_roster_row_written": 0,
                        "dob_collection_started": 0,
                        "bazi_variables_computed": 0,
                    })
                    rec["matched_section_terms"].add(term)
                    rec["matched_journal_codes"].add(cdjournal)
                    rec["api_match_rows"] += 1

                query_inventory.append({
                    "cdjournal": cdjournal,
                    "section_term": term,
                    "page_number": pages,
                    "start": start,
                    "api_total": total,
                    "api_status": api_status,
                    "api_message": api_message,
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
                f"family={family_idx}/{total_query_families} journal={cdjournal} term={term} "
                f"api_total={family_total if family_total is not None else 0} "
                f"pages={pages} candidate_intersections={family_hits} "
                f"unique_candidate_articles_so_far={len(intersections)} "
                f"elapsed={time.monotonic()-started:.1f}s",
                flush=True,
            )

    intersection_rows: list[dict[str, Any]] = []
    for doi, r in intersections.items():
        rr = dict(r)
        rr["matched_section_terms"] = " | ".join(sorted(rr["matched_section_terms"]))
        rr["matched_journal_codes"] = " | ".join(sorted(rr["matched_journal_codes"]))
        rr["review_status"] = "section_term_and_target_name_article_intersection_manual_review_required"
        rr["automatic_section_acceptance"] = 0
        intersection_rows.append(rr)

    intersection_rows.sort(key=lambda r: (
        int(r.get("fetch_wave") or 9),
        str(r.get("doi") or ""),
    ))

    write_csv(out / "section_term_query_inventory_v1.csv", query_inventory)
    write_csv(out / "jstage_section_intersection_candidates_v1.csv", intersection_rows)
    write_csv(out / "api_fetch_inventory_v1.csv", fetcher.records)

    summary = {
        "dataset": SCRIPT_VERSION,
        "source_snapshot_date": SOURCE_SNAPSHOT_DATE,
        "input_unique_candidate_articles": len(candidates),
        "journal_codes": list(JOURNAL_CODES),
        "section_terms": list(SECTION_TERMS),
        "query_families_completed": total_query_families,
        "api_pages_fetched_or_cached": len(query_inventory),
        "fetch_state_counts": dict(sorted(Counter(r["state"] for r in fetcher.records).items())),
        "unique_candidate_articles_with_section_term_intersection": len(intersection_rows),
        "intersection_rows_by_original_priority": dict(sorted(Counter(r["retrieval_priority"] for r in intersection_rows).items())),
        "unique_target_members_covered": len({
            key
            for r in intersection_rows
            for key in str(r.get("target_member_keys", "")).split(" | ")
            if key
        }),
        "decision_rule": (
            "This is retrieval intersection only: the same J-STAGE article appeared in a target-name full-text search "
            "and in at least one section-term full-text search. It does not prove that the section term refers to the target person. "
            "Underlying article/PDF must be reviewed under the frozen explicit-source policy."
        ),
        "automatic_section_acceptance": 0,
        "direct_section_evidence_accepted": 0,
        "final_roster_rows_written": 0,
        "final_roster_frozen": 0,
        "dob_collection_started": 0,
        "bazi_variables_computed": 0,
        "input_sha256": {"jstage_unique_article_triage_v1": sha256_file(candidate_path)},
        "next_action": (
            "Fetch/review only the section-intersection article PDFs that have not already been closed out in P1. "
            "Preserve unresolved status unless the source directly binds the exact target person to Japan Academy Section I/II or subsection."
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
