#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from collections import Counter, deque
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

SCRIPT_VERSION = "japan-academy-remaining40-official-html-discovery-v1"
SNAPSHOT_DATE = "2026-10-15"
BASE = "https://www.japan-acad.go.jp"
DEFAULT_INPUT = Path("data/japan_academy_remaining40_direct_evidence_queue_v1/remaining40_direct_evidence_queue_v1.csv")
DEFAULT_OUT = Path("data/japan_academy_remaining40_official_html_discovery_v1")
UA = "bazi-public-figure-study/1.0 (Japan Academy remaining-40 official evidence discovery; no DOB/BaZi computation)"
SLEEP = 0.20
MAX_PAGES = 1400
DEFAULT_PROGRESS_EVERY = 20
ROBOTS_TIMEOUT = 15

SEEDS = [
    f"{BASE}/japanese/sitemap/index.html",
    f"{BASE}/japanese/members/index.html",
    f"{BASE}/japanese/members/bukko_members_index.html",
    f"{BASE}/japanese/publishing/transactions.html",
    f"{BASE}/japanese/publishing/transcont/old_list.html",
    f"{BASE}/japanese/publishing/newsletter.html",
    f"{BASE}/japanese/publishing/other.html",
    f"{BASE}/japanese/activities/kouen/index.html",
    f"{BASE}/japanese/activities/jyusho/index.html",
]
ALLOWED_PREFIXES = (
    "/japanese/members/",
    "/japanese/publishing/",
    "/japanese/activities/",
    "/japanese/news/",
    "/pdf/newsletter/",
)
SECTION_RE = re.compile(r"第\s*([12])\s*部(?:\s*第\s*([1-7])\s*分科)?")
PDF_RE = re.compile(r"\.pdf(?:$|[?#])", re.I)

def norm_name(s: str) -> str:
    return re.sub(r"[\s　・･]+", "", html.unescape(str(s or "")))

def norm_text(s: str) -> str:
    return " ".join(html.unescape(str(s or "")).replace("\u3000", " ").split())

def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

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

class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self._href = ""
        self._anchor: list[str] = []
        self._stack: list[tuple[str, list[str]]] = []
        self.blocks: list[tuple[str, str]] = []
        self.all_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        d = dict(attrs)
        if tag == "a":
            self._href = d.get("href") or ""
            self._anchor = []
        if tag in {"tr", "li", "p", "dd", "dt", "section", "article", "h1", "h2", "h3", "h4"}:
            self._stack.append((tag, []))

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._href:
            label = norm_text(" ".join(self._anchor))
            self.links.append((self._href, label))
            self._href = ""
            self._anchor = []
        if self._stack and self._stack[-1][0] == tag:
            t, chunks = self._stack.pop()
            txt = norm_text(" ".join(chunks))
            if txt:
                self.blocks.append((t, txt))

    def handle_data(self, data: str) -> None:
        if data:
            self.all_text.append(data)
            if self._href:
                self._anchor.append(data)
            for i in range(len(self._stack)):
                self._stack[i][1].append(data)

def canonical_url(href: str, base: str) -> str:
    u = urllib.parse.urljoin(base, href)
    p = urllib.parse.urlsplit(u)
    if p.scheme not in {"http", "https"}:
        return ""
    if p.netloc.lower() != "www.japan-acad.go.jp":
        return ""
    path = re.sub(r"/+", "/", p.path)
    return urllib.parse.urlunsplit(("https", p.netloc.lower(), path, p.query, ""))

def allowed_url(url: str) -> bool:
    p = urllib.parse.urlsplit(url)
    return p.netloc.lower() == "www.japan-acad.go.jp" and any(p.path.startswith(x) for x in ALLOWED_PREFIXES)

