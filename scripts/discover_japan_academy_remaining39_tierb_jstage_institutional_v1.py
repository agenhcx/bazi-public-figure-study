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

SCRIPT_VERSION = "japan-academy-remaining39-tierb-jstage-institutional-discovery-v1"
SOURCE_SNAPSHOT_DATE = "2026-10-17"

DEFAULT_REMAINING = Path("data/japan_academy_remaining40_direct_evidence_queue_v1/remaining40_direct_evidence_queue_v1.csv")
DEFAULT_HIRATSUKA = Path("data/japan_academy_remaining40_tierb_hiratsuka_adjudication_v1/accepted_direct_section_evidence_v1.csv")
DEFAULT_OUT = Path("data/japan_academy_remaining39_tierb_jstage_institutional_discovery_v1")

API_BASE = "https://api.jstage.jst.go.jp/searchapi/do"
SECTION_TERMS = ("第一部", "第二部", "第1部", "第2部", "分科")
EXCLUDED_JOURNAL_CODES = {"tja", "tja1948"}
EXPECTED_INPUT = 40
EXPECTED_RESOLVED = 1
EXPECTED_SEARCH_TARGETS = 39
COUNT = 100
MAX_PAGES_PER_QUERY = 5
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

def clean_name(name: str) -> str:
    return "".join(str(name or "").replace("　", " ").split())

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
        title_root = e.find("atom:article_title", NS)
        title_ja = text_of(title_root.find("atom:ja", NS)) if title_root is not None else ""
        title_en = text_of(title_root.find("atom:en", NS)) if title_root is not None else ""
        link_root = e.find("atom:article_link", NS)
        url_ja = text_of(link_root.find("atom:ja", NS)) if link_root is not None else ""
        url_en = text_of(link_root.find("atom:en", NS)) if link_root is not None else ""
        material_root = e.find("atom:material_title", NS)
        journal_ja = text_of(material_root.find("atom:ja", NS)) if material_root is not None else ""
        journal_en = text_of(material_root.find("atom:en", NS)) if material_root is not None else ""
        cdjournal = text_of(e.find("atom:cdjournal", NS))
        doi = text_of(e.find("prism:doi", NS))
        pubyear = text_of(e.find("atom:pubyear", NS))

        authors_ja: list[str] = []
        authors_en: list[str] = []
        for a in e.findall("atom:author", NS):
            ja = text_of(a.find("atom:ja/atom:name", NS))
            en = text_of(a.find("atom:en/atom:name", NS))
            if ja:
                authors_ja.append(ja)
            if en:
                authors_en.append(en)

        if not (title_ja or title_en or doi or url_ja or url_en):
            continue

        rows.append({
            "doi": doi,
            "cdjournal": cdjournal,
            "article_title_ja": title_ja,
            "article_title_en": title_en,
            "article_url_ja": url_ja,
            "article_url_en": url_en,
            "journal_title_ja": journal_ja,
            "journal_title_en": journal_en,
            "authors_ja": " | ".join(authors_ja),
            "authors_en": " | ".join(authors_en),
            "pubyear": pubyear,
        })
    return total, start, status, message, rows

