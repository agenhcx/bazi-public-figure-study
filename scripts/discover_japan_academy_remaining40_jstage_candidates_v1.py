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

SCRIPT_VERSION = "japan-academy-remaining40-jstage-candidate-discovery-v1"
SOURCE_SNAPSHOT_DATE = "2026-10-16"
DEFAULT_INPUT = Path("data/japan_academy_remaining40_direct_evidence_queue_v1/remaining40_direct_evidence_queue_v1.csv")
DEFAULT_OUT = Path("data/japan_academy_remaining40_jstage_candidate_discovery_v1")

API_BASE = "https://api.jstage.jst.go.jp/searchapi/do"
JOURNAL_CODES = ("tja", "tja1948")
COUNT = 100
SLEEP_SECONDS = 0.35
PROGRESS_EVERY = 5
UA = "bazi-public-figure-study/1.0 (noncommercial research; Powered by J-STAGE)"
EXPECTED_MEMBERS = 40

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
    fields = list(rows[0].keys()) if rows else [
        "member_key","name_jp","name_en","cdjournal","query_text","api_total",
        "article_title_ja","article_title_en","article_url_ja","article_url_en",
        "authors_ja","authors_en","volume","issue","starting_page","ending_page",
        "pubyear","doi","candidate_status","automatic_acceptance",
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

def clean_name(name: str) -> str:
    return "".join(str(name or "").replace("　", " ").split())

def text_of(el: ET.Element | None) -> str:
    if el is None:
        return ""
    return " ".join("".join(el.itertext()).split())

def bilingual(entry: ET.Element, tag: str) -> tuple[str, str]:
    root = entry.find(f"atom:{tag}", NS)
    if root is None:
        return "", ""
    ja = text_of(root.find("atom:ja", NS))
    en = text_of(root.find("atom:en", NS))
    return ja, en

def bilingual_link(entry: ET.Element, tag: str) -> tuple[str, str]:
    root = entry.find(f"atom:{tag}", NS)
    if root is None:
        return "", ""
    ja = text_of(root.find("atom:ja", NS))
    en = text_of(root.find("atom:en", NS))
    return ja, en

def authors(entry: ET.Element) -> tuple[str, str]:
    ja: list[str] = []
    en: list[str] = []
    for a in entry.findall("atom:author", NS):
        ja_name = text_of(a.find("atom:ja/atom:name", NS))
        en_name = text_of(a.find("atom:en/atom:name", NS))
        if ja_name:
            ja.append(ja_name)
        if en_name:
            en.append(en_name)
    return " | ".join(ja), " | ".join(en)

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
        url_ja, url_en = bilingual_link(e, "article_link")
        a_ja, a_en = authors(e)
        if not (title_ja or title_en or url_ja or url_en):
            continue
        rows.append({
            "article_title_ja": title_ja,
            "article_title_en": title_en,
            "article_url_ja": url_ja,
            "article_url_en": url_en,
            "authors_ja": a_ja,
            "authors_en": a_en,
            "volume": text_of(e.find("prism:volume", NS)),
            "issue": text_of(e.find("prism:number", NS)),
            "starting_page": text_of(e.find("prism:startingPage", NS)),
            "ending_page": text_of(e.find("prism:endingPage", NS)),
            "pubyear": text_of(e.find("atom:pubyear", NS)),
            "doi": text_of(e.find("prism:doi", NS)),
        })
    return total, start, status, message, rows

def build_url(name: str, cdjournal: str) -> str:
    params = {
        "service": 3,
        "cdjournal": cdjournal,
        "text": clean_name(name),
        "count": COUNT,
        "start": 1,
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
        body_path = self.cache / f"{key}.xml"
        meta_path = self.cache / f"{key}.json"

        if not self.refresh and body_path.exists() and meta_path.exists():
            body = body_path.read_bytes()
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            if meta.get("url") == url and meta.get("sha256") == sha256_bytes(body):
                self.records.append({
                    "url": url,
                    "state": "cached_hash_verified",
                    "http_status": meta.get("http_status", ""),
                    "sha256": meta.get("sha256", ""),
                    "bytes": len(body),
                    "error": "",
                })
                return body, "cached_hash_verified"

        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                body = resp.read(8 * 1024 * 1024)
                status = getattr(resp, "status", 200)
            meta = {
                "url": url,
                "http_status": status,
                "sha256": sha256_bytes(body),
            }
            body_path.write_bytes(body)
            meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            self.records.append({
                "url": url,
                "state": "fetched",
                "http_status": status,
                "sha256": meta["sha256"],
                "bytes": len(body),
                "error": "",
            })
            time.sleep(SLEEP_SECONDS)
            return body, "fetched"
        except urllib.error.HTTPError as e:
            self.records.append({
                "url": url,
                "state": "http_error",
                "http_status": e.code,
                "sha256": "",
                "bytes": 0,
                "error": f"{e.code} {e.reason}",
            })
            return b"", "http_error"
        except Exception as e:
            self.records.append({
                "url": url,
                "state": "network_error",
                "http_status": "",
                "sha256": "",
                "bytes": 0,
                "error": f"{type(e).__name__}: {e}",
            })
            return b"", "network_error"

def self_test() -> None:
    sample = b'''<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
 xmlns:prism="http://prismstandard.org/namespaces/basic/2.0/"
 xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/">
 <result><status>0</status><message/></result>
 <opensearch:totalResults>1</opensearch:totalResults>
 <opensearch:startIndex>1</opensearch:startIndex>
 <entry>
  <article_title><ja>故都留重人会員追悼の辞</ja><en/></article_title>
  <article_link><ja>https://www.jstage.jst.go.jp/article/tja/61/1/x/_article/-char/ja/</ja><en/></article_link>
  <author><ja><name>山田 太郎</name></ja><en><name>Taro YAMADA</name></en></author>
  <prism:volume>61</prism:volume><prism:number>1</prism:number>
  <prism:startingPage>1</prism:startingPage><prism:endingPage>5</prism:endingPage>
  <pubyear>2007</pubyear><prism:doi>10.2183/tja.test</prism:doi>
 </entry>
</feed>'''
    total, start, status, message, rows = parse_api(sample)
    assert total == 1 and start == 1 and status == "0"
    assert rows[0]["article_title_ja"] == "故都留重人会員追悼の辞"
    assert rows[0]["authors_ja"] == "山田 太郎"
    assert clean_name("都留 重人") == "都留重人"
    assert "service=3" in build_url("都留 重人", "tja")
    print("SELF-TEST OK: J-STAGE API URL construction and Atom parsing are consistent")

def run(inp: Path, out: Path, refresh: bool = False, progress_every: int = PROGRESS_EVERY) -> None:
    if not inp.exists():
        raise FileNotFoundError(inp)
    members = read_csv(inp)
    if len(members) != EXPECTED_MEMBERS:
        raise RuntimeError(f"Expected {EXPECTED_MEMBERS} members, found {len(members)}")
    if progress_every < 1:
        raise ValueError("progress_every must be >= 1")

    out.mkdir(parents=True, exist_ok=True)
    fetcher = Fetcher(out, refresh=refresh)

    planned = len(members) * len(JOURNAL_CODES)
    print(
        f"[start] members={len(members)} journal_codes={len(JOURNAL_CODES)} "
        f"planned_queries={planned} progress_every={progress_every}",
        flush=True,
    )

    query_rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []
    qn = 0
    started = time.monotonic()

    for member in members:
        for cdjournal in JOURNAL_CODES:
            qn += 1
            name = member["name_jp"]
            url = build_url(name, cdjournal)
            body, state = fetcher.get(url)

            api_total = 0
            api_status = ""
            api_message = ""
            parsed_rows: list[dict[str, str]] = []
            parse_error = ""

            if body:
                try:
                    api_total, api_start, api_status, api_message, parsed_rows = parse_api(body)
                except Exception as e:
                    parse_error = f"{type(e).__name__}: {e}"

            query_rows.append({
                "member_key": member["member_key"],
                "name_jp": name,
                "name_en": member.get("name_en", ""),
                "cdjournal": cdjournal,
                "query_text": clean_name(name),
                "api_url": url,
                "retrieval_state": state,
                "api_total": api_total,
                "api_status": api_status,
                "api_message": api_message,
                "records_parsed": len(parsed_rows),
                "parse_error": parse_error,
                "automatic_acceptance": 0,
                "final_roster_row_written": 0,
                "dob_collection_started": 0,
                "bazi_variables_computed": 0,
            })

            for art in parsed_rows:
                candidate_rows.append({
                    "member_key": member["member_key"],
                    "name_jp": name,
                    "name_en": member.get("name_en", ""),
                    "degree_jp": member.get("degree_jp", ""),
                    "specialty_jp": member.get("specialty_jp", ""),
                    "cdjournal": cdjournal,
                    "query_text": clean_name(name),
                    "api_total": api_total,
                    **art,
                    "candidate_status": "jstage_fulltext_name_hit_review_required",
                    "article_pdf_url_guess": (
                        (art["article_url_ja"] or art["article_url_en"]).replace("/_article", "/_pdf")
                        if (art["article_url_ja"] or art["article_url_en"])
                        else ""
                    ),
                    "automatic_acceptance": 0,
                    "final_roster_row_written": 0,
                    "dob_collection_started": 0,
                    "bazi_variables_computed": 0,
                })

            if qn % progress_every == 0 or qn == planned:
                states = Counter(r["state"] for r in fetcher.records)
                member_hits = len({r["member_key"] for r in candidate_rows})
                print(
                    "[progress] "
                    f"queries={qn}/{planned} "
                    f"fetched={states.get('fetched',0)} cached={states.get('cached_hash_verified',0)} "
                    f"http_error={states.get('http_error',0)} network_error={states.get('network_error',0)} "
                    f"candidate_rows={len(candidate_rows)} members_with_candidates={member_hits} "
                    f"elapsed={time.monotonic()-started:.1f}s",
                    flush=True,
                )
                write_json(out / "progress.json", {
                    "dataset": SCRIPT_VERSION,
                    "run_status": "running" if qn < planned else "complete",
                    "queries_completed": qn,
                    "planned_queries": planned,
                    "fetch_state_counts": dict(sorted(states.items())),
                    "candidate_rows": len(candidate_rows),
                    "members_with_candidates": member_hits,
                    "elapsed_seconds": round(time.monotonic() - started, 1),
                })

    dedup: dict[tuple[str, str, str], dict[str, Any]] = {}
    for r in candidate_rows:
        key = (r["member_key"], r.get("doi",""), r.get("article_url_ja","") or r.get("article_url_en",""))
        dedup[key] = r
    candidate_rows = list(dedup.values())

    write_csv(out / "jstage_query_inventory_v1.csv", query_rows)
    write_csv(out / "jstage_article_candidates_v1.csv", candidate_rows)
    write_csv(out / "api_fetch_inventory_v1.csv", fetcher.records)

    summary = {
        "dataset": SCRIPT_VERSION,
        "source_snapshot_date": SOURCE_SNAPSHOT_DATE,
        "input_members": len(members),
        "journal_codes": list(JOURNAL_CODES),
        "planned_queries": planned,
        "queries_completed": len(query_rows),
        "fetch_state_counts": dict(sorted(Counter(r["state"] for r in fetcher.records).items())),
        "candidate_rows_after_dedup": len(candidate_rows),
        "members_with_any_jstage_candidate": len({r["member_key"] for r in candidate_rows}),
        "candidate_rows_by_journal_code": dict(sorted(Counter(r["cdjournal"] for r in candidate_rows).items())),
        "decision_rule": (
            "J-STAGE results are Tier-A publication leads only. "
            "A full-text name hit does not resolve Section I/II. "
            "Candidate article/PDF content must be fetched and manually reviewed for an explicit Japan Academy division/subsection statement."
        ),
        "powered_by": "Powered by J-STAGE",
        "direct_section_evidence_accepted": 0,
        "final_roster_rows_written": 0,
        "final_roster_frozen": 0,
        "dob_collection_started": 0,
        "bazi_variables_computed": 0,
        "input_sha256": {"remaining40_queue": sha256_file(inp)},
        "next_action": (
            "Review candidate articles; fetch only promising Japan Academy journal PDFs/pages "
            "and search them for explicit 第1部/第2部 or 第x部第y分科 statements referring to the exact target person."
        ),
    }
    write_json(out / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=str(DEFAULT_INPUT))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--progress-every", type=int, default=PROGRESS_EVERY)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        self_test()
        return 0

    run(
        Path(args.input),
        Path(args.out),
        refresh=args.refresh,
        progress_every=args.progress_every,
    )
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