class Fetcher:
    def __init__(self, out: Path, refresh: bool = False):
        self.cache = out / "cache"
        self.cache.mkdir(parents=True, exist_ok=True)
        self.refresh = refresh
        self.records: list[dict[str, Any]] = []
        self.rp = urllib.robotparser.RobotFileParser()
        robots_url = f"{BASE}/robots.txt"
        self.rp.set_url(robots_url)
        print(f"[startup] loading robots.txt timeout={ROBOTS_TIMEOUT}s url={robots_url}", flush=True)
        try:
            req = urllib.request.Request(robots_url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=ROBOTS_TIMEOUT) as resp:
                robots_body = resp.read(512 * 1024)
            self.rp.parse(robots_body.decode("utf-8", errors="replace").splitlines())
            self.robots_state = "loaded"
            print(f"[startup] robots.txt loaded bytes={len(robots_body)}", flush=True)
        except Exception as e:
            self.robots_state = "unavailable"
            print(
                f"[startup] robots.txt unavailable: {type(e).__name__}: {e}; "
                "continuing with same-origin crawl",
                flush=True,
            )

    def get(self, url: str) -> tuple[bytes, str, str]:
        key = sha256_bytes(url.encode("utf-8"))
        bp = self.cache / f"{key}.body"
        mp = self.cache / f"{key}.json"
        if not self.refresh and bp.exists() and mp.exists():
            meta = json.loads(mp.read_text(encoding="utf-8"))
            b = bp.read_bytes()
            if meta.get("url") == url and meta.get("sha256") == sha256_bytes(b):
                self.records.append({"url": url, "state": "cached_hash_verified", "http_status": meta.get("http_status",""), "content_type": meta.get("content_type",""), "sha256": meta["sha256"], "bytes": len(b), "error": ""})
                return b, meta.get("content_type",""), "cached_hash_verified"

        if self.robots_state == "loaded" and not self.rp.can_fetch(UA, url):
            self.records.append({"url": url, "state": "robots_disallowed", "http_status": "", "content_type": "", "sha256": "", "bytes": 0, "error": ""})
            return b"", "", "robots_disallowed"

        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=45) as r:
                b = r.read(8 * 1024 * 1024)
                ctype = r.headers.get("Content-Type", "")
                status = getattr(r, "status", 200)
            meta = {"url": url, "http_status": status, "content_type": ctype, "sha256": sha256_bytes(b)}
            bp.write_bytes(b)
            mp.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            self.records.append({"url": url, "state": "fetched", "http_status": status, "content_type": ctype, "sha256": meta["sha256"], "bytes": len(b), "error": ""})
            time.sleep(SLEEP)
            return b, ctype, "fetched"
        except urllib.error.HTTPError as e:
            self.records.append({"url": url, "state": "http_error", "http_status": e.code, "content_type": e.headers.get("Content-Type",""), "sha256": "", "bytes": 0, "error": f"{e.code} {e.reason}"})
            return b"", "", "http_error"
        except Exception as e:
            self.records.append({"url": url, "state": "network_error", "http_status": "", "content_type": "", "sha256": "", "bytes": 0, "error": f"{type(e).__name__}: {e}"})
            return b"", "", "network_error"

def name_occurs(text: str, name_jp: str) -> bool:
    return norm_name(name_jp) in norm_name(text)

def explicit_sections(text: str) -> list[tuple[str, str]]:
    out = []
    for m in SECTION_RE.finditer(text):
        out.append((m.group(1), m.group(2) or ""))
    return out

def self_test() -> None:
    p = PageParser()
    p.feed('<table><tr><td>第1部第2分科</td><td>辻 清明</td></tr><tr><td>第2部</td><td>山田 太郎</td></tr></table>')
    hits = [(tag, txt) for tag, txt in p.blocks if name_occurs(txt, "辻 清明")]
    assert hits and explicit_sections(hits[0][1]) == [("1","2")]
    assert norm_name("辻 清明") == "辻清明"
    assert canonical_url("../publishing/transactions.html", f"{BASE}/japanese/members/index.html").startswith(BASE)
    print("SELF-TEST OK: official-site parsing, name normalization, section extraction, and URL canonicalization are consistent")

