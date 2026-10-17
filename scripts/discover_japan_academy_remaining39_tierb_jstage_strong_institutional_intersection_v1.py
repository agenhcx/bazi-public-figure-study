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

SCRIPT_VERSION = "japan-academy-remaining39-tierb-jstage-strong-institutional-intersection-v1"
SOURCE_SNAPSHOT_DATE = "2026-10-17"

DEFAULT_CANDIDATES = Path(
    "data/japan_academy_remaining39_tierb_jstage_institutional_discovery_v1/"
    "tierb_jstage_institutional_candidates_v1.csv"
)
DEFAULT_OUT = Path(
    "data/japan_academy_remaining39_tierb_jstage_strong_institutional_intersection_v1"
)

API_BASE = "https://api.jstage.jst.go.jp/searchapi/do"
EXPECTED_MEMBER_ARTICLE_ROWS = 50
EXPECTED_UNIQUE_ARTICLES = 34
EXPECTED_MEMBERS = 23
COUNT = 100
MAX_PAGES_PER_QUERY = 20
SLEEP_SECONDS = 0.30
RETRY_ATTEMPTS = 6
RETRY_BACKOFF_SECONDS = (2, 4, 8, 16, 24)
RETRIABLE_HTTP_CODES = {429, 500, 502, 503, 504}
UA = "bazi-public-figure-study/1.0 (noncommercial research; Powered by J-STAGE)"

# Institution-specific section/subsection phrases only.
# This is retrieval filtering, not section adjudication.
STRONG_TERMS = (
    "日本学士院第一部",
    "日本学士院第二部",
    "日本学士院第1部",
    "日本学士院第2部",
    "日本学士院第一部会員",
    "日本学士院第二部会員",
    "日本学士院第1部会員",
    "日本学士院第2部会員",
    "日本学士院第一部部長",
    "日本学士院第二部部長",
    "日本学士院第1部部長",
    "日本学士院第2部部長",
    "日本学士院第一分科",
    "日本学士院第二分科",
    "日本学士院第三分科",
    "日本学士院第四分科",
    "日本学士院第五分科",
    "日本学士院第六分科",
    "日本学士院第七分科",
    "日本学士院第1分科",
    "日本学士院第2分科",
    "日本学士院第3分科",
    "日本学士院第4分科",
    "日本学士院第5分科",
    "日本学士院第6分科",
    "日本学士院第7分科",
)

NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "prism": "http://prismstandard.org/namespaces/basic/2.0/",
    "opensearch": "http://a9.com/-/spec/opensearch/1.1/",
}

def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
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
        link_root = e.find("atom:article_link", NS)
        url_ja = text_of(link_root.find("atom:ja", NS)) if link_root is not None else ""
        url_en = text_of(link_root.find("atom:en", NS)) if link_root is not None else ""
        cdjournal = text_of(e.find("atom:cdjournal", NS))
        if doi or title_ja or title_en or url_ja or url_en:
            rows.append({
                "doi": doi,
                "article_title_ja": title_ja,
                "article_title_en": title_en,
                "article_url_ja": url_ja,
                "article_url_en": url_en,
                "cdjournal": cdjournal,
            })
    return total, start, status, message, rows

def build_url(term: str, start: int) -> str:
    params = {
        "service": 3,
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
                    "attempts": 0,
                    "retry_errors": "",
                    "error": "",
                })
                return body, "cached_hash_verified"

        retry_errors: list[str] = []
        for attempt in range(1, RETRY_ATTEMPTS + 1):
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            try:
                with urllib.request.urlopen(req, timeout=45) as resp:
                    body = resp.read(8 * 1024 * 1024)
                    status = getattr(resp, "status", 200)
                meta = {"url": url, "http_status": status, "sha256": sha256_bytes(body)}
                bp.write_bytes(body)
                mp.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                state = "fetched" if attempt == 1 else "fetched_after_retry"
                self.records.append({
                    "url": url,
                    "state": state,
                    "http_status": status,
                    "bytes": len(body),
                    "sha256": meta["sha256"],
                    "attempts": attempt,
                    "retry_errors": " | ".join(retry_errors),
                    "error": "",
                })
                time.sleep(SLEEP_SECONDS)
                return body, state
            except urllib.error.HTTPError as e:
                msg = f"attempt={attempt}: HTTPError {e.code} {e.reason}"
                retry_errors.append(msg)
                if e.code not in RETRIABLE_HTTP_CODES or attempt >= RETRY_ATTEMPTS:
                    self.records.append({
                        "url": url,
                        "state": "http_error",
                        "http_status": e.code,
                        "bytes": 0,
                        "sha256": "",
                        "attempts": attempt,
                        "retry_errors": " | ".join(retry_errors),
                        "error": f"{e.code} {e.reason}",
                    })
                    return b"", "http_error"
            except Exception as e:
                msg = f"attempt={attempt}: {type(e).__name__}: {e}"
                retry_errors.append(msg)
                if attempt >= RETRY_ATTEMPTS:
                    self.records.append({
                        "url": url,
                        "state": "network_error",
                        "http_status": "",
                        "bytes": 0,
                        "sha256": "",
                        "attempts": attempt,
                        "retry_errors": " | ".join(retry_errors),
                        "error": f"{type(e).__name__}: {e}",
                    })
                    return b"", "network_error"

            delay = RETRY_BACKOFF_SECONDS[min(attempt - 1, len(RETRY_BACKOFF_SECONDS) - 1)]
            print(
                f"[retry] attempt={attempt}/{RETRY_ATTEMPTS} delay={delay}s url={url} "
                f"last_error={retry_errors[-1]}",
                flush=True,
            )
            time.sleep(delay)

        raise RuntimeError("unreachable retry loop exit")