def build_url(name: str, section_term: str, start: int) -> str:
    query = f"{clean_name(name)} 日本学士院 {section_term}"
    params = {
        "service": 3,
        "text": query,
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
  <article_title><ja>平塚直秀先生を悼む</ja><en/></article_title>
  <article_link><ja>https://www.jstage.jst.go.jp/article/jjom/41/4/x/_article/-char/ja/</ja><en/></article_link>
  <material_title><ja>日本菌学会会報</ja><en/></material_title>
  <cdjournal>jjom</cdjournal>
  <pubyear>2000</pubyear>
  <prism:doi>10.example/hiratsuka</prism:doi>
 </entry>
</feed>'''.encode("utf-8")
    total, start, status, _, rows = parse_api(sample)
    assert total == 1 and start == 1 and status == "0"
    assert rows[0]["cdjournal"] == "jjom"
    assert "tja" in EXCLUDED_JOURNAL_CODES and "jjom" not in EXCLUDED_JOURNAL_CODES
    u = build_url("岡田 正弘", "第二部", 1)
    assert "%E6%97%A5%E6%9C%AC%E5%AD%A6%E5%A3%AB%E9%99%A2" in u
    print("SELF-TEST OK: Tier-B J-STAGE institutional discovery parsing and exclusion rules are consistent")

def run(remaining_path: Path, hiratsuka_path: Path, out: Path, refresh: bool = False) -> None:
    for p in (remaining_path, hiratsuka_path):
        if not p.exists():
            raise FileNotFoundError(p)

    remaining = read_csv(remaining_path)
    accepted = read_csv(hiratsuka_path)

    if len(remaining) != EXPECTED_INPUT:
        raise RuntimeError(f"Expected {EXPECTED_INPUT} input rows, found {len(remaining)}")
    if len(accepted) != EXPECTED_RESOLVED:
        raise RuntimeError(f"Expected {EXPECTED_RESOLVED} accepted Tier-B row, found {len(accepted)}")

    resolved_keys = {r.get("member_key", "") for r in accepted}
    targets = [r for r in remaining if r.get("member_key", "") not in resolved_keys]
    if len(targets) != EXPECTED_SEARCH_TARGETS:
        raise RuntimeError(f"Expected {EXPECTED_SEARCH_TARGETS} remaining search targets, found {len(targets)}")

    out.mkdir(parents=True, exist_ok=True)
    fetcher = Fetcher(out, refresh=refresh)

    total_families = len(targets) * len(SECTION_TERMS)
    family_idx = 0
    started = time.monotonic()
    query_inventory: list[dict[str, Any]] = []
    raw_candidates: list[dict[str, Any]] = []

    print(
        f"[start] remaining_targets={len(targets)} section_terms={len(SECTION_TERMS)} "
        f"query_families={total_families} excluded_journals={sorted(EXCLUDED_JOURNAL_CODES)}",
        flush=True,
    )

    for member_idx, member in enumerate(targets, start=1):
        name = member["name_jp"]

        for term in SECTION_TERMS:
            family_idx += 1
            start = 1
            pages = 0
            family_total = None
            kept = 0

            while pages < MAX_PAGES_PER_QUERY:
                pages += 1
                url = build_url(name, term, start)
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

                page_kept = 0
                for art in rows:
                    if art.get("cdjournal", "") in EXCLUDED_JOURNAL_CODES:
                        continue
                    page_kept += 1
                    kept += 1
                    raw_candidates.append({
                        "member_key": member["member_key"],
                        "name_jp": name,
                        "name_en": member.get("name_en", ""),
                        "matched_section_term": term,
                        "query_text": f"{clean_name(name)} 日本学士院 {term}",
                        **art,
                        "candidate_source_class": "non_Japan_Academy_J_STAGE_publication",
                        "candidate_status": "tier_b_institutional_candidate_manual_source_review_required",
                        "automatic_section_acceptance": 0,
                        "final_roster_row_written": 0,
                        "dob_collection_started": 0,
                        "bazi_variables_computed": 0,
                    })

                query_inventory.append({
                    "member_key": member["member_key"],
                    "name_jp": name,
                    "section_term": term,
                    "page_number": pages,
                    "start": start,
                    "api_total": total,
                    "api_status": api_status,
                    "api_message": api_message,
                    "records_parsed": len(rows),
                    "non_academy_journal_candidates_on_page": page_kept,
                    "retrieval_state": state,
                    "parse_error": parse_error,
                    "api_url": url,
                })

                if not body or parse_error or not rows or start + COUNT > total:
                    break
                start += COUNT

            print(
                "[progress] "
                f"member={member_idx}/{len(targets)} name={name} "
                f"family={family_idx}/{total_families} term={term} "
                f"api_total={family_total if family_total is not None else 0} "
                f"kept_non_academy={kept} unique_candidates_so_far={len(raw_candidates)} "
                f"elapsed={time.monotonic()-started:.1f}s",
                flush=True,
            )

    # Deduplicate same article for same member across synonymous section terms.
    dedup: dict[tuple[str, str, str], dict[str, Any]] = {}
    term_sets: dict[tuple[str, str, str], set[str]] = {}

    for r in raw_candidates:
        key = (
            r["member_key"],
            r.get("doi", ""),
            r.get("article_url_ja", "") or r.get("article_url_en", ""),
        )
        if key not in dedup:
            dedup[key] = dict(r)
            term_sets[key] = set()
        term_sets[key].add(r["matched_section_term"])

    candidates: list[dict[str, Any]] = []
    for key, r in dedup.items():
        r["matched_section_terms"] = " | ".join(sorted(term_sets[key]))
        r.pop("matched_section_term", None)
        candidates.append(r)

    candidates.sort(key=lambda r: (
        r["name_jp"],
        r.get("pubyear", ""),
        r.get("journal_title_ja", ""),
        r.get("doi", ""),
    ))

    write_csv(out / "tierb_jstage_institutional_candidates_v1.csv", candidates)
    write_csv(out / "tierb_jstage_query_inventory_v1.csv", query_inventory)
    write_csv(out / "api_fetch_inventory_v1.csv", fetcher.records)

    summary = {
        "dataset": SCRIPT_VERSION,
        "source_snapshot_date": SOURCE_SNAPSHOT_DATE,
        "input_remaining40_rows": len(remaining),
        "already_resolved_tier_b_members": len(resolved_keys),
        "search_targets": len(targets),
        "section_terms": list(SECTION_TERMS),
        "query_families_completed": total_families,
        "api_pages_fetched_or_cached": len(query_inventory),
        "fetch_state_counts": dict(sorted(Counter(r["state"] for r in fetcher.records).items())),
        "raw_non_academy_jstage_candidate_rows": len(raw_candidates),
        "deduplicated_member_article_candidates": len(candidates),
        "members_with_any_tier_b_jstage_candidate": len({r["member_key"] for r in candidates}),
        "candidate_journal_codes": dict(sorted(Counter(r.get("cdjournal", "") for r in candidates).items())),
        "decision_rule": (
            "Discovery only. Results must be from non-Japan-Academy J-STAGE journals and matched by target name, "
            "日本学士院, and a section/subsection term in the API full-text query. "
            "A hit is not automatically Tier-B acceptable evidence; the underlying publication and issuing organization "
            "must be reviewed against the frozen source policy, and the exact text must directly bind the target person "
            "to Japan Academy Section I/II or a subsection."
        ),
        "automatic_section_acceptance": 0,
        "direct_section_evidence_accepted": 0,
        "final_roster_rows_written": 0,
        "final_roster_frozen": 0,
        "dob_collection_started": 0,
        "bazi_variables_computed": 0,
        "input_sha256": {
            "remaining40_direct_evidence_queue_v1": sha256_file(remaining_path),
            "accepted_hiratsuka_tier_b_evidence_v1": sha256_file(hiratsuka_path),
        },
        "next_action": (
            "Review the deduplicated candidate journals and article titles. "
            "Fetch only promising academic-society/institutional publications, preserve source hashes, "
            "and adjudicate direct person-section wording manually."
        ),
    }
    write_json(out / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--remaining", default=str(DEFAULT_REMAINING))
    ap.add_argument("--hiratsuka", default=str(DEFAULT_HIRATSUKA))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        self_test()
        return 0

    run(Path(args.remaining), Path(args.hiratsuka), Path(args.out), refresh=args.refresh)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