def run(inp: Path, out: Path, refresh: bool = False, max_pages: int = MAX_PAGES, progress_every: int = DEFAULT_PROGRESS_EVERY) -> None:
    if not inp.exists():
        raise FileNotFoundError(inp)
    members = read_csv(inp)
    if len(members) != 40:
        raise RuntimeError(f"Expected 40 members, found {len(members)}")

    if progress_every < 1:
        raise ValueError("progress_every must be >= 1")

    out.mkdir(parents=True, exist_ok=True)
    targets = {r["member_key"]: r for r in members}
    print(
        f"[startup] targets={len(members)} max_pages={max_pages} "
        f"progress_every={progress_every} output={out}",
        flush=True,
    )
    fetcher = Fetcher(out, refresh=refresh)
    q = deque(SEEDS + sorted({r.get("official_index_url","") for r in members if r.get("official_index_url")}))
    seen: set[str] = set()
    page_hits: list[dict[str, Any]] = []
    explicit: list[dict[str, Any]] = []
    pdf_links: list[dict[str, Any]] = []
    started = time.monotonic()
    last_reported = 0

    def emit_progress(force: bool = False) -> None:
        nonlocal last_reported
        visited = len(seen)
        if not force and visited - last_reported < progress_every:
            return
        states = Counter(x["state"] for x in fetcher.records)
        elapsed = time.monotonic() - started
        progress = {
            "dataset": SCRIPT_VERSION,
            "run_status": "running",
            "visited": visited,
            "max_pages": max_pages,
            "queued_urls": len(q),
            "fetch_state_counts": dict(sorted(states.items())),
            "name_hit_rows": len(page_hits),
            "members_with_any_name_hit": len({x["member_key"] for x in page_hits}),
            "explicit_candidate_rows_so_far": len(explicit),
            "members_with_explicit_candidate_so_far": len({x["member_key"] for x in explicit}),
            "pdf_links_so_far": len(pdf_links),
            "elapsed_seconds": round(elapsed, 1),
        }
        write_json(out / "progress.json", progress)
        print(
            "[progress] "
            f"visited={visited}/{max_pages} queued={len(q)} "
            f"fetched={states.get('fetched', 0)} "
            f"cached={states.get('cached_hash_verified', 0)} "
            f"robots={states.get('robots_disallowed', 0)} "
            f"http_error={states.get('http_error', 0)} "
            f"network_error={states.get('network_error', 0)} "
            f"name_hits={len(page_hits)} explicit={len(explicit)} "
            f"pdf_links={len(pdf_links)} elapsed={elapsed:.1f}s",
            flush=True,
        )
        last_reported = visited

    print(f"[start] initial_queue={len(q)} cache_dir={fetcher.cache}", flush=True)

    while q and len(seen) < max_pages:
        url = canonical_url(q.popleft(), BASE)
        if not url or url in seen or not allowed_url(url):
            continue
        seen.add(url)
        body, ctype, state = fetcher.get(url)
        if not body or "html" not in ctype.lower():
            emit_progress()
            continue
        try:
            text = body.decode("utf-8", errors="replace")
        except Exception:
            emit_progress()
            continue
        parser = PageParser()
        parser.feed(text)
        full_text = norm_text(" ".join(parser.all_text))

        for key, r in targets.items():
            if not name_occurs(full_text, r["name_jp"]):
                continue
            page_hits.append({
                "member_key": key,
                "name_jp": r["name_jp"],
                "name_en": r.get("name_en",""),
                "url": url,
                "page_state": state,
                "page_sha256": sha256_bytes(body),
                "explicit_section_candidate": 0,
                "matched_block_tag": "",
                "matched_block_text": "",
                "section": "",
                "subsection": "",
                "evidence_status": "name_hit_only",
                "roster_acceptance_written": 0,
                "dob_collection_started": 0,
                "bazi_variables_computed": 0,
            })

            member_blocks = [(tag, txt) for tag, txt in parser.blocks if name_occurs(txt, r["name_jp"])]
            for tag, txt in member_blocks:
                secs = explicit_sections(txt)
                for sec, sub in secs:
                    explicit.append({
                        "member_key": key,
                        "name_jp": r["name_jp"],
                        "name_en": r.get("name_en",""),
                        "url": url,
                        "page_sha256": sha256_bytes(body),
                        "block_tag": tag,
                        "block_text": txt[:3000],
                        "explicit_section": sec,
                        "explicit_subsection": sub,
                        "evidence_status": "machine_positive_explicit_same_block_manual_review_required",
                        "automatic_acceptance": 0,
                        "final_roster_row_written": 0,
                        "dob_collection_started": 0,
                        "bazi_variables_computed": 0,
                    })

        for href, label in parser.links:
            cu = canonical_url(href, url)
            if not cu:
                continue
            if PDF_RE.search(cu):
                label_text = norm_text(label)
                matched = [r for r in members if label_text and name_occurs(label_text, r["name_jp"])]
                if matched or re.search(r"会員|會員|第1部|第2部|名簿|追悼|会員選定", label_text):
                    pdf_links.append({
                        "discovered_on_url": url,
                        "pdf_url": cu,
                        "anchor_text": label_text,
                        "matched_member_keys": "|".join(r["member_key"] for r in matched),
                        "pdf_fetched": 0,
                        "pdf_text_extracted": 0,
                        "automatic_acceptance": 0,
                    })
                continue
            if allowed_url(cu) and cu not in seen:
                q.append(cu)

        emit_progress()

    emit_progress(force=True)

    # deduplicate exact evidence rows
    dedup = {}
    for r in explicit:
        k = (r["member_key"], r["url"], r["block_text"], r["explicit_section"], r["explicit_subsection"])
        dedup[k] = r
    explicit = list(dedup.values())

    # Aggregate member states, but do not accept.
    by_member = []
    for r in members:
        key = r["member_key"]
        ex = [x for x in explicit if x["member_key"] == key]
        sections = sorted({x["explicit_section"] for x in ex})
        if len(sections) == 1:
            status = "explicit_same_block_candidate_available"
        elif len(sections) > 1:
            status = "explicit_section_conflict_manual_review"
        else:
            status = "no_explicit_same_block_candidate"
        by_member.append({
            **r,
            "official_html_name_hit_count": sum(x["member_key"] == key for x in page_hits),
            "explicit_same_block_evidence_count": len(ex),
            "explicit_sections_seen": "|".join(sections),
            "official_html_discovery_status": status,
            "automatic_acceptance": 0,
            "final_roster_row_written": 0,
            "dob_collection_started": 0,
            "bazi_variables_computed": 0,
        })

    write_csv(out / "official_html_page_hits_v1.csv", page_hits)
    write_csv(out / "machine_positive_explicit_section_review_v1.csv", explicit)
    write_csv(out / "official_pdf_link_queue_v1.csv", pdf_links)
    write_csv(out / "member_official_html_discovery_summary_v1.csv", by_member)
    write_csv(out / "page_inventory_v1.csv", fetcher.records)

    summary = {
        "dataset": SCRIPT_VERSION,
        "source_snapshot_date": SNAPSHOT_DATE,
        "input_members": len(members),
        "official_pages_visited": len(seen),
        "fetch_state_counts": dict(sorted(Counter(r["state"] for r in fetcher.records).items())),
        "robots_state": fetcher.robots_state,
        "name_hit_rows": len(page_hits),
        "members_with_any_name_hit": len({r["member_key"] for r in page_hits}),
        "explicit_same_block_candidate_rows": len(explicit),
        "members_with_explicit_same_block_candidate": len({r["member_key"] for r in explicit}),
        "member_discovery_status_counts": dict(sorted(Counter(r["official_html_discovery_status"] for r in by_member).items())),
        "pdf_link_review_rows": len(pdf_links),
        "decision_rule": (
            "Only exact target-name occurrences on japan-acad.go.jp are collected. "
            "A machine-positive Section candidate requires the same HTML block to contain the target name and an explicit 第1部/第2部 token. "
            "All such rows remain manual review; no automatic roster acceptance is written."
        ),
        "direct_section_evidence_accepted": 0,
        "final_roster_rows_written": 0,
        "final_roster_frozen": 0,
        "dob_collection_started": 0,
        "bazi_variables_computed": 0,
        "input_sha256": {"remaining40_queue": sha256_file(inp)},
        "next_action": "Manually review explicit same-block candidates, then separately fetch only queued official PDFs likely to contain direct section evidence.",
    }
    write_json(out / "summary.json", summary)
    write_json(out / "progress.json", {
        "dataset": SCRIPT_VERSION,
        "run_status": "complete",
        "visited": len(seen),
        "max_pages": max_pages,
        "queued_urls_remaining": len(q),
        "fetch_state_counts": summary["fetch_state_counts"],
        "name_hit_rows": len(page_hits),
        "members_with_any_name_hit": summary["members_with_any_name_hit"],
        "explicit_candidate_rows": len(explicit),
        "members_with_explicit_candidate": summary["members_with_explicit_same_block_candidate"],
        "pdf_link_review_rows": len(pdf_links),
        "elapsed_seconds": round(time.monotonic() - started, 1),
    })
    print(json.dumps(summary, ensure_ascii=False, indent=2))

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=str(DEFAULT_INPUT))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--max-pages", type=int, default=MAX_PAGES)
    ap.add_argument("--progress-every", type=int, default=DEFAULT_PROGRESS_EVERY)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        self_test()
        return 0
    run(
        Path(args.input),
        Path(args.out),
        refresh=args.refresh,
        max_pages=args.max_pages,
        progress_every=args.progress_every,
    )
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