def self_test() -> None:
    sample = '''<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
 xmlns:prism="http://prismstandard.org/namespaces/basic/2.0/"
 xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/">
 <result><status>0</status><message/></result>
 <opensearch:totalResults>1</opensearch:totalResults>
 <opensearch:startIndex>1</opensearch:startIndex>
 <entry>
  <article_title><ja>平塚直秀先生を悼む</ja><en/></article_title>
  <article_link><ja>https://example.invalid/a</ja><en/></article_link>
  <cdjournal>jjom</cdjournal>
  <prism:doi>10.example/hiratsuka</prism:doi>
 </entry>
</feed>'''.encode("utf-8")
    total, start, status, _, rows = parse_api(sample)
    assert total == 1 and start == 1 and status == "0"
    assert rows[0]["cdjournal"] == "jjom"
    assert "日本学士院第二部部長" in STRONG_TERMS
    assert "日本学士院第六分科" in STRONG_TERMS
    assert 502 in RETRIABLE_HTTP_CODES and RETRY_ATTEMPTS >= 2
    u = build_url("日本学士院第二部", 1)
    assert "%E6%97%A5%E6%9C%AC%E5%AD%A6%E5%A3%AB%E9%99%A2%E7%AC%AC%E4%BA%8C%E9%83%A8" in u
    print("SELF-TEST OK: Tier-B strong institutional phrases and J-STAGE parser are consistent")

def run(candidate_path: Path, out: Path, refresh: bool = False) -> None:
    if not candidate_path.exists():
        raise FileNotFoundError(candidate_path)

    member_article_rows = read_csv(candidate_path)
    if len(member_article_rows) != EXPECTED_MEMBER_ARTICLE_ROWS:
        raise RuntimeError(
            f"Expected {EXPECTED_MEMBER_ARTICLE_ROWS} member-article rows, found {len(member_article_rows)}"
        )

    unique_members = {r.get("member_key", "") for r in member_article_rows if r.get("member_key")}
    if len(unique_members) != EXPECTED_MEMBERS:
        raise RuntimeError(f"Expected {EXPECTED_MEMBERS} members, found {len(unique_members)}")

    # DOI-level article inventory, retaining all target members mapped to each article.
    by_doi_rows: dict[str, list[dict[str, str]]] = defaultdict(list)
    for r in member_article_rows:
        doi = str(r.get("doi", "") or "").strip()
        if not doi:
            raise RuntimeError("Candidate row without DOI")
        by_doi_rows[doi].append(r)

    if len(by_doi_rows) != EXPECTED_UNIQUE_ARTICLES:
        raise RuntimeError(
            f"Expected {EXPECTED_UNIQUE_ARTICLES} unique DOI articles, found {len(by_doi_rows)}"
        )

    article_meta: dict[str, dict[str, Any]] = {}
    for doi, rows in by_doi_rows.items():
        first = rows[0]
        article_meta[doi] = {
            "doi": doi,
            "cdjournal": first.get("cdjournal", ""),
            "article_title_ja": first.get("article_title_ja", ""),
            "article_title_en": first.get("article_title_en", ""),
            "article_url_ja": first.get("article_url_ja", ""),
            "article_url_en": first.get("article_url_en", ""),
            "journal_title_ja": first.get("journal_title_ja", ""),
            "journal_title_en": first.get("journal_title_en", ""),
            "authors_ja": first.get("authors_ja", ""),
            "authors_en": first.get("authors_en", ""),
            "pubyear": first.get("pubyear", ""),
            "target_member_keys": " | ".join(sorted({r.get("member_key", "") for r in rows if r.get("member_key")})),
            "target_members": " | ".join(sorted({r.get("name_jp", "") for r in rows if r.get("name_jp")})),
            "n_target_members": len({r.get("member_key", "") for r in rows if r.get("member_key")}),
        }

    out.mkdir(parents=True, exist_ok=True)
    fetcher = Fetcher(out, refresh=refresh)

    total_families = len(STRONG_TERMS)
    started = time.monotonic()
    query_inventory: list[dict[str, Any]] = []
    intersections: dict[str, dict[str, Any]] = {}

    print(
        f"[start] candidate_articles={len(article_meta)} strong_terms={len(STRONG_TERMS)} "
        f"query_families={total_families}",
        flush=True,
    )

    for family_idx, term in enumerate(STRONG_TERMS, start=1):
        start = 1
        pages = 0
        family_total = None
        family_intersections = 0

        while pages < MAX_PAGES_PER_QUERY:
            pages += 1
            url = build_url(term, start)
            body, state = fetcher.get(url)

            total = 0
            api_status = ""
            api_message = ""
            rows: list[dict[str, str]] = []
            parse_error = ""

            if body:
                try:
                    total, _, api_status, api_message, rows = parse_api(body)
                except Exception as e:
                    parse_error = f"{type(e).__name__}: {e}"

            if family_total is None:
                family_total = total

            page_intersections = 0
            for art in rows:
                doi = art.get("doi", "")
                if doi not in article_meta:
                    continue
                page_intersections += 1
                family_intersections += 1
                meta = article_meta[doi]
                rec = intersections.setdefault(doi, {
                    **meta,
                    "matched_strong_terms": set(),
                    "api_match_rows": 0,
                })
                rec["matched_strong_terms"].add(term)
                rec["api_match_rows"] += 1

            query_inventory.append({
                "strong_term": term,
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
            f"family={family_idx}/{total_families} term={term} "
            f"api_total={family_total if family_total is not None else 0} "
            f"pages={pages} candidate_intersections={family_intersections} "
            f"unique_articles_so_far={len(intersections)} "
            f"elapsed={time.monotonic()-started:.1f}s",
            flush=True,
        )

    rows_out: list[dict[str, Any]] = []
    for doi, rec in intersections.items():
        rr = dict(rec)
        rr["matched_strong_terms"] = " | ".join(sorted(rr["matched_strong_terms"]))
        rr["review_status"] = "tier_b_strong_institutional_phrase_intersection_manual_review_required"
        rr["automatic_section_acceptance"] = 0
        rr["direct_section_evidence_accepted"] = 0
        rr["final_roster_row_written"] = 0
        rr["dob_collection_started"] = 0
        rr["bazi_variables_computed"] = 0
        rows_out.append(rr)

    rows_out.sort(key=lambda r: (
        -int(r["n_target_members"]),
        str(r.get("pubyear", "")),
        str(r.get("doi", "")),
    ))

    write_csv(out / "tierb_strong_institutional_intersection_candidates_v1.csv", rows_out)
    write_csv(out / "strong_term_query_inventory_v1.csv", query_inventory)
    write_csv(out / "api_fetch_inventory_v1.csv", fetcher.records)

    summary = {
        "dataset": SCRIPT_VERSION,
        "source_snapshot_date": SOURCE_SNAPSHOT_DATE,
        "input_member_article_rows": len(member_article_rows),
        "input_unique_articles": len(article_meta),
        "input_members_with_candidates": len(unique_members),
        "strong_terms": list(STRONG_TERMS),
        "query_families_completed": total_families,
        "api_pages_fetched_or_cached": len(query_inventory),
        "fetch_state_counts": dict(sorted(Counter(r["state"] for r in fetcher.records).items())),
        "retrieval_complete": int(not any(r["state"] in {"http_error", "network_error"} for r in fetcher.records)),
        "failed_query_pages": sum(r["state"] in {"http_error", "network_error"} for r in fetcher.records),
        "queries_recovered_after_retry": sum(r["state"] == "fetched_after_retry" for r in fetcher.records),
        "unique_candidate_articles_with_strong_institutional_phrase": len(rows_out),
        "unique_target_members_covered": len({
            key
            for r in rows_out
            for key in str(r.get("target_member_keys", "")).split(" | ")
            if key
        }),
        "matched_candidate_journal_codes": dict(sorted(Counter(r.get("cdjournal", "") for r in rows_out).items())),
        "decision_rule": (
            "Retrieval-only DOI intersection. A candidate article must already be in the remaining-39 non-Academy J-STAGE "
            "candidate set and must also match an institution-specific phrase such as 日本学士院第二部, "
            "日本学士院第二部部長, or 日本学士院第六分科. "
            "This does not prove that the phrase refers to a target person; manual source review remains mandatory."
        ),
        "automatic_section_acceptance": 0,
        "direct_section_evidence_accepted": 0,
        "final_roster_rows_written": 0,
        "final_roster_frozen": 0,
        "dob_collection_started": 0,
        "bazi_variables_computed": 0,
        "input_sha256": {
            "tierb_jstage_institutional_candidates_v1": sha256_file(candidate_path),
        },
        "next_action": (
            "First require retrieval_complete=1. If any query pages still fail, rerun without --refresh so successful cache entries are reused "
            "and only failed requests are retried. Once complete, fetch only the small intersection PDF queue and inspect exact "
            "target-name/section wording. Preserve unresolved status unless the source directly binds the target person to "
            "Japan Academy Section I/II or a subsection."
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
